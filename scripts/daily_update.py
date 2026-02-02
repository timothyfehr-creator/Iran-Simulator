#!/usr/bin/env python3
"""
Daily crisis intel update coordinator.

Orchestrates the full pipeline:
1. Import evidence bundle
2. Compile intel
2.5. Enrich with live economic data (Bonbast Rial rates)
3. Run simulation
4. Generate reports
5. Compare to previous run (diff)

Usage:
    # Manual daily run with Deep Research bundle
    python scripts/daily_update.py --bundle bundle_daily_2026-01-12.json --cutoff 2026-01-12T12:00:00Z

    # Manual run with ISW scraping only
    python scripts/daily_update.py --use-isw --cutoff 2026-01-12T12:00:00Z

    # Automated daily run (cron-friendly)
    python scripts/daily_update.py --auto
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import shutil

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Import coverage and alerts modules
from src.ingest.coverage import write_coverage_report
from src.ingest.alerts import write_alerts, should_exit_nonzero

# Import ingest config loader for guardrails
from src.ingest.base_fetcher import load_ingest_config

# Import run manifest module
from src.run_manifest import generate_run_manifest, write_run_manifest

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/daily_update.log', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


_REQUIRED_THRESHOLD_KEYS = [
    "rial_critical_threshold",
    "rial_pressured_threshold",
    "inflation_critical_threshold",
    "inflation_pressured_threshold",
]


def validate_econ_priors(priors_path: str) -> tuple:
    """Validate analyst_priors.json contains valid economic config.

    Checks:
    - economic_thresholds exists with all 4 required sub-keys
    - Sub-key values are numeric and castable to int/float
    - Pressured thresholds < critical thresholds (ordering)
    - economic_modifiers exists and is a dict

    Returns:
        (status, errors) where status is "OK" or "FAIL" and errors is a list of strings.
    """
    errors: list = []
    try:
        with open(priors_path, 'r') as f:
            priors = json.load(f)
    except Exception as e:
        return "FAIL", [f"Could not read priors JSON at {priors_path}: {e}"]

    # --- economic_thresholds ---
    thresholds = priors.get("economic_thresholds")
    if not isinstance(thresholds, dict):
        errors.append("Missing or invalid economic_thresholds (must be a dict)")
        return "FAIL", errors

    for k in _REQUIRED_THRESHOLD_KEYS:
        if k not in thresholds:
            errors.append(f"economic_thresholds missing required key: {k}")

    if errors:
        return "FAIL", errors

    # Castability
    try:
        rial_critical = int(thresholds["rial_critical_threshold"])
        rial_pressured = int(thresholds["rial_pressured_threshold"])
        infl_critical = float(thresholds["inflation_critical_threshold"])
        infl_pressured = float(thresholds["inflation_pressured_threshold"])
    except (TypeError, ValueError) as e:
        return "FAIL", [f"economic_thresholds value not numeric: {e}"]

    # Ordering
    if rial_pressured >= rial_critical:
        errors.append(
            f"rial_pressured_threshold ({rial_pressured}) must be < "
            f"rial_critical_threshold ({rial_critical})"
        )
    if infl_pressured >= infl_critical:
        errors.append(
            f"inflation_pressured_threshold ({infl_pressured}) must be < "
            f"inflation_critical_threshold ({infl_critical})"
        )

    # --- economic_modifiers ---
    mods = priors.get("economic_modifiers")
    if not isinstance(mods, dict):
        errors.append("Missing or invalid economic_modifiers (must be a dict)")

    return ("OK" if not errors else "FAIL"), errors


@dataclass
class StageResult:
    """Result of a pipeline stage execution."""
    status: str   # "OK" | "FAIL" | "TIMEOUT" | "CRASH"
    returncode: int


# Default stage timeout in seconds
STAGE_TIMEOUT = 300


def run_stage(cmd: List[str], label: str, timeout: int = STAGE_TIMEOUT) -> StageResult:
    """Run a pipeline subprocess with timeout and soft-fail semantics.

    Return codes:
        0  -> StageResult("OK", 0)
        2  -> StageResult("FAIL", 2)   — soft fail, pipeline continues to gate
        TimeoutExpired -> StageResult("TIMEOUT", -1)
        1 / other -> StageResult("CRASH", rc) — hard fail, caller should abort

    Args:
        cmd: Command list to run via subprocess
        label: Human-readable stage name for logging
        timeout: Timeout in seconds (default: 300)

    Returns:
        StageResult with status and return code
    """
    logger.info(f"Running {label}: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        if result.stdout:
            logger.info(result.stdout.rstrip())
        if result.stderr:
            logger.warning(result.stderr.rstrip())

        if result.returncode == 0:
            logger.info(f"[OK] {label} completed successfully")
            return StageResult("OK", 0)
        elif result.returncode == 2:
            logger.warning(f"[FAIL] {label} soft-failed (exit 2)")
            return StageResult("FAIL", 2)
        else:
            logger.error(f"[CRASH] {label} crashed with exit code {result.returncode}")
            return StageResult("CRASH", result.returncode)

    except subprocess.TimeoutExpired:
        logger.error(f"[TIMEOUT] {label} timed out after {timeout}s")
        return StageResult("TIMEOUT", -1)
    except Exception as e:
        logger.error(f"[CRASH] {label} raised exception: {e}")
        return StageResult("CRASH", -1)


def determine_run_id(date: datetime) -> str:
    """Generate RUN_YYYYMMDD_daily format."""
    return f"RUN_{date.strftime('%Y%m%d')}_daily"


def find_previous_run(current_run_id: str) -> Optional[str]:
    """
    Locate previous day's run for comparison.

    Args:
        current_run_id: Current run ID (e.g., RUN_20260112_daily)

    Returns:
        Previous run ID or None if not found
    """
    runs_dir = Path('runs')
    if not runs_dir.exists():
        return None

    # List all daily runs
    daily_runs = sorted([
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and d.name.endswith('_daily')
    ], reverse=True)

    # Find the run immediately before current
    try:
        current_idx = daily_runs.index(current_run_id)
        if current_idx + 1 < len(daily_runs):
            return daily_runs[current_idx + 1]
    except ValueError:
        # Current run not in list yet (first run)
        if daily_runs:
            return daily_runs[0]

    return None


def build_stage_cmd(stage: str, **kwargs) -> List[str]:
    """Build subprocess command for a pipeline stage.

    Args:
        stage: Stage name (import, compile, simulate, report, diff, enrich_economic)
        **kwargs: Stage-specific arguments

    Returns:
        Command list for subprocess
    """
    if stage == 'import':
        return [
            sys.executable, '-m', 'src.pipeline.import_deep_research_bundle_v3',
            '--bundle', kwargs['bundle'],
            '--out_dir', kwargs['out_dir']
        ]
    elif stage == 'compile':
        return [
            sys.executable, '-m', 'src.pipeline.compile_intel_v2',
            '--claims', os.path.join(kwargs['run_dir'], 'claims_deep_research.jsonl'),
            '--template', 'data/iran_crisis_intel.json',
            '--outdir', kwargs['run_dir']
        ]
    elif stage == 'enrich_economic':
        return [
            sys.executable, 'scripts/enrich_economic_data.py',
            '--intel', kwargs['intel_path'],
            '--no-backup'
        ]
    elif stage == 'simulate':
        return [
            sys.executable, 'src/simulation.py',
            '--intel', os.path.join(kwargs['run_dir'], 'compiled_intel.json'),
            '--priors', 'data/analyst_priors.json',
            '--runs', str(kwargs.get('runs', 10000)),
            '--seed', str(kwargs.get('seed', 42)),
            '--abm',
            '--output', os.path.join(kwargs['run_dir'], 'simulation_results.json')
        ]
    elif stage == 'report':
        return [
            sys.executable, '-m', 'src.report.generate_report',
            '--run_dir', kwargs['run_dir']
        ]
    elif stage == 'diff':
        return [
            sys.executable, '-m', 'src.pipeline.run_comparator',
            kwargs['previous_run'],
            kwargs['current_run'],
            '--output', os.path.join(kwargs['current_run'], 'diff_report.json')
        ]
    else:
        raise ValueError(f"Unknown stage: {stage}")


def check_coverage_warnings(run_dir: str) -> List[str]:
    """
    Parse coverage_report.json for alerts.

    Args:
        run_dir: Run directory path

    Returns:
        List of warning messages
    """
    coverage_path = os.path.join(run_dir, 'coverage_report.json')
    if not os.path.exists(coverage_path):
        return ["Coverage report not found"]

    try:
        with open(coverage_path, 'r') as f:
            coverage = json.load(f)

        warnings = []
        if coverage.get('status') == 'FAIL':
            warnings.extend(coverage.get('failures', []))

        if 'daily_coverage' in coverage:
            daily = coverage['daily_coverage']
            warnings.extend(daily.get('warnings', []))

        return warnings

    except Exception as e:
        return [f"Error reading coverage report: {e}"]


def fetch_isw_data(cutoff: str) -> Optional[str]:
    """
    Fetch ISW updates and create temporary bundle.

    Args:
        cutoff: Data cutoff timestamp

    Returns:
        Path to generated bundle or None
    """
    logger.info("Fetching ISW updates...")

    try:
        # Run ISW fetcher
        result = subprocess.run(
            [sys.executable, '-m', 'src.ingest.fetch_isw_updates', '--seed'],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"ISW fetch failed: {result.stderr}")
            return None

        # Create minimal bundle from ISW data
        import json

        with open('ingest/isw_output/evidence_docs_isw.jsonl', 'r') as f:
            evidence_docs = [json.loads(line) for line in f]

        with open('ingest/isw_output/source_index_isw.json', 'r') as f:
            source_index = json.load(f)

        bundle = {
            "run_manifest": {
                "run_id": determine_run_id(datetime.now(timezone.utc)),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "description": "Auto-generated from ISW scraping"
            },
            "data_cutoff_utc": cutoff,
            "source_index": source_index,
            "evidence_docs": evidence_docs,
            "candidate_claims": []  # No claims extraction, compile will use existing template
        }

        bundle_path = f"bundle_isw_auto_{datetime.now().strftime('%Y%m%d')}.json"
        with open(bundle_path, 'w') as f:
            json.dump(bundle, f, indent=2)

        logger.info(f"✓ Created ISW bundle: {bundle_path}")
        return bundle_path

    except Exception as e:
        logger.error(f"Exception fetching ISW data: {e}")
        return None


def create_bundle_from_ingest(ingest_dir: str, cutoff: str, candidate_claims_path: Optional[str] = None, claims_partial: bool = False) -> str:
    """
    Create Deep Research bundle from ingested evidence and claims.

    Args:
        ingest_dir: Directory containing evidence_docs.jsonl and source_index.json
        cutoff: Data cutoff timestamp
        candidate_claims_path: Optional path to extracted claims JSONL
        claims_partial: Whether the claims file is from a partial/failed extraction

    Returns:
        Path to created bundle
    """
    from datetime import datetime, timezone, timedelta
    import json

    now = datetime.now(timezone.utc)
    cutoff_dt = datetime.fromisoformat(cutoff.replace('Z', '+00:00'))

    bundle_data = {
        "run_manifest": {
            "requirement_id": f"AUTO-{cutoff_dt.strftime('%Y%m%d')}",
            "generated_at_utc": now.isoformat(),
            "data_cutoff_utc": cutoff,
            "date_range_covered": {
                "start": (cutoff_dt - timedelta(days=2)).strftime('%Y-%m-%d'),
                "end": cutoff_dt.strftime('%Y-%m-%d')
            },
            "languages_used": ["en", "fa"],
            "known_collection_limits": [
                "Auto-fetched from RSS/web sources only",
                "Some sources may have been blocked or unavailable"
            ],
            "collection_notes": "Automated ingestion from configured sources (see source_index)",
            "claims_partial": claims_partial
        },
        "evidence_docs": [],
        "candidate_claims": []
    }

    # Load evidence docs
    evidence_path = os.path.join(ingest_dir, 'evidence_docs.jsonl')
    if os.path.exists(evidence_path):
        with open(evidence_path, 'r') as f:
            for line in f:
                bundle_data['evidence_docs'].append(json.loads(line))

    # Load candidate claims if available
    if candidate_claims_path and os.path.exists(candidate_claims_path):
        with open(candidate_claims_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    bundle_data['candidate_claims'].append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning(f"Skipping malformed claims line {line_num} in {candidate_claims_path}")
                    continue

    # Load source index
    source_index_path = os.path.join(ingest_dir, 'source_index.json')
    if os.path.exists(source_index_path):
        with open(source_index_path, 'r') as f:
            bundle_data['source_index'] = json.load(f)

    # Write bundle
    bundle_path = os.path.join(ingest_dir, 'bundle_auto_ingest.json')
    with open(bundle_path, 'w') as f:
        json.dump(bundle_data, f, indent=2)

    return bundle_path


def main():
    parser = argparse.ArgumentParser(description="Daily crisis intel update coordinator")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--bundle', help="Deep Research bundle path")
    mode.add_argument('--use-isw', action='store_true', help="Use ISW scraping only")
    mode.add_argument('--auto', action='store_true', help="Automated mode (default bundle location)")
    mode.add_argument('--auto-ingest', action='store_true', help="Automatically fetch evidence from all sources (no bundle needed)")

    parser.add_argument('--cutoff', help="Data cutoff (ISO 8601). Defaults to now")
    parser.add_argument('--runs', type=int, default=10000, help="Simulation runs (default: 10000)")
    parser.add_argument('--seed', type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument('--no-simulate', action='store_true', help="Skip simulation (compile only)")
    parser.add_argument('--strict-coverage', action='store_true',
                        help="Exit with error if coverage status is FAIL")
    parser.add_argument('--warn-coverage', action='store_true',
                        help="Exit with error if coverage status is WARN or FAIL")

    args = parser.parse_args()

    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

    # Determine cutoff
    if args.cutoff:
        cutoff = args.cutoff
    else:
        # For daily runs, default to end-of-day to capture all same-day docs
        now = datetime.now(timezone.utc)
        cutoff = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
        logger.info(f"No cutoff specified, using end-of-day: {cutoff}")

    # Determine bundle
    if args.bundle:
        bundle_path = args.bundle
    elif args.use_isw:
        bundle_path = fetch_isw_data(cutoff)
        if not bundle_path:
            logger.error("Failed to fetch ISW data")
            sys.exit(1)
    elif args.auto_ingest:
        logger.info("Auto-ingest mode: fetching from all sources...")

        # Step 1: Fetch evidence
        from datetime import timedelta
        from src.ingest.coordinator import IngestionCoordinator

        coordinator = IngestionCoordinator()
        # Use 96h window to catch NGO reports (they publish less frequently)
        since = datetime.now(timezone.utc) - timedelta(hours=96)
        docs, fetch_summary = coordinator.fetch_all(since=since)

        logger.info(f"Fetch summary: {fetch_summary['sources_succeeded']} succeeded, "
                   f"{fetch_summary['sources_failed']} failed, {fetch_summary['sources_skipped']} skipped")

        # Write evidence
        ingest_dir = 'ingest/auto_fetched'
        os.makedirs(ingest_dir, exist_ok=True)
        coordinator.write_evidence_jsonl(docs, os.path.join(ingest_dir, 'evidence_docs.jsonl'))

        source_index = coordinator.generate_source_index()
        with open(os.path.join(ingest_dir, 'source_index.json'), 'w') as f:
            json.dump(source_index, f, indent=2)

        # Evaluate coverage
        ingest_run_id = f"INGEST_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}"
        coverage_report = coordinator.evaluate_coverage(docs, run_id=ingest_run_id)
        write_coverage_report(coverage_report, os.path.join(ingest_dir, 'coverage_report.json'))
        logger.info(f"Coverage: {coverage_report.status} - {coverage_report.status_reason}")

        # Log health summary
        if coverage_report.health_summary:
            logger.info(f"Source health: {coverage_report.health_summary.get('overall_status', 'OK')}")
            if coverage_report.health_summary.get('down_sources'):
                logger.warning(f"DOWN sources: {coverage_report.health_summary['down_sources']}")
            if coverage_report.health_summary.get('degraded_sources'):
                logger.warning(f"DEGRADED sources: {coverage_report.health_summary['degraded_sources']}")

        # Generate alerts
        alert_report = coordinator.generate_alerts(
            coverage_report=coverage_report,
            fetch_errors=fetch_summary.get("errors", {}),
            runs_dir="runs",
            run_id=ingest_run_id
        )
        write_alerts(alert_report, os.path.join(ingest_dir, 'alerts.json'))
        logger.info(f"Alerts: {alert_report.summary}")

        # Coverage gates
        if args.strict_coverage and should_exit_nonzero(alert_report):
            logger.error(f"Pipeline FAILED: coverage status is {alert_report.status}")
            sys.exit(1)
        if args.warn_coverage and alert_report.status in ["WARN", "FAIL"]:
            logger.error(f"Pipeline FAILED: coverage status is {alert_report.status}")
            sys.exit(1)

        # Step 2: Extract claims (if API key available)
        candidate_claims_path = None
        claims_partial = False
        if os.getenv('OPENAI_API_KEY'):
            logger.info("Extracting claims using GPT API...")
            from src.ingest.extract_claims import ClaimExtractor
            claims_output = os.path.join(ingest_dir, 'claims_extracted.jsonl')
            try:
                extractor = ClaimExtractor()
                extractor.extract_from_jsonl(
                    os.path.join(ingest_dir, 'evidence_docs.jsonl'),
                    claims_output
                )
                candidate_claims_path = claims_output
            except Exception as e:
                logger.warning(f"Claim extraction failed: {e}")
                # With incremental writes, partial results may exist
                if os.path.exists(claims_output) and os.path.getsize(claims_output) > 0:
                    candidate_claims_path = claims_output
                    claims_partial = True
                    logger.info(f"Using partial claims file: {claims_output}")
        else:
            logger.warning("No OPENAI_API_KEY found, skipping claim extraction")

        # Step 3: Create bundle
        bundle_path = create_bundle_from_ingest(ingest_dir, cutoff, candidate_claims_path, claims_partial=claims_partial)
        logger.info(f"✓ Auto-generated bundle: {bundle_path}")

    elif args.auto:
        # Look for default bundle location
        today = datetime.now().strftime('%Y-%m-%d')
        default_bundle = f"bundle_daily_{today}.json"
        if os.path.exists(default_bundle):
            bundle_path = default_bundle
        else:
            logger.info(f"Default bundle not found, using ISW scraping")
            bundle_path = fetch_isw_data(cutoff)
            if not bundle_path:
                logger.error("Failed to fetch ISW data")
                sys.exit(1)
    else:
        logger.error("Must specify --bundle, --use-isw, --auto, or --auto-ingest")
        sys.exit(1)

    # Verify bundle exists
    if not os.path.exists(bundle_path):
        logger.error(f"Bundle not found: {bundle_path}")
        sys.exit(1)

    # Determine run_id
    cutoff_date = datetime.fromisoformat(cutoff.replace('Z', '+00:00'))
    run_id = determine_run_id(cutoff_date)
    run_dir = os.path.join('runs', run_id)

    logger.info(f"Starting daily update: {run_id}")
    logger.info(f"  Bundle: {bundle_path}")
    logger.info(f"  Cutoff: {cutoff}")
    logger.info(f"  Output: {run_dir}")

    # Stage 1: Import
    logger.info("\n=== STAGE 1: Import Bundle ===")
    import_result = run_stage(build_stage_cmd('import', bundle=bundle_path, out_dir=run_dir), "Import Bundle")
    if import_result.status == "CRASH":
        logger.error("Import stage crashed — aborting pipeline")
        sys.exit(1)

    # Copy coverage/alerts from ingest to run directory (auto-ingest mode only)
    if args.auto_ingest:
        ingest_dir = 'ingest/auto_fetched'
        for fname in ['coverage_report.json', 'alerts.json']:
            src = os.path.join(ingest_dir, fname)
            dst = os.path.join(run_dir, fname)
            if os.path.exists(src):
                shutil.copy(src, dst)
                logger.info(f"Copied {fname} to run directory")

    # Stage 2: Compile
    logger.info("\n=== STAGE 2: Compile Intel ===")
    compile_result = run_stage(build_stage_cmd('compile', run_dir=run_dir), "Compile Intel")
    if compile_result.status == "CRASH":
        logger.error("Compile stage crashed — aborting pipeline")
        sys.exit(1)

    # Determine QA status from qa_report.json
    qa_status = "OK"
    qa_report_path = os.path.join(run_dir, 'qa_report.json')
    if os.path.exists(qa_report_path):
        try:
            with open(qa_report_path, 'r') as f:
                qa_report = json.load(f)
            if qa_report.get('status') == 'FAIL':
                qa_status = "FAIL"
        except Exception:
            pass
    if compile_result.status in ("FAIL", "TIMEOUT"):
        qa_status = "FAIL"

    # Check coverage warnings
    warnings = check_coverage_warnings(run_dir)
    if warnings:
        logger.warning("Coverage warnings:")
        for w in warnings:
            logger.warning(f"  - {w}")

    # Stage 2.5: Enrich with economic data
    logger.info("\n=== STAGE 2.5: Economic Enrichment ===")
    intel_path = os.path.join(run_dir, 'compiled_intel.json')
    econ_enrichment_result = run_stage(
        build_stage_cmd('enrich_economic', intel_path=intel_path), "Economic Enrichment"
    )
    econ_enrichment_status = "OK" if econ_enrichment_result.status == "OK" else "FAIL"

    # Load coverage report to determine coverage status
    coverage_path = os.path.join(run_dir, 'coverage_report.json')
    coverage_status = "UNKNOWN"
    coverage_report_data = None

    if os.path.exists(coverage_path):
        with open(coverage_path, 'r') as f:
            coverage_report_data = json.load(f)
            coverage_status = coverage_report_data.get('status', 'UNKNOWN')

    # Check config for on_coverage_fail behavior
    ingest_config = load_ingest_config()
    on_coverage_fail = ingest_config.get('on_coverage_fail', 'skip_simulation')

    if coverage_status == 'FAIL' and on_coverage_fail == 'skip_simulation':
        logger.warning(f"Coverage status is FAIL — will feed into unified gate")

    # --- Pre-simulation: validate economic priors ---
    econ_priors_status, econ_priors_errors = validate_econ_priors('data/analyst_priors.json')
    for err in econ_priors_errors:
        logger.warning(f"econ_priors: {err}")

    # --- Claims status ---
    claims_status = "OK"
    claims_count = 0
    claims_path = os.path.join(run_dir, 'claims_deep_research.jsonl')
    if os.path.exists(claims_path):
        with open(claims_path, 'r') as f:
            claims_count = sum(1 for line in f if line.strip())

    if args.auto_ingest and os.getenv('OPENAI_API_KEY') and claims_count == 0:
        claims_status = "FAIL"
        logger.warning("OPENAI_API_KEY set but 0 claims extracted (auto-ingest) — claims_status=FAIL")
    if os.getenv('REQUIRE_CLAIMS') == '1' and claims_count == 0:
        claims_status = "FAIL"
        logger.warning("REQUIRE_CLAIMS=1 but 0 claims — claims_status=FAIL")

    # --- Unified Gate ---
    gate_statuses = {
        "coverage": coverage_status if (coverage_status == "FAIL" and on_coverage_fail == "skip_simulation") else "OK",
        "econ_enrichment": econ_enrichment_status,
        "econ_priors": econ_priors_status,
        "qa": qa_status,
        "claims": claims_status,
    }

    gate_decision = "PASS"
    run_reliable = True
    if any(s == "FAIL" for s in gate_statuses.values()):
        gate_decision = "SKIP_SIMULATION"
        run_reliable = False
        failed_gates = [k for k, v in gate_statuses.items() if v == "FAIL"]
        logger.warning(f"Unified gate: SKIP_SIMULATION — failed gates: {failed_gates}")

    skip_simulation_due_to_gate = (gate_decision == "SKIP_SIMULATION")

    # Stage 3: Simulate (unless skipped or gate blocks)
    if not args.no_simulate and not skip_simulation_due_to_gate:
        logger.info("\n=== STAGE 3: Simulation ===")
        sim_result = run_stage(
            build_stage_cmd('simulate', run_dir=run_dir, runs=args.runs, seed=args.seed),
            "Simulation"
        )
        if sim_result.status in ("CRASH", "TIMEOUT"):
            logger.error(f"Simulation stage {sim_result.status} — aborting pipeline")
            sys.exit(1)

        # Stage 4: Report
        logger.info("\n=== STAGE 4: Generate Reports ===")
        report_result = run_stage(build_stage_cmd('report', run_dir=run_dir), "Generate Reports")
        if report_result.status in ("CRASH", "TIMEOUT"):
            logger.error(f"Report stage {report_result.status} — aborting pipeline")
            sys.exit(1)

    # Determine ingest_since_utc
    from datetime import timedelta
    ingest_since = None

    if args.auto_ingest:
        # For auto-ingest, use actual 96h window that was passed to fetch
        ingest_since = (datetime.now(timezone.utc) - timedelta(hours=96)).isoformat()
    else:
        # For bundle runs, try to derive from bundle run_manifest.date_range_covered.start
        try:
            with open(bundle_path, 'r') as f:
                bundle_data = json.load(f)
            date_range = bundle_data.get('run_manifest', {}).get('date_range_covered', {})
            if date_range.get('start'):
                ingest_since = date_range['start'] + 'T00:00:00Z'
        except Exception:
            pass

        # Fallback to cutoff - 96h
        if not ingest_since:
            ingest_since = (cutoff_date - timedelta(hours=96)).isoformat()

    # Generate run manifest with hashes
    logger.info("\n=== Generating Run Manifest ===")
    try:
        manifest = generate_run_manifest(
            run_dir=run_dir,
            data_cutoff_utc=cutoff,
            ingest_since_utc=ingest_since,
            seed=args.seed,
            coverage_status=coverage_status,
            coverage_report=coverage_report_data,
            run_id=run_id,
            as_of_utc=datetime.now(timezone.utc).isoformat(),
            n_sims=args.runs if (not args.no_simulate and not skip_simulation_due_to_gate) else None,
            qa_status=qa_status,
            econ_enrichment_status=econ_enrichment_status,
            econ_priors_status=econ_priors_status,
            claims_status=claims_status,
            claims_count=claims_count,
            gate_decision=gate_decision,
        )
        manifest_path = write_run_manifest(manifest, run_dir)
        logger.info(f"✓ Wrote run manifest: {manifest_path}")
        logger.info(f"  Git commit: {manifest.git_commit[:8]}...")
        logger.info(f"  Run reliable: {manifest.run_reliable}")
        if manifest.unreliable_reason:
            logger.warning(f"  Unreliable reason: {manifest.unreliable_reason}")
    except Exception as e:
        logger.warning(f"Failed to generate run manifest: {e}")

    # Stage 4.5: Generate scorecard + public artifacts
    if not args.no_simulate and not skip_simulation_due_to_gate:
        logger.info("\n=== STAGE 4.5: Scorecard + Public Artifacts ===")
        try:
            from src.forecasting.reporter import generate_report
            report_outputs = generate_report(
                ledger_dir=Path("forecasting/ledger"),
                reports_dir=Path("forecasting/reports"),
                output_format="both",
            )
            logger.info(f"Scorecard generated: {report_outputs}")
        except Exception as e:
            logger.warning(f"Scorecard generation failed (non-fatal): {e}")

        try:
            artifact_cmd = [
                sys.executable, "scripts/generate_public_artifacts.py",
                "--run-dir", run_dir,
                "--live-wire", "data/live_wire/latest.json",
                "--scorecard", "forecasting/reports/scorecard.json",
                "--output-dir", "latest/",
            ]
            artifact_result = run_stage(artifact_cmd, "Public Artifacts", timeout=120)
            if artifact_result.status != "OK":
                logger.warning(f"Public artifact generation failed (non-fatal)")
        except Exception as e:
            logger.warning(f"Public artifact generation failed (non-fatal): {e}")

    # Stage 5: Diff (if previous run exists and simulation ran)
    if not args.no_simulate and not skip_simulation_due_to_gate:
        logger.info("\n=== STAGE 5: Generate Diff ===")
        previous_run = find_previous_run(run_id)
        if previous_run:
            previous_run_dir = os.path.join('runs', previous_run)
            logger.info(f"Comparing to previous run: {previous_run}")
            diff_result = run_stage(
            build_stage_cmd('diff', previous_run=previous_run_dir, current_run=run_dir), "Diff"
        )
        if diff_result.status == "OK":
                # Generate markdown summary
                try:
                    subprocess.run([
                        sys.executable, '-m', 'src.report.generate_diff_report',
                        os.path.join(run_dir, 'diff_report.json'),
                        '--output', os.path.join(run_dir, 'daily_summary.md')
                    ], check=True)
                    logger.info("✓ Diff report generated")
                except subprocess.CalledProcessError:
                    logger.warning("Diff markdown generation failed (non-fatal)")
        else:
            logger.info("No previous run found, skipping diff")
    elif args.no_simulate:
        logger.info("\n=== Simulation skipped (--no-simulate) ===")
    elif skip_simulation_due_to_gate:
        logger.info(f"\n=== Simulation skipped (gate: {gate_decision}) ===")

    logger.info(f"\n✓ Daily update complete: {run_id}")
    logger.info(f"  Output directory: {run_dir}")

    # Final summary
    if os.path.exists(os.path.join(run_dir, 'daily_summary.md')):
        logger.info("\n--- Daily Summary ---")
        with open(os.path.join(run_dir, 'daily_summary.md'), 'r') as f:
            print(f.read())

    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        logger.exception("Pipeline failed with unhandled exception")
        sys.exit(1)

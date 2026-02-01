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


def run_pipeline_stage(stage: str, **kwargs) -> bool:
    """
    Invoke pipeline stage via subprocess.

    Args:
        stage: Stage name (import, compile, simulate, report, diff)
        **kwargs: Stage-specific arguments

    Returns:
        True if successful, False otherwise
    """
    try:
        if stage == 'import':
            cmd = [
                sys.executable, '-m', 'src.pipeline.import_deep_research_bundle_v3',
                '--bundle', kwargs['bundle'],
                '--out_dir', kwargs['out_dir']
            ]

        elif stage == 'compile':
            # Use compile_intel_v2 for deterministic merge with documented tiebreak order
            cmd = [
                sys.executable, '-m', 'src.pipeline.compile_intel_v2',
                '--claims', os.path.join(kwargs['run_dir'], 'claims_deep_research.jsonl'),
                '--template', 'data/iran_crisis_intel.json',
                '--outdir', kwargs['run_dir']
            ]

        elif stage == 'enrich_economic':
            cmd = [
                sys.executable, 'scripts/enrich_economic_data.py',
                '--intel', kwargs['intel_path'],
                '--no-backup'  # Don't create backup in automated pipeline runs
            ]

        elif stage == 'simulate':
            cmd = [
                sys.executable, 'src/simulation.py',
                '--intel', os.path.join(kwargs['run_dir'], 'compiled_intel.json'),
                '--priors', 'data/analyst_priors.json',
                '--runs', str(kwargs.get('runs', 10000)),
                '--seed', str(kwargs.get('seed', 42)),
                '--abm',  # Use multi-agent ABM (Project Swarm) for protest dynamics
                '--output', os.path.join(kwargs['run_dir'], 'simulation_results.json')
            ]

        elif stage == 'report':
            cmd = [
                sys.executable, '-m', 'src.report.generate_report',
                '--run_dir', kwargs['run_dir']
            ]

        elif stage == 'diff':
            cmd = [
                sys.executable, '-m', 'src.pipeline.run_comparator',
                kwargs['previous_run'],
                kwargs['current_run'],
                '--output', os.path.join(kwargs['current_run'], 'diff_report.json')
            ]

        else:
            logger.error(f"Unknown stage: {stage}")
            return False

        logger.info(f"Running {stage}: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info(f"✓ {stage} completed successfully")
            if result.stdout:
                logger.info(result.stdout)
            return True
        else:
            logger.error(f"✗ {stage} failed with exit code {result.returncode}")
            if result.stderr:
                logger.error(result.stderr)
            if result.stdout:
                logger.error(result.stdout)
            return False

    except Exception as e:
        logger.error(f"Exception in {stage}: {e}")
        return False


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


def create_bundle_from_ingest(ingest_dir: str, cutoff: str, candidate_claims_path: Optional[str] = None) -> str:
    """
    Create Deep Research bundle from ingested evidence and claims.

    Args:
        ingest_dir: Directory containing evidence_docs.jsonl and source_index.json
        cutoff: Data cutoff timestamp
        candidate_claims_path: Optional path to extracted claims JSONL

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
            "collection_notes": "Automated ingestion from configured sources (see source_index)"
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
            for line in f:
                bundle_data['candidate_claims'].append(json.loads(line))

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
        if os.getenv('OPENAI_API_KEY'):
            logger.info("Extracting claims using GPT API...")
            from src.ingest.extract_claims import ClaimExtractor
            try:
                extractor = ClaimExtractor()
                extractor.extract_from_jsonl(
                    os.path.join(ingest_dir, 'evidence_docs.jsonl'),
                    os.path.join(ingest_dir, 'claims_extracted.jsonl')
                )
                candidate_claims_path = os.path.join(ingest_dir, 'claims_extracted.jsonl')
            except Exception as e:
                logger.warning(f"Claim extraction failed: {e}")
        else:
            logger.warning("No OPENAI_API_KEY found, skipping claim extraction")

        # Step 3: Create bundle
        bundle_path = create_bundle_from_ingest(ingest_dir, cutoff, candidate_claims_path)
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
    if not run_pipeline_stage('import', bundle=bundle_path, out_dir=run_dir):
        logger.error("Import stage failed")
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
    if not run_pipeline_stage('compile', run_dir=run_dir):
        logger.error("Compile stage failed")
        sys.exit(1)

    # Check coverage warnings
    warnings = check_coverage_warnings(run_dir)
    if warnings:
        logger.warning("Coverage warnings:")
        for w in warnings:
            logger.warning(f"  - {w}")

    # Stage 2.5: Enrich with economic data
    logger.info("\n=== STAGE 2.5: Economic Enrichment ===")
    intel_path = os.path.join(run_dir, 'compiled_intel.json')
    if not run_pipeline_stage('enrich_economic', intel_path=intel_path):
        logger.warning("Economic enrichment failed (non-fatal, continuing with defaults)")

    # Load coverage report to determine if we should skip simulation
    coverage_path = os.path.join(run_dir, 'coverage_report.json')
    coverage_status = "UNKNOWN"
    coverage_report_data = None
    skip_simulation_due_to_coverage = False

    if os.path.exists(coverage_path):
        with open(coverage_path, 'r') as f:
            coverage_report_data = json.load(f)
            coverage_status = coverage_report_data.get('status', 'UNKNOWN')

    # Check config for on_coverage_fail behavior
    ingest_config = load_ingest_config()
    on_coverage_fail = ingest_config.get('on_coverage_fail', 'skip_simulation')

    if coverage_status == 'FAIL' and on_coverage_fail == 'skip_simulation':
        logger.warning(f"Coverage status is FAIL - skipping simulation per config (on_coverage_fail={on_coverage_fail})")
        skip_simulation_due_to_coverage = True

    # Stage 3: Simulate (unless skipped or coverage FAIL)
    if not args.no_simulate and not skip_simulation_due_to_coverage:
        logger.info("\n=== STAGE 3: Simulation ===")
        if not run_pipeline_stage('simulate', run_dir=run_dir, runs=args.runs, seed=args.seed):
            logger.error("Simulation stage failed")
            sys.exit(1)

        # Stage 4: Report
        logger.info("\n=== STAGE 4: Generate Reports ===")
        if not run_pipeline_stage('report', run_dir=run_dir):
            logger.error("Report stage failed")
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
            n_sims=args.runs if (not args.no_simulate and not skip_simulation_due_to_coverage) else None
        )
        manifest_path = write_run_manifest(manifest, run_dir)
        logger.info(f"✓ Wrote run manifest: {manifest_path}")
        logger.info(f"  Git commit: {manifest.git_commit[:8]}...")
        logger.info(f"  Run reliable: {manifest.run_reliable}")
        if manifest.unreliable_reason:
            logger.warning(f"  Unreliable reason: {manifest.unreliable_reason}")
    except Exception as e:
        logger.warning(f"Failed to generate run manifest: {e}")

    # Stage 5: Diff (if previous run exists and simulation ran)
    if not args.no_simulate and not skip_simulation_due_to_coverage:
        logger.info("\n=== STAGE 5: Generate Diff ===")
        previous_run = find_previous_run(run_id)
        if previous_run:
            previous_run_dir = os.path.join('runs', previous_run)
            logger.info(f"Comparing to previous run: {previous_run}")
            if run_pipeline_stage('diff', previous_run=previous_run_dir, current_run=run_dir):
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
    elif skip_simulation_due_to_coverage:
        logger.info("\n=== Simulation skipped (coverage FAIL) ===")

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

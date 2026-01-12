#!/usr/bin/env python3
"""
Daily crisis intel update coordinator.

Orchestrates the full pipeline:
1. Import evidence bundle
2. Compile intel
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
                'python3', '-m', 'src.pipeline.import_deep_research_bundle_v3',
                '--bundle', kwargs['bundle'],
                '--out_dir', kwargs['out_dir']
            ]

        elif stage == 'compile':
            cmd = [
                'python3', '-m', 'src.pipeline.compile_intel',
                '--claims', os.path.join(kwargs['run_dir'], 'claims_deep_research.jsonl'),
                '--template', 'data/iran_crisis_intel.json',
                '--outdir', kwargs['run_dir']
            ]

        elif stage == 'simulate':
            cmd = [
                'python3', 'src/simulation.py',
                '--intel', os.path.join(kwargs['run_dir'], 'compiled_intel.json'),
                '--priors', 'data/analyst_priors.json',
                '--runs', str(kwargs.get('runs', 10000)),
                '--seed', str(kwargs.get('seed', 42)),
                '--output', os.path.join(kwargs['run_dir'], 'simulation_results.json')
            ]

        elif stage == 'report':
            cmd = [
                'python3', '-m', 'src.report.generate_report',
                '--run_dir', kwargs['run_dir']
            ]

        elif stage == 'diff':
            cmd = [
                'python3', '-m', 'src.pipeline.run_comparator',
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
            ['python3', '-m', 'src.ingest.fetch_isw_updates', '--seed'],
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
    from datetime import datetime, timezone
    import json

    bundle_data = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "auto_ingest",
            "data_cutoff_utc": cutoff,
            "description": "Auto-fetched evidence from multiple sources"
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
        since = datetime.now(timezone.utc) - timedelta(hours=24)  # Last 24h
        docs = coordinator.fetch_all(since=since)

        # Write evidence
        ingest_dir = 'ingest/auto_fetched'
        os.makedirs(ingest_dir, exist_ok=True)
        coordinator.write_evidence_jsonl(docs, os.path.join(ingest_dir, 'evidence_docs.jsonl'))

        source_index = coordinator.generate_source_index()
        with open(os.path.join(ingest_dir, 'source_index.json'), 'w') as f:
            json.dump(source_index, f, indent=2)

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

    # Stage 3: Simulate (unless skipped)
    if not args.no_simulate:
        logger.info("\n=== STAGE 3: Simulation ===")
        if not run_pipeline_stage('simulate', run_dir=run_dir, runs=args.runs, seed=args.seed):
            logger.error("Simulation stage failed")
            sys.exit(1)

        # Stage 4: Report
        logger.info("\n=== STAGE 4: Generate Reports ===")
        if not run_pipeline_stage('report', run_dir=run_dir):
            logger.error("Report stage failed")
            sys.exit(1)

        # Stage 5: Diff (if previous run exists)
        logger.info("\n=== STAGE 5: Generate Diff ===")
        previous_run = find_previous_run(run_id)
        if previous_run:
            previous_run_dir = os.path.join('runs', previous_run)
            logger.info(f"Comparing to previous run: {previous_run}")
            if run_pipeline_stage('diff', previous_run=previous_run_dir, current_run=run_dir):
                # Generate markdown summary
                try:
                    subprocess.run([
                        'python3', '-m', 'src.report.generate_diff_report',
                        os.path.join(run_dir, 'diff_report.json'),
                        '--output', os.path.join(run_dir, 'daily_summary.md')
                    ], check=True)
                    logger.info("✓ Diff report generated")
                except subprocess.CalledProcessError:
                    logger.warning("Diff markdown generation failed (non-fatal)")
        else:
            logger.info("No previous run found, skipping diff")
    else:
        logger.info("\n=== Simulation skipped (--no-simulate) ===")

    logger.info(f"\n✓ Daily update complete: {run_id}")
    logger.info(f"  Output directory: {run_dir}")

    # Final summary
    if os.path.exists(os.path.join(run_dir, 'daily_summary.md')):
        logger.info("\n--- Daily Summary ---")
        with open(os.path.join(run_dir, 'daily_summary.md'), 'r') as f:
            print(f.read())

    sys.exit(0)


if __name__ == '__main__':
    main()

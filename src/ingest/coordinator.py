"""
Ingestion coordinator with health tracking and coverage monitoring.

Orchestrates all evidence fetchers with:
- Automatic retries with backoff
- Source health tracking
- Window-based coverage evaluation
- Alerts for missing/degraded sources
- Document caching to avoid reprocessing
- Per-bucket caps to control costs
"""

import hashlib
import json
import importlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
import yaml

from .coverage import (
    evaluate_coverage,
    check_bucket_completeness,
    load_source_config_from_yaml,
    CoverageReport,
    write_coverage_report,
    BUCKET_WINDOWS
)
from .health import (
    HealthTracker,
    load_health_tracker,
    save_health_tracker,
    SourceHealth
)
from .alerts import (
    generate_alerts,
    write_alerts,
    load_prior_coverage,
    should_exit_nonzero,
    AlertReport
)
from .base_fetcher import load_ingest_config


class DocCache:
    """
    Document cache to avoid reprocessing identical documents.

    Cache key is hash of: url + published_at + title
    """

    def __init__(self, cache_path: str = "runs/_meta/doc_cache.json"):
        self.cache_path = cache_path
        self.cache: Set[str] = set()
        self._load()

    def _load(self):
        """Load cache from disk."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r') as f:
                    data = json.load(f)
                    self.cache = set(data.get("hashes", []))
            except (json.JSONDecodeError, KeyError):
                self.cache = set()

    def save(self):
        """Save cache to disk."""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, 'w') as f:
            json.dump({
                "hashes": list(self.cache),
                "count": len(self.cache),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }, f, indent=2)

    @staticmethod
    def compute_doc_hash(doc: Dict[str, Any]) -> str:
        """Compute hash for a document based on url + published_at + title."""
        key = f"{doc.get('url', '')}|{doc.get('published_at_utc', '')}|{doc.get('title', '')}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def is_cached(self, doc: Dict[str, Any]) -> bool:
        """Check if document is in cache."""
        return self.compute_doc_hash(doc) in self.cache

    def add(self, doc: Dict[str, Any]):
        """Add document to cache."""
        self.cache.add(self.compute_doc_hash(doc))

    def add_all(self, docs: List[Dict[str, Any]]):
        """Add multiple documents to cache."""
        for doc in docs:
            self.add(doc)


def apply_per_bucket_caps(
    docs: List[Dict[str, Any]],
    source_config: Dict[str, Dict],
    max_per_bucket: int = 200
) -> List[Dict[str, Any]]:
    """
    Apply per-bucket caps, keeping most recent docs by published_at.

    Args:
        docs: List of evidence documents
        source_config: Source configuration mapping
        max_per_bucket: Maximum docs per bucket

    Returns:
        Filtered list respecting caps
    """
    # Group docs by bucket
    bucket_docs: Dict[str, List[Dict[str, Any]]] = {}

    for doc in docs:
        source_id = doc.get("source_id", "").lower()
        if source_id.startswith("src_"):
            source_id = source_id[4:]

        bucket = source_config.get(source_id, {}).get("bucket", "unknown")
        if bucket not in bucket_docs:
            bucket_docs[bucket] = []
        bucket_docs[bucket].append(doc)

    # Sort each bucket by published_at (newest first) and cap
    capped_docs = []
    for bucket, bdocs in bucket_docs.items():
        # Sort by published_at descending
        sorted_docs = sorted(
            bdocs,
            key=lambda d: d.get("published_at_utc", ""),
            reverse=True
        )
        # Keep only max_per_bucket
        capped_docs.extend(sorted_docs[:max_per_bucket])

    return capped_docs


class IngestionCoordinator:
    """Coordinates evidence fetching with health and coverage monitoring."""

    def __init__(self, config_path: str = "config/sources.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.sources = self.config['sources']
        self.config_path = config_path

        # Load health tracker
        self.health_tracker = load_health_tracker()

        # Previous health for comparison
        self._previous_health: Optional[HealthTracker] = None

        # Load ingest guardrail config
        self.ingest_config = load_ingest_config()

        # Initialize doc cache if enabled
        cache_config = self.ingest_config.get('cache', {})
        if cache_config.get('enabled', True):
            cache_path = cache_config.get('path', 'runs/_meta/doc_cache.json')
            self.doc_cache = DocCache(cache_path)
        else:
            self.doc_cache = None

        # Per-bucket caps
        self.max_docs_per_bucket = self.ingest_config.get('max_docs_per_bucket', 200)

    def fetch_all(
        self,
        since: Optional[datetime] = None,
        skip_down_sources: bool = True
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetch from all enabled sources with health tracking.

        Args:
            since: Only fetch docs published after this time
            skip_down_sources: If True, skip sources marked as DOWN

        Returns:
            Tuple of (docs, fetch_summary)
            fetch_summary contains success/failure counts and errors
        """
        # Save previous health state for comparison
        self._previous_health = HealthTracker.from_dict(self.health_tracker.to_dict())

        all_docs = []
        fetch_summary = {
            "sources_attempted": 0,
            "sources_succeeded": 0,
            "sources_failed": 0,
            "sources_skipped": 0,
            "errors": {}
        }

        for source in self.sources:
            source_id = source['id']

            # Skip disabled sources
            if not source.get('enabled', True):
                print(f"Skipping disabled source: {source_id}")
                fetch_summary["sources_skipped"] += 1
                continue

            # Skip manual sources
            if source.get('type') == 'manual':
                print(f"Skipping manual source: {source_id}")
                fetch_summary["sources_skipped"] += 1
                continue

            # Get/create health record
            health = self.health_tracker.get_or_create(
                source_id,
                name=source.get('name', ''),
                bucket=source.get('bucket', '')
            )

            # Skip DOWN sources if configured
            if skip_down_sources and health.status == "DOWN":
                print(f"Skipping DOWN source: {source_id}")
                fetch_summary["sources_skipped"] += 1
                continue

            print(f"Fetching from {source['name']}...")
            fetch_summary["sources_attempted"] += 1

            try:
                # Dynamic import of fetcher module
                fetcher_module = source.get('fetcher', 'src.ingest.fetch_rss')
                module = importlib.import_module(fetcher_module)

                # Instantiate fetcher class (new pattern)
                if fetcher_module == 'src.ingest.fetch_rss':
                    from .fetch_rss import RSSFetcher
                    fetcher = RSSFetcher(source)
                elif fetcher_module == 'src.ingest.fetch_web':
                    from .fetch_web import WebFetcher
                    fetcher = WebFetcher(source)
                else:
                    # Fallback to legacy fetch function
                    fetch_func = getattr(module, 'fetch')
                    docs = fetch_func(source, since=since)
                    health.record_success(len(docs))
                    print(f"  ✓ Fetched {len(docs)} docs from {source_id}")
                    all_docs.extend(docs)
                    fetch_summary["sources_succeeded"] += 1
                    continue

                # Use new pattern with retry logic
                docs, error = fetcher.fetch(since=since)

                if error:
                    health.record_failure(error)
                    fetch_summary["sources_failed"] += 1
                    fetch_summary["errors"][source_id] = error
                    print(f"  ✗ Failed: {error}")
                else:
                    health.record_success(len(docs))
                    print(f"  ✓ Fetched {len(docs)} docs from {source_id}")
                    all_docs.extend(docs)
                    fetch_summary["sources_succeeded"] += 1

            except Exception as e:
                error_msg = str(e)
                health.record_failure(error_msg)
                fetch_summary["sources_failed"] += 1
                fetch_summary["errors"][source_id] = error_msg
                print(f"  ✗ Error: {e}")
                import traceback
                traceback.print_exc()

        # Save updated health
        save_health_tracker(self.health_tracker)

        # Deduplicate by URL
        seen_urls = set()
        deduped_docs = []
        for doc in all_docs:
            url = doc.get('url', '')
            if url not in seen_urls:
                seen_urls.add(url)
                deduped_docs.append(doc)

        fetch_summary["duplicates_removed"] = len(all_docs) - len(deduped_docs)

        # Filter out cached docs (already processed in previous runs)
        if self.doc_cache:
            pre_cache_count = len(deduped_docs)
            deduped_docs = [doc for doc in deduped_docs if not self.doc_cache.is_cached(doc)]
            fetch_summary["cached_docs_skipped"] = pre_cache_count - len(deduped_docs)
            if fetch_summary["cached_docs_skipped"] > 0:
                print(f"  Skipped {fetch_summary['cached_docs_skipped']} cached docs")
        else:
            fetch_summary["cached_docs_skipped"] = 0

        # Apply per-bucket caps
        source_config = load_source_config_from_yaml(self.config_path)
        pre_cap_count = len(deduped_docs)
        deduped_docs = apply_per_bucket_caps(
            deduped_docs,
            source_config,
            self.max_docs_per_bucket
        )
        fetch_summary["docs_capped"] = pre_cap_count - len(deduped_docs)
        if fetch_summary["docs_capped"] > 0:
            print(f"  Capped {fetch_summary['docs_capped']} docs (max {self.max_docs_per_bucket}/bucket)")

        # Update cache with new docs
        if self.doc_cache:
            self.doc_cache.add_all(deduped_docs)
            self.doc_cache.save()

        fetch_summary["total_docs"] = len(deduped_docs)

        print(f"\n✓ Total: {len(deduped_docs)} unique docs from {fetch_summary['sources_succeeded']} sources")

        return deduped_docs, fetch_summary

    def evaluate_coverage(
        self,
        docs: List[Dict[str, Any]],
        reference_time: Optional[datetime] = None,
        run_id: str = ""
    ) -> CoverageReport:
        """
        Evaluate window-based coverage for all buckets.

        Args:
            docs: Evidence documents to evaluate
            reference_time: Reference time for window calculation
            run_id: Run identifier

        Returns:
            CoverageReport with coverage status
        """
        source_config = load_source_config_from_yaml(self.config_path)
        report = evaluate_coverage(docs, source_config, reference_time, run_id)

        # Add health summary
        report.health_summary = self.health_tracker.get_summary()

        return report

    def check_bucket_config(self) -> Dict[str, Any]:
        """Check that all buckets have at least one configured source."""
        source_config = load_source_config_from_yaml(self.config_path)
        return check_bucket_completeness(source_config)

    def get_newly_problematic_sources(self) -> Dict[str, List[str]]:
        """Get sources that became DEGRADED or DOWN since last fetch."""
        if self._previous_health is None:
            return {"newly_degraded": [], "newly_down": []}
        return self.health_tracker.get_newly_degraded_or_down(self._previous_health)

    def generate_alerts(
        self,
        coverage_report: CoverageReport,
        fetch_errors: Dict[str, str],
        runs_dir: str = "runs",
        run_id: str = ""
    ) -> AlertReport:
        """
        Generate alerts from coverage and health status.

        Args:
            coverage_report: Current coverage report
            fetch_errors: Dict of source_id -> error message
            runs_dir: Directory containing run folders (for prior comparison)
            run_id: Current run identifier

        Returns:
            AlertReport with all alerts
        """
        newly_problematic = self.get_newly_problematic_sources()
        prior_coverage = load_prior_coverage(runs_dir, run_id)

        return generate_alerts(
            coverage_report=coverage_report,
            newly_problematic=newly_problematic,
            fetch_errors=fetch_errors,
            prior_coverage=prior_coverage,
            run_id=run_id
        )

    def write_evidence_jsonl(self, docs: List[Dict[str, Any]], output_path: str):
        """Write evidence docs to JSONL."""
        with open(output_path, 'w') as f:
            for doc in docs:
                f.write(json.dumps(doc) + '\n')
        print(f"Wrote evidence_docs.jsonl: {output_path}")

    def generate_source_index(self) -> List[Dict[str, Any]]:
        """Generate source_index.json from config."""
        index = []
        for source in self.sources:
            if source.get('type') != 'manual':
                index.append({
                    "source_id": f"SRC_{source['id'].upper()}",
                    "organization": source['name'],
                    "default_access_grade": source['access_grade'],
                    "default_bias_grade": source['bias_grade'],
                    "language": source.get('language', 'en'),
                    "bucket": source.get('bucket', 'unknown'),
                    "notes": f"{source.get('bucket', '')} - {source.get('type', '')}"
                })
        return index


def main():
    """CLI entry point for testing."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Fetch evidence from all sources")
    parser.add_argument('--since-hours', type=int, default=24,
                        help="Fetch docs from last N hours (default: 24)")
    parser.add_argument('--output', default='ingest/auto_fetched',
                        help="Output directory")
    parser.add_argument('--check-config', action='store_true',
                        help="Check bucket configuration only")
    parser.add_argument('--run-id', default='CLI_TEST',
                        help="Run identifier for tracking")
    args = parser.parse_args()

    coordinator = IngestionCoordinator()

    # Check config mode
    if args.check_config:
        result = coordinator.check_bucket_config()
        print("\nBucket Configuration Check:")
        print(f"  Complete: {result['complete']}")
        print(f"  Missing: {result['missing']}")
        for bucket, sources in result['sources_by_bucket'].items():
            print(f"  {bucket}: {sources if sources else 'NO SOURCES'}")
        return

    # Calculate since timestamp
    since = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)

    # Fetch all
    docs, summary = coordinator.fetch_all(since=since)

    # Write outputs
    os.makedirs(args.output, exist_ok=True)

    coordinator.write_evidence_jsonl(docs, os.path.join(args.output, 'evidence_docs.jsonl'))

    source_index = coordinator.generate_source_index()
    with open(os.path.join(args.output, 'source_index.json'), 'w') as f:
        json.dump(source_index, f, indent=2)

    # Evaluate coverage
    report = coordinator.evaluate_coverage(docs, run_id=args.run_id)
    write_coverage_report(report, os.path.join(args.output, 'coverage_report.json'))

    # Generate and write alerts
    alert_report = coordinator.generate_alerts(
        coverage_report=report,
        fetch_errors=summary.get("errors", {}),
        run_id=args.run_id
    )
    write_alerts(alert_report, os.path.join(args.output, 'alerts.json'))

    print(f"\n✓ Evidence fetching complete: {args.output}")
    print(f"  Coverage status: {report.status}")
    print(f"  Alert status: {alert_report.status}")
    if report.buckets_missing:
        print(f"  Missing buckets: {report.buckets_missing}")
    if alert_report.summary.get("critical", 0) > 0:
        print(f"  Critical alerts: {alert_report.summary['critical']}")
    if alert_report.summary.get("warning", 0) > 0:
        print(f"  Warning alerts: {alert_report.summary['warning']}")

    # Exit nonzero on FAIL (for cron alerting)
    if should_exit_nonzero(alert_report):
        print("\n✗ Pipeline FAILED - exiting with error code")
        sys.exit(1)


if __name__ == '__main__':
    main()

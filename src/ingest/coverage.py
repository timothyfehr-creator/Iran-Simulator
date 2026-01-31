"""
Window-based coverage gates for ingestion quality control.

Defines rolling windows per bucket and computes coverage status.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
import json


# Rolling window requirements per bucket (hours)
BUCKET_WINDOWS = {
    "osint_thinktank": 36,      # ISW/CTP: >=1 doc in last 36h
    "ngo_rights": 72,           # HRANA/IHR/Amnesty: >=1 doc in last 72h
    "regime_outlets": 72,       # IRNA/Tasnim/Mehr/Fars/PressTV: >=1 doc in last 72h
    "persian_services": 72,     # IranIntl/RadioFarda/BBCPersian: >=1 doc in last 72h
    "internet_monitoring": 72,  # NetBlocks/OONI: >=1 doc in last 72h (changed from 168)
    "econ_fx": 72,              # Rial/inflation proxies: >=1 doc in last 72h
}

# Critical buckets - missing >=2 triggers FAIL
CRITICAL_BUCKETS = {
    "osint_thinktank",
    "ngo_rights",
    "regime_outlets",
    "persian_services",
}

# Bucket display names
BUCKET_NAMES = {
    "osint_thinktank": "OSINT Think Tanks (ISW/CTP)",
    "ngo_rights": "NGO/Rights Monitors",
    "regime_outlets": "Regime Outlets",
    "persian_services": "Persian Services",
    "internet_monitoring": "Internet Monitoring",
    "econ_fx": "Economic/FX Data",
}


@dataclass
class BucketCoverage:
    """Coverage status for a single bucket."""
    bucket: str
    window_hours: int
    docs_in_window: int
    oldest_doc_age_hours: Optional[float] = None
    newest_doc_age_hours: Optional[float] = None
    sources_contributing: List[str] = field(default_factory=list)
    covered: bool = False


@dataclass
class CoverageReport:
    """Full coverage report for a run."""
    run_id: str
    evaluated_at_utc: str
    reference_time_utc: str
    buckets_present: List[str] = field(default_factory=list)
    buckets_missing: List[str] = field(default_factory=list)
    counts_by_bucket: Dict[str, int] = field(default_factory=dict)
    bucket_details: Dict[str, Dict] = field(default_factory=dict)
    total_docs: int = 0
    status: str = "PASS"  # PASS, WARN, FAIL
    status_reason: str = ""
    health_summary: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return asdict(self)


def get_doc_timestamp(doc: Dict[str, Any]) -> Optional[datetime]:
    """
    Extract document timestamp, preferring published_at_utc, falling back to retrieved_at_utc.

    Returns:
        datetime or None if no valid timestamp
    """
    # Try published_at_utc first
    pub = doc.get("published_at_utc")
    if pub:
        try:
            if isinstance(pub, str):
                return datetime.fromisoformat(pub.replace("Z", "+00:00"))
            return pub
        except (ValueError, TypeError):
            pass

    # Fall back to retrieved_at_utc
    ret = doc.get("retrieved_at_utc")
    if ret:
        try:
            if isinstance(ret, str):
                return datetime.fromisoformat(ret.replace("Z", "+00:00"))
            return ret
        except (ValueError, TypeError):
            pass

    return None


def compute_doc_age_hours(doc: Dict[str, Any], reference_time: datetime) -> Optional[float]:
    """Compute document age in hours from reference time."""
    ts = get_doc_timestamp(doc)
    if ts is None:
        return None
    delta = reference_time - ts
    return delta.total_seconds() / 3600


def get_doc_bucket(doc: Dict[str, Any], source_config: Dict[str, Dict]) -> Optional[str]:
    """
    Determine which bucket a document belongs to.

    Args:
        doc: Evidence document
        source_config: Mapping of source_id -> source config with bucket field

    Returns:
        Bucket name or None if unknown
    """
    source_id = doc.get("source_id", "")

    # Strip SRC_ prefix if present
    if source_id.startswith("SRC_"):
        source_id = source_id[4:].lower()
    else:
        source_id = source_id.lower()

    # Look up in source config
    if source_id in source_config:
        return source_config[source_id].get("bucket")

    # Try matching by organization name
    org = doc.get("organization", "").lower()
    for sid, conf in source_config.items():
        if conf.get("name", "").lower() in org or org in conf.get("name", "").lower():
            return conf.get("bucket")

    return None


def evaluate_coverage(
    docs: List[Dict[str, Any]],
    source_config: Dict[str, Dict],
    reference_time: Optional[datetime] = None,
    run_id: str = ""
) -> CoverageReport:
    """
    Evaluate window-based coverage for all buckets.

    Args:
        docs: List of evidence documents
        source_config: Mapping of source_id -> {bucket, name, ...}
        reference_time: Reference time for window calculation (default: now)
        run_id: Run identifier

    Returns:
        CoverageReport with coverage status
    """
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    report = CoverageReport(
        run_id=run_id,
        evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
        reference_time_utc=reference_time.isoformat(),
        total_docs=len(docs)
    )

    # Group docs by bucket and compute ages
    bucket_docs: Dict[str, List[Tuple[Dict, float]]] = {b: [] for b in BUCKET_WINDOWS}

    for doc in docs:
        bucket = get_doc_bucket(doc, source_config)
        if bucket and bucket in bucket_docs:
            age = compute_doc_age_hours(doc, reference_time)
            if age is not None:
                bucket_docs[bucket].append((doc, age))

    # Evaluate each bucket
    for bucket, window_hours in BUCKET_WINDOWS.items():
        docs_with_ages = bucket_docs[bucket]

        # Filter to docs within window
        in_window = [(d, a) for d, a in docs_with_ages if a <= window_hours]

        coverage = BucketCoverage(
            bucket=bucket,
            window_hours=window_hours,
            docs_in_window=len(in_window),
            covered=len(in_window) >= 1
        )

        if in_window:
            ages = [a for _, a in in_window]
            coverage.oldest_doc_age_hours = max(ages)
            coverage.newest_doc_age_hours = min(ages)

            # Track contributing sources
            sources = set()
            for doc, _ in in_window:
                src = doc.get("source_id", "")
                if src:
                    sources.add(src)
            coverage.sources_contributing = list(sources)

        # Record in report
        report.counts_by_bucket[bucket] = coverage.docs_in_window
        report.bucket_details[bucket] = asdict(coverage)

        if coverage.covered:
            report.buckets_present.append(bucket)
        else:
            report.buckets_missing.append(bucket)

    # Determine status
    missing_critical = [b for b in report.buckets_missing if b in CRITICAL_BUCKETS]

    if len(missing_critical) >= 2:
        report.status = "FAIL"
        report.status_reason = f"Missing {len(missing_critical)} critical buckets: {', '.join(missing_critical)}"
    elif len(report.buckets_missing) > 0:
        report.status = "WARN"
        report.status_reason = f"Missing {len(report.buckets_missing)} buckets: {', '.join(report.buckets_missing)}"
    else:
        report.status = "PASS"
        report.status_reason = "All buckets covered"

    return report


def load_source_config_from_yaml(yaml_path: str = "config/sources.yaml") -> Dict[str, Dict]:
    """
    Load source configuration from YAML and index by source_id.

    Returns:
        Dict mapping source_id (lowercase) -> source config
    """
    import yaml

    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)

    source_map = {}
    for source in config.get('sources', []):
        source_id = source.get('id', '').lower()
        source_map[source_id] = source

    return source_map


def check_bucket_completeness(source_config: Dict[str, Dict]) -> Dict[str, List[str]]:
    """
    Check that each bucket has at least one configured source.

    Returns:
        Dict with 'complete' and 'missing' bucket lists
    """
    buckets_with_sources: Dict[str, List[str]] = {b: [] for b in BUCKET_WINDOWS}

    for source_id, conf in source_config.items():
        bucket = conf.get("bucket")
        if bucket in buckets_with_sources:
            if conf.get("enabled", True):
                buckets_with_sources[bucket].append(source_id)

    complete = [b for b, sources in buckets_with_sources.items() if sources]
    missing = [b for b, sources in buckets_with_sources.items() if not sources]

    return {
        "complete": complete,
        "missing": missing,
        "sources_by_bucket": buckets_with_sources
    }


def write_coverage_report(report: CoverageReport, output_path: str):
    """Write coverage report to JSON file."""
    with open(output_path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)

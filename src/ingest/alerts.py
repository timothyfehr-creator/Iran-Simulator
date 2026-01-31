"""Alert generation for ingestion pipeline.

Generates alerts.json with:
- Missing buckets (no docs in window)
- Sources newly DEGRADED or DOWN
- Large coverage drops vs prior run
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from enum import Enum

from .coverage import CoverageReport
from .health import HealthTracker


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class AlertType(Enum):
    """Types of alerts."""
    MISSING_BUCKET = "MISSING_BUCKET"
    SOURCE_DEGRADED = "SOURCE_DEGRADED"
    SOURCE_DOWN = "SOURCE_DOWN"
    COVERAGE_DROP = "COVERAGE_DROP"
    FETCH_FAILURE = "FETCH_FAILURE"


@dataclass
class Alert:
    """Individual alert."""
    alert_type: str
    severity: str
    message: str
    source_id: Optional[str] = None
    bucket: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class AlertReport:
    """Collection of alerts from a pipeline run."""
    run_id: str
    generated_at: str
    status: str  # PASS, WARN, FAIL
    alerts: List[Alert] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "status": self.status,
            "summary": self.summary,
            "alerts": [a.to_dict() for a in self.alerts]
        }


def generate_alerts(
    coverage_report: CoverageReport,
    newly_problematic: Dict[str, List[str]],
    fetch_errors: Dict[str, str],
    prior_coverage: Optional[CoverageReport] = None,
    run_id: str = ""
) -> AlertReport:
    """
    Generate alerts from coverage report and health changes.

    Args:
        coverage_report: Current coverage report
        newly_problematic: Dict with 'newly_degraded' and 'newly_down' source lists
        fetch_errors: Dict of source_id -> error message for failed fetches
        prior_coverage: Previous coverage report for comparison
        run_id: Run identifier

    Returns:
        AlertReport with all generated alerts
    """
    alerts = []

    # 1. Missing bucket alerts
    for bucket in coverage_report.buckets_missing:
        alerts.append(Alert(
            alert_type=AlertType.MISSING_BUCKET.value,
            severity=AlertSeverity.CRITICAL.value,
            message=f"No documents in window for bucket: {bucket}",
            bucket=bucket,
            details={"window_hours": coverage_report.bucket_details.get(bucket, {}).get("window_hours")}
        ))

    # 2. Source degraded alerts
    for source_id in newly_problematic.get("newly_degraded", []):
        alerts.append(Alert(
            alert_type=AlertType.SOURCE_DEGRADED.value,
            severity=AlertSeverity.WARNING.value,
            message=f"Source degraded: {source_id}",
            source_id=source_id
        ))

    # 3. Source down alerts
    for source_id in newly_problematic.get("newly_down", []):
        alerts.append(Alert(
            alert_type=AlertType.SOURCE_DOWN.value,
            severity=AlertSeverity.CRITICAL.value,
            message=f"Source is DOWN: {source_id}",
            source_id=source_id
        ))

    # 4. Fetch failure alerts (immediate errors, not yet degraded/down)
    for source_id, error in fetch_errors.items():
        # Only alert if not already in degraded/down
        if source_id not in newly_problematic.get("newly_degraded", []) and \
           source_id not in newly_problematic.get("newly_down", []):
            alerts.append(Alert(
                alert_type=AlertType.FETCH_FAILURE.value,
                severity=AlertSeverity.INFO.value,
                message=f"Fetch failed for {source_id}: {error[:100]}",
                source_id=source_id,
                details={"error": error}
            ))

    # 5. Coverage drop alerts (compare to prior run)
    if prior_coverage:
        # Check if any bucket went from covered to missing
        prior_covered = set(prior_coverage.buckets_present)
        current_covered = set(coverage_report.buckets_present)
        newly_missing = prior_covered - current_covered

        for bucket in newly_missing:
            alerts.append(Alert(
                alert_type=AlertType.COVERAGE_DROP.value,
                severity=AlertSeverity.WARNING.value,
                message=f"Coverage dropped: bucket '{bucket}' was covered, now missing",
                bucket=bucket
            ))

        # Check overall doc count drop (>50% drop is concerning)
        prior_total = prior_coverage.total_docs
        current_total = coverage_report.total_docs
        if prior_total > 0:
            drop_pct = (prior_total - current_total) / prior_total * 100
            if drop_pct > 50:
                alerts.append(Alert(
                    alert_type=AlertType.COVERAGE_DROP.value,
                    severity=AlertSeverity.WARNING.value,
                    message=f"Document count dropped {drop_pct:.0f}% ({prior_total} -> {current_total})",
                    details={"prior_total": prior_total, "current_total": current_total, "drop_percent": drop_pct}
                ))

    # Determine overall status
    status = determine_status(alerts, coverage_report)

    # Generate summary
    summary = {
        "total_alerts": len(alerts),
        "critical": sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL.value),
        "warning": sum(1 for a in alerts if a.severity == AlertSeverity.WARNING.value),
        "info": sum(1 for a in alerts if a.severity == AlertSeverity.INFO.value),
        "buckets_missing": len(coverage_report.buckets_missing),
        "buckets_present": len(coverage_report.buckets_present)
    }

    return AlertReport(
        run_id=run_id,
        generated_at=datetime.now(timezone.utc).isoformat(),
        status=status,
        alerts=alerts,
        summary=summary
    )


def determine_status(alerts: List[Alert], coverage_report: CoverageReport) -> str:
    """
    Determine overall alert status.

    FAIL conditions:
    - Coverage report status is FAIL
    - Any SOURCE_DOWN alert
    - 2+ MISSING_BUCKET alerts

    WARN conditions:
    - Coverage report status is WARN
    - Any SOURCE_DEGRADED alert
    - 1 MISSING_BUCKET alert

    Otherwise: PASS
    """
    # Check coverage report status first
    if coverage_report.status == "FAIL":
        return "FAIL"

    # Count critical conditions
    down_sources = sum(1 for a in alerts if a.alert_type == AlertType.SOURCE_DOWN.value)
    missing_buckets = sum(1 for a in alerts if a.alert_type == AlertType.MISSING_BUCKET.value)
    degraded_sources = sum(1 for a in alerts if a.alert_type == AlertType.SOURCE_DEGRADED.value)

    # FAIL conditions
    if down_sources > 0:
        return "FAIL"
    if missing_buckets >= 2:
        return "FAIL"

    # WARN conditions
    if coverage_report.status == "WARN":
        return "WARN"
    if degraded_sources > 0:
        return "WARN"
    if missing_buckets == 1:
        return "WARN"

    return "PASS"


def write_alerts(alert_report: AlertReport, output_path: str) -> None:
    """Write alert report to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(alert_report.to_dict(), f, indent=2)
    print(f"Wrote alerts: {output_path}")


def load_prior_coverage(runs_dir: str, current_run_id: str) -> Optional[CoverageReport]:
    """
    Load coverage report from the most recent prior run.

    Args:
        runs_dir: Directory containing run folders
        current_run_id: Current run ID to exclude

    Returns:
        CoverageReport from prior run, or None if not found
    """
    if not os.path.isdir(runs_dir):
        return None

    # Get run directories sorted by name (assumes YYYYMMDD_HHMM format)
    run_dirs = []
    for name in os.listdir(runs_dir):
        if name.startswith("RUN_") and name != f"RUN_{current_run_id}":
            path = os.path.join(runs_dir, name, "coverage_report.json")
            if os.path.exists(path):
                run_dirs.append((name, path))

    if not run_dirs:
        return None

    # Sort by name descending to get most recent
    run_dirs.sort(key=lambda x: x[0], reverse=True)
    prior_path = run_dirs[0][1]

    try:
        with open(prior_path, 'r') as f:
            data = json.load(f)
        # Convert to CoverageReport
        from .coverage import CoverageReport
        return CoverageReport(
            run_id=data.get("run_id", ""),
            evaluated_at_utc=data.get("evaluated_at_utc", ""),
            reference_time_utc=data.get("reference_time_utc", ""),
            status=data.get("status", "UNKNOWN"),
            total_docs=data.get("total_docs", 0),
            buckets_present=data.get("buckets_present", []),
            buckets_missing=data.get("buckets_missing", []),
            bucket_details=data.get("bucket_details", {})
        )
    except Exception as e:
        print(f"Warning: Could not load prior coverage from {prior_path}: {e}")
        return None


def should_exit_nonzero(alert_report: AlertReport) -> bool:
    """Check if pipeline should exit with nonzero status (for cron alerts)."""
    return alert_report.status == "FAIL"

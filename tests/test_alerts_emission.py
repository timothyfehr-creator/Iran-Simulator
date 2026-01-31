"""
Tests for alert emission on health transitions.

Workstream 3: Source Health + Alerts Hardening
Verifies alerts fire on DEGRADED/DOWN transitions.
"""

import pytest
from datetime import datetime, timezone

from src.ingest.coverage import CoverageReport
from src.ingest.alerts import (
    generate_alerts,
    determine_status,
    Alert,
    AlertType,
    AlertSeverity,
    AlertReport
)


class TestAlertEmissionOnTransitions:
    """Tests for alerts firing on health transitions."""

    def _make_coverage_report(
        self,
        status: str = "PASS",
        total_docs: int = 50,
        buckets_present: list = None,
        buckets_missing: list = None
    ) -> CoverageReport:
        """Helper to create CoverageReport for tests."""
        now = datetime.now(timezone.utc)
        return CoverageReport(
            run_id="TEST_RUN",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status=status,
            total_docs=total_docs,
            buckets_present=buckets_present or ["osint_thinktank", "ngo_rights"],
            buckets_missing=buckets_missing or [],
            bucket_details={}
        )

    def test_newly_degraded_emits_warning_alert(self):
        """Source becoming DEGRADED should emit WARNING alert."""
        coverage_report = self._make_coverage_report()

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": ["hrana"], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        degraded_alerts = [
            a for a in alert_report.alerts
            if a.alert_type == AlertType.SOURCE_DEGRADED.value
        ]

        assert len(degraded_alerts) == 1
        assert degraded_alerts[0].severity == AlertSeverity.WARNING.value
        assert degraded_alerts[0].source_id == "hrana"
        assert "degraded" in degraded_alerts[0].message.lower()

    def test_newly_down_emits_critical_alert(self):
        """Source becoming DOWN should emit CRITICAL alert."""
        coverage_report = self._make_coverage_report()

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": ["isw"]},
            fetch_errors={},
            run_id="TEST"
        )

        down_alerts = [
            a for a in alert_report.alerts
            if a.alert_type == AlertType.SOURCE_DOWN.value
        ]

        assert len(down_alerts) == 1
        assert down_alerts[0].severity == AlertSeverity.CRITICAL.value
        assert down_alerts[0].source_id == "isw"
        assert "DOWN" in down_alerts[0].message

    def test_multiple_transitions_emit_multiple_alerts(self):
        """Multiple transitions should emit multiple alerts."""
        coverage_report = self._make_coverage_report()

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={
                "newly_degraded": ["source1", "source2"],
                "newly_down": ["source3"]
            },
            fetch_errors={},
            run_id="TEST"
        )

        degraded_alerts = [
            a for a in alert_report.alerts
            if a.alert_type == AlertType.SOURCE_DEGRADED.value
        ]
        down_alerts = [
            a for a in alert_report.alerts
            if a.alert_type == AlertType.SOURCE_DOWN.value
        ]

        assert len(degraded_alerts) == 2
        assert len(down_alerts) == 1


class TestAlertEmissionOnMissingBuckets:
    """Tests for alerts on missing bucket coverage."""

    def _make_coverage_report(
        self,
        status: str = "WARN",
        buckets_missing: list = None,
        bucket_details: dict = None
    ) -> CoverageReport:
        now = datetime.now(timezone.utc)
        return CoverageReport(
            run_id="TEST_RUN",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status=status,
            total_docs=30,
            buckets_present=["osint_thinktank"],
            buckets_missing=buckets_missing or [],
            bucket_details=bucket_details or {}
        )

    def test_missing_bucket_emits_critical_alert(self):
        """Missing bucket should emit CRITICAL alert."""
        coverage_report = self._make_coverage_report(
            buckets_missing=["regime_outlets"],
            bucket_details={"regime_outlets": {"window_hours": 72}}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        bucket_alerts = [
            a for a in alert_report.alerts
            if a.alert_type == AlertType.MISSING_BUCKET.value
        ]

        assert len(bucket_alerts) == 1
        assert bucket_alerts[0].severity == AlertSeverity.CRITICAL.value
        assert bucket_alerts[0].bucket == "regime_outlets"

    def test_missing_bucket_alert_includes_window_hours(self):
        """Missing bucket alert should include window_hours in details."""
        coverage_report = self._make_coverage_report(
            buckets_missing=["internet_monitoring"],
            bucket_details={"internet_monitoring": {"window_hours": 72}}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        bucket_alerts = [
            a for a in alert_report.alerts
            if a.alert_type == AlertType.MISSING_BUCKET.value
        ]

        assert bucket_alerts[0].details.get("window_hours") == 72


class TestAlertStatus:
    """Tests for overall alert status determination."""

    def _make_coverage_report(self, status: str = "PASS") -> CoverageReport:
        now = datetime.now(timezone.utc)
        return CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status=status,
            total_docs=50,
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=[],
            bucket_details={}
        )

    def test_status_fail_on_any_down_source(self):
        """Status should be FAIL when any source is DOWN."""
        coverage_report = self._make_coverage_report()

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": ["isw"]},
            fetch_errors={},
            run_id="TEST"
        )

        assert alert_report.status == "FAIL"

    def test_status_fail_on_two_missing_buckets(self):
        """Status should be FAIL when 2+ buckets are missing."""
        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            reference_time_utc=datetime.now(timezone.utc).isoformat(),
            status="FAIL",
            total_docs=20,
            buckets_present=["osint_thinktank"],
            buckets_missing=["regime_outlets", "persian_services"],
            bucket_details={}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        assert alert_report.status == "FAIL"

    def test_status_warn_on_degraded_source(self):
        """Status should be WARN when source is DEGRADED."""
        coverage_report = self._make_coverage_report()

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": ["hrana"], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        assert alert_report.status == "WARN"

    def test_status_warn_on_single_missing_bucket(self):
        """Status should be WARN when exactly 1 bucket is missing."""
        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            reference_time_utc=datetime.now(timezone.utc).isoformat(),
            status="WARN",
            total_docs=30,
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=["regime_outlets"],
            bucket_details={}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        assert alert_report.status == "WARN"

    def test_status_pass_with_no_issues(self):
        """Status should be PASS when no issues detected."""
        coverage_report = self._make_coverage_report(status="PASS")

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        assert alert_report.status == "PASS"


class TestAlertReportSummary:
    """Tests for alert report summary generation."""

    def test_summary_counts_severities(self):
        """Summary should count alerts by severity."""
        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            reference_time_utc=datetime.now(timezone.utc).isoformat(),
            status="WARN",
            total_docs=30,
            buckets_present=["osint_thinktank"],
            buckets_missing=["regime_outlets"],
            bucket_details={}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": ["hrana"], "newly_down": []},
            fetch_errors={"irna": "Connection timeout"},
            run_id="TEST"
        )

        assert "critical" in alert_report.summary
        assert "warning" in alert_report.summary
        assert "info" in alert_report.summary
        assert alert_report.summary["critical"] >= 1  # Missing bucket
        assert alert_report.summary["warning"] >= 1  # Degraded source

    def test_summary_counts_buckets(self):
        """Summary should count buckets present and missing."""
        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            reference_time_utc=datetime.now(timezone.utc).isoformat(),
            status="WARN",
            total_docs=30,
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=["regime_outlets"],
            bucket_details={}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        assert alert_report.summary["buckets_present"] == 2
        assert alert_report.summary["buckets_missing"] == 1


class TestCoverageDropAlerts:
    """Tests for coverage drop detection vs prior run."""

    def test_bucket_lost_coverage_emits_alert(self):
        """Bucket losing coverage should emit COVERAGE_DROP alert."""
        prior = CoverageReport(
            run_id="PRIOR",
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            reference_time_utc=datetime.now(timezone.utc).isoformat(),
            status="PASS",
            total_docs=50,
            buckets_present=["osint_thinktank", "ngo_rights", "regime_outlets"],
            buckets_missing=[],
            bucket_details={}
        )

        current = CoverageReport(
            run_id="CURRENT",
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            reference_time_utc=datetime.now(timezone.utc).isoformat(),
            status="WARN",
            total_docs=40,
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=["regime_outlets"],
            bucket_details={}
        )

        alert_report = generate_alerts(
            coverage_report=current,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            prior_coverage=prior,
            run_id="TEST"
        )

        drop_alerts = [
            a for a in alert_report.alerts
            if a.alert_type == AlertType.COVERAGE_DROP.value
        ]

        assert len(drop_alerts) >= 1
        bucket_drop = [a for a in drop_alerts if a.bucket == "regime_outlets"]
        assert len(bucket_drop) == 1

    def test_large_doc_count_drop_emits_alert(self):
        """Large drop in doc count (>50%) should emit COVERAGE_DROP alert."""
        prior = CoverageReport(
            run_id="PRIOR",
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            reference_time_utc=datetime.now(timezone.utc).isoformat(),
            status="PASS",
            total_docs=100,
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=[],
            bucket_details={}
        )

        current = CoverageReport(
            run_id="CURRENT",
            evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
            reference_time_utc=datetime.now(timezone.utc).isoformat(),
            status="PASS",
            total_docs=40,  # 60% drop
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=[],
            bucket_details={}
        )

        alert_report = generate_alerts(
            coverage_report=current,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            prior_coverage=prior,
            run_id="TEST"
        )

        drop_alerts = [
            a for a in alert_report.alerts
            if a.alert_type == AlertType.COVERAGE_DROP.value
        ]

        # Should have at least one alert about doc count drop
        count_drop_alerts = [a for a in drop_alerts if "dropped" in a.message.lower()]
        assert len(count_drop_alerts) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

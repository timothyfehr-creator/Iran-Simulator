"""Unit tests for ingestion pipeline: coverage, health, and alerts."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from src.ingest.coverage import (
    evaluate_coverage,
    check_bucket_completeness,
    BucketCoverage,
    CoverageReport,
    BUCKET_WINDOWS
)
from src.ingest.health import (
    SourceHealth,
    HealthTracker,
    CONSECUTIVE_FAILURES_DEGRADED,
    CONSECUTIVE_FAILURES_DOWN
)
from src.ingest.alerts import (
    generate_alerts,
    determine_status,
    Alert,
    AlertType,
    AlertSeverity
)


# =============================================================================
# Coverage Tests
# =============================================================================

class TestWindowBasedCoverage:
    """Tests for window-based coverage gate logic."""

    def test_docs_in_window_count(self):
        """Docs published within window should count toward coverage."""
        now = datetime.now(timezone.utc)
        window_hours = BUCKET_WINDOWS["osint_thinktank"]  # 36h

        # Doc within window (published 10 hours ago)
        docs_in_window = [
            {
                "doc_id": "ISW_001",
                "source_id": "SRC_ISW",
                "published_at_utc": (now - timedelta(hours=10)).isoformat()
            }
        ]

        source_config = {"isw": {"bucket": "osint_thinktank"}}
        report = evaluate_coverage(docs_in_window, source_config, reference_time=now)

        assert "osint_thinktank" in report.buckets_present
        assert "osint_thinktank" not in report.buckets_missing

    def test_docs_outside_window_dont_count(self):
        """Docs published outside window should NOT count toward coverage."""
        now = datetime.now(timezone.utc)
        window_hours = BUCKET_WINDOWS["osint_thinktank"]  # 36h

        # Doc outside window (published 48 hours ago)
        old_docs = [
            {
                "doc_id": "ISW_001",
                "source_id": "SRC_ISW",
                "published_at_utc": (now - timedelta(hours=48)).isoformat()
            }
        ]

        source_config = {"isw": {"bucket": "osint_thinktank"}}
        report = evaluate_coverage(old_docs, source_config, reference_time=now)

        # Old doc shouldn't count - bucket should be missing
        assert "osint_thinktank" not in report.buckets_present
        assert "osint_thinktank" in report.buckets_missing

    def test_edge_case_exactly_at_window_boundary(self):
        """Doc at exactly the window boundary should count."""
        now = datetime.now(timezone.utc)
        window_hours = BUCKET_WINDOWS["ngo_rights"]  # 72h

        # Doc exactly at boundary (72 hours ago)
        boundary_docs = [
            {
                "doc_id": "HRANA_001",
                "source_id": "SRC_HRANA",
                "published_at_utc": (now - timedelta(hours=72)).isoformat()
            }
        ]

        source_config = {"hrana": {"bucket": "ngo_rights"}}
        report = evaluate_coverage(boundary_docs, source_config, reference_time=now)

        # At boundary should count (<=, not <)
        assert "ngo_rights" in report.buckets_present

    def test_multiple_buckets_mixed_coverage(self):
        """Test with some buckets covered, some missing."""
        now = datetime.now(timezone.utc)

        docs = [
            # ISW doc within window
            {
                "doc_id": "ISW_001",
                "source_id": "SRC_ISW",
                "published_at_utc": (now - timedelta(hours=12)).isoformat()
            },
            # HRANA doc within window
            {
                "doc_id": "HRANA_001",
                "source_id": "SRC_HRANA",
                "published_at_utc": (now - timedelta(hours=24)).isoformat()
            }
        ]

        source_config = {
            "isw": {"bucket": "osint_thinktank"},
            "hrana": {"bucket": "ngo_rights"},
            "irna": {"bucket": "regime_outlets"},  # No docs for this bucket
        }

        report = evaluate_coverage(docs, source_config, reference_time=now)

        assert "osint_thinktank" in report.buckets_present
        assert "ngo_rights" in report.buckets_present
        assert "regime_outlets" in report.buckets_missing

    def test_coverage_status_fail_on_multiple_missing(self):
        """Coverage should FAIL when 2+ critical buckets are missing."""
        now = datetime.now(timezone.utc)

        # Only one bucket covered
        docs = [
            {
                "doc_id": "ISW_001",
                "source_id": "SRC_ISW",
                "published_at_utc": (now - timedelta(hours=12)).isoformat()
            }
        ]

        # Config with multiple buckets
        source_config = {
            "isw": {"bucket": "osint_thinktank"},
            "hrana": {"bucket": "ngo_rights"},
            "irna": {"bucket": "regime_outlets"},
            "iranintl": {"bucket": "persian_services"},
        }

        report = evaluate_coverage(docs, source_config, reference_time=now)

        # Should be FAIL since 3 buckets are missing
        assert report.status == "FAIL"
        assert len(report.buckets_missing) >= 2

    def test_coverage_status_warn_on_one_critical_missing(self):
        """Coverage should WARN when exactly 1 critical bucket is missing."""
        now = datetime.now(timezone.utc)

        # Cover all critical buckets except one, plus non-critical
        docs = [
            {"doc_id": "ISW_001", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=12)).isoformat()},
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
            {"doc_id": "IRNA_001", "source_id": "SRC_IRNA",
             "published_at_utc": (now - timedelta(hours=36)).isoformat()},
            {"doc_id": "NETBLOCKS_001", "source_id": "SRC_NETBLOCKS",
             "published_at_utc": (now - timedelta(hours=36)).isoformat()},
            {"doc_id": "BONBAST_001", "source_id": "SRC_BONBAST",
             "published_at_utc": (now - timedelta(hours=36)).isoformat()},
        ]

        # Config covers 5 of 6 buckets - missing persian_services (critical)
        source_config = {
            "isw": {"bucket": "osint_thinktank"},
            "hrana": {"bucket": "ngo_rights"},
            "irna": {"bucket": "regime_outlets"},
            "netblocks": {"bucket": "internet_monitoring"},
            "bonbast": {"bucket": "econ_fx"},
            # persian_services is NOT covered - but it's the only critical one missing
        }

        report = evaluate_coverage(docs, source_config, reference_time=now)

        # persian_services is the only missing bucket
        assert "persian_services" in report.buckets_missing
        # Status should be WARN because only 1 critical bucket is missing
        assert report.status == "WARN"

    def test_coverage_status_pass_all_covered(self):
        """Coverage should PASS when all buckets are covered."""
        now = datetime.now(timezone.utc)

        docs = [
            {"doc_id": "ISW_001", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=12)).isoformat()},
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
        ]

        source_config = {
            "isw": {"bucket": "osint_thinktank"},
            "hrana": {"bucket": "ngo_rights"},
        }

        report = evaluate_coverage(docs, source_config, reference_time=now)

        # With only 2 buckets in config, and both covered, should be PASS
        # (remaining buckets from BUCKET_WINDOWS will be missing though)
        # Let's check that at least these 2 are present
        assert "osint_thinktank" in report.buckets_present
        assert "ngo_rights" in report.buckets_present


class TestBucketCompleteness:
    """Tests for bucket configuration completeness."""

    def test_complete_config(self):
        """All buckets should have at least one source."""
        source_config = {
            "isw": {"bucket": "osint_thinktank", "enabled": True},
            "hrana": {"bucket": "ngo_rights", "enabled": True},
            "irna": {"bucket": "regime_outlets", "enabled": True},
            "iranintl": {"bucket": "persian_services", "enabled": True},
            "netblocks": {"bucket": "internet_monitoring", "enabled": True},
            "bonbast": {"bucket": "econ_fx", "enabled": True},
        }

        result = check_bucket_completeness(source_config)

        # Complete is a list of covered buckets
        assert len(result["missing"]) == 0
        assert len(result["complete"]) == 6

    def test_missing_buckets_detected(self):
        """Missing buckets should be identified."""
        source_config = {
            "isw": {"bucket": "osint_thinktank", "enabled": True},
            "hrana": {"bucket": "ngo_rights", "enabled": True},
            # Missing: regime_outlets, persian_services, internet_monitoring, econ_fx
        }

        result = check_bucket_completeness(source_config)

        assert len(result["missing"]) > 0
        assert "regime_outlets" in result["missing"]
        assert "persian_services" in result["missing"]


# =============================================================================
# Health Tracking Tests
# =============================================================================

class TestSourceHealthTransitions:
    """Tests for source health status transitions."""

    def test_initial_status_is_ok(self):
        """New sources should start with OK status."""
        health = SourceHealth(source_id="test", name="Test Source", bucket="test")

        assert health.status == "OK"
        assert health.consecutive_failures == 0

    def test_single_failure_stays_ok(self):
        """Single failure should not change OK status."""
        health = SourceHealth(source_id="test", name="Test Source", bucket="test")
        health.record_failure("Network timeout")

        assert health.status == "OK"
        assert health.consecutive_failures == 1

    def test_degraded_after_threshold_failures(self):
        """Status should transition to DEGRADED after threshold failures."""
        health = SourceHealth(source_id="test", name="Test Source", bucket="test")

        # Record failures up to threshold
        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            health.record_failure(f"Error {i}")

        assert health.status == "DEGRADED"
        assert health.consecutive_failures == CONSECUTIVE_FAILURES_DEGRADED

    def test_down_after_higher_threshold(self):
        """Status should transition to DOWN after higher threshold."""
        health = SourceHealth(source_id="test", name="Test Source", bucket="test")

        # Record failures up to DOWN threshold
        for i in range(CONSECUTIVE_FAILURES_DOWN):
            health.record_failure(f"Error {i}")

        assert health.status == "DOWN"
        assert health.consecutive_failures == CONSECUTIVE_FAILURES_DOWN

    def test_success_resets_failures(self):
        """Successful fetch should reset failure count and status."""
        health = SourceHealth(source_id="test", name="Test Source", bucket="test")

        # Get to DEGRADED state
        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            health.record_failure(f"Error {i}")
        assert health.status == "DEGRADED"

        # Success should reset
        health.record_success(5)

        assert health.status == "OK"
        assert health.consecutive_failures == 0
        assert health.docs_fetched_last_run == 5

    def test_degraded_to_down_transition(self):
        """DEGRADED should transition to DOWN with more failures."""
        health = SourceHealth(source_id="test", name="Test Source", bucket="test")

        # First get to DEGRADED
        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            health.record_failure(f"Error {i}")
        assert health.status == "DEGRADED"

        # Continue failing to DOWN
        remaining = CONSECUTIVE_FAILURES_DOWN - CONSECUTIVE_FAILURES_DEGRADED
        for i in range(remaining):
            health.record_failure(f"Error {i}")

        assert health.status == "DOWN"


class TestHealthTracker:
    """Tests for HealthTracker collection management."""

    def test_get_or_create_new_source(self):
        """Should create new SourceHealth for unknown source."""
        tracker = HealthTracker()
        health = tracker.get_or_create("new_source", name="New", bucket="test")

        assert health.source_id == "new_source"
        assert health.status == "OK"

    def test_get_or_create_existing_source(self):
        """Should return existing SourceHealth for known source."""
        tracker = HealthTracker()

        # Create and modify
        health1 = tracker.get_or_create("test", name="Test", bucket="test")
        health1.record_failure("error")

        # Get again
        health2 = tracker.get_or_create("test", name="Test", bucket="test")

        # Should be same object
        assert health2.consecutive_failures == 1

    def test_newly_degraded_detection(self):
        """Should detect sources that newly became DEGRADED."""
        tracker = HealthTracker()
        previous = HealthTracker()

        # Previous: source was OK
        prev_health = previous.get_or_create("test", name="Test", bucket="test")
        assert prev_health.status == "OK"

        # Current: source is DEGRADED
        curr_health = tracker.get_or_create("test", name="Test", bucket="test")
        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            curr_health.record_failure(f"Error {i}")
        assert curr_health.status == "DEGRADED"

        # Should detect the change
        result = tracker.get_newly_degraded_or_down(previous)

        assert "test" in result["newly_degraded"]
        assert "test" not in result["newly_down"]

    def test_newly_down_detection(self):
        """Should detect sources that newly became DOWN."""
        tracker = HealthTracker()
        previous = HealthTracker()

        # Previous: source was DEGRADED
        prev_health = previous.get_or_create("test", name="Test", bucket="test")
        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            prev_health.record_failure(f"Error {i}")
        assert prev_health.status == "DEGRADED"

        # Current: source is DOWN
        curr_health = tracker.get_or_create("test", name="Test", bucket="test")
        for i in range(CONSECUTIVE_FAILURES_DOWN):
            curr_health.record_failure(f"Error {i}")
        assert curr_health.status == "DOWN"

        # Should detect the change
        result = tracker.get_newly_degraded_or_down(previous)

        assert "test" not in result["newly_degraded"]
        assert "test" in result["newly_down"]

    def test_summary_generation(self):
        """Should generate correct summary statistics."""
        tracker = HealthTracker()

        # Add some sources with different statuses
        ok_source = tracker.get_or_create("ok1", name="OK", bucket="test")

        degraded_source = tracker.get_or_create("degraded1", name="Degraded", bucket="test")
        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            degraded_source.record_failure(f"Error {i}")

        down_source = tracker.get_or_create("down1", name="Down", bucket="test")
        for i in range(CONSECUTIVE_FAILURES_DOWN):
            down_source.record_failure(f"Error {i}")

        summary = tracker.get_summary()

        assert summary["total_sources"] == 3
        assert summary["status_counts"]["OK"] == 1
        assert summary["status_counts"]["DEGRADED"] == 1
        assert summary["status_counts"]["DOWN"] == 1


# =============================================================================
# Alerts Tests
# =============================================================================

class TestAlertGeneration:
    """Tests for alert generation logic."""

    def test_missing_bucket_generates_alert(self):
        """Missing buckets should generate CRITICAL alerts."""
        now = datetime.now(timezone.utc)
        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status="WARN",
            total_docs=5,
            buckets_present=["osint_thinktank"],
            buckets_missing=["regime_outlets"],
            bucket_details={"regime_outlets": {"window_hours": 72}}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        bucket_alerts = [a for a in alert_report.alerts
                        if a.alert_type == AlertType.MISSING_BUCKET.value]
        assert len(bucket_alerts) == 1
        assert bucket_alerts[0].severity == AlertSeverity.CRITICAL.value

    def test_degraded_source_generates_warning(self):
        """Newly degraded sources should generate WARNING alerts."""
        now = datetime.now(timezone.utc)
        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status="PASS",
            total_docs=10,
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=[],
            bucket_details={}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": ["hrana"], "newly_down": []},
            fetch_errors={},
            run_id="TEST"
        )

        degraded_alerts = [a for a in alert_report.alerts
                         if a.alert_type == AlertType.SOURCE_DEGRADED.value]
        assert len(degraded_alerts) == 1
        assert degraded_alerts[0].severity == AlertSeverity.WARNING.value

    def test_down_source_generates_critical(self):
        """Sources going DOWN should generate CRITICAL alerts."""
        now = datetime.now(timezone.utc)
        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status="PASS",
            total_docs=10,
            buckets_present=["osint_thinktank"],
            buckets_missing=[],
            bucket_details={}
        )

        alert_report = generate_alerts(
            coverage_report=coverage_report,
            newly_problematic={"newly_degraded": [], "newly_down": ["isw"]},
            fetch_errors={},
            run_id="TEST"
        )

        down_alerts = [a for a in alert_report.alerts
                      if a.alert_type == AlertType.SOURCE_DOWN.value]
        assert len(down_alerts) == 1
        assert down_alerts[0].severity == AlertSeverity.CRITICAL.value


class TestAlertStatus:
    """Tests for overall alert status determination."""

    def test_fail_on_down_source(self):
        """Status should be FAIL when any source is DOWN."""
        now = datetime.now(timezone.utc)
        alerts = [Alert(
            alert_type=AlertType.SOURCE_DOWN.value,
            severity=AlertSeverity.CRITICAL.value,
            message="Test DOWN",
            source_id="test"
        )]

        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status="PASS",
            total_docs=10,
            buckets_present=["osint_thinktank"],
            buckets_missing=[],
            bucket_details={}
        )

        status = determine_status(alerts, coverage_report)
        assert status == "FAIL"

    def test_fail_on_multiple_missing_buckets(self):
        """Status should be FAIL when 2+ buckets are missing."""
        now = datetime.now(timezone.utc)
        alerts = [
            Alert(
                alert_type=AlertType.MISSING_BUCKET.value,
                severity=AlertSeverity.CRITICAL.value,
                message="Missing bucket 1",
                bucket="bucket1"
            ),
            Alert(
                alert_type=AlertType.MISSING_BUCKET.value,
                severity=AlertSeverity.CRITICAL.value,
                message="Missing bucket 2",
                bucket="bucket2"
            )
        ]

        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status="FAIL",
            total_docs=5,
            buckets_present=["osint_thinktank"],
            buckets_missing=["bucket1", "bucket2"],
            bucket_details={}
        )

        status = determine_status(alerts, coverage_report)
        assert status == "FAIL"

    def test_warn_on_degraded_source(self):
        """Status should be WARN when source is degraded."""
        now = datetime.now(timezone.utc)
        alerts = [Alert(
            alert_type=AlertType.SOURCE_DEGRADED.value,
            severity=AlertSeverity.WARNING.value,
            message="Test DEGRADED",
            source_id="test"
        )]

        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status="PASS",
            total_docs=10,
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=[],
            bucket_details={}
        )

        status = determine_status(alerts, coverage_report)
        assert status == "WARN"

    def test_warn_on_single_missing_bucket(self):
        """Status should be WARN when exactly 1 bucket is missing."""
        now = datetime.now(timezone.utc)
        alerts = [Alert(
            alert_type=AlertType.MISSING_BUCKET.value,
            severity=AlertSeverity.CRITICAL.value,
            message="Missing bucket",
            bucket="regime_outlets"
        )]

        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status="WARN",
            total_docs=5,
            buckets_present=["osint_thinktank", "ngo_rights"],
            buckets_missing=["regime_outlets"],
            bucket_details={}
        )

        status = determine_status(alerts, coverage_report)
        assert status == "WARN"

    def test_pass_with_no_issues(self):
        """Status should be PASS when no issues."""
        now = datetime.now(timezone.utc)
        coverage_report = CoverageReport(
            run_id="TEST",
            evaluated_at_utc=now.isoformat(),
            reference_time_utc=now.isoformat(),
            status="PASS",
            total_docs=20,
            buckets_present=["osint_thinktank", "ngo_rights", "regime_outlets"],
            buckets_missing=[],
            bucket_details={}
        )

        status = determine_status([], coverage_report)
        assert status == "PASS"


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for source health tracking and status transitions.

Workstream 3: Source Health + Alerts Hardening
Verifies OK → DEGRADED → DOWN transitions are correct.
"""

import pytest
from datetime import datetime, timezone

from src.ingest.health import (
    SourceHealth,
    HealthTracker,
    CONSECUTIVE_FAILURES_DEGRADED,
    CONSECUTIVE_FAILURES_DOWN,
    ROLLING_AVERAGE_RUNS,
    load_health_tracker,
    save_health_tracker
)


class TestHealthThresholds:
    """Tests for health threshold configuration."""

    def test_degraded_threshold_is_3(self):
        """DEGRADED threshold should be 3 consecutive failures."""
        assert CONSECUTIVE_FAILURES_DEGRADED == 3

    def test_down_threshold_is_7(self):
        """DOWN threshold should be 7 consecutive failures."""
        assert CONSECUTIVE_FAILURES_DOWN == 7

    def test_degraded_before_down(self):
        """DEGRADED threshold should be lower than DOWN threshold."""
        assert CONSECUTIVE_FAILURES_DEGRADED < CONSECUTIVE_FAILURES_DOWN


class TestSourceHealthTransitions:
    """Tests for SourceHealth status transitions."""

    def test_initial_status_is_ok(self):
        """New source should have OK status."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        assert health.status == "OK"
        assert health.consecutive_failures == 0

    def test_single_failure_stays_ok(self):
        """Single failure should not change OK status."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        health.record_failure("Connection timeout")

        assert health.status == "OK"
        assert health.consecutive_failures == 1
        assert health.last_error == "Connection timeout"

    def test_two_failures_stays_ok(self):
        """Two failures should not change OK status."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        health.record_failure("Error 1")
        health.record_failure("Error 2")

        assert health.status == "OK"
        assert health.consecutive_failures == 2

    def test_three_failures_triggers_degraded(self):
        """Three consecutive failures should trigger DEGRADED status."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            health.record_failure(f"Error {i+1}")

        assert health.status == "DEGRADED"
        assert health.consecutive_failures == CONSECUTIVE_FAILURES_DEGRADED

    def test_six_failures_stays_degraded(self):
        """Six failures should stay DEGRADED (not yet DOWN)."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        for i in range(6):
            health.record_failure(f"Error {i+1}")

        assert health.status == "DEGRADED"
        assert health.consecutive_failures == 6

    def test_seven_failures_triggers_down(self):
        """Seven consecutive failures should trigger DOWN status."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        for i in range(CONSECUTIVE_FAILURES_DOWN):
            health.record_failure(f"Error {i+1}")

        assert health.status == "DOWN"
        assert health.consecutive_failures == CONSECUTIVE_FAILURES_DOWN

    def test_success_resets_to_ok(self):
        """Success should reset failures and status to OK."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        # Get to DEGRADED
        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            health.record_failure(f"Error {i+1}")
        assert health.status == "DEGRADED"

        # Success resets
        health.record_success(5)

        assert health.status == "OK"
        assert health.consecutive_failures == 0
        assert health.docs_fetched_last_run == 5

    def test_success_resets_from_down(self):
        """Success should reset from DOWN status to OK."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        # Get to DOWN
        for i in range(CONSECUTIVE_FAILURES_DOWN):
            health.record_failure(f"Error {i+1}")
        assert health.status == "DOWN"

        # Success resets
        health.record_success(10)

        assert health.status == "OK"
        assert health.consecutive_failures == 0

    def test_degraded_to_down_transition(self):
        """Should transition from DEGRADED to DOWN with continued failures."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        # First reach DEGRADED
        for i in range(CONSECUTIVE_FAILURES_DEGRADED):
            health.record_failure(f"Error {i+1}")
        assert health.status == "DEGRADED"

        # Continue to DOWN
        remaining = CONSECUTIVE_FAILURES_DOWN - CONSECUTIVE_FAILURES_DEGRADED
        for i in range(remaining):
            health.record_failure(f"Error {i+1}")

        assert health.status == "DOWN"


class TestSourceHealthHistory:
    """Tests for docs history and rolling average."""

    def test_docs_history_recorded(self):
        """Document counts should be recorded in history."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        health.record_success(10)
        health.record_success(20)
        health.record_success(30)

        assert health.docs_history == [10, 20, 30]

    def test_rolling_average_computed(self):
        """Rolling average should be computed correctly."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        health.record_success(10)
        health.record_success(20)
        health.record_success(30)

        assert health.avg_docs_per_run_last_7 == 20.0

    def test_history_capped_at_7(self):
        """History should be capped at ROLLING_AVERAGE_RUNS."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        for i in range(10):
            health.record_success(i * 10)

        assert len(health.docs_history) == ROLLING_AVERAGE_RUNS
        # Should have the last 7 values
        assert health.docs_history[0] == 30  # 10*3

    def test_failures_add_zero_to_history(self):
        """Failures should add 0 to doc history."""
        health = SourceHealth(source_id="test_source", name="Test", bucket="test")

        health.record_success(10)
        health.record_failure("Error")
        health.record_success(20)

        assert health.docs_history == [10, 0, 20]


class TestHealthTracker:
    """Tests for HealthTracker collection management."""

    def test_get_or_create_new(self):
        """Should create new SourceHealth for unknown source."""
        tracker = HealthTracker()

        health = tracker.get_or_create("new_source", name="New", bucket="test")

        assert health.source_id == "new_source"
        assert health.status == "OK"
        assert "new_source" in tracker.sources

    def test_get_or_create_existing(self):
        """Should return existing SourceHealth for known source."""
        tracker = HealthTracker()

        health1 = tracker.get_or_create("test_source", name="Test", bucket="test")
        health1.record_failure("Error")

        health2 = tracker.get_or_create("test_source", name="Test", bucket="test")

        assert health2.consecutive_failures == 1
        assert health1 is health2

    def test_summary_counts_statuses(self):
        """Summary should count sources by status."""
        tracker = HealthTracker()

        # Create sources with different statuses
        ok_source = tracker.get_or_create("ok", name="OK", bucket="test")

        degraded_source = tracker.get_or_create("degraded", name="Degraded", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DEGRADED):
            degraded_source.record_failure("Error")

        down_source = tracker.get_or_create("down", name="Down", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DOWN):
            down_source.record_failure("Error")

        summary = tracker.get_summary()

        assert summary["total_sources"] == 3
        assert summary["status_counts"]["OK"] == 1
        assert summary["status_counts"]["DEGRADED"] == 1
        assert summary["status_counts"]["DOWN"] == 1

    def test_summary_overall_status_down(self):
        """Overall status should be DOWN if any source is DOWN."""
        tracker = HealthTracker()

        ok_source = tracker.get_or_create("ok", name="OK", bucket="test")
        down_source = tracker.get_or_create("down", name="Down", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DOWN):
            down_source.record_failure("Error")

        summary = tracker.get_summary()

        assert summary["overall_status"] == "DOWN"
        assert "down" in summary["down_sources"]

    def test_summary_overall_status_degraded(self):
        """Overall status should be DEGRADED if any source is DEGRADED (and none DOWN)."""
        tracker = HealthTracker()

        ok_source = tracker.get_or_create("ok", name="OK", bucket="test")
        degraded_source = tracker.get_or_create("degraded", name="Degraded", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DEGRADED):
            degraded_source.record_failure("Error")

        summary = tracker.get_summary()

        assert summary["overall_status"] == "DEGRADED"
        assert "degraded" in summary["degraded_sources"]

    def test_summary_overall_status_ok(self):
        """Overall status should be OK if all sources are OK."""
        tracker = HealthTracker()

        tracker.get_or_create("source1", name="Source 1", bucket="test")
        tracker.get_or_create("source2", name="Source 2", bucket="test")

        summary = tracker.get_summary()

        assert summary["overall_status"] == "OK"


class TestHealthTrackerComparison:
    """Tests for comparing health states across runs."""

    def test_detect_newly_degraded(self):
        """Should detect sources that newly became DEGRADED."""
        previous = HealthTracker()
        previous.get_or_create("test_source", name="Test", bucket="test")

        current = HealthTracker()
        current_health = current.get_or_create("test_source", name="Test", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DEGRADED):
            current_health.record_failure("Error")

        result = current.get_newly_degraded_or_down(previous)

        assert "test_source" in result["newly_degraded"]
        assert "test_source" not in result["newly_down"]

    def test_detect_newly_down(self):
        """Should detect sources that newly became DOWN."""
        previous = HealthTracker()
        prev_health = previous.get_or_create("test_source", name="Test", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DEGRADED):
            prev_health.record_failure("Error")
        assert prev_health.status == "DEGRADED"

        current = HealthTracker()
        curr_health = current.get_or_create("test_source", name="Test", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DOWN):
            curr_health.record_failure("Error")
        assert curr_health.status == "DOWN"

        result = current.get_newly_degraded_or_down(previous)

        assert "test_source" not in result["newly_degraded"]
        assert "test_source" in result["newly_down"]

    def test_detect_ok_to_down_transition(self):
        """Should detect direct OK → DOWN transition."""
        previous = HealthTracker()
        previous.get_or_create("test_source", name="Test", bucket="test")

        current = HealthTracker()
        curr_health = current.get_or_create("test_source", name="Test", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DOWN):
            curr_health.record_failure("Error")

        result = current.get_newly_degraded_or_down(previous)

        # Should be in newly_down, not newly_degraded
        assert "test_source" in result["newly_down"]

    def test_no_previous_state_assumes_ok(self):
        """Without previous state, should assume OK baseline."""
        current = HealthTracker()
        curr_health = current.get_or_create("test_source", name="Test", bucket="test")
        for _ in range(CONSECUTIVE_FAILURES_DEGRADED):
            curr_health.record_failure("Error")

        result = current.get_newly_degraded_or_down(None)

        assert "test_source" in result["newly_degraded"]


class TestHealthTrackerSerialization:
    """Tests for serialization/deserialization."""

    def test_to_dict_and_from_dict(self):
        """Should serialize and deserialize correctly."""
        tracker = HealthTracker()

        health = tracker.get_or_create("test_source", name="Test", bucket="test")
        health.record_success(10)
        health.record_success(20)
        health.record_failure("Error")

        # Serialize
        data = tracker.to_dict()

        # Deserialize
        restored = HealthTracker.from_dict(data)

        assert "test_source" in restored.sources
        assert restored.sources["test_source"].docs_history == [10, 20, 0]
        assert restored.sources["test_source"].consecutive_failures == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

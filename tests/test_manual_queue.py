"""
Tests for Phase 3B Red-Team Fix 1: Manual Resolution Queue Visibility.

Tests for get_pending_manual_adjudication() and get_manual_resolution_queue()
which provide visibility into forecasts awaiting human adjudication.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.forecasting import ledger
from src.forecasting import resolver


@pytest.fixture
def temp_ledger_dir(tmp_path):
    """Create a temporary ledger directory."""
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    return ledger_dir


@pytest.fixture
def sample_catalog():
    """Sample catalog with manual and auto resolution events."""
    return {
        "catalog_version": "3.0.0",
        "events": [
            {
                "event_id": "test.auto_event",
                "name": "Auto Event",
                "category": "test",
                "event_type": "binary",
                "allowed_outcomes": ["YES", "NO", "UNKNOWN"],
                "auto_resolve": True,
                "requires_manual_resolution": False,
                "resolution_source": {"type": "compiled_intel", "path": "test.value", "rule": "threshold_gte"},
            },
            {
                "event_id": "test.manual_event",
                "name": "Manual Event",
                "category": "test",
                "event_type": "binary",
                "allowed_outcomes": ["YES", "NO", "UNKNOWN"],
                "auto_resolve": False,
                "requires_manual_resolution": True,
                "resolution_source": {"type": "manual"},
            },
            {
                "event_id": "test.another_manual",
                "name": "Another Manual Event",
                "category": "test",
                "event_type": "categorical",
                "allowed_outcomes": ["A", "B", "C", "UNKNOWN"],
                "auto_resolve": False,
                "requires_manual_resolution": True,
                "resolution_source": {"type": "manual"},
            },
        ]
    }


def create_forecast(ledger_dir: Path, forecast_id: str, event_id: str, target_date: datetime):
    """Helper to create a test forecast."""
    record = {
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": 7,
        "target_date_utc": target_date.isoformat(),
        "probabilities": {"YES": 0.6, "NO": 0.4},
        "abstain": False,
    }
    ledger.append_forecast(record, ledger_dir)


def create_resolution(ledger_dir: Path, forecast_id: str, event_id: str, outcome: str):
    """Helper to create a test resolution."""
    record = {
        "resolution_id": f"res_{forecast_id}",
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": 7,
        "resolved_outcome": outcome,
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolution_mode": "external_manual",
        "reason_code": "test",
        "evidence_refs": [],
        "evidence_hashes": [],
    }
    ledger.append_resolution(record, ledger_dir)


class TestGetPendingManualAdjudication:
    """Tests for ledger.get_pending_manual_adjudication()."""

    def test_returns_only_manual_events(self, temp_ledger_dir, sample_catalog):
        """Test that only events with requires_manual_resolution=true are returned."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)

        # Create forecasts for both auto and manual events
        create_forecast(temp_ledger_dir, "f1", "test.auto_event", yesterday)
        create_forecast(temp_ledger_dir, "f2", "test.manual_event", yesterday)

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog
        )

        # Only manual event should be returned
        assert len(pending) == 1
        assert pending[0]["event_id"] == "test.manual_event"

    def test_excludes_resolved_forecasts(self, temp_ledger_dir, sample_catalog):
        """Test that resolved forecasts are not included."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)

        # Create two manual forecasts
        create_forecast(temp_ledger_dir, "f1", "test.manual_event", yesterday)
        create_forecast(temp_ledger_dir, "f2", "test.manual_event", yesterday)

        # Resolve one
        create_resolution(temp_ledger_dir, "f1", "test.manual_event", "YES")

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog
        )

        # Only unresolved should be returned
        assert len(pending) == 1
        assert pending[0]["forecast"]["forecast_id"] == "f2"

    def test_excludes_future_target_dates(self, temp_ledger_dir, sample_catalog):
        """Test that forecasts with future target dates are not included."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)

        # Create one past and one future forecast
        create_forecast(temp_ledger_dir, "f1", "test.manual_event", yesterday)
        create_forecast(temp_ledger_dir, "f2", "test.manual_event", tomorrow)

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog
        )

        # Only past should be returned
        assert len(pending) == 1
        assert pending[0]["forecast"]["forecast_id"] == "f1"

    def test_due_date_calculation(self, temp_ledger_dir, sample_catalog):
        """Test that due_date_utc is correctly calculated."""
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)

        create_forecast(temp_ledger_dir, "f1", "test.manual_event", five_days_ago)

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog,
            grace_days=7
        )

        assert len(pending) == 1
        # Due date should be 7 days after target
        due_date = datetime.fromisoformat(pending[0]["due_date_utc"].replace('Z', '+00:00'))
        expected_due = five_days_ago + timedelta(days=7)

        # Allow 1 second tolerance for test timing
        assert abs((due_date - expected_due).total_seconds()) < 1

    def test_days_overdue_calculation(self, temp_ledger_dir, sample_catalog):
        """Test that days_overdue is correctly calculated."""
        # 10 days ago with 7-day grace = 3 days overdue
        ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)

        create_forecast(temp_ledger_dir, "f1", "test.manual_event", ten_days_ago)

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog,
            grace_days=7
        )

        assert len(pending) == 1
        assert pending[0]["days_overdue"] == 3

    def test_status_overdue(self, temp_ledger_dir, sample_catalog):
        """Test that status is 'overdue' when days_overdue > 0."""
        ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)

        create_forecast(temp_ledger_dir, "f1", "test.manual_event", ten_days_ago)

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog,
            grace_days=7
        )

        assert pending[0]["status"] == "overdue"

    def test_status_due_soon(self, temp_ledger_dir, sample_catalog):
        """Test that status is 'due_soon' when due date is within 2 days."""
        # 6 days ago with 7-day grace = 1 day until due (due_soon)
        six_days_ago = datetime.now(timezone.utc) - timedelta(days=6)

        create_forecast(temp_ledger_dir, "f1", "test.manual_event", six_days_ago)

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog,
            grace_days=7
        )

        assert pending[0]["status"] == "due_soon"

    def test_status_pending(self, temp_ledger_dir, sample_catalog):
        """Test that status is 'pending' when due date is more than 2 days away."""
        # 2 days ago with 7-day grace = 5 days until due (pending)
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)

        create_forecast(temp_ledger_dir, "f1", "test.manual_event", two_days_ago)

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog,
            grace_days=7
        )

        assert pending[0]["status"] == "pending"

    def test_sorted_by_urgency(self, temp_ledger_dir, sample_catalog):
        """Test that results are sorted by urgency (most overdue first)."""
        # Create forecasts with different ages
        ten_days_ago = datetime.now(timezone.utc) - timedelta(days=10)
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)

        create_forecast(temp_ledger_dir, "f1", "test.manual_event", five_days_ago)
        create_forecast(temp_ledger_dir, "f2", "test.manual_event", ten_days_ago)
        create_forecast(temp_ledger_dir, "f3", "test.manual_event", two_days_ago)

        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog,
            grace_days=7
        )

        # Should be sorted: f2 (most overdue), f1, f3
        assert len(pending) == 3
        assert pending[0]["forecast"]["forecast_id"] == "f2"
        assert pending[1]["forecast"]["forecast_id"] == "f1"
        assert pending[2]["forecast"]["forecast_id"] == "f3"

    def test_empty_ledger(self, temp_ledger_dir, sample_catalog):
        """Test that empty ledger returns empty list."""
        pending = ledger.get_pending_manual_adjudication(
            ledger_dir=temp_ledger_dir,
            catalog=sample_catalog
        )

        assert pending == []


class TestGetManualResolutionQueue:
    """Tests for resolver.get_manual_resolution_queue()."""

    def test_returns_enriched_results(self, temp_ledger_dir, sample_catalog, tmp_path):
        """Test that results include event data."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        create_forecast(temp_ledger_dir, "f1", "test.manual_event", yesterday)

        # Create minimal catalog file
        catalog_path = tmp_path / "catalog.json"
        import json
        with open(catalog_path, 'w') as f:
            json.dump(sample_catalog, f)

        queue = resolver.get_manual_resolution_queue(
            catalog_path=catalog_path,
            ledger_dir=temp_ledger_dir
        )

        assert len(queue) == 1
        assert "forecast" in queue[0]
        assert "event" in queue[0]
        assert queue[0]["event"]["event_id"] == "test.manual_event"
        assert "due_date_utc" in queue[0]
        assert "days_overdue" in queue[0]
        assert "status" in queue[0]

    def test_multiple_manual_events(self, temp_ledger_dir, sample_catalog, tmp_path):
        """Test queue with multiple manual event types."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)

        create_forecast(temp_ledger_dir, "f1", "test.manual_event", yesterday)
        create_forecast(temp_ledger_dir, "f2", "test.another_manual", yesterday)

        catalog_path = tmp_path / "catalog.json"
        import json
        with open(catalog_path, 'w') as f:
            json.dump(sample_catalog, f)

        queue = resolver.get_manual_resolution_queue(
            catalog_path=catalog_path,
            ledger_dir=temp_ledger_dir
        )

        assert len(queue) == 2
        event_ids = {q["event"]["event_id"] for q in queue}
        assert "test.manual_event" in event_ids
        assert "test.another_manual" in event_ids

"""
Tests for resolution queue functionality.

Validates that the queue command correctly lists due forecasts.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from io import StringIO
import sys

from src.forecasting import ledger
from src.forecasting.cli import cmd_queue


@pytest.fixture
def temp_ledger_dir(tmp_path):
    """Create a temporary ledger directory."""
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    return ledger_dir


@pytest.fixture
def mock_args(temp_ledger_dir):
    """Create mock CLI args."""
    class Args:
        def __init__(self):
            self.ledger_dir = str(temp_ledger_dir)
            self.due_only = True
    return Args()


def create_forecast(ledger_dir: Path, event_id: str, target_date: datetime, horizon_days: int = 7):
    """Helper to create a test forecast record."""
    target_str = target_date.strftime("%Y%m%d")
    forecast_id = f"fcst_{target_str}_RUN_TEST_{event_id}_{horizon_days}d"

    record = {
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": horizon_days,
        "target_date_utc": target_date.isoformat(),
        "as_of_utc": (target_date - timedelta(days=horizon_days)).isoformat(),
        "probabilities": {"YES": 0.6, "NO": 0.4},
        "abstain": False,
    }
    ledger.append_forecast(record, ledger_dir)
    return forecast_id


def create_resolution(ledger_dir: Path, forecast_id: str, event_id: str, outcome: str = "YES"):
    """Helper to create a test resolution record."""
    record = {
        "resolution_id": f"res_{forecast_id}",
        "forecast_id": forecast_id,
        "event_id": event_id,
        "resolved_outcome": outcome,
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolution_mode": "external_auto",
        "reason_code": "test",
        "evidence_refs": [],
        "evidence_hashes": [],
    }
    ledger.append_resolution(record, ledger_dir)


class TestQueueCommand:
    """Tests for the queue CLI command."""

    def test_queue_empty_ledger(self, mock_args, capsys):
        """Test queue with no forecasts."""
        result = cmd_queue(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "No forecasts due" in captured.out

    def test_queue_shows_due_forecasts(self, mock_args, temp_ledger_dir, capsys):
        """Test queue shows forecasts past target date."""
        # Create a forecast due yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        create_forecast(temp_ledger_dir, "econ.rial_ge_1_2m", yesterday)

        result = cmd_queue(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "econ.rial_ge_1_2m" in captured.out
        assert "1d" in captured.out  # 1 day overdue

    def test_queue_excludes_future_forecasts(self, mock_args, temp_ledger_dir, capsys):
        """Test queue excludes forecasts not yet due."""
        # Create a forecast due tomorrow
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        create_forecast(temp_ledger_dir, "econ.rial_ge_1_2m", tomorrow)

        result = cmd_queue(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "No forecasts due" in captured.out

    def test_queue_excludes_resolved_forecasts(self, mock_args, temp_ledger_dir, capsys):
        """Test queue excludes already resolved forecasts."""
        # Create a forecast due yesterday
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        forecast_id = create_forecast(temp_ledger_dir, "econ.rial_ge_1_2m", yesterday)

        # Resolve it
        create_resolution(temp_ledger_dir, forecast_id, "econ.rial_ge_1_2m")

        result = cmd_queue(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "No forecasts due" in captured.out

    def test_queue_counts_overdue_days(self, mock_args, temp_ledger_dir, capsys):
        """Test queue shows correct overdue days."""
        # Create a forecast due 5 days ago
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)
        create_forecast(temp_ledger_dir, "econ.rial_ge_1_2m", five_days_ago)

        result = cmd_queue(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "5d" in captured.out

    def test_queue_multiple_forecasts(self, mock_args, temp_ledger_dir, capsys):
        """Test queue with multiple due forecasts."""
        # Create multiple forecasts at different times
        for i in range(3):
            past_date = datetime.now(timezone.utc) - timedelta(days=i+1)
            create_forecast(temp_ledger_dir, f"test.event_{i}", past_date)

        result = cmd_queue(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "awaiting resolution: 3" in captured.out

    def test_queue_sorted_by_overdue(self, mock_args, temp_ledger_dir, capsys):
        """Test queue sorts by most overdue first."""
        # Create forecasts with different overdue times
        one_day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        five_days_ago = datetime.now(timezone.utc) - timedelta(days=5)

        create_forecast(temp_ledger_dir, "test.event_recent", one_day_ago)
        create_forecast(temp_ledger_dir, "test.event_old", five_days_ago)

        result = cmd_queue(mock_args)

        assert result == 0
        captured = capsys.readouterr()

        # Most overdue should appear first
        old_pos = captured.out.find("test.event_old")
        recent_pos = captured.out.find("test.event_recent")
        assert old_pos < recent_pos

    def test_queue_shows_horizon_days(self, mock_args, temp_ledger_dir, capsys):
        """Test queue shows horizon days."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        create_forecast(temp_ledger_dir, "econ.rial_ge_1_2m", yesterday, horizon_days=15)

        result = cmd_queue(mock_args)

        assert result == 0
        captured = capsys.readouterr()
        assert "15" in captured.out


class TestQueuePendingLogic:
    """Tests for pending forecast logic used by queue."""

    def test_pending_excludes_resolved(self, temp_ledger_dir):
        """Test that get_pending_forecasts excludes resolved."""
        # Create forecast
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        forecast_id = create_forecast(temp_ledger_dir, "econ.rial_ge_1_2m", yesterday)

        # Check pending before resolution
        pending = ledger.get_pending_forecasts(temp_ledger_dir)
        assert len(pending) == 1

        # Resolve
        create_resolution(temp_ledger_dir, forecast_id, "econ.rial_ge_1_2m")

        # Check pending after resolution
        pending = ledger.get_pending_forecasts(temp_ledger_dir)
        assert len(pending) == 0

    def test_pending_includes_unknown_resolutions(self, temp_ledger_dir):
        """Test that UNKNOWN resolutions are not pending (they are resolved)."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        forecast_id = create_forecast(temp_ledger_dir, "econ.rial_ge_1_2m", yesterday)

        # Resolve with UNKNOWN
        create_resolution(temp_ledger_dir, forecast_id, "econ.rial_ge_1_2m", outcome="UNKNOWN")

        # Should not be in pending (it has a resolution)
        pending = ledger.get_pending_forecasts(temp_ledger_dir)
        assert len(pending) == 0

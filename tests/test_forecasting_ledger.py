"""
Tests for src/forecasting/ledger.py - Append-only JSONL ledger.
"""

import json
import pytest
import tempfile
from pathlib import Path

from src.forecasting import ledger
from src.forecasting.ledger import LedgerError


@pytest.fixture
def temp_ledger_dir():
    """Create a temporary ledger directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestAppendRecord:
    """Tests for append_record function."""

    def test_append_record_creates_file(self, temp_ledger_dir):
        """Test that append_record creates file if it doesn't exist."""
        file_path = temp_ledger_dir / "test.jsonl"
        record = {"id": "test_1", "value": 42}

        ledger.append_record(file_path, record)

        assert file_path.exists()
        with open(file_path) as f:
            lines = f.readlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["id"] == "test_1"

    def test_append_record_appends_to_existing(self, temp_ledger_dir):
        """Test that append_record appends to existing file."""
        file_path = temp_ledger_dir / "test.jsonl"

        ledger.append_record(file_path, {"id": "record_1"})
        ledger.append_record(file_path, {"id": "record_2"})
        ledger.append_record(file_path, {"id": "record_3"})

        with open(file_path) as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_append_record_json_serialization(self, temp_ledger_dir):
        """Test that records are properly JSON serialized."""
        file_path = temp_ledger_dir / "test.jsonl"
        record = {
            "string": "test",
            "number": 3.14159,
            "boolean": True,
            "null": None,
            "list": [1, 2, 3],
            "nested": {"a": 1}
        }

        ledger.append_record(file_path, record)

        with open(file_path) as f:
            loaded = json.loads(f.readline())
        assert loaded == record


class TestReadRecords:
    """Tests for read_records function."""

    def test_read_records_empty_file(self, temp_ledger_dir):
        """Test reading from non-existent file returns empty list."""
        file_path = temp_ledger_dir / "nonexistent.jsonl"
        records = ledger.read_records(file_path)

        assert records == []

    def test_read_records_all(self, temp_ledger_dir):
        """Test reading all records."""
        file_path = temp_ledger_dir / "test.jsonl"

        for i in range(5):
            ledger.append_record(file_path, {"id": f"record_{i}"})

        records = ledger.read_records(file_path)
        assert len(records) == 5

    def test_read_records_with_filter(self, temp_ledger_dir):
        """Test reading records with filter function."""
        file_path = temp_ledger_dir / "test.jsonl"

        ledger.append_record(file_path, {"type": "A", "value": 1})
        ledger.append_record(file_path, {"type": "B", "value": 2})
        ledger.append_record(file_path, {"type": "A", "value": 3})

        records = ledger.read_records(file_path, lambda r: r.get("type") == "A")
        assert len(records) == 2
        assert all(r["type"] == "A" for r in records)


class TestForecastRecords:
    """Tests for forecast-specific ledger functions."""

    def test_append_and_get_forecast(self, temp_ledger_dir):
        """Test appending and retrieving forecasts."""
        forecast = {
            "forecast_id": "fcst_20260115_TEST_econ.rial_ge_1_2m_7d",
            "event_id": "econ.rial_ge_1_2m",
            "run_id": "TEST_RUN",
            "probabilities": {"YES": 0.8, "NO": 0.2}
        }

        ledger.append_forecast(forecast, temp_ledger_dir)
        forecasts = ledger.get_forecasts(temp_ledger_dir)

        assert len(forecasts) == 1
        assert forecasts[0]["forecast_id"] == forecast["forecast_id"]
        assert forecasts[0]["record_type"] == "forecast"

    def test_get_forecasts_with_event_filter(self, temp_ledger_dir):
        """Test filtering forecasts by event_id."""
        ledger.append_forecast({
            "forecast_id": "fcst_1",
            "event_id": "econ.rial_ge_1_2m",
            "run_id": "TEST"
        }, temp_ledger_dir)
        ledger.append_forecast({
            "forecast_id": "fcst_2",
            "event_id": "econ.inflation_ge_50",
            "run_id": "TEST"
        }, temp_ledger_dir)

        forecasts = ledger.get_forecasts(temp_ledger_dir, event_id="econ.rial_ge_1_2m")
        assert len(forecasts) == 1
        assert forecasts[0]["event_id"] == "econ.rial_ge_1_2m"


class TestResolutionRecords:
    """Tests for resolution-specific ledger functions."""

    def test_append_and_get_resolution(self, temp_ledger_dir):
        """Test appending and retrieving resolutions."""
        resolution = {
            "resolution_id": "res_20260122_econ.rial_ge_1_2m_7d",
            "forecast_id": "fcst_20260115_TEST_econ.rial_ge_1_2m_7d",
            "event_id": "econ.rial_ge_1_2m",
            "resolved_outcome": "YES"
        }

        ledger.append_resolution(resolution, temp_ledger_dir)
        resolutions = ledger.get_resolutions(temp_ledger_dir)

        assert len(resolutions) == 1
        assert resolutions[0]["resolved_outcome"] == "YES"
        assert resolutions[0]["record_type"] == "resolution"


class TestPendingForecasts:
    """Tests for pending forecast tracking."""

    def test_get_pending_forecasts(self, temp_ledger_dir):
        """Test getting forecasts that haven't been resolved."""
        # Add forecasts
        ledger.append_forecast({
            "forecast_id": "fcst_1",
            "event_id": "event_1"
        }, temp_ledger_dir)
        ledger.append_forecast({
            "forecast_id": "fcst_2",
            "event_id": "event_2"
        }, temp_ledger_dir)
        ledger.append_forecast({
            "forecast_id": "fcst_3",
            "event_id": "event_3"
        }, temp_ledger_dir)

        # Resolve one
        ledger.append_resolution({
            "resolution_id": "res_1",
            "forecast_id": "fcst_2",
            "event_id": "event_2",
            "resolved_outcome": "YES"
        }, temp_ledger_dir)

        pending = ledger.get_pending_forecasts(temp_ledger_dir)
        assert len(pending) == 2
        pending_ids = {p["forecast_id"] for p in pending}
        assert "fcst_1" in pending_ids
        assert "fcst_3" in pending_ids
        assert "fcst_2" not in pending_ids


class TestGetById:
    """Tests for getting records by ID."""

    def test_get_forecast_by_id(self, temp_ledger_dir):
        """Test retrieving specific forecast by ID."""
        ledger.append_forecast({
            "forecast_id": "fcst_target",
            "event_id": "test"
        }, temp_ledger_dir)
        ledger.append_forecast({
            "forecast_id": "fcst_other",
            "event_id": "test"
        }, temp_ledger_dir)

        result = ledger.get_forecast_by_id("fcst_target", temp_ledger_dir)
        assert result is not None
        assert result["forecast_id"] == "fcst_target"

    def test_get_forecast_by_id_not_found(self, temp_ledger_dir):
        """Test returning None for non-existent forecast."""
        result = ledger.get_forecast_by_id("nonexistent", temp_ledger_dir)
        assert result is None

    def test_get_resolution_by_forecast_id(self, temp_ledger_dir):
        """Test retrieving resolution for a forecast."""
        ledger.append_resolution({
            "resolution_id": "res_1",
            "forecast_id": "fcst_target",
            "resolved_outcome": "NO"
        }, temp_ledger_dir)

        result = ledger.get_resolution_by_forecast_id("fcst_target", temp_ledger_dir)
        assert result is not None
        assert result["resolved_outcome"] == "NO"

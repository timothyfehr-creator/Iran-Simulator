"""
Integration tests for baseline forecaster generation.
"""

import json
import pytest
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.forecasting import forecast
from src.forecasting import ledger
from src.forecasting import baseline_history


@pytest.fixture
def temp_ledger_dir():
    """Create a temporary ledger directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_run_dir():
    """Create a temporary run directory with required artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = Path(tmpdir) / "RUN_20260120_test"
        run_dir.mkdir(parents=True)

        # Create run_manifest.json
        manifest = {
            "run_id": "RUN_20260120_test",
            "data_cutoff_utc": "2026-01-20T00:00:00Z",
            "seed": 42,
            "hashes": {}
        }
        with open(run_dir / "run_manifest.json", "w") as f:
            json.dump(manifest, f)

        # Create compiled_intel.json
        intel = {"current_state": {}}
        with open(run_dir / "compiled_intel.json", "w") as f:
            json.dump(intel, f)

        # Create simulation_results.json
        simulation = {"n_runs": 1000}
        with open(run_dir / "simulation_results.json", "w") as f:
            json.dump(simulation, f)

        yield run_dir


@pytest.fixture
def basic_event():
    """Basic binary event definition."""
    return {
        "event_id": "test.binary_event",
        "name": "Test Binary Event",
        "event_type": "binary",
        "allowed_outcomes": ["YES", "NO", "UNKNOWN"],
        "enabled": True,
        "horizons_days": [7],
        "forecast_source": {
            "type": "baseline_climatology"
        }
    }


@pytest.fixture
def categorical_event():
    """Categorical event definition."""
    return {
        "event_id": "test.categorical_event",
        "name": "Test Categorical Event",
        "event_type": "categorical",
        "allowed_outcomes": ["A", "B", "C", "D", "UNKNOWN"],
        "enabled": True,
        "horizons_days": [7],
        "forecast_source": {
            "type": "baseline_persistence"
        }
    }


def make_resolution(
    event_id: str,
    horizon_days: int,
    outcome: str,
    resolved_at: datetime,
    mode: str = "external_auto"
) -> dict:
    """Helper to create a resolution record."""
    ts = int(resolved_at.timestamp())
    return {
        "record_type": "resolution",
        "resolution_id": f"res_{event_id}_{horizon_days}_{ts}",
        "forecast_id": f"fcst_{event_id}_{horizon_days}_{ts}",
        "event_id": event_id,
        "horizon_days": horizon_days,
        "resolved_outcome": outcome,
        "resolved_at_utc": resolved_at.isoformat(),
        "resolution_mode": mode,
        "resolved_by": "test"
    }


class TestForecastGeneration:
    """Tests for baseline forecast generation integration."""

    def test_climatology_uses_history(self, temp_ledger_dir, temp_run_dir, basic_event):
        """Climatology baseline uses historical data when available."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add enough history (30 YES, 20 NO)
        for i in range(30):
            res = make_resolution(
                "test.binary_event", 7, "YES",
                as_of_utc - timedelta(days=i + 1)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        for i in range(20):
            res = make_resolution(
                "test.binary_event", 7, "NO",
                as_of_utc - timedelta(days=i + 31)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        # Build history index
        config = baseline_history.load_baseline_config()
        config["defaults"]["min_history_n"] = 10  # Lower threshold for test
        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)

        # Generate forecast
        artifacts = forecast.load_run_artifacts(temp_run_dir)
        record = forecast.generate_baseline_forecast_record(
            basic_event, temp_run_dir, artifacts, 7, as_of_utc,
            "baseline_climatology",
            history_index=index,
            baseline_config=config
        )

        # Verify distribution reflects history (30 YES, 20 NO)
        probs = record["probabilities"]
        assert abs(sum(probs.values()) - 1.0) < 1e-6
        assert probs["YES"] > probs["NO"]  # 60% vs 40% expected

        # Verify metadata
        assert record["baseline_history_n"] == 50
        assert record["baseline_fallback"] is None

    def test_persistence_uses_history(self, temp_ledger_dir, temp_run_dir, categorical_event):
        """Persistence baseline uses last outcome with stickiness."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add history with recent "B" outcome
        for i, outcome in enumerate(["A", "B", "C", "B"]):  # Last is B
            res = make_resolution(
                "test.categorical_event", 7, outcome,
                as_of_utc - timedelta(days=(4 - i))  # Most recent last
            )
            ledger.append_resolution(res, temp_ledger_dir)

        # Build history index
        config = baseline_history.load_baseline_config()
        config["defaults"]["min_history_n"] = 2
        config["defaults"]["persistence_stickiness"] = 0.7
        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)

        # Generate forecast
        artifacts = forecast.load_run_artifacts(temp_run_dir)
        record = forecast.generate_baseline_forecast_record(
            categorical_event, temp_run_dir, artifacts, 7, as_of_utc,
            "baseline_persistence",
            history_index=index,
            baseline_config=config
        )

        # Verify B has highest probability due to recency
        probs = record["probabilities"]
        assert abs(sum(probs.values()) - 1.0) < 1e-6
        assert probs["B"] > probs["A"]
        assert probs["B"] > probs["C"]
        assert probs["B"] > probs["D"]

        # Verify metadata
        assert record["baseline_history_n"] == 4
        assert record["baseline_staleness_days"] is not None

    def test_metadata_fields_populated(self, temp_ledger_dir, temp_run_dir, basic_event):
        """Baseline metadata fields are populated correctly."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add some history
        for i in range(10):
            res = make_resolution(
                "test.binary_event", 7, "YES" if i % 2 == 0 else "NO",
                as_of_utc - timedelta(days=i + 1)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        config = baseline_history.load_baseline_config()
        config["defaults"]["min_history_n"] = 5
        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)

        artifacts = forecast.load_run_artifacts(temp_run_dir)
        record = forecast.generate_baseline_forecast_record(
            basic_event, temp_run_dir, artifacts, 7, as_of_utc,
            "baseline_climatology",
            history_index=index,
            baseline_config=config
        )

        # Check all metadata fields exist
        assert "baseline_history_n" in record
        assert "baseline_fallback" in record
        assert "baseline_config_version" in record
        assert "baseline_resolution_modes" in record
        assert "baseline_excluded_counts_by_reason" in record

        # Check values
        assert record["baseline_history_n"] == 10
        assert record["baseline_config_version"] == "1.0.0"
        assert "external_auto" in record["baseline_resolution_modes"]

    def test_fallback_flagged_when_insufficient(self, temp_ledger_dir, temp_run_dir, basic_event):
        """Uniform fallback is flagged when history insufficient."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add minimal history (below threshold)
        for i in range(3):
            res = make_resolution(
                "test.binary_event", 7, "YES",
                as_of_utc - timedelta(days=i + 1)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        config = baseline_history.load_baseline_config()
        config["defaults"]["min_history_n"] = 10  # Higher than we have
        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)

        artifacts = forecast.load_run_artifacts(temp_run_dir)
        record = forecast.generate_baseline_forecast_record(
            basic_event, temp_run_dir, artifacts, 7, as_of_utc,
            "baseline_climatology",
            history_index=index,
            baseline_config=config
        )

        # Should be uniform fallback
        probs = record["probabilities"]
        assert abs(probs["YES"] - 0.5) < 1e-6
        assert abs(probs["NO"] - 0.5) < 1e-6

        # Fallback should be flagged
        assert record["baseline_fallback"] == "uniform"

    def test_no_history_index_falls_back(self, temp_run_dir, basic_event):
        """When no history index provided, falls back to uniform."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        artifacts = forecast.load_run_artifacts(temp_run_dir)
        record = forecast.generate_baseline_forecast_record(
            basic_event, temp_run_dir, artifacts, 7, as_of_utc,
            "baseline_climatology",
            history_index=None,
            baseline_config=None
        )

        # Should be uniform
        probs = record["probabilities"]
        assert abs(probs["YES"] - 0.5) < 1e-6
        assert abs(probs["NO"] - 0.5) < 1e-6

        # Metadata should indicate fallback
        assert record["baseline_fallback"] == "uniform"
        assert record["baseline_history_n"] == 0


class TestScoringAlignment:
    """Tests ensuring scorer uses same logic as forecaster."""

    def test_scorer_matches_forecaster_logic(self, temp_ledger_dir, basic_event):
        """Scorer and forecaster produce identical climatology."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add history
        outcomes = ["YES"] * 30 + ["NO"] * 20
        for i, outcome in enumerate(outcomes):
            res = make_resolution(
                "test.binary_event", 7, outcome,
                as_of_utc - timedelta(days=i + 1)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        # Build index with same config
        config = baseline_history.load_baseline_config()
        config["defaults"]["min_history_n"] = 5
        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)

        # Get entry and compute climatology
        entry = index.get_entry("test.binary_event", 7)
        assert entry is not None

        event_config = baseline_history.get_event_config(
            "test.binary_event", config["defaults"], config["overrides"]
        )
        probs, _ = baseline_history.compute_climatology_distribution(
            entry, ["YES", "NO"], event_config
        )

        # Verify distribution
        assert probs["YES"] > 0.5  # More YES than NO
        assert probs["NO"] < 0.5
        assert abs(sum(probs.values()) - 1.0) < 1e-6


class TestDistributionValidation:
    """Tests that generated distributions pass validation."""

    def test_climatology_passes_validation(self, temp_ledger_dir, basic_event):
        """Climatology distribution passes forecast validation."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add history
        for i in range(25):
            res = make_resolution(
                "test.binary_event", 7, "YES" if i % 3 != 0 else "NO",
                as_of_utc - timedelta(days=i + 1)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        config = baseline_history.load_baseline_config()
        config["defaults"]["min_history_n"] = 5
        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)
        entry = index.get_entry("test.binary_event", 7)

        event_config = baseline_history.get_event_config(
            "test.binary_event", config["defaults"], config["overrides"]
        )
        probs, _ = baseline_history.compute_climatology_distribution(
            entry, ["YES", "NO"], event_config
        )

        # Validate using forecast validation
        errors = forecast.validate_distribution(probs, basic_event)
        assert errors == []

    def test_persistence_passes_validation(self, temp_ledger_dir, categorical_event):
        """Persistence distribution passes forecast validation."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add history
        for i, outcome in enumerate(["A", "B", "C", "D", "B", "A"]):
            res = make_resolution(
                "test.categorical_event", 7, outcome,
                as_of_utc - timedelta(days=i + 1)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        config = baseline_history.load_baseline_config()
        config["defaults"]["min_history_n"] = 3
        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)
        entry = index.get_entry("test.categorical_event", 7)

        event_config = baseline_history.get_event_config(
            "test.categorical_event", config["defaults"], config["overrides"]
        )
        probs, _ = baseline_history.compute_persistence_distribution(
            entry, ["A", "B", "C", "D"], event_config
        )

        # Validate using forecast validation
        errors = forecast.validate_distribution(probs, categorical_event)
        assert errors == []

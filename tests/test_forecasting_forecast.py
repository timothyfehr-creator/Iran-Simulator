"""
Tests for src/forecasting/forecast.py - Forecast generation.
"""

import json
import math
import pytest
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.forecasting import forecast
from src.forecasting.forecast import ForecastError


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "forecasting"


@pytest.fixture
def temp_runs_dir():
    """Create a temporary runs directory with test fixtures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runs_dir = Path(tmpdir)
        test_run = runs_dir / "RUN_20260115_test"
        test_run.mkdir(parents=True)

        # Copy fixtures (including priors_resolved.json for simulation mode)
        for filename in ["run_manifest.json", "compiled_intel.json",
                         "simulation_results.json", "coverage_report.json",
                         "priors_resolved.json"]:
            src = FIXTURES_DIR / filename
            if src.exists():
                shutil.copy(src, test_run / filename)

        yield runs_dir


@pytest.fixture
def temp_ledger_dir():
    """Create a temporary ledger directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestHazardRateConversion:
    """Tests for hazard rate probability conversion."""

    def test_hazard_rate_zero_probability(self):
        """Test conversion of zero probability."""
        result = forecast.hazard_rate_conversion(0.0, 7)
        assert result == 0.0

    def test_hazard_rate_full_probability(self):
        """Test conversion of 100% probability."""
        result = forecast.hazard_rate_conversion(1.0, 7)
        assert result == 1.0

    def test_hazard_rate_90_day_identity(self):
        """Test that 90-day horizon returns same probability."""
        result = forecast.hazard_rate_conversion(0.5, 90)
        assert abs(result - 0.5) < 1e-6

    def test_hazard_rate_shorter_horizon_lower(self):
        """Test that shorter horizons have lower probabilities."""
        p_90 = 0.5

        p_7 = forecast.hazard_rate_conversion(p_90, 7)
        p_30 = forecast.hazard_rate_conversion(p_90, 30)

        assert p_7 < p_30 < p_90

    def test_hazard_rate_known_values(self):
        """Test against known computed values."""
        # P_h = 1 - (1 - 0.08)^(h/90)
        p_90 = 0.08

        p_7 = forecast.hazard_rate_conversion(p_90, 7)
        # 1 - 0.92^(7/90) ≈ 0.00647
        expected_p_7 = 1 - math.pow(0.92, 7/90)
        assert abs(p_7 - expected_p_7) < 1e-6

        p_30 = forecast.hazard_rate_conversion(p_90, 30)
        expected_p_30 = 1 - math.pow(0.92, 30/90)
        assert abs(p_30 - expected_p_30) < 1e-6


class TestSelectValidRun:
    """Tests for run selection logic."""

    def test_select_valid_run_success(self, temp_runs_dir):
        """Test selecting a valid run."""
        run_dir = forecast.select_valid_run(temp_runs_dir, require_simulation=True)

        assert run_dir is not None
        assert run_dir.name == "RUN_20260115_test"

    def test_select_valid_run_no_runs(self):
        """Test returning None when no valid runs exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = forecast.select_valid_run(Path(tmpdir))
            assert run_dir is None

    def test_select_valid_run_skips_unreliable(self, temp_runs_dir):
        """Test that unreliable runs are skipped."""
        # Modify manifest to mark run as unreliable
        manifest_path = temp_runs_dir / "RUN_20260115_test" / "run_manifest.json"
        with open(manifest_path) as f:
            manifest = json.load(f)
        manifest["run_reliable"] = False
        manifest["unreliable_reason"] = "Test unreliable"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

        run_dir = forecast.select_valid_run(temp_runs_dir)
        assert run_dir is None


class TestLoadRunArtifacts:
    """Tests for loading run artifacts."""

    def test_load_run_artifacts_success(self, temp_runs_dir):
        """Test loading artifacts from a run."""
        run_dir = temp_runs_dir / "RUN_20260115_test"
        artifacts = forecast.load_run_artifacts(run_dir)

        assert "manifest" in artifacts
        assert "intel" in artifacts
        assert "simulation" in artifacts

    def test_load_run_artifacts_missing_manifest(self, temp_runs_dir):
        """Test error when manifest is missing."""
        run_dir = temp_runs_dir / "RUN_20260115_test"
        (run_dir / "run_manifest.json").unlink()

        with pytest.raises(ForecastError, match="manifest"):
            forecast.load_run_artifacts(run_dir)


class TestExtractNestedValue:
    """Tests for nested dictionary value extraction."""

    def test_extract_nested_value_simple(self):
        """Test extracting simple nested value."""
        data = {"a": {"b": {"c": 42}}}
        result = forecast.extract_nested_value(data, "a.b.c")
        assert result == 42

    def test_extract_nested_value_top_level(self):
        """Test extracting top-level value."""
        data = {"key": "value"}
        result = forecast.extract_nested_value(data, "key")
        assert result == "value"

    def test_extract_nested_value_missing(self):
        """Test returning None for missing path."""
        data = {"a": {"b": 1}}
        result = forecast.extract_nested_value(data, "a.c.d")
        assert result is None


class TestGenerateForecastId:
    """Tests for forecast ID generation."""

    def test_generate_forecast_id_format(self):
        """Test forecast ID format."""
        forecast_id = forecast.generate_forecast_id(
            "20260115", "RUN_20260114_daily", "econ.rial_ge_1_2m", 7
        )

        assert forecast_id == "fcst_20260115_RUN_20260114_daily_econ.rial_ge_1_2m_7d"


class TestGenerateForecasts:
    """Tests for complete forecast generation."""

    def test_generate_forecasts_success(self, temp_runs_dir, temp_ledger_dir):
        """Test generating forecasts from a run."""
        records = forecast.generate_forecasts(
            catalog_path=Path("config/event_catalog.json"),
            runs_dir=temp_runs_dir,
            horizons=[7],
            ledger_dir=temp_ledger_dir,
            dry_run=True
        )

        # Should generate one forecast per event per horizon
        assert len(records) == 5  # 5 events, 1 horizon

        # Check record structure
        for r in records:
            assert "forecast_id" in r
            assert "event_id" in r
            assert "horizon_days" in r
            assert "probabilities" in r

            # Binary events should have YES + NO = 1.0
            probs = r["probabilities"]
            assert abs(probs.get("YES", 0) + probs.get("NO", 0) - 1.0) < 1e-6

    def test_generate_forecasts_multiple_horizons(self, temp_runs_dir, temp_ledger_dir):
        """Test generating forecasts for multiple horizons."""
        records = forecast.generate_forecasts(
            catalog_path=Path("config/event_catalog.json"),
            runs_dir=temp_runs_dir,
            horizons=[1, 7, 30],
            ledger_dir=temp_ledger_dir,
            dry_run=True
        )

        # 5 events × 3 horizons = 15 forecasts
        assert len(records) == 15

    def test_generate_forecasts_diagnostic_abstain(self, temp_runs_dir, temp_ledger_dir):
        """Test that diagnostic events result in abstained forecasts."""
        records = forecast.generate_forecasts(
            catalog_path=Path("config/event_catalog.json"),
            runs_dir=temp_runs_dir,
            horizons=[7],
            ledger_dir=temp_ledger_dir,
            dry_run=True
        )

        # Find diagnostic events (state.internet_degraded, state.protests_escalating)
        diagnostic_forecasts = [
            r for r in records
            if r["event_id"].startswith("state.")
        ]

        assert len(diagnostic_forecasts) == 2
        for f in diagnostic_forecasts:
            assert f["abstain"] is True
            assert f["abstain_reason"] == "diagnostic_only"

    def test_generate_forecasts_invalid_horizon(self, temp_runs_dir, temp_ledger_dir):
        """Test error for invalid horizon."""
        with pytest.raises(ForecastError, match="Invalid horizons"):
            forecast.generate_forecasts(
                catalog_path=Path("config/event_catalog.json"),
                runs_dir=temp_runs_dir,
                horizons=[14],  # Invalid - not in {1, 7, 15, 30}
                ledger_dir=temp_ledger_dir,
                dry_run=True
            )

    def test_generate_forecasts_writes_to_ledger(self, temp_runs_dir, temp_ledger_dir):
        """Test that forecasts are written to ledger when not dry_run."""
        forecast.generate_forecasts(
            catalog_path=Path("config/event_catalog.json"),
            runs_dir=temp_runs_dir,
            horizons=[7],
            ledger_dir=temp_ledger_dir,
            dry_run=False
        )

        # Verify ledger file exists and has content
        ledger_file = temp_ledger_dir / "forecasts.jsonl"
        assert ledger_file.exists()

        with open(ledger_file) as f:
            lines = f.readlines()
        assert len(lines) == 5


class TestForecastDeterminism:
    """Tests for forecast generation determinism."""

    def test_forecast_determinism(self, temp_runs_dir):
        """Test that same inputs produce identical forecasts."""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                records1 = forecast.generate_forecasts(
                    catalog_path=Path("config/event_catalog.json"),
                    runs_dir=temp_runs_dir,
                    horizons=[7],
                    ledger_dir=Path(tmpdir1),
                    dry_run=True
                )

                records2 = forecast.generate_forecasts(
                    catalog_path=Path("config/event_catalog.json"),
                    runs_dir=temp_runs_dir,
                    horizons=[7],
                    ledger_dir=Path(tmpdir2),
                    dry_run=True
                )

                # Compare non-timestamp fields
                for r1, r2 in zip(records1, records2):
                    assert r1["forecast_id"] == r2["forecast_id"]
                    assert r1["event_id"] == r2["event_id"]
                    assert r1["probabilities"] == r2["probabilities"]
                    assert r1["run_id"] == r2["run_id"]

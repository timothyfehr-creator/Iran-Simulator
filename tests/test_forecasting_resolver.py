"""
Tests for src/forecasting/resolver.py - Resolution logic.
"""

import json
import pytest
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.forecasting import resolver, ledger
from src.forecasting.resolver import ResolutionError


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "forecasting"


@pytest.fixture
def temp_runs_dir():
    """Create a temporary runs directory with test fixtures."""
    with tempfile.TemporaryDirectory() as tmpdir:
        runs_dir = Path(tmpdir)

        # Create a run at "day 0" (forecast source)
        run_day0 = runs_dir / "RUN_20260115_source"
        run_day0.mkdir(parents=True)
        for filename in ["run_manifest.json", "compiled_intel.json",
                         "simulation_results.json", "coverage_report.json"]:
            src = FIXTURES_DIR / filename
            if src.exists():
                shutil.copy(src, run_day0 / filename)

        # Also copy priors_resolved.json for simulation mode
        if (FIXTURES_DIR / "priors_resolved.json").exists():
            shutil.copy(FIXTURES_DIR / "priors_resolved.json", run_day0 / "priors_resolved.json")

        # Create a run at "day 7" (resolution source)
        run_day7 = runs_dir / "RUN_20260122_resolution"
        run_day7.mkdir(parents=True)

        # Copy and modify manifest for different cutoff date
        with open(FIXTURES_DIR / "run_manifest.json") as f:
            manifest = json.load(f)
        manifest["data_cutoff_utc"] = "2026-01-22T23:59:59+00:00"
        with open(run_day7 / "run_manifest.json", 'w') as f:
            json.dump(manifest, f)

        # Copy and modify intel with updated values
        with open(FIXTURES_DIR / "compiled_intel.json") as f:
            intel = json.load(f)
        # Update values to trigger resolutions
        intel["compiled_fields"]["current_state.economic_conditions.rial_usd_rate.market"] = 1250000
        intel["compiled_fields"]["current_state.information_environment.internet_status.current"] = "SEVERELY_DEGRADED"
        intel["current_state"]["economic_conditions"]["rial_usd_rate"]["market"] = 1250000
        with open(run_day7 / "compiled_intel.json", 'w') as f:
            json.dump(intel, f)

        shutil.copy(FIXTURES_DIR / "coverage_report.json", run_day7 / "coverage_report.json")

        yield runs_dir


@pytest.fixture
def temp_ledger_dir():
    """Create a temporary ledger directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestParseDatetime:
    """Tests for ISO datetime parsing."""

    def test_parse_iso_datetime_with_z(self):
        """Test parsing datetime with Z suffix."""
        dt = resolver.parse_iso_datetime("2026-01-15T12:00:00Z")
        assert dt.tzinfo is not None
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15

    def test_parse_iso_datetime_with_offset(self):
        """Test parsing datetime with timezone offset."""
        dt = resolver.parse_iso_datetime("2026-01-15T12:00:00+00:00")
        assert dt.tzinfo is not None

    def test_parse_iso_datetime_naive(self):
        """Test parsing naive datetime (no timezone)."""
        dt = resolver.parse_iso_datetime("2026-01-15T12:00:00")
        assert dt.tzinfo == timezone.utc


class TestFindResolutionRun:
    """Tests for finding resolution runs."""

    def test_find_resolution_run_success(self, temp_runs_dir):
        """Test finding a valid resolution run."""
        target_date = datetime(2026, 1, 22, 0, 0, 0, tzinfo=timezone.utc)

        run_dir = resolver.find_resolution_run(target_date, temp_runs_dir, max_lag_days=7)

        assert run_dir is not None
        assert "20260122" in run_dir.name

    def test_find_resolution_run_too_early(self, temp_runs_dir):
        """Test no run found when target is in future."""
        target_date = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

        run_dir = resolver.find_resolution_run(target_date, temp_runs_dir, max_lag_days=7)

        assert run_dir is None


class TestExtractCompiledValue:
    """Tests for extracting values from compiled intel."""

    def test_extract_from_compiled_fields(self):
        """Test extracting value from flat compiled_fields."""
        intel = {
            "compiled_fields": {
                "current_state.economic_conditions.rial_usd_rate.market": 1350000
            }
        }

        value, found = resolver.extract_compiled_value(
            intel, "current_state.economic_conditions.rial_usd_rate.market"
        )

        assert found is True
        assert value == 1350000

    def test_extract_from_nested_path(self):
        """Test extracting value from nested structure."""
        intel = {
            "current_state": {
                "economic_conditions": {
                    "rial_usd_rate": {"market": 1350000}
                }
            }
        }

        value, found = resolver.extract_compiled_value(
            intel, "current_state.economic_conditions.rial_usd_rate.market"
        )

        assert found is True
        assert value == 1350000

    def test_extract_missing_path(self):
        """Test extracting from non-existent path."""
        intel = {"something": "else"}

        value, found = resolver.extract_compiled_value(
            intel, "nonexistent.path.value"
        )

        assert found is False
        assert value is None


class TestApplyResolutionRule:
    """Tests for resolution rule application."""

    @pytest.fixture
    def dummy_event(self):
        """Minimal event definition for rule tests."""
        return {"event_id": "test.dummy", "allowed_outcomes": ["YES", "NO"]}

    def test_threshold_gte_yes(self, dummy_event):
        """Test threshold_gte rule resolving to YES."""
        outcome, reason = resolver.apply_resolution_rule(
            1500000, "threshold_gte", {"threshold": 1200000}, dummy_event
        )
        assert outcome == "YES"
        assert reason is None

    def test_threshold_gte_no(self, dummy_event):
        """Test threshold_gte rule resolving to NO."""
        outcome, reason = resolver.apply_resolution_rule(
            1000000, "threshold_gte", {"threshold": 1200000}, dummy_event
        )
        assert outcome == "NO"
        assert reason is None

    def test_threshold_gt_boundary(self, dummy_event):
        """Test threshold_gt at exact boundary."""
        outcome, reason = resolver.apply_resolution_rule(
            100, "threshold_gt", {"threshold": 100}, dummy_event
        )
        assert outcome == "NO"  # gt, not gte

    def test_enum_equals_yes(self, dummy_event):
        """Test enum_equals rule resolving to YES."""
        outcome, reason = resolver.apply_resolution_rule(
            "ESCALATING", "enum_equals", {"value": "ESCALATING"}, dummy_event
        )
        assert outcome == "YES"

    def test_enum_equals_case_insensitive(self, dummy_event):
        """Test enum_equals is case-insensitive."""
        outcome, reason = resolver.apply_resolution_rule(
            "escalating", "enum_equals", {"value": "ESCALATING"}, dummy_event
        )
        assert outcome == "YES"

    def test_enum_in_yes(self, dummy_event):
        """Test enum_in rule resolving to YES."""
        outcome, reason = resolver.apply_resolution_rule(
            "BLACKOUT", "enum_in", {"values": ["BLACKOUT", "SEVERELY_DEGRADED"]}, dummy_event
        )
        assert outcome == "YES"

    def test_enum_in_no(self, dummy_event):
        """Test enum_in rule resolving to NO."""
        outcome, reason = resolver.apply_resolution_rule(
            "PARTIAL", "enum_in", {"values": ["BLACKOUT", "SEVERELY_DEGRADED"]}, dummy_event
        )
        assert outcome == "NO"

    def test_missing_value(self, dummy_event):
        """Test UNKNOWN outcome for missing value."""
        outcome, reason = resolver.apply_resolution_rule(
            None, "threshold_gte", {"threshold": 100}, dummy_event
        )
        assert outcome == "UNKNOWN"
        assert reason == "missing_value"


class TestResolveEvent:
    """Tests for single event resolution."""

    def test_resolve_event_success(self, temp_runs_dir):
        """Test resolving an event with available data."""
        event = {
            "event_id": "econ.rial_ge_1_2m",
            "resolution_source": {
                "type": "compiled_intel",
                "path": "current_state.economic_conditions.rial_usd_rate.market",
                "rule": "threshold_gte",
                "threshold": 1200000
            }
        }
        forecast = {
            "forecast_id": "fcst_20260115_TEST_econ.rial_ge_1_2m_7d",
            "event_id": "econ.rial_ge_1_2m",
            "horizon_days": 7,
            "target_date_utc": "2026-01-22T00:00:00Z"
        }

        resolution_run = temp_runs_dir / "RUN_20260122_resolution"
        record = resolver.resolve_event(event, forecast, resolution_run)

        assert record["resolved_outcome"] == "YES"  # 1250000 >= 1200000
        assert record["forecast_id"] == forecast["forecast_id"]
        assert record["event_id"] == event["event_id"]

    def test_auto_resolve_missing_path_stays_external_auto(self, temp_runs_dir):
        """Test that auto_resolve + compiled_intel + missing path -> external_auto with UNKNOWN."""
        event = {
            "event_id": "test.missing_path",
            "auto_resolve": True,
            "resolution_source": {
                "type": "compiled_intel",
                "path": "nonexistent.path.that.does.not.exist",
                "rule": "threshold_gte",
                "threshold": 100
            }
        }
        forecast = {
            "forecast_id": "fcst_20260115_TEST_test.missing_path_7d",
            "event_id": "test.missing_path",
            "horizon_days": 7,
            "target_date_utc": "2026-01-22T00:00:00Z"
        }

        resolution_run = temp_runs_dir / "RUN_20260122_resolution"
        record = resolver.resolve_event(event, forecast, resolution_run)

        # Should stay external_auto even with missing path
        assert record["resolution_mode"] == "external_auto"
        assert record["resolved_outcome"] == "UNKNOWN"
        assert record["unknown_reason"] == "missing_path"
        # Evidence not written for UNKNOWN outcomes
        assert record["evidence_refs"] == []
        assert record["evidence_hashes"] == []

    def test_auto_resolve_claims_fallback_becomes_claims_inferred(self, temp_runs_dir):
        """Test that auto_resolve with claims_based fallback -> claims_inferred."""
        event = {
            "event_id": "test.claims_fallback",
            "auto_resolve": True,
            "resolution_source": {
                "type": "compiled_intel",
                "path": "nonexistent.path",
                "rule": "threshold_gte",
                "threshold": 100,
                "fallback": "claims_based"
            }
        }
        forecast = {
            "forecast_id": "fcst_20260115_TEST_test.claims_fallback_7d",
            "event_id": "test.claims_fallback",
            "horizon_days": 7,
            "target_date_utc": "2026-01-22T00:00:00Z"
        }

        resolution_run = temp_runs_dir / "RUN_20260122_resolution"
        record = resolver.resolve_event(event, forecast, resolution_run)

        # Should downgrade to claims_inferred because of explicit fallback
        assert record["resolution_mode"] == "claims_inferred"
        assert record["resolved_outcome"] == "UNKNOWN"
        assert record["unknown_reason"] == "requires_claims_resolution"


class TestResolvePending:
    """Tests for resolving all pending forecasts."""

    def test_resolve_pending_basic(self, temp_runs_dir, temp_ledger_dir):
        """Test resolving pending forecasts."""
        # Add a forecast with target date in the past (before the resolution run's cutoff)
        # Resolution run has cutoff 2026-01-22, target must be <= cutoff and in the past
        target_date = datetime(2026, 1, 15, 0, 0, 0, tzinfo=timezone.utc)
        ledger.append_forecast({
            "forecast_id": "fcst_20260108_TEST_econ.rial_ge_1_2m_7d",
            "event_id": "econ.rial_ge_1_2m",
            "horizon_days": 7,
            "target_date_utc": target_date.isoformat(),
            "probabilities": {"YES": 0.5, "NO": 0.5}
        }, temp_ledger_dir)

        records = resolver.resolve_pending(
            catalog_path=Path("config/event_catalog.json"),
            runs_dir=temp_runs_dir,
            ledger_dir=temp_ledger_dir,
            max_lag_days=14,
            dry_run=True
        )

        # Should resolve the forecast
        assert len(records) >= 1

    def test_resolve_pending_skips_future_targets(self, temp_runs_dir, temp_ledger_dir):
        """Test that future target dates are not resolved."""
        # Add a forecast with target date in the future
        future_date = datetime.now(timezone.utc) + timedelta(days=30)
        ledger.append_forecast({
            "forecast_id": "fcst_future",
            "event_id": "econ.rial_ge_1_2m",
            "horizon_days": 30,
            "target_date_utc": future_date.isoformat(),
            "probabilities": {"YES": 0.5, "NO": 0.5}
        }, temp_ledger_dir)

        records = resolver.resolve_pending(
            catalog_path=Path("config/event_catalog.json"),
            runs_dir=temp_runs_dir,
            ledger_dir=temp_ledger_dir,
            dry_run=True
        )

        # Should not resolve future forecast
        assert not any(r["forecast_id"] == "fcst_future" for r in records)

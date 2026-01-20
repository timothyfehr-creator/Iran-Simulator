"""
Tests for backward compatibility with old resolution records.

Validates that old resolutions without resolution_mode are treated as external_auto.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.forecasting import ledger
from src.forecasting.resolver import get_resolution_mode
from src.forecasting.scorer import compute_scores, compute_scores_for_mode


@pytest.fixture
def temp_ledger_dir(tmp_path):
    """Create a temporary ledger directory."""
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir()
    return ledger_dir


def create_forecast(ledger_dir: Path, forecast_id: str, event_id: str, p_yes: float = 0.6):
    """Helper to create a test forecast."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    record = {
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": 7,
        "target_date_utc": yesterday.isoformat(),
        "probabilities": {"YES": p_yes, "NO": 1 - p_yes},
        "abstain": False,
    }
    ledger.append_forecast(record, ledger_dir)


def create_legacy_resolution(ledger_dir: Path, forecast_id: str, event_id: str, outcome: str):
    """Helper to create a legacy resolution without resolution_mode."""
    record = {
        "resolution_id": f"res_{forecast_id}",
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": 7,
        "resolved_outcome": outcome,
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolved_by": "oracle_resolver_v1",
        # Note: NO resolution_mode field - legacy format
        "evidence": {
            "run_id": "RUN_TEST",
            "manifest_id": "sha256:test",
        },
    }
    ledger.append_resolution(record, ledger_dir)


def create_new_resolution(
    ledger_dir: Path,
    forecast_id: str,
    event_id: str,
    outcome: str,
    resolution_mode: str
):
    """Helper to create a new resolution with resolution_mode."""
    record = {
        "resolution_id": f"res_{forecast_id}",
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": 7,
        "resolved_outcome": outcome,
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolved_by": "oracle_resolver_v2",
        "resolution_mode": resolution_mode,
        "reason_code": "test",
        "evidence_refs": [],
        "evidence_hashes": [],
        "evidence": {},
    }
    ledger.append_resolution(record, ledger_dir)


class TestGetResolutionMode:
    """Tests for get_resolution_mode helper function."""

    def test_returns_mode_when_present(self):
        """Test that existing mode is returned."""
        resolution = {"resolution_mode": "claims_inferred"}
        assert get_resolution_mode(resolution) == "claims_inferred"

    def test_returns_external_auto_when_missing(self):
        """Test that missing mode defaults to external_auto."""
        resolution = {}
        assert get_resolution_mode(resolution) == "external_auto"

    def test_handles_all_valid_modes(self):
        """Test that all valid modes are returned correctly."""
        for mode in ["external_auto", "external_manual", "claims_inferred"]:
            resolution = {"resolution_mode": mode}
            assert get_resolution_mode(resolution) == mode


class TestLegacyResolutionScoring:
    """Tests for scoring legacy resolutions."""

    def test_legacy_counted_in_core_scores(self, temp_ledger_dir):
        """Test that legacy resolutions are counted in core_scores."""
        # Create forecast and legacy resolution
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.8)
        create_legacy_resolution(temp_ledger_dir, "f1", "test.event1", "YES")

        result = compute_scores(temp_ledger_dir)

        # Legacy should be in core_scores (treated as external_auto)
        assert result["core_scores"]["count"] == 1
        assert result["claims_inferred_scores"]["count"] == 0

    def test_legacy_brier_score_calculated(self, temp_ledger_dir):
        """Test that Brier score is calculated for legacy resolutions."""
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.9)
        create_legacy_resolution(temp_ledger_dir, "f1", "test.event1", "YES")

        result = compute_scores(temp_ledger_dir)

        # Should have valid Brier score: (0.9 - 1)^2 = 0.01
        assert result["core_scores"]["brier_score"] == pytest.approx(0.01)

    def test_mixed_legacy_and_new(self, temp_ledger_dir):
        """Test scoring with mix of legacy and new resolutions."""
        # Legacy resolution (external_auto by default)
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.8)
        create_legacy_resolution(temp_ledger_dir, "f1", "test.event1", "YES")

        # New external_auto resolution
        create_forecast(temp_ledger_dir, "f2", "test.event2", p_yes=0.8)
        create_new_resolution(temp_ledger_dir, "f2", "test.event2", "YES", "external_auto")

        # New claims_inferred resolution
        create_forecast(temp_ledger_dir, "f3", "test.event3", p_yes=0.8)
        create_new_resolution(temp_ledger_dir, "f3", "test.event3", "NO", "claims_inferred")

        result = compute_scores(temp_ledger_dir)

        # Legacy + new external_auto = 2 in core
        assert result["core_scores"]["count"] == 2
        # Only claims_inferred in that section
        assert result["claims_inferred_scores"]["count"] == 1
        # All three in combined
        assert result["combined_scores"]["count"] == 3


class TestComputeScoresForModeLegacy:
    """Tests for compute_scores_for_mode with legacy resolutions."""

    def test_legacy_included_in_external_auto_filter(self):
        """Test that legacy resolutions pass external_auto filter."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.8}, "abstain": False},
        ]
        # Legacy resolution without resolution_mode
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
        ]

        result = compute_scores_for_mode(forecasts, resolutions, ["external_auto"])

        assert result["count"] == 1

    def test_legacy_excluded_from_claims_inferred_filter(self):
        """Test that legacy resolutions are excluded from claims_inferred filter."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.8}, "abstain": False},
        ]
        # Legacy resolution without resolution_mode
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
        ]

        result = compute_scores_for_mode(forecasts, resolutions, ["claims_inferred"])

        assert result["count"] == 0


class TestLegacyResolutionCoverage:
    """Tests for coverage metrics with legacy resolutions."""

    def test_legacy_counted_in_coverage(self, temp_ledger_dir):
        """Test that legacy resolutions are counted in coverage metrics."""
        create_forecast(temp_ledger_dir, "f1", "test.event1")
        create_legacy_resolution(temp_ledger_dir, "f1", "test.event1", "YES")

        result = compute_scores(temp_ledger_dir)

        assert result["coverage"]["resolved_known"] == 1
        assert result["coverage"]["coverage_rate"] == 1.0

    def test_legacy_unknown_counted(self, temp_ledger_dir):
        """Test that legacy UNKNOWN resolutions are counted correctly."""
        create_forecast(temp_ledger_dir, "f1", "test.event1")
        create_legacy_resolution(temp_ledger_dir, "f1", "test.event1", "UNKNOWN")

        result = compute_scores(temp_ledger_dir)

        assert result["coverage"]["resolved_unknown"] == 1
        assert result["coverage"]["resolved_known"] == 0


class TestLegacyEffectiveBrier:
    """Tests for effective Brier score with legacy resolutions."""

    def test_legacy_included_in_effective_brier(self, temp_ledger_dir):
        """Test that legacy resolutions are included in effective Brier."""
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.7)
        create_legacy_resolution(temp_ledger_dir, "f1", "test.event1", "YES")

        result = compute_scores(temp_ledger_dir)

        # Effective Brier should be computed: (0.7 - 1)^2 = 0.09
        assert result["effective_brier"] == pytest.approx(0.09)

"""
Tests for scoring separation by resolution mode.

Validates that external_auto/external_manual scores are separated
from claims_inferred scores.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.forecasting import ledger
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


def create_resolution(
    ledger_dir: Path,
    forecast_id: str,
    event_id: str,
    outcome: str,
    resolution_mode: str
):
    """Helper to create a test resolution with specific mode."""
    record = {
        "resolution_id": f"res_{forecast_id}",
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": 7,
        "resolved_outcome": outcome,
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolution_mode": resolution_mode,
        "reason_code": "test",
        "evidence_refs": [],
        "evidence_hashes": [],
    }
    ledger.append_resolution(record, ledger_dir)


class TestComputeScoresForMode:
    """Tests for compute_scores_for_mode function."""

    def test_filter_by_mode(self):
        """Test filtering resolutions by mode."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.8}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.3}, "abstain": False},
            {"forecast_id": "f3", "probabilities": {"YES": 0.6}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
            {"forecast_id": "f2", "resolved_outcome": "NO", "resolution_mode": "claims_inferred"},
            {"forecast_id": "f3", "resolved_outcome": "YES", "resolution_mode": "external_manual"},
        ]

        # Filter for external modes only
        result = compute_scores_for_mode(forecasts, resolutions, ["external_auto", "external_manual"])

        assert result["count"] == 2  # f1 and f3

    def test_no_filter_includes_all(self):
        """Test that no filter includes all resolutions."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.8}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.3}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
            {"forecast_id": "f2", "resolved_outcome": "NO", "resolution_mode": "claims_inferred"},
        ]

        result = compute_scores_for_mode(forecasts, resolutions, None)

        assert result["count"] == 2

    def test_empty_mode_filter(self):
        """Test filtering with mode that has no matches."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.8}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
        ]

        result = compute_scores_for_mode(forecasts, resolutions, ["claims_inferred"])

        assert result["count"] == 0
        assert result["brier_score"] is None


class TestComputeScoresSeparation:
    """Tests for score separation in compute_scores."""

    def test_core_scores_excludes_claims_inferred(self, temp_ledger_dir):
        """Test that core_scores excludes claims_inferred."""
        # Create forecasts
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.8)
        create_forecast(temp_ledger_dir, "f2", "test.event2", p_yes=0.3)

        # Create resolutions with different modes
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "external_auto")
        create_resolution(temp_ledger_dir, "f2", "test.event2", "NO", "claims_inferred")

        result = compute_scores(temp_ledger_dir)

        assert result["core_scores"]["count"] == 1  # Only f1
        assert result["claims_inferred_scores"]["count"] == 1  # Only f2
        assert result["combined_scores"]["count"] == 2  # Both

    def test_core_scores_includes_external_manual(self, temp_ledger_dir):
        """Test that core_scores includes external_manual."""
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.8)
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "external_manual")

        result = compute_scores(temp_ledger_dir)

        assert result["core_scores"]["count"] == 1

    def test_separate_brier_scores(self, temp_ledger_dir):
        """Test that Brier scores are calculated separately."""
        # Good external_auto prediction
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.9)
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "external_auto")

        # Bad claims_inferred prediction
        create_forecast(temp_ledger_dir, "f2", "test.event2", p_yes=0.9)
        create_resolution(temp_ledger_dir, "f2", "test.event2", "NO", "claims_inferred")

        result = compute_scores(temp_ledger_dir)

        # Core should have low Brier (good prediction)
        core_brier = result["core_scores"]["brier_score"]
        # Claims inferred should have high Brier (bad prediction)
        claims_brier = result["claims_inferred_scores"]["brier_score"]

        assert core_brier < 0.1  # Good: (0.9 - 1)^2 = 0.01
        assert claims_brier > 0.5  # Bad: (0.9 - 0)^2 = 0.81

    def test_combined_is_average(self, temp_ledger_dir):
        """Test that combined scores include all resolutions."""
        # Create multiple forecasts
        for i in range(4):
            create_forecast(temp_ledger_dir, f"f{i}", f"test.event{i}", p_yes=0.5)
            mode = "external_auto" if i < 2 else "claims_inferred"
            create_resolution(temp_ledger_dir, f"f{i}", f"test.event{i}", "YES", mode)

        result = compute_scores(temp_ledger_dir)

        assert result["core_scores"]["count"] == 2
        assert result["claims_inferred_scores"]["count"] == 2
        assert result["combined_scores"]["count"] == 4

    def test_only_claims_inferred(self, temp_ledger_dir):
        """Test when all resolutions are claims_inferred."""
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.6)
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "claims_inferred")

        result = compute_scores(temp_ledger_dir)

        assert result["core_scores"]["count"] == 0
        assert result["core_scores"]["brier_score"] is None
        assert result["claims_inferred_scores"]["count"] == 1

    def test_only_external(self, temp_ledger_dir):
        """Test when all resolutions are external."""
        create_forecast(temp_ledger_dir, "f1", "test.event1", p_yes=0.6)
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "external_auto")

        result = compute_scores(temp_ledger_dir)

        assert result["core_scores"]["count"] == 1
        assert result["claims_inferred_scores"]["count"] == 0
        assert result["claims_inferred_scores"]["brier_score"] is None


class TestScoreOutputStructure:
    """Tests for score output structure."""

    def test_has_coverage_metrics(self, temp_ledger_dir):
        """Test that output includes coverage metrics."""
        create_forecast(temp_ledger_dir, "f1", "test.event1")
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "external_auto")

        result = compute_scores(temp_ledger_dir)

        assert "coverage" in result
        assert "forecasts_due" in result["coverage"]
        assert "coverage_rate" in result["coverage"]

    def test_has_effective_brier(self, temp_ledger_dir):
        """Test that output includes effective Brier score."""
        create_forecast(temp_ledger_dir, "f1", "test.event1")
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "external_auto")

        result = compute_scores(temp_ledger_dir)

        assert "effective_brier" in result

    def test_has_all_score_sections(self, temp_ledger_dir):
        """Test that output includes all score sections."""
        create_forecast(temp_ledger_dir, "f1", "test.event1")
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "external_auto")

        result = compute_scores(temp_ledger_dir)

        assert "core_scores" in result
        assert "claims_inferred_scores" in result
        assert "combined_scores" in result

    def test_score_section_structure(self, temp_ledger_dir):
        """Test structure of score sections."""
        create_forecast(temp_ledger_dir, "f1", "test.event1")
        create_resolution(temp_ledger_dir, "f1", "test.event1", "YES", "external_auto")

        result = compute_scores(temp_ledger_dir)

        for section in ["core_scores", "claims_inferred_scores", "combined_scores"]:
            assert "brier_score" in result[section]
            assert "log_score" in result[section]
            assert "count" in result[section]

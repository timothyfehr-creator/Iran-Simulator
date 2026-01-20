"""
Tests for coverage metrics calculation.

Validates coverage rate, unknown rate, and abstain rate calculations.
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.forecasting.scorer import compute_coverage_metrics, effective_brier_score, ScoringError


def make_forecast(forecast_id: str, event_id: str, target_date: datetime, abstain: bool = False):
    """Helper to create a test forecast."""
    return {
        "forecast_id": forecast_id,
        "event_id": event_id,
        "target_date_utc": target_date.isoformat(),
        "probabilities": {"YES": 0.6, "NO": 0.4},
        "abstain": abstain,
    }


def make_resolution(forecast_id: str, outcome: str, resolution_mode: str = "external_auto"):
    """Helper to create a test resolution."""
    return {
        "forecast_id": forecast_id,
        "resolved_outcome": outcome,
        "resolution_mode": resolution_mode,
    }


class TestCoverageMetrics:
    """Tests for compute_coverage_metrics function."""

    def test_empty_forecasts(self):
        """Test with no forecasts."""
        result = compute_coverage_metrics([], [])

        assert result["forecasts_due"] == 0
        assert result["resolved_known"] == 0
        assert result["coverage_rate"] == 0.0

    def test_no_due_forecasts(self):
        """Test with forecasts not yet due."""
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        forecasts = [make_forecast("f1", "test.event", tomorrow)]

        result = compute_coverage_metrics(forecasts, [])

        assert result["forecasts_due"] == 0

    def test_all_resolved_known(self):
        """Test with all forecasts resolved to YES/NO."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        forecasts = [
            make_forecast("f1", "test.event", yesterday),
            make_forecast("f2", "test.event", yesterday),
        ]
        resolutions = [
            make_resolution("f1", "YES"),
            make_resolution("f2", "NO"),
        ]

        result = compute_coverage_metrics(forecasts, resolutions)

        assert result["forecasts_due"] == 2
        assert result["resolved_known"] == 2
        assert result["resolved_unknown"] == 0
        assert result["coverage_rate"] == 1.0

    def test_some_unknown(self):
        """Test with some UNKNOWN resolutions."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        forecasts = [
            make_forecast("f1", "test.event", yesterday),
            make_forecast("f2", "test.event", yesterday),
            make_forecast("f3", "test.event", yesterday),
        ]
        resolutions = [
            make_resolution("f1", "YES"),
            make_resolution("f2", "UNKNOWN"),
            make_resolution("f3", "NO"),
        ]

        result = compute_coverage_metrics(forecasts, resolutions)

        assert result["forecasts_due"] == 3
        assert result["resolved_known"] == 2
        assert result["resolved_unknown"] == 1
        assert result["coverage_rate"] == pytest.approx(2/3)
        assert result["unknown_rate"] == pytest.approx(1/3)

    def test_some_abstained(self):
        """Test with some abstained forecasts."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        forecasts = [
            make_forecast("f1", "test.event", yesterday),
            make_forecast("f2", "test.event", yesterday, abstain=True),
            make_forecast("f3", "test.event", yesterday),
        ]
        resolutions = [
            make_resolution("f1", "YES"),
            make_resolution("f3", "NO"),
        ]

        result = compute_coverage_metrics(forecasts, resolutions)

        assert result["forecasts_due"] == 3
        assert result["resolved_known"] == 2
        assert result["abstained"] == 1
        assert result["abstain_rate"] == pytest.approx(1/3)

    def test_some_unresolved(self):
        """Test with some unresolved forecasts."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        forecasts = [
            make_forecast("f1", "test.event", yesterday),
            make_forecast("f2", "test.event", yesterday),
            make_forecast("f3", "test.event", yesterday),
        ]
        resolutions = [
            make_resolution("f1", "YES"),
        ]

        result = compute_coverage_metrics(forecasts, resolutions)

        assert result["forecasts_due"] == 3
        assert result["resolved_known"] == 1
        assert result["unresolved"] == 2
        assert result["coverage_rate"] == pytest.approx(1/3)

    def test_mixed_due_and_future(self):
        """Test with mix of due and future forecasts."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        forecasts = [
            make_forecast("f1", "test.event", yesterday),
            make_forecast("f2", "test.event", tomorrow),  # Not due
        ]
        resolutions = [
            make_resolution("f1", "YES"),
        ]

        result = compute_coverage_metrics(forecasts, resolutions)

        assert result["forecasts_due"] == 1
        assert result["resolved_known"] == 1
        assert result["coverage_rate"] == 1.0


class TestEffectiveBrierScore:
    """Tests for effective Brier score calculation."""

    def test_perfect_forecasts(self):
        """Test with perfect forecasts."""
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 1.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        result = effective_brier_score(forecasts, resolutions)

        assert result == 0.0

    def test_worst_forecasts(self):
        """Test with completely wrong forecasts."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 1.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        result = effective_brier_score(forecasts, resolutions)

        assert result == 1.0

    def test_abstained_treated_as_half(self):
        """Test that abstained forecasts use p=0.5."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.8}, "abstain": True},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
        ]

        result = effective_brier_score(forecasts, resolutions)

        # Abstained uses 0.5, outcome is YES (1.0)
        # Brier = (0.5 - 1.0)^2 = 0.25
        assert result == pytest.approx(0.25)

    def test_unknown_penalized_as_half_outcome(self):
        """Test that UNKNOWN outcomes are penalized as outcome=0.5."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.6}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.9}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "UNKNOWN"},
        ]

        result = effective_brier_score(forecasts, resolutions)

        # f1: (0.6 - 1.0)^2 = 0.16
        # f2: (0.9 - 0.5)^2 = 0.16 (UNKNOWN treated as outcome=0.5)
        # Average: (0.16 + 0.16) / 2 = 0.16
        assert result == pytest.approx(0.16)

    def test_no_valid_pairs_raises(self):
        """Test that no resolution records raises error."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.6}, "abstain": False},
        ]
        resolutions = []

        with pytest.raises(ScoringError):
            effective_brier_score(forecasts, resolutions)

    def test_all_unknown_returns_penalty(self):
        """Test that all UNKNOWN outcomes returns valid penalty score."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.6}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "UNKNOWN"},
        ]

        result = effective_brier_score(forecasts, resolutions)

        # UNKNOWN treated as outcome=0.5
        # (0.6 - 0.5)^2 = 0.01
        assert result == pytest.approx(0.01)

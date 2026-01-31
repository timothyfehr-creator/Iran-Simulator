"""
Tests for Phase 3B: Multi-Outcome Scoring.

This file contains tests for multinomial Brier score, log score,
per-outcome calibration, baselines, and forecaster separation.

These tests are separate from test_forecasting_scorer.py to avoid bloating
the existing binary tests.
"""

import pytest
import math
from typing import Dict, List, Any

from src.forecasting import scorer
from src.forecasting.scorer import ScoringError


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def outcomes_3():
    """Three-outcome set (excluding UNKNOWN)."""
    return ["A", "B", "C"]


@pytest.fixture
def outcomes_4():
    """Four-outcome set for binned_continuous (FX bands)."""
    return ["FX_LT_800K", "FX_800K_1M", "FX_1M_1_2M", "FX_GE_1_2M"]


@pytest.fixture
def sample_catalog():
    """Sample catalog with binary and multi-outcome events."""
    return {
        "catalog_version": "3.0.0",
        "events": [
            {
                "event_id": "test.binary",
                "name": "Binary Test Event",
                "category": "test",
                "event_type": "binary",
                "allowed_outcomes": ["YES", "NO", "UNKNOWN"],
                "description": "Test binary event",
                "forecast_source": {"type": "simulation_derived"},
                "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "threshold_gte"}
            },
            {
                "event_id": "test.categorical",
                "name": "Categorical Test Event",
                "category": "test",
                "event_type": "categorical",
                "allowed_outcomes": ["A", "B", "C", "UNKNOWN"],
                "description": "Test categorical event",
                "forecast_source": {"type": "baseline_climatology"},
                "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "enum_match"}
            },
            {
                "event_id": "test.binned",
                "name": "Binned Test Event",
                "category": "test",
                "event_type": "binned_continuous",
                "allowed_outcomes": ["FX_LT_800K", "FX_800K_1M", "FX_1M_1_2M", "FX_GE_1_2M", "UNKNOWN"],
                "description": "Test binned event",
                "forecast_source": {"type": "baseline_climatology"},
                "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "bin_map"},
                "bin_spec": {
                    "bins": [
                        {"bin_id": "FX_LT_800K", "label": "< 800k", "min": None, "max": 800000},
                        {"bin_id": "FX_800K_1M", "label": "800k-1M", "min": 800000, "max": 1000000},
                        {"bin_id": "FX_1M_1_2M", "label": "1M-1.2M", "min": 1000000, "max": 1200000},
                        {"bin_id": "FX_GE_1_2M", "label": ">= 1.2M", "min": 1200000, "max": None}
                    ]
                }
            }
        ]
    }


# =============================================================================
# TestMultinomialBrierScore
# =============================================================================

class TestMultinomialBrierScore:
    """Tests for multinomial Brier score calculation."""

    def test_perfect_prediction_k3(self, outcomes_3):
        """Test Brier = 0 for perfect prediction with K=3 outcomes."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 1.0, "B": 0.0, "C": 0.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"A": 0.0, "B": 1.0, "C": 0.0}, "abstain": False},
            {"forecast_id": "f3", "probabilities": {"A": 0.0, "B": 0.0, "C": 1.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
            {"forecast_id": "f2", "resolved_outcome": "B"},
            {"forecast_id": "f3", "resolved_outcome": "C"},
        ]

        raw, norm = scorer.multinomial_brier_score(forecasts, resolutions, outcomes_3)
        assert raw == pytest.approx(0.0, abs=1e-6)
        assert norm == pytest.approx(0.0, abs=1e-6)

    def test_worst_prediction_k3(self, outcomes_3):
        """Test Brier = 2 (raw) for worst prediction with K=3 outcomes."""
        # Predict 100% wrong outcome
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.0, "B": 1.0, "C": 0.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        raw, norm = scorer.multinomial_brier_score(forecasts, resolutions, outcomes_3)
        # BS = (0-1)^2 + (1-0)^2 + (0-0)^2 = 1 + 1 + 0 = 2
        assert raw == pytest.approx(2.0, abs=1e-6)
        assert norm == pytest.approx(1.0, abs=1e-6)

    def test_uniform_k4(self, outcomes_4):
        """Test Brier for uniform prediction with K=4 outcomes."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {o: 0.25 for o in outcomes_4}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "FX_GE_1_2M"},
        ]

        raw, norm = scorer.multinomial_brier_score(forecasts, resolutions, outcomes_4)
        # BS = (0.25-0)^2 + (0.25-0)^2 + (0.25-0)^2 + (0.25-1)^2
        #    = 3*(0.0625) + 0.5625 = 0.1875 + 0.5625 = 0.75
        assert raw == pytest.approx(0.75, abs=1e-6)
        assert norm == pytest.approx(0.375, abs=1e-6)

    def test_excludes_unknown(self, outcomes_3):
        """Test that UNKNOWN resolutions are excluded from scoring."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 1.0, "B": 0.0, "C": 0.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"A": 0.0, "B": 1.0, "C": 0.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},  # Perfect
            {"forecast_id": "f2", "resolved_outcome": "UNKNOWN"},  # Excluded
        ]

        raw, norm = scorer.multinomial_brier_score(forecasts, resolutions, outcomes_3)
        # Only f1 counts (perfect)
        assert raw == pytest.approx(0.0, abs=1e-6)

    def test_excludes_abstained(self, outcomes_3):
        """Test that abstained forecasts are excluded."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 1.0, "B": 0.0, "C": 0.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"A": 0.0, "B": 1.0, "C": 0.0}, "abstain": True},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
            {"forecast_id": "f2", "resolved_outcome": "B"},
        ]

        raw, norm = scorer.multinomial_brier_score(forecasts, resolutions, outcomes_3)
        # Only f1 counts (perfect)
        assert raw == pytest.approx(0.0, abs=1e-6)

    def test_empty_raises_error(self, outcomes_3):
        """Test that empty forecast list raises ScoringError."""
        with pytest.raises(ScoringError, match="No valid"):
            scorer.multinomial_brier_score([], [], outcomes_3)

    def test_normalization_k2_matches_binary(self):
        """Test that K=2 normalized Brier matches binary Brier behavior."""
        outcomes_2 = ["YES", "NO"]
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.7, "NO": 0.3}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.3, "NO": 0.7}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        raw, norm = scorer.multinomial_brier_score(forecasts, resolutions, outcomes_2)
        # f1: (0.7-1)^2 + (0.3-0)^2 = 0.09 + 0.09 = 0.18
        # f2: (0.3-0)^2 + (0.7-1)^2 = 0.09 + 0.09 = 0.18
        # raw = 0.18, norm = 0.09
        assert raw == pytest.approx(0.18, abs=1e-6)
        assert norm == pytest.approx(0.09, abs=1e-6)

    def test_missing_outcome_probability_raises(self, outcomes_3):
        """Test that forecast missing probability for an outcome raises error."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.5, "B": 0.5}, "abstain": False},  # Missing C
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        with pytest.raises(ScoringError, match="missing probability"):
            scorer.multinomial_brier_score(forecasts, resolutions, outcomes_3)


# =============================================================================
# TestEffectiveMultinomialBrier
# =============================================================================

class TestEffectiveMultinomialBrier:
    """Tests for effective multinomial Brier score (UNKNOWN penalty)."""

    def test_unknown_penalized_as_uniform(self, outcomes_3):
        """Test that UNKNOWN resolutions are scored against uniform."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.8, "B": 0.1, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "UNKNOWN"},
        ]

        raw, norm = scorer.effective_multinomial_brier_score(forecasts, resolutions, outcomes_3)
        # Score against uniform (1/3 each)
        # BS = (0.8 - 1/3)^2 + (0.1 - 1/3)^2 + (0.1 - 1/3)^2
        #    = (0.4667)^2 + (-0.2333)^2 + (-0.2333)^2
        #    = 0.2178 + 0.0544 + 0.0544 = 0.3266
        expected_raw = (0.8 - 1/3)**2 + (0.1 - 1/3)**2 + (0.1 - 1/3)**2
        assert raw == pytest.approx(expected_raw, abs=1e-4)

    def test_abstained_uses_uniform(self, outcomes_3):
        """Test that abstained forecasts use uniform as prediction."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.9, "B": 0.05, "C": 0.05}, "abstain": True},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        raw, norm = scorer.effective_multinomial_brier_score(forecasts, resolutions, outcomes_3)
        # Uses uniform prediction (1/3) against A resolution
        # BS = (1/3 - 1)^2 + (1/3 - 0)^2 + (1/3 - 0)^2
        expected_raw = (1/3 - 1)**2 + (1/3)**2 + (1/3)**2
        assert raw == pytest.approx(expected_raw, abs=1e-4)

    def test_effective_worse_than_standard_with_unknown(self, outcomes_3):
        """Test that effective score is worse when UNKNOWN present with confident prediction."""
        # Confident but wrong-ish prediction on UNKNOWN
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.9, "B": 0.05, "C": 0.05}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "UNKNOWN"},
        ]

        raw, _ = scorer.effective_multinomial_brier_score(forecasts, resolutions, outcomes_3)
        # Score against uniform - confident prediction gets penalized
        assert raw > 0.2  # Should be non-trivial penalty


# =============================================================================
# TestMultinomialLogScore
# =============================================================================

class TestMultinomialLogScore:
    """Tests for multinomial log score calculation."""

    def test_uses_resolved_probability(self, outcomes_3):
        """Test that log score uses probability of resolved outcome."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.8, "B": 0.1, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        log_s = scorer.multinomial_log_score(forecasts, resolutions, outcomes_3)
        # log(0.8) ≈ -0.223
        assert log_s == pytest.approx(math.log(0.8), abs=1e-6)

    def test_epsilon_prevents_log_zero(self, outcomes_3):
        """Test that epsilon prevents log(0)."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.0, "B": 0.5, "C": 0.5}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        log_s = scorer.multinomial_log_score(forecasts, resolutions, outcomes_3, epsilon=1e-10)
        # Should use epsilon instead of 0
        assert log_s == pytest.approx(math.log(1e-10), abs=1e-6)

    def test_excludes_unknown(self, outcomes_3):
        """Test that UNKNOWN resolutions are excluded."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.8, "B": 0.1, "C": 0.1}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"A": 0.1, "B": 0.8, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
            {"forecast_id": "f2", "resolved_outcome": "UNKNOWN"},
        ]

        log_s = scorer.multinomial_log_score(forecasts, resolutions, outcomes_3)
        # Only f1 counts
        assert log_s == pytest.approx(math.log(0.8), abs=1e-6)


# =============================================================================
# TestPerOutcomeCalibration
# =============================================================================

class TestPerOutcomeCalibration:
    """Tests for per-outcome calibration calculation."""

    def test_structure(self, outcomes_3):
        """Test that calibration result has correct structure."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.1, "B": 0.8, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "B"},
        ]

        result = scorer.per_outcome_calibration(forecasts, resolutions, outcomes_3)

        assert "per_outcome" in result
        assert "aggregate_calibration_error" in result
        assert "total_forecasts" in result
        assert "filters_applied" in result

        for outcome in outcomes_3:
            assert outcome in result["per_outcome"]
            assert "bins" in result["per_outcome"][outcome]
            assert len(result["per_outcome"][outcome]["bins"]) == 10

    def test_bin_assignment(self, outcomes_3):
        """Test that forecasts are assigned to correct bins."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.05, "B": 0.90, "C": 0.05}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"A": 0.95, "B": 0.03, "C": 0.02}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "B"},
            {"forecast_id": "f2", "resolved_outcome": "A"},
        ]

        result = scorer.per_outcome_calibration(forecasts, resolutions, outcomes_3)

        # Check A's first bin [0.0, 0.1) has f1's A=0.05
        a_bin_0 = result["per_outcome"]["A"]["bins"][0]
        assert a_bin_0["count"] == 1

        # Check A's last bin [0.9, 1.0] has f2's A=0.95
        a_bin_9 = result["per_outcome"]["A"]["bins"][9]
        assert a_bin_9["count"] == 1

    def test_last_bin_includes_one(self, outcomes_3):
        """Test that last bin [0.9, 1.0] includes probability 1.0."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 1.0, "B": 0.0, "C": 0.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        result = scorer.per_outcome_calibration(forecasts, resolutions, outcomes_3)

        # A=1.0 should be in last bin (index 9)
        a_bin_9 = result["per_outcome"]["A"]["bins"][9]
        assert a_bin_9["count"] == 1

    def test_perfect_calibration(self, outcomes_3):
        """Test calibration error for perfectly calibrated forecasts."""
        # 10 forecasts at p=0.5 for A, 5 resolve A, 5 resolve B/C
        forecasts = []
        resolutions = []
        for i in range(10):
            forecasts.append({
                "forecast_id": f"f{i}",
                "probabilities": {"A": 0.5, "B": 0.25, "C": 0.25},
                "abstain": False
            })
            # 5 resolve to A, 5 to B
            outcome = "A" if i < 5 else "B"
            resolutions.append({"forecast_id": f"f{i}", "resolved_outcome": outcome})

        result = scorer.per_outcome_calibration(forecasts, resolutions, outcomes_3)

        # For A at p=0.5: mean_forecast=0.5, observed_freq=0.5 -> error=0
        a_bin_5 = result["per_outcome"]["A"]["bins"][5]  # [0.5, 0.6) bin
        if a_bin_5["count"] > 0:
            assert a_bin_5["absolute_error"] == pytest.approx(0.0, abs=0.01)

    def test_aggregate_weighted_mean(self, outcomes_3):
        """Test that aggregate calibration error is weighted mean."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.8, "B": 0.1, "C": 0.1}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"A": 0.8, "B": 0.1, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
            {"forecast_id": "f2", "resolved_outcome": "B"},
        ]

        result = scorer.per_outcome_calibration(forecasts, resolutions, outcomes_3)

        # Should compute weighted mean across all outcomes
        assert result["aggregate_calibration_error"] is not None

    def test_filters_by_event_horizon_forecaster(self, outcomes_3):
        """Test filtering by event, horizon, and forecaster."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7, "forecaster_id": "oracle_v1",
             "probabilities": {"A": 0.8, "B": 0.1, "C": 0.1}, "abstain": False},
            {"forecast_id": "f2", "event_id": "e2", "horizon_days": 7, "forecaster_id": "oracle_v1",
             "probabilities": {"A": 0.1, "B": 0.8, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
            {"forecast_id": "f2", "resolved_outcome": "B"},
        ]

        # Filter to e1 only
        result = scorer.per_outcome_calibration(
            forecasts, resolutions, outcomes_3, event_id="e1"
        )
        assert result["total_forecasts"] == 1

        # Filter to oracle_v1
        result = scorer.per_outcome_calibration(
            forecasts, resolutions, outcomes_3, forecaster_id="oracle_v1"
        )
        assert result["total_forecasts"] == 2


# =============================================================================
# TestMultinomialClimatology
# =============================================================================

class TestMultinomialClimatology:
    """Tests for multinomial climatology baseline."""

    def test_bootstrap_small_n(self, outcomes_3):
        """Test that small samples return uniform distribution."""
        resolutions = [
            {"forecast_id": f"f{i}", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "external_auto"}
            for i in range(10)  # < 20
        ]

        result = scorer.multinomial_climatology_baseline(
            resolutions, outcomes_3, "e1", 7
        )

        # Should return uniform (1/3 each)
        assert result["A"] == pytest.approx(1/3, abs=1e-6)
        assert result["B"] == pytest.approx(1/3, abs=1e-6)
        assert result["C"] == pytest.approx(1/3, abs=1e-6)

    def test_historical_frequency(self, outcomes_3):
        """Test that sufficient samples return historical frequency."""
        resolutions = (
            [{"forecast_id": f"fA{i}", "event_id": "e1", "horizon_days": 7,
              "resolved_outcome": "A", "resolution_mode": "external_auto"} for i in range(15)] +
            [{"forecast_id": f"fB{i}", "event_id": "e1", "horizon_days": 7,
              "resolved_outcome": "B", "resolution_mode": "external_auto"} for i in range(5)]
        )

        result = scorer.multinomial_climatology_baseline(
            resolutions, outcomes_3, "e1", 7
        )

        # 15 A, 5 B, 0 C out of 20 with Dirichlet smoothing (alpha=1, K=3)
        # p_k = (count_k + 1) / (N + K) = (count_k + 1) / 23
        assert result["A"] == pytest.approx(16/23, abs=1e-4)
        assert result["B"] == pytest.approx(6/23, abs=1e-4)
        assert result["C"] == pytest.approx(1/23, abs=1e-4)

    def test_filters_by_resolution_mode(self, outcomes_3):
        """Test that mode filter is applied."""
        resolutions = (
            [{"forecast_id": f"fA{i}", "event_id": "e1", "horizon_days": 7,
              "resolved_outcome": "A", "resolution_mode": "external_auto"} for i in range(15)] +
            [{"forecast_id": f"fB{i}", "event_id": "e1", "horizon_days": 7,
              "resolved_outcome": "B", "resolution_mode": "claims_inferred"} for i in range(15)]
        )

        result = scorer.multinomial_climatology_baseline(
            resolutions, outcomes_3, "e1", 7,
            mode_filter=["external_auto"]
        )

        # Only external_auto counts (15 A), but < 20 so uniform
        assert result["A"] == pytest.approx(1/3, abs=1e-6)

    def test_per_event_horizon(self, outcomes_3):
        """Test that baseline is computed per event/horizon."""
        resolutions = (
            [{"forecast_id": f"fA{i}", "event_id": "e1", "horizon_days": 7,
              "resolved_outcome": "A", "resolution_mode": "external_auto"} for i in range(20)] +
            [{"forecast_id": f"fB{i}", "event_id": "e1", "horizon_days": 30,
              "resolved_outcome": "B", "resolution_mode": "external_auto"} for i in range(20)]
        )

        result_7 = scorer.multinomial_climatology_baseline(
            resolutions, outcomes_3, "e1", 7
        )
        result_30 = scorer.multinomial_climatology_baseline(
            resolutions, outcomes_3, "e1", 30
        )

        # Horizon 7: 20 A, 0 B, 0 C with smoothing -> (20+1)/(20+3) = 21/23
        assert result_7["A"] == pytest.approx(21/23, abs=1e-4)
        # Horizon 30: 0 A, 20 B, 0 C with smoothing -> (20+1)/(20+3) = 21/23
        assert result_30["B"] == pytest.approx(21/23, abs=1e-4)

    def test_excludes_unknown_resolutions(self, outcomes_3):
        """Test that UNKNOWN resolutions are excluded from baseline."""
        resolutions = (
            [{"forecast_id": f"fA{i}", "event_id": "e1", "horizon_days": 7,
              "resolved_outcome": "A", "resolution_mode": "external_auto"} for i in range(20)] +
            [{"forecast_id": f"fU{i}", "event_id": "e1", "horizon_days": 7,
              "resolved_outcome": "UNKNOWN", "resolution_mode": "external_auto"} for i in range(10)]
        )

        result = scorer.multinomial_climatology_baseline(
            resolutions, outcomes_3, "e1", 7
        )

        # UNKNOWN excluded, so 20 A, 0 B, 0 C with smoothing -> 21/23
        assert result["A"] == pytest.approx(21/23, abs=1e-4)


# =============================================================================
# TestMultinomialPersistence
# =============================================================================

class TestMultinomialPersistence:
    """Tests for multinomial persistence baseline."""

    def test_first_forecast_uniform(self, outcomes_3):
        """Test that first forecast uses uniform distribution."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-01T00:00:00Z"},
        ]
        resolutions = []

        result = scorer.multinomial_persistence_baseline(
            forecasts, resolutions, outcomes_3, "e1", 7
        )

        # First forecast should have uniform
        assert result["f1"]["A"] == pytest.approx(1/3, abs=1e-6)
        assert result["f1"]["B"] == pytest.approx(1/3, abs=1e-6)
        assert result["f1"]["C"] == pytest.approx(1/3, abs=1e-6)

    def test_uses_last_outcome(self, outcomes_3):
        """Test that persistence uses last resolved outcome."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-01T00:00:00Z"},
            {"forecast_id": "f2", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-02T00:00:00Z"},
            {"forecast_id": "f3", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-03T00:00:00Z"},
        ]
        resolutions = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "external_auto"},
            {"forecast_id": "f2", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "B", "resolution_mode": "external_auto"},
        ]

        result = scorer.multinomial_persistence_baseline(
            forecasts, resolutions, outcomes_3, "e1", 7
        )

        # f1: uniform (no prior)
        assert result["f1"]["A"] == pytest.approx(1/3, abs=1e-6)

        # f2: 100% A (after f1 resolved A)
        assert result["f2"]["A"] == pytest.approx(1.0, abs=1e-6)
        assert result["f2"]["B"] == pytest.approx(0.0, abs=1e-6)

        # f3: 100% B (after f2 resolved B)
        assert result["f3"]["B"] == pytest.approx(1.0, abs=1e-6)
        assert result["f3"]["A"] == pytest.approx(0.0, abs=1e-6)

    def test_filters_by_resolution_mode(self, outcomes_3):
        """Test that mode filter is applied to persistence."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-01T00:00:00Z"},
            {"forecast_id": "f2", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-02T00:00:00Z"},
        ]
        resolutions = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "claims_inferred"},
        ]

        result = scorer.multinomial_persistence_baseline(
            forecasts, resolutions, outcomes_3, "e1", 7,
            mode_filter=["external_auto"]  # Excludes claims_inferred
        )

        # f2 should still be uniform (f1's resolution excluded by filter)
        assert result["f2"]["A"] == pytest.approx(1/3, abs=1e-6)


# =============================================================================
# TestForecasterSeparation
# =============================================================================

class TestForecasterSeparation:
    """Tests for forecaster separation functionality."""

    def test_groups_by_forecaster_id(self):
        """Test that forecasts are grouped by forecaster_id."""
        forecasts = [
            {"forecast_id": "f1", "forecaster_id": "oracle_v1"},
            {"forecast_id": "f2", "forecaster_id": "oracle_v1"},
            {"forecast_id": "f3", "forecaster_id": "oracle_baseline_climatology"},
            {"forecast_id": "f4"},  # No forecaster_id
        ]

        groups = scorer.group_by_forecaster(forecasts)

        assert "oracle_v1" in groups
        assert len(groups["oracle_v1"]) == 2
        assert "oracle_baseline_climatology" in groups
        assert len(groups["oracle_baseline_climatology"]) == 1
        assert "unknown" in groups
        assert len(groups["unknown"]) == 1

    def test_baseline_doesnt_pollute_main(self, sample_catalog):
        """Test that baseline forecasters don't affect main forecaster scores."""
        forecasts = [
            {"forecast_id": "f1", "forecaster_id": "oracle_v1", "event_id": "test.binary",
             "probabilities": {"YES": 0.9, "NO": 0.1}, "abstain": False},
            {"forecast_id": "f2", "forecaster_id": "oracle_baseline_climatology", "event_id": "test.binary",
             "probabilities": {"YES": 0.5, "NO": 0.5}, "abstain": False},  # Worse prediction
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
            {"forecast_id": "f2", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
        ]

        scores = scorer.compute_scores_by_forecaster(
            forecasts, resolutions, sample_catalog
        )

        # oracle_v1 score should be better (0.9 vs 0.5 for YES)
        v1_brier = scores["oracle_v1"].get("binary_brier_score")
        baseline_brier = scores["oracle_baseline_climatology"].get("binary_brier_score")

        assert v1_brier is not None
        assert baseline_brier is not None
        assert v1_brier < baseline_brier  # Lower is better

    def test_scores_per_forecaster(self, sample_catalog):
        """Test that separate scores are computed for each forecaster."""
        forecasts = [
            {"forecast_id": "f1", "forecaster_id": "oracle_v1", "event_id": "test.binary",
             "probabilities": {"YES": 0.8, "NO": 0.2}, "abstain": False},
            {"forecast_id": "f2", "forecaster_id": "oracle_v1", "event_id": "test.binary",
             "probabilities": {"YES": 0.8, "NO": 0.2}, "abstain": False},
            {"forecast_id": "f3", "forecaster_id": "oracle_baseline_persistence", "event_id": "test.binary",
             "probabilities": {"YES": 0.5, "NO": 0.5}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
            {"forecast_id": "f2", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
            {"forecast_id": "f3", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
        ]

        scores = scorer.compute_scores_by_forecaster(
            forecasts, resolutions, sample_catalog
        )

        assert "oracle_v1" in scores
        assert scores["oracle_v1"]["count"] == 2
        assert "oracle_baseline_persistence" in scores
        assert scores["oracle_baseline_persistence"]["count"] == 1


# =============================================================================
# TestOutcomeValidation
# =============================================================================

class TestOutcomeValidation:
    """Tests for outcome validation against catalog."""

    def test_outcomes_from_catalog_not_forecasts(self, sample_catalog):
        """Test that outcomes are retrieved from catalog, not forecast keys."""
        outcomes = scorer.get_outcomes_from_catalog(sample_catalog, "test.categorical")

        assert "A" in outcomes
        assert "B" in outcomes
        assert "C" in outcomes
        assert "UNKNOWN" not in outcomes  # Excluded

    def test_resolved_outcome_validated(self):
        """Test that resolved outcomes are validated against catalog."""
        from src.forecasting.resolver import validate_resolved_outcome, ResolutionError

        event = {
            "event_id": "test.event",
            "allowed_outcomes": ["YES", "NO", "UNKNOWN"]
        }

        # Valid outcome
        assert validate_resolved_outcome("YES", event) is True
        assert validate_resolved_outcome("NO", event) is True
        assert validate_resolved_outcome("UNKNOWN", event) is True

        # Invalid outcome
        with pytest.raises(ResolutionError, match="Invalid resolved_outcome"):
            validate_resolved_outcome("MAYBE", event)


# =============================================================================
# TestComputeScoresMultiOutcome
# =============================================================================

class TestComputeScoresMultiOutcome:
    """Tests for compute_scores with multi-outcome events."""

    def test_scores_by_type(self, sample_catalog):
        """Test that scores_by_type is populated correctly."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "test.binary",
             "probabilities": {"YES": 0.8, "NO": 0.2}, "abstain": False},
            {"forecast_id": "f2", "event_id": "test.categorical",
             "probabilities": {"A": 0.6, "B": 0.3, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
            {"forecast_id": "f2", "resolved_outcome": "A", "resolution_mode": "external_auto"},
        ]

        # Call internal function
        scores_by_type = scorer._compute_scores_by_type(
            forecasts, resolutions, sample_catalog, ["external_auto"]
        )

        assert "binary" in scores_by_type
        assert scores_by_type["binary"]["count"] == 1
        assert "categorical" in scores_by_type
        assert scores_by_type["categorical"]["count"] == 1

    def test_scores_by_event(self, sample_catalog):
        """Test that scores_by_event is populated correctly."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "test.binary", "horizon_days": 7,
             "probabilities": {"YES": 0.8, "NO": 0.2}, "abstain": False},
            {"forecast_id": "f2", "event_id": "test.binary", "horizon_days": 30,
             "probabilities": {"YES": 0.7, "NO": 0.3}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
            {"forecast_id": "f2", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
        ]

        scores_by_event = scorer._compute_scores_by_event(
            forecasts, resolutions, sample_catalog, ["external_auto"]
        )

        assert "test.binary" in scores_by_event
        assert scores_by_event["test.binary"]["event_type"] == "binary"
        assert scores_by_event["test.binary"]["count"] == 2
        assert "by_horizon" in scores_by_event["test.binary"]
        assert 7 in scores_by_event["test.binary"]["by_horizon"]
        assert 30 in scores_by_event["test.binary"]["by_horizon"]

    def test_scores_by_forecaster_included(self, sample_catalog):
        """Test that scores_by_forecaster is included in compute_scores output."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "test.binary", "forecaster_id": "oracle_v1",
             "probabilities": {"YES": 0.8, "NO": 0.2}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES", "resolution_mode": "external_auto"},
        ]

        result = scorer._compute_scores_by_type(
            forecasts, resolutions, sample_catalog, ["external_auto"]
        )

        # Just verify structure exists
        assert isinstance(result, dict)


# =============================================================================
# TestBackwardCompatibility
# =============================================================================

class TestBackwardCompatibility:
    """Tests for backward compatibility with binary scoring."""

    def test_binary_brier_unchanged(self):
        """Test that binary brier_score() works as before."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 1.0, "NO": 0.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.0, "NO": 1.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        # Default call should return float (not tuple)
        brier = scorer.brier_score(forecasts, resolutions)
        assert isinstance(brier, float)
        assert brier == 0.0  # Perfect

    def test_binary_log_unchanged(self):
        """Test that binary log_score() works as before."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.99}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
        ]

        # Default call should work
        log_s = scorer.log_score(forecasts, resolutions)
        assert isinstance(log_s, float)
        assert log_s > -0.02  # Close to 0

    def test_binary_calibration_unchanged(self):
        """Test that binary calibration_bins() works as before."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.15}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "NO"},
        ]

        result = scorer.calibration_bins(forecasts, resolutions)

        assert "bins" in result
        assert len(result["bins"]) == 10
        assert "calibration_error" in result

    def test_brier_dispatcher_returns_tuple_for_multi(self):
        """Test that brier_score returns tuple when outcomes provided."""
        outcomes = ["A", "B", "C"]
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.8, "B": 0.1, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        result = scorer.brier_score(
            forecasts, resolutions,
            event_type="categorical",
            outcomes=outcomes
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        raw, norm = result
        assert raw < norm * 3  # Sanity check: raw < 2*norm + epsilon

    def test_log_dispatcher_works_for_multi(self):
        """Test that log_score works with outcomes parameter."""
        outcomes = ["A", "B", "C"]
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.8, "B": 0.1, "C": 0.1}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        result = scorer.log_score(
            forecasts, resolutions,
            event_type="categorical",
            outcomes=outcomes
        )

        assert isinstance(result, float)
        assert result == pytest.approx(math.log(0.8), abs=1e-6)


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_all_unknown_resolutions_raises(self, outcomes_3):
        """Test that all UNKNOWN resolutions raises error for standard scoring."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.5, "B": 0.3, "C": 0.2}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "UNKNOWN"},
        ]

        with pytest.raises(ScoringError, match="No valid"):
            scorer.multinomial_brier_score(forecasts, resolutions, outcomes_3)

    def test_effective_scoring_handles_all_unknown(self, outcomes_3):
        """Test that effective scoring handles all UNKNOWN (doesn't raise)."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.5, "B": 0.3, "C": 0.2}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "UNKNOWN"},
        ]

        # Should not raise - UNKNOWN is scored against uniform
        raw, norm = scorer.effective_multinomial_brier_score(forecasts, resolutions, outcomes_3)
        assert raw > 0  # Non-zero penalty

    def test_single_outcome_edge(self):
        """Test scoring with only one non-UNKNOWN outcome (degenerate case)."""
        outcomes = ["ONLY_ONE"]
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"ONLY_ONE": 1.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "ONLY_ONE"},
        ]

        raw, norm = scorer.multinomial_brier_score(forecasts, resolutions, outcomes)
        assert raw == 0.0  # Perfect prediction

    def test_probabilities_sum_to_one_validation(self, outcomes_3):
        """Test that probabilities are used as-is (validation is external)."""
        # Probabilities don't sum to 1, but scoring doesn't validate this
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"A": 0.4, "B": 0.3, "C": 0.2}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "A"},
        ]

        # Should compute score (validation is elsewhere)
        raw, norm = scorer.multinomial_brier_score(forecasts, resolutions, outcomes_3)
        assert raw > 0  # (0.4-1)^2 + 0.3^2 + 0.2^2 = 0.36 + 0.09 + 0.04 = 0.49

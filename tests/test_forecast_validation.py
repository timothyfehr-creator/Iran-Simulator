"""
Tests for forecast.py - validate_distribution() probability validation.
"""

import pytest
import math
from src.forecasting import forecast


class TestValidateDistribution:
    """Tests for validate_distribution()"""

    @pytest.fixture
    def binary_event(self):
        """Binary event definition."""
        return {
            "event_id": "test.binary",
            "event_type": "binary",
            "allowed_outcomes": ["YES", "NO"],
        }

    @pytest.fixture
    def categorical_event(self):
        """Categorical event definition."""
        return {
            "event_id": "test.categorical",
            "event_type": "categorical",
            "allowed_outcomes": ["A", "B", "C", "UNKNOWN"],
        }

    @pytest.fixture
    def binned_event(self):
        """Binned continuous event definition."""
        return {
            "event_id": "test.binned",
            "event_type": "binned_continuous",
            "allowed_outcomes": ["LOW", "MEDIUM", "HIGH", "UNKNOWN"],
        }

    def test_valid_binary_distribution(self, binary_event):
        """Valid binary distribution should pass."""
        probs = {"YES": 0.7, "NO": 0.3}
        errors = forecast.validate_distribution(probs, binary_event)
        assert errors == []

    def test_valid_categorical_distribution(self, categorical_event):
        """Valid categorical distribution should pass."""
        probs = {"A": 0.4, "B": 0.3, "C": 0.3}
        errors = forecast.validate_distribution(probs, categorical_event)
        assert errors == []

    def test_valid_binned_distribution(self, binned_event):
        """Valid binned distribution should pass."""
        probs = {"LOW": 0.2, "MEDIUM": 0.5, "HIGH": 0.3}
        errors = forecast.validate_distribution(probs, binned_event)
        assert errors == []

    def test_negative_probability(self, binary_event):
        """Negative probability should fail."""
        probs = {"YES": -0.1, "NO": 1.1}
        errors = forecast.validate_distribution(probs, binary_event)
        assert any("negative" in e.lower() for e in errors)

    def test_nan_probability(self, binary_event):
        """NaN probability should fail."""
        probs = {"YES": float('nan'), "NO": 0.5}
        errors = forecast.validate_distribution(probs, binary_event)
        assert any("nan" in e.lower() for e in errors)

    def test_probability_exceeds_one(self, binary_event):
        """Probability > 1.0 should fail."""
        probs = {"YES": 1.5, "NO": -0.5}
        errors = forecast.validate_distribution(probs, binary_event)
        assert any("exceeds" in e.lower() or "negative" in e.lower() for e in errors)

    def test_sum_not_one_low(self, binary_event):
        """Probabilities summing to < 1.0 should fail."""
        probs = {"YES": 0.4, "NO": 0.5}  # Sum = 0.9
        errors = forecast.validate_distribution(probs, binary_event)
        assert any("sum" in e.lower() for e in errors)

    def test_sum_not_one_high(self, binary_event):
        """Probabilities summing to > 1.0 should fail."""
        probs = {"YES": 0.6, "NO": 0.5}  # Sum = 1.1
        errors = forecast.validate_distribution(probs, binary_event)
        assert any("sum" in e.lower() for e in errors)

    def test_sum_within_tolerance(self, binary_event):
        """Probabilities summing to 1.0 within tolerance should pass."""
        probs = {"YES": 0.333333, "NO": 0.666667}  # Sum = 1.0 within tolerance
        errors = forecast.validate_distribution(probs, binary_event)
        assert errors == []

    def test_unexpected_outcome(self, binary_event):
        """Outcome not in allowed_outcomes should fail."""
        probs = {"YES": 0.5, "NO": 0.3, "MAYBE": 0.2}
        errors = forecast.validate_distribution(probs, binary_event)
        assert any("unexpected" in e.lower() or "maybe" in e.lower() for e in errors)

    def test_missing_required_outcome(self, binary_event):
        """Missing required outcome should fail."""
        probs = {"YES": 1.0}  # Missing NO
        errors = forecast.validate_distribution(probs, binary_event)
        assert any("missing" in e.lower() for e in errors)

    def test_unknown_always_allowed(self, binary_event):
        """UNKNOWN outcome should always be allowed even if not in allowed_outcomes."""
        probs = {"YES": 0.5, "NO": 0.4, "UNKNOWN": 0.1}
        errors = forecast.validate_distribution(probs, binary_event)
        # Even though UNKNOWN is not in binary allowed_outcomes, it's always allowed
        # Check that the only errors (if any) are not about UNKNOWN
        unexpected_errors = [e for e in errors if "unknown" in e.lower() and "unexpected" in e.lower()]
        assert len(unexpected_errors) == 0


class TestGenerateBaselineDistribution:
    """Tests for generate_baseline_distribution()"""

    def test_uniform_binary(self):
        """Binary event should get 50/50 distribution."""
        event = {"allowed_outcomes": ["YES", "NO"]}
        dist = forecast.generate_baseline_distribution(event, "baseline_climatology")

        assert "YES" in dist
        assert "NO" in dist
        assert abs(dist["YES"] - 0.5) < 0.001
        assert abs(dist["NO"] - 0.5) < 0.001

    def test_uniform_categorical(self):
        """Categorical event should get uniform distribution."""
        event = {"allowed_outcomes": ["A", "B", "C", "UNKNOWN"]}
        dist = forecast.generate_baseline_distribution(event, "baseline_climatology")

        # Should exclude UNKNOWN from probability mass
        assert "A" in dist
        assert "B" in dist
        assert "C" in dist
        assert "UNKNOWN" not in dist

        # Each should be 1/3
        for outcome in ["A", "B", "C"]:
            assert abs(dist[outcome] - 1/3) < 0.001

    def test_uniform_binned(self):
        """Binned event should get uniform distribution over bins."""
        event = {"allowed_outcomes": ["LOW", "MEDIUM", "HIGH", "UNKNOWN"]}
        dist = forecast.generate_baseline_distribution(event, "baseline_persistence")

        assert "LOW" in dist
        assert "MEDIUM" in dist
        assert "HIGH" in dist
        assert "UNKNOWN" not in dist

        # Each should be 1/3
        for outcome in ["LOW", "MEDIUM", "HIGH"]:
            assert abs(dist[outcome] - 1/3) < 0.001

    def test_sum_equals_one(self):
        """Generated distribution should sum to exactly 1.0."""
        event = {"allowed_outcomes": ["A", "B", "C", "D", "E", "UNKNOWN"]}
        dist = forecast.generate_baseline_distribution(event, "baseline_climatology")

        total = sum(dist.values())
        assert abs(total - 1.0) < 1e-9

    def test_empty_outcomes_returns_unknown(self):
        """Event with no outcomes should return UNKNOWN:1.0."""
        event = {"allowed_outcomes": ["UNKNOWN"]}
        dist = forecast.generate_baseline_distribution(event, "baseline_climatology")

        assert dist == {"UNKNOWN": 1.0}

    def test_rounding_adjustment(self):
        """Distribution with rounding should still sum to 1.0."""
        # 7 outcomes will have 1/7 = 0.142857... which rounds
        event = {"allowed_outcomes": ["A", "B", "C", "D", "E", "F", "G", "UNKNOWN"]}
        dist = forecast.generate_baseline_distribution(event, "baseline_climatology")

        total = sum(dist.values())
        assert abs(total - 1.0) < 1e-9


class TestProbabilitySumTolerance:
    """Tests for probability sum tolerance constant."""

    def test_tolerance_value(self):
        """Tolerance should be 1e-6."""
        assert forecast.PROBABILITY_SUM_TOLERANCE == 1e-6

    def test_at_tolerance_boundary(self):
        """Sum at tolerance boundary should pass."""
        event = {"allowed_outcomes": ["YES", "NO"]}

        # Just within tolerance
        probs = {"YES": 0.5, "NO": 0.5 - 0.5e-6}
        errors = forecast.validate_distribution(probs, event)
        assert errors == []

    def test_beyond_tolerance_boundary(self):
        """Sum beyond tolerance should fail."""
        event = {"allowed_outcomes": ["YES", "NO"]}

        # Just beyond tolerance
        probs = {"YES": 0.5, "NO": 0.5 - 2e-6}
        errors = forecast.validate_distribution(probs, event)
        assert any("sum" in e.lower() for e in errors)

"""
Tests for climatology distribution computation in baseline_history.py.
"""

import pytest
from datetime import datetime, timezone

from src.forecasting import baseline_history
from src.forecasting.baseline_history import HistoryEntry


@pytest.fixture
def basic_config():
    """Basic baseline configuration for testing."""
    return {
        "config_version": "1.0.0",
        "min_history_n": 5,
        "smoothing_alpha": 1.0,
        "include_unknown": False,
    }


@pytest.fixture
def entry_with_counts():
    """History entry with sample counts."""
    entry = HistoryEntry(event_id="test.event", horizon_days=7)
    entry.counts_by_outcome = {"YES": 30, "NO": 20}
    entry.history_n = 50
    entry.last_resolved_outcome = "YES"
    entry.last_verified_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    entry.staleness_days = 5
    entry.excluded_counts_by_reason = {"unknown_outcome": 2}
    return entry


class TestClimatologyDistribution:
    """Tests for compute_climatology_distribution function."""

    def test_binary_sums_to_one(self, entry_with_counts, basic_config):
        """Binary distribution sums to 1.0."""
        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry_with_counts, outcomes, basic_config
        )

        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-6

    def test_categorical_sums_to_one(self, basic_config):
        """Categorical distribution sums to 1.0."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"A": 10, "B": 20, "C": 15, "D": 5}
        entry.history_n = 50

        outcomes = ["A", "B", "C", "D"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-6

    def test_binned_sums_to_one(self, basic_config):
        """Binned continuous distribution sums to 1.0."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {
            "FX_LT_800K": 5,
            "FX_800K_1M": 20,
            "FX_1M_1_2M": 15,
            "FX_GE_1_2M": 10
        }
        entry.history_n = 50

        outcomes = ["FX_LT_800K", "FX_800K_1M", "FX_1M_1_2M", "FX_GE_1_2M"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-6

    def test_smoothing_prevents_zero_probabilities(self, basic_config):
        """Dirichlet smoothing ensures no zero probabilities."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        # Only observed YES, never NO
        entry.counts_by_outcome = {"YES": 50}
        entry.history_n = 50

        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        # Both should be > 0 due to smoothing
        assert probs["YES"] > 0
        assert probs["NO"] > 0
        # YES should be higher since it was observed more
        assert probs["YES"] > probs["NO"]

    def test_insufficient_history_returns_uniform(self, basic_config):
        """When history_n < min_history_n, returns uniform."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"YES": 2, "NO": 1}
        entry.history_n = 3  # Less than min_history_n=5

        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        # Should be uniform
        assert abs(probs["YES"] - 0.5) < 1e-6
        assert abs(probs["NO"] - 0.5) < 1e-6
        assert metadata["baseline_fallback"] == "uniform"

    def test_window_days_filter_applied(self, basic_config):
        """Config with window_days filters old data (tested via metadata)."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"YES": 30, "NO": 20}
        entry.history_n = 50
        entry.excluded_counts_by_reason = {"outside_window": 15}

        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        # Excluded counts should be in metadata
        assert metadata["baseline_excluded_counts_by_reason"]["outside_window"] == 15


class TestSmoothingParameter:
    """Tests for smoothing_alpha parameter."""

    def test_alpha_zero_is_mle(self):
        """alpha=0 gives maximum likelihood estimate (no smoothing)."""
        config = {"min_history_n": 1, "smoothing_alpha": 0.0}

        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"YES": 80, "NO": 20}
        entry.history_n = 100

        outcomes = ["YES", "NO"]

        probs, _ = baseline_history.compute_climatology_distribution(
            entry, outcomes, config
        )

        # With alpha=0, should be close to MLE
        assert abs(probs["YES"] - 0.8) < 1e-6
        assert abs(probs["NO"] - 0.2) < 1e-6

    def test_higher_alpha_more_uniform(self):
        """Higher alpha pulls distribution toward uniform."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"YES": 80, "NO": 20}
        entry.history_n = 100

        outcomes = ["YES", "NO"]

        # Low alpha
        config_low = {"min_history_n": 1, "smoothing_alpha": 0.1}
        probs_low, _ = baseline_history.compute_climatology_distribution(
            entry, outcomes, config_low
        )

        # High alpha
        config_high = {"min_history_n": 1, "smoothing_alpha": 10.0}
        probs_high, _ = baseline_history.compute_climatology_distribution(
            entry, outcomes, config_high
        )

        # High alpha should be more uniform (closer to 0.5)
        assert abs(probs_high["YES"] - 0.5) < abs(probs_low["YES"] - 0.5)


class TestMetadata:
    """Tests for metadata returned by climatology."""

    def test_history_n_in_metadata(self, entry_with_counts, basic_config):
        """baseline_history_n is in metadata."""
        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry_with_counts, outcomes, basic_config
        )

        assert metadata["baseline_history_n"] == 50

    def test_fallback_null_when_sufficient_history(self, entry_with_counts, basic_config):
        """baseline_fallback is null when history sufficient."""
        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry_with_counts, outcomes, basic_config
        )

        assert metadata["baseline_fallback"] is None

    def test_excluded_counts_in_metadata(self, entry_with_counts, basic_config):
        """excluded_counts_by_reason is in metadata."""
        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry_with_counts, outcomes, basic_config
        )

        assert "unknown_outcome" in metadata["baseline_excluded_counts_by_reason"]
        assert metadata["baseline_excluded_counts_by_reason"]["unknown_outcome"] == 2


class TestEdgeCases:
    """Edge case tests for climatology."""

    def test_empty_outcomes_returns_empty(self, entry_with_counts, basic_config):
        """Empty outcomes list returns empty distribution."""
        probs, metadata = baseline_history.compute_climatology_distribution(
            entry_with_counts, [], basic_config
        )

        assert probs == {}

    def test_no_history_returns_uniform(self, basic_config):
        """Entry with no history returns uniform."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {}
        entry.history_n = 0

        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        assert abs(probs["YES"] - 0.5) < 1e-6
        assert abs(probs["NO"] - 0.5) < 1e-6
        assert metadata["baseline_fallback"] == "uniform"

    def test_unobserved_outcomes_get_smoothed_probability(self, basic_config):
        """Outcomes not in history still get non-zero probability."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"A": 50}  # Only A observed
        entry.history_n = 50

        outcomes = ["A", "B", "C"]

        probs, _ = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        # All should be positive
        assert probs["A"] > 0
        assert probs["B"] > 0
        assert probs["C"] > 0
        # A should be highest
        assert probs["A"] > probs["B"]
        assert probs["A"] > probs["C"]

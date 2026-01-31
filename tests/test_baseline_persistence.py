"""
Tests for persistence distribution computation in baseline_history.py.
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
        "persistence_stickiness": 0.7,
        "max_staleness_days": 30,
        "staleness_decay": "linear",
    }


@pytest.fixture
def entry_with_recent_outcome():
    """History entry with recent outcome (low staleness)."""
    entry = HistoryEntry(event_id="test.event", horizon_days=7)
    entry.counts_by_outcome = {"YES": 30, "NO": 20}
    entry.history_n = 50
    entry.last_resolved_outcome = "YES"
    entry.last_verified_at = datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc)
    entry.staleness_days = 2  # Very recent
    entry.excluded_counts_by_reason = {}
    return entry


@pytest.fixture
def entry_with_stale_outcome():
    """History entry with stale outcome (high staleness)."""
    entry = HistoryEntry(event_id="test.event", horizon_days=7)
    entry.counts_by_outcome = {"YES": 30, "NO": 20}
    entry.history_n = 50
    entry.last_resolved_outcome = "YES"
    entry.last_verified_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    entry.staleness_days = 25  # Pretty stale
    entry.excluded_counts_by_reason = {}
    return entry


class TestPersistenceDistribution:
    """Tests for compute_persistence_distribution function."""

    def test_stickiness_weights_last_outcome(self, entry_with_recent_outcome, basic_config):
        """Recent last outcome gets extra weight from stickiness."""
        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_persistence_distribution(
            entry_with_recent_outcome, outcomes, basic_config
        )

        # YES was last outcome with low staleness, should be weighted more
        # With stickiness=0.7 and staleness=2 days (decay = 1 - 2/30 ≈ 0.93)
        # Effective stickiness ≈ 0.7 * 0.93 = 0.65
        # So YES gets ~0.65 weight, plus (1-0.65) * climatology weight
        assert probs["YES"] > probs["NO"]
        assert probs["YES"] > 0.6  # Should be significantly higher

    def test_staleness_decay_linear(self, entry_with_stale_outcome, basic_config):
        """Linear staleness decay reduces stickiness over time."""
        outcomes = ["YES", "NO"]

        # With staleness=25, max_staleness=30:
        # decay_factor = 1 - 25/30 = 0.167
        # Effective stickiness = 0.7 * 0.167 ≈ 0.117

        probs, metadata = baseline_history.compute_persistence_distribution(
            entry_with_stale_outcome, outcomes, basic_config
        )

        # YES still weighted more, but closer to climatology
        assert probs["YES"] > probs["NO"]
        # With reduced stickiness, should be more uniform
        assert probs["YES"] < 0.7  # Less than full stickiness would give

    def test_staleness_decay_exponential(self, entry_with_stale_outcome):
        """Exponential staleness decay reduces stickiness differently."""
        config = {
            "min_history_n": 5,
            "smoothing_alpha": 1.0,
            "persistence_stickiness": 0.7,
            "max_staleness_days": 30,
            "staleness_decay": "exponential",
        }

        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_persistence_distribution(
            entry_with_stale_outcome, outcomes, config
        )

        # With exponential decay, should still be positive
        assert probs["YES"] > probs["NO"]
        # Sum to 1
        assert abs(sum(probs.values()) - 1.0) < 1e-6

    def test_max_staleness_reverts_to_climatology(self, basic_config):
        """When staleness >= max_staleness_days, reverts to climatology."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"YES": 30, "NO": 20}
        entry.history_n = 50
        entry.last_resolved_outcome = "YES"
        entry.staleness_days = 35  # Beyond max_staleness_days=30

        outcomes = ["YES", "NO"]

        # Get climatology for comparison
        clim_probs, _ = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        # Get persistence
        persist_probs, metadata = baseline_history.compute_persistence_distribution(
            entry, outcomes, basic_config
        )

        # Should match climatology when fully stale
        assert abs(persist_probs["YES"] - clim_probs["YES"]) < 1e-6
        assert abs(persist_probs["NO"] - clim_probs["NO"]) < 1e-6

    def test_no_last_outcome_returns_climatology(self, basic_config):
        """When no last outcome, returns climatology."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"YES": 30, "NO": 20}
        entry.history_n = 50
        entry.last_resolved_outcome = None  # No last outcome
        entry.staleness_days = 0

        outcomes = ["YES", "NO"]

        # Get climatology for comparison
        clim_probs, _ = baseline_history.compute_climatology_distribution(
            entry, outcomes, basic_config
        )

        # Get persistence
        persist_probs, metadata = baseline_history.compute_persistence_distribution(
            entry, outcomes, basic_config
        )

        # Should match climatology
        assert abs(persist_probs["YES"] - clim_probs["YES"]) < 1e-6
        assert abs(persist_probs["NO"] - clim_probs["NO"]) < 1e-6


class TestDecayStickiness:
    """Tests for decay_stickiness helper function."""

    def test_zero_staleness_full_stickiness(self):
        """Zero staleness returns full base stickiness."""
        result = baseline_history.decay_stickiness(
            base_stickiness=0.7,
            staleness_days=0,
            max_staleness_days=30,
            decay_type="linear"
        )
        assert result == 0.7

    def test_max_staleness_zero_stickiness(self):
        """At max staleness, returns zero."""
        result = baseline_history.decay_stickiness(
            base_stickiness=0.7,
            staleness_days=30,
            max_staleness_days=30,
            decay_type="linear"
        )
        assert result == 0.0

    def test_beyond_max_staleness_zero(self):
        """Beyond max staleness, returns zero."""
        result = baseline_history.decay_stickiness(
            base_stickiness=0.7,
            staleness_days=45,
            max_staleness_days=30,
            decay_type="linear"
        )
        assert result == 0.0

    def test_linear_halfway_is_half(self):
        """Linear decay at halfway point gives half stickiness."""
        result = baseline_history.decay_stickiness(
            base_stickiness=0.8,
            staleness_days=15,
            max_staleness_days=30,
            decay_type="linear"
        )
        assert abs(result - 0.4) < 1e-6

    def test_exponential_decay(self):
        """Exponential decay follows expected curve."""
        result = baseline_history.decay_stickiness(
            base_stickiness=0.8,
            staleness_days=15,  # At half-life
            max_staleness_days=30,
            decay_type="exponential"
        )
        # Half-life is max_staleness/2 = 15 days
        # At 15 days, decay_factor = 0.5
        expected = 0.8 * 0.5
        assert abs(result - expected) < 1e-6


class TestSumsToOne:
    """Tests ensuring persistence distributions sum to 1.0."""

    def test_binary_sums_to_one(self, entry_with_recent_outcome, basic_config):
        """Binary persistence distribution sums to 1.0."""
        outcomes = ["YES", "NO"]

        probs, _ = baseline_history.compute_persistence_distribution(
            entry_with_recent_outcome, outcomes, basic_config
        )

        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-6

    def test_categorical_sums_to_one(self, basic_config):
        """Categorical persistence distribution sums to 1.0."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"A": 10, "B": 20, "C": 15, "D": 5}
        entry.history_n = 50
        entry.last_resolved_outcome = "B"
        entry.staleness_days = 5

        outcomes = ["A", "B", "C", "D"]

        probs, _ = baseline_history.compute_persistence_distribution(
            entry, outcomes, basic_config
        )

        total = sum(probs.values())
        assert abs(total - 1.0) < 1e-6


class TestMetadata:
    """Tests for metadata returned by persistence."""

    def test_staleness_days_in_metadata(self, entry_with_recent_outcome, basic_config):
        """baseline_staleness_days is in metadata."""
        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_persistence_distribution(
            entry_with_recent_outcome, outcomes, basic_config
        )

        assert metadata["baseline_staleness_days"] == 2

    def test_last_verified_at_in_metadata(self, entry_with_recent_outcome, basic_config):
        """baseline_last_verified_at is in metadata."""
        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_persistence_distribution(
            entry_with_recent_outcome, outcomes, basic_config
        )

        assert "baseline_last_verified_at" in metadata
        assert "2026-01-18" in metadata["baseline_last_verified_at"]

    def test_history_n_in_metadata(self, entry_with_recent_outcome, basic_config):
        """baseline_history_n is in metadata."""
        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_persistence_distribution(
            entry_with_recent_outcome, outcomes, basic_config
        )

        assert metadata["baseline_history_n"] == 50


class TestInsufficientHistory:
    """Tests for fallback behavior with insufficient history."""

    def test_insufficient_history_returns_uniform(self, basic_config):
        """When history_n < min_history_n, returns uniform."""
        entry = HistoryEntry(event_id="test.event", horizon_days=7)
        entry.counts_by_outcome = {"YES": 2, "NO": 1}
        entry.history_n = 3  # Less than min_history_n=5
        entry.last_resolved_outcome = "YES"
        entry.staleness_days = 1

        outcomes = ["YES", "NO"]

        probs, metadata = baseline_history.compute_persistence_distribution(
            entry, outcomes, basic_config
        )

        # Should be uniform due to insufficient history
        assert abs(probs["YES"] - 0.5) < 1e-6
        assert abs(probs["NO"] - 0.5) < 1e-6
        assert metadata["baseline_fallback"] == "uniform"


class TestCustomClimatology:
    """Tests for passing custom climatology to persistence."""

    def test_uses_provided_climatology(self, entry_with_recent_outcome, basic_config):
        """Persistence uses provided climatology if given."""
        outcomes = ["YES", "NO"]

        # Custom climatology (different from what would be computed)
        custom_clim = {"YES": 0.3, "NO": 0.7}

        probs, _ = baseline_history.compute_persistence_distribution(
            entry_with_recent_outcome, outcomes, basic_config,
            climatology_probs=custom_clim
        )

        # Should use custom climatology as base
        # Last outcome was YES, so it gets stickiness boost
        # But NO should still be relatively high due to custom climatology
        assert probs["YES"] > 0.3  # Higher than custom clim due to stickiness
        assert sum(probs.values()) - 1.0 < 1e-6

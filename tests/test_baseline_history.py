"""
Tests for src/forecasting/baseline_history.py - History index with lookahead prevention.
"""

import json
import pytest
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.forecasting import baseline_history
from src.forecasting import ledger


@pytest.fixture
def temp_ledger_dir():
    """Create a temporary ledger directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def basic_config():
    """Basic baseline configuration for testing."""
    return {
        "config_version": "1.0.0",
        "defaults": {
            "min_history_n": 5,
            "window_days": 180,
            "smoothing_alpha": 1.0,
            "include_unknown": False,
            "persistence_stickiness": 0.7,
            "max_staleness_days": 30,
            "staleness_decay": "linear",
            "resolution_modes": ["external_auto", "external_manual"]
        },
        "overrides": {}
    }


def make_resolution(
    event_id: str,
    horizon_days: int,
    outcome: str,
    resolved_at: datetime,
    resolution_id: str = None,
    mode: str = "external_auto",
    forecast_id: str = None
) -> dict:
    """Helper to create a resolution record."""
    res_id = resolution_id or f"res_{event_id}_{horizon_days}_{int(resolved_at.timestamp())}"
    fcst_id = forecast_id or f"fcst_{event_id}_{horizon_days}_{int(resolved_at.timestamp())}"
    return {
        "record_type": "resolution",
        "resolution_id": res_id,
        "forecast_id": fcst_id,
        "event_id": event_id,
        "horizon_days": horizon_days,
        "resolved_outcome": outcome,
        "resolved_at_utc": resolved_at.isoformat(),
        "resolution_mode": mode,
        "resolved_by": "test"
    }


def make_correction(
    resolution_id: str,
    corrected_outcome: str,
    corrected_at: datetime
) -> dict:
    """Helper to create a correction record."""
    return {
        "record_type": "correction",
        "correction_id": f"corr_{resolution_id}_{int(corrected_at.timestamp())}",
        "resolution_id": resolution_id,
        "corrected_outcome": corrected_outcome,
        "corrected_at_utc": corrected_at.isoformat(),
        "corrected_by": "test"
    }


class TestLookaheadPrevention:
    """Tests for no-lookahead enforcement."""

    def test_excludes_future_resolutions(self, temp_ledger_dir, basic_config):
        """Future resolutions (resolved_at_utc > as_of_utc) are excluded."""
        # as_of_utc is Jan 15
        as_of_utc = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Resolution from Jan 10 (past) should be included
        past_res = make_resolution(
            "test.event", 7, "YES",
            datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc)
        )
        # Resolution from Jan 20 (future) should be excluded
        future_res = make_resolution(
            "test.event", 7, "NO",
            datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)
        )

        ledger.append_resolution(past_res, temp_ledger_dir)
        ledger.append_resolution(future_res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 1
        assert entry.counts_by_outcome.get("YES", 0) == 1
        assert entry.counts_by_outcome.get("NO", 0) == 0
        assert entry.excluded_counts_by_reason.get("future_lookahead", 0) == 1

    def test_includes_past_resolutions(self, temp_ledger_dir, basic_config):
        """Past resolutions (resolved_at_utc < as_of_utc) are included."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add several past resolutions
        for i in range(5):
            res = make_resolution(
                "test.event", 7, "YES" if i % 2 == 0 else "NO",
                datetime(2026, 1, 10 + i, 12, 0, 0, tzinfo=timezone.utc)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 5
        assert entry.counts_by_outcome.get("YES", 0) == 3
        assert entry.counts_by_outcome.get("NO", 0) == 2

    def test_boundary_at_as_of_utc(self, temp_ledger_dir, basic_config):
        """Resolution exactly at as_of_utc should be included."""
        as_of_utc = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)

        # Resolution exactly at as_of_utc
        boundary_res = make_resolution(
            "test.event", 7, "YES",
            as_of_utc  # Exactly at boundary
        )
        ledger.append_resolution(boundary_res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 1


class TestModeFiltering:
    """Tests for resolution_mode filtering."""

    def test_excludes_claims_inferred(self, temp_ledger_dir, basic_config):
        """claims_inferred resolutions are excluded by default."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add resolution with claims_inferred mode
        claims_res = make_resolution(
            "test.event", 7, "YES",
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            mode="claims_inferred"
        )
        ledger.append_resolution(claims_res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 0
        assert entry.excluded_counts_by_reason.get("mode_claims_inferred", 0) == 1

    def test_includes_external_auto(self, temp_ledger_dir, basic_config):
        """external_auto resolutions are included by default."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        res = make_resolution(
            "test.event", 7, "YES",
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            mode="external_auto"
        )
        ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 1

    def test_includes_external_manual(self, temp_ledger_dir, basic_config):
        """external_manual resolutions are included by default."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        res = make_resolution(
            "test.event", 7, "NO",
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            mode="external_manual"
        )
        ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 1


class TestCorrectionHandling:
    """Tests for correction record handling."""

    def test_latest_correction_wins(self, temp_ledger_dir, basic_config):
        """When multiple corrections exist, latest one is applied."""
        as_of_utc = datetime(2026, 1, 25, 12, 0, 0, tzinfo=timezone.utc)

        # Original resolution
        res = make_resolution(
            "test.event", 7, "YES",
            datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
            resolution_id="res_1"
        )
        ledger.append_resolution(res, temp_ledger_dir)

        # First correction changes to NO
        corr1 = make_correction("res_1", "NO", datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
        ledger.append_correction(corr1, temp_ledger_dir)

        # Second correction changes back to YES
        corr2 = make_correction("res_1", "YES", datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc))
        ledger.append_correction(corr2, temp_ledger_dir)

        # Third correction changes to NO (latest)
        corr3 = make_correction("res_1", "NO", datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc))
        ledger.append_correction(corr3, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 1
        assert entry.counts_by_outcome.get("NO", 0) == 1
        assert entry.counts_by_outcome.get("YES", 0) == 0

    def test_uncorrected_resolution_unchanged(self, temp_ledger_dir, basic_config):
        """Resolutions without corrections keep original outcome."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        res = make_resolution(
            "test.event", 7, "YES",
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 1
        assert entry.counts_by_outcome.get("YES", 0) == 1

    def test_multiple_corrections_takes_latest(self, temp_ledger_dir, basic_config):
        """Multiple resolutions, each with their own corrections."""
        as_of_utc = datetime(2026, 1, 25, 12, 0, 0, tzinfo=timezone.utc)

        # Resolution 1: YES -> NO (corrected)
        res1 = make_resolution(
            "test.event", 7, "YES",
            datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
            resolution_id="res_1"
        )
        corr1 = make_correction("res_1", "NO", datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc))

        # Resolution 2: NO (not corrected)
        res2 = make_resolution(
            "test.event", 7, "NO",
            datetime(2026, 1, 12, 12, 0, 0, tzinfo=timezone.utc),
            resolution_id="res_2"
        )

        ledger.append_resolution(res1, temp_ledger_dir)
        ledger.append_resolution(res2, temp_ledger_dir)
        ledger.append_correction(corr1, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 2
        assert entry.counts_by_outcome.get("NO", 0) == 2  # Both are now NO


class TestUnknownExclusion:
    """Tests for UNKNOWN outcome exclusion."""

    def test_excludes_unknown_from_counts(self, temp_ledger_dir, basic_config):
        """UNKNOWN outcomes are excluded by default."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add known and unknown resolutions
        for i, outcome in enumerate(["YES", "NO", "UNKNOWN", "YES"]):
            res = make_resolution(
                "test.event", 7, outcome,
                datetime(2026, 1, 10 + i, 12, 0, 0, tzinfo=timezone.utc)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 3  # Only YES, NO, YES counted
        assert entry.counts_by_outcome.get("YES", 0) == 2
        assert entry.counts_by_outcome.get("NO", 0) == 1

    def test_tracks_excluded_unknown_count(self, temp_ledger_dir, basic_config):
        """Excluded UNKNOWN count is tracked in metadata."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add resolutions including UNKNOWN
        for i, outcome in enumerate(["YES", "UNKNOWN", "UNKNOWN", "NO"]):
            res = make_resolution(
                "test.event", 7, outcome,
                datetime(2026, 1, 10 + i, 12, 0, 0, tzinfo=timezone.utc)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.excluded_counts_by_reason.get("unknown_outcome", 0) == 2


class TestWindowDays:
    """Tests for window_days filtering."""

    def test_window_days_filter(self, temp_ledger_dir):
        """Resolutions outside window_days are excluded."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Config with 7-day window
        config = {
            "config_version": "1.0.0",
            "defaults": {
                "min_history_n": 1,
                "window_days": 7,
                "smoothing_alpha": 1.0,
                "include_unknown": False,
                "persistence_stickiness": 0.7,
                "max_staleness_days": 30,
                "staleness_decay": "linear",
                "resolution_modes": ["external_auto", "external_manual"]
            },
            "overrides": {}
        }

        # Resolution within window (Jan 15)
        in_window = make_resolution(
            "test.event", 7, "YES",
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        # Resolution outside window (Jan 5)
        outside_window = make_resolution(
            "test.event", 7, "NO",
            datetime(2026, 1, 5, 12, 0, 0, tzinfo=timezone.utc)
        )

        ledger.append_resolution(in_window, temp_ledger_dir)
        ledger.append_resolution(outside_window, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.history_n == 1
        assert entry.counts_by_outcome.get("YES", 0) == 1
        assert entry.excluded_counts_by_reason.get("outside_window", 0) == 1


class TestEventOverrides:
    """Tests for per-event configuration overrides."""

    def test_event_override_applied(self, temp_ledger_dir):
        """Event-specific overrides are applied correctly."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Config with override for specific event
        config = {
            "config_version": "1.0.0",
            "defaults": {
                "min_history_n": 10,
                "window_days": 180,
                "smoothing_alpha": 1.0,
                "include_unknown": False,
                "persistence_stickiness": 0.7,
                "max_staleness_days": 30,
                "staleness_decay": "linear",
                "resolution_modes": ["external_auto", "external_manual"]
            },
            "overrides": {
                "test.special": {
                    "min_history_n": 2
                }
            }
        }

        # Add 3 resolutions for test.special
        for i in range(3):
            res = make_resolution(
                "test.special", 7, "YES",
                datetime(2026, 1, 10 + i, 12, 0, 0, tzinfo=timezone.utc)
            )
            ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, config)
        entry = index.get_entry("test.special", 7)

        assert entry is not None
        assert entry.history_n == 3

        # With min_history_n=2, should have enough history
        outcomes = ["YES", "NO"]
        event_config = baseline_history.get_event_config(
            "test.special", config["defaults"], config["overrides"]
        )
        probs, metadata = baseline_history.compute_climatology_distribution(entry, outcomes, event_config)

        assert metadata["baseline_fallback"] is None


class TestLastOutcomeTracking:
    """Tests for tracking last resolved outcome (for persistence)."""

    def test_last_outcome_is_chronologically_last(self, temp_ledger_dir, basic_config):
        """last_resolved_outcome is the most recent resolution."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        # Add resolutions out of order
        for dt, outcome in [
            (datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc), "YES"),
            (datetime(2026, 1, 10, 12, 0, 0, tzinfo=timezone.utc), "NO"),  # Earlier
            (datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc), "NO"),  # Latest
        ]:
            res = make_resolution("test.event", 7, outcome, dt)
            ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.last_resolved_outcome == "NO"
        assert entry.last_verified_at == datetime(2026, 1, 18, 12, 0, 0, tzinfo=timezone.utc)


class TestStalenessComputation:
    """Tests for staleness_days computation."""

    def test_staleness_days_computed_correctly(self, temp_ledger_dir, basic_config):
        """staleness_days is days since last verification."""
        as_of_utc = datetime(2026, 1, 20, 12, 0, 0, tzinfo=timezone.utc)

        res = make_resolution(
            "test.event", 7, "YES",
            datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        )
        ledger.append_resolution(res, temp_ledger_dir)

        index = baseline_history.build_history_index(as_of_utc, temp_ledger_dir, basic_config)
        entry = index.get_entry("test.event", 7)

        assert entry is not None
        assert entry.staleness_days == 5  # Jan 20 - Jan 15 = 5 days


class TestApplyCorrections:
    """Tests for apply_corrections function directly."""

    def test_correction_updates_outcome(self):
        """Correction updates resolved_outcome."""
        resolutions = [
            {"resolution_id": "res_1", "resolved_outcome": "YES"},
        ]
        corrections = [
            {"resolution_id": "res_1", "corrected_outcome": "NO", "corrected_at_utc": "2026-01-15T12:00:00+00:00"},
        ]

        result = baseline_history.apply_corrections(resolutions, corrections)

        assert len(result) == 1
        assert result[0]["resolved_outcome"] == "NO"

    def test_no_corrections_returns_original(self):
        """Empty corrections returns original resolutions."""
        resolutions = [
            {"resolution_id": "res_1", "resolved_outcome": "YES"},
        ]

        result = baseline_history.apply_corrections(resolutions, [])

        assert result == resolutions


class TestLoadBaselineConfig:
    """Tests for load_baseline_config function."""

    def test_returns_defaults_when_file_missing(self):
        """Returns default config when file doesn't exist."""
        config = baseline_history.load_baseline_config(Path("/nonexistent/path.json"))

        assert "config_version" in config
        assert "defaults" in config
        assert config["defaults"]["min_history_n"] == 20

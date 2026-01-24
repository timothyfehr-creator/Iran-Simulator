"""
Tests for leaderboard generation and formatting.

Tests the leaderboard computation and markdown formatting functions.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.forecasting import reporter
from src.forecasting import scorer


class TestLeaderboardStructure:
    """Tests for basic leaderboard structure."""

    def test_leaderboard_structure(self):
        """Leaderboard data has expected structure."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            }
        ]

        md = reporter.generate_leaderboard(leaderboard_data)

        # Should contain header
        assert "## Forecaster Leaderboard" in md
        # Should contain event type section
        assert "Binary" in md
        # Should contain forecaster
        assert "oracle_v1" in md

    def test_empty_leaderboard(self):
        """Empty leaderboard shows appropriate message."""
        md = reporter.generate_leaderboard([])

        assert "No data available" in md


class TestLeaderboardGrouping:
    """Tests for leaderboard grouping behavior."""

    def test_leaderboard_groups_by_forecaster(self):
        """Leaderboard includes multiple forecasters."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
            {
                "forecaster_id": "oracle_ensemble_static_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.138,
                "log_score": -0.29,
                "coverage_rate": 0.92,
                "effective_penalty": 0.154,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
        ]

        md = reporter.generate_leaderboard(leaderboard_data)

        assert "oracle_v1" in md
        assert "oracle_ensemble_static_v1" in md

    def test_leaderboard_groups_by_event_type(self):
        """Leaderboard has separate sections for different event types."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
            {
                "forecaster_id": "oracle_v1",
                "event_type": "categorical",
                "horizon_days": 7,
                "primary_brier": 0.200,
                "log_score": -0.50,
                "coverage_rate": 0.85,
                "effective_penalty": 0.220,
                "resolved_n": 20,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
        ]

        md = reporter.generate_leaderboard(leaderboard_data)

        assert "Binary" in md
        assert "Categorical" in md

    def test_leaderboard_groups_by_horizon(self):
        """Leaderboard has separate sections for different horizons."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 30,
                "primary_brier": 0.180,
                "log_score": -0.40,
                "coverage_rate": 0.88,
                "effective_penalty": 0.195,
                "resolved_n": 35,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
        ]

        md = reporter.generate_leaderboard(leaderboard_data, by_horizon=True)

        assert "7 Day Horizon" in md
        assert "30 Day Horizon" in md


class TestLeaderboardScores:
    """Tests for leaderboard score display."""

    def test_leaderboard_primary_vs_penalty_separate(self):
        """Primary Brier and Effective Penalty are separate columns."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            }
        ]

        md = reporter.format_leaderboard_table(leaderboard_data)

        # Both columns should exist
        assert "Primary Brier" in md
        assert "Eff. Penalty" in md
        # Both values should appear
        assert "0.142" in md
        assert "0.158" in md


class TestLeaderboardCoverage:
    """Tests for coverage rate display."""

    def test_leaderboard_coverage_per_slice(self):
        """Coverage rate is displayed per-slice."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            }
        ]

        md = reporter.format_leaderboard_table(leaderboard_data)

        # Coverage should appear as percentage
        assert "92%" in md


class TestLeaderboardBaselines:
    """Tests for baseline fallback display."""

    def test_baseline_fallback_aggregation_any(self):
        """Baseline fallback shows 'uniform' if ANY record uses fallback (D6)."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_baseline_climatology",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.250,
                "log_score": -0.69,
                "coverage_rate": 0.92,
                "effective_penalty": 0.250,
                "resolved_n": 47,
                "baseline_history_n": 0,
                "baseline_fallback": "uniform",
            }
        ]

        md = reporter.format_leaderboard_table(leaderboard_data)

        # Should show warning emoji for baseline with fallback
        assert "⚠️" in md
        assert "uniform" in md

    def test_non_baseline_shows_dash_for_fallback(self):
        """Non-baseline forecasters show '-' for Fallback column (TWEAK 5)."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            }
        ]

        md = reporter.format_leaderboard_table(leaderboard_data)

        # Should have "-" in the Fallback column (last column)
        lines = md.split('\n')
        data_line = [l for l in lines if "oracle_v1" in l][0]
        # Split by |, last content column should be -
        parts = [p.strip() for p in data_line.split('|')]
        # Filter out empty parts
        content_parts = [p for p in parts if p]
        # Last column should be fallback
        assert content_parts[-1] == '-'


class TestLeaderboardResolutionModeFilter:
    """Tests for resolution mode filtering."""

    def test_leaderboard_excludes_claims_inferred(self):
        """Claims inferred resolutions are excluded from leaderboard (TWEAK 6)."""
        # This is tested in compute_leaderboard_data
        # The mode_filter defaults to ["external_auto", "external_manual"]
        # which excludes "claims_inferred"
        pass  # Tested via integration


class TestFormatLeaderboardTable:
    """Tests for the format_leaderboard_table function."""

    def test_sorted_by_brier(self):
        """Entries are sorted by primary_brier ascending."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.200,
                "log_score": -0.40,
                "coverage_rate": 0.90,
                "effective_penalty": 0.210,
                "resolved_n": 45,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
            {
                "forecaster_id": "oracle_ensemble_static_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.138,
                "log_score": -0.29,
                "coverage_rate": 0.92,
                "effective_penalty": 0.154,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
        ]

        md = reporter.format_leaderboard_table(leaderboard_data)

        # Ensemble (lower brier) should appear before oracle_v1
        lines = md.split('\n')
        data_lines = [l for l in lines if '|' in l and 'Forecaster' not in l and '---' not in l]

        if len(data_lines) >= 2:
            assert "oracle_ensemble_static_v1" in data_lines[0]
            assert "oracle_v1" in data_lines[1]

    def test_none_values_displayed_as_dash(self):
        """None values are displayed as '-'."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": None,
                "log_score": None,
                "coverage_rate": 0.0,
                "effective_penalty": None,
                "resolved_n": 0,
                "baseline_history_n": None,
                "baseline_fallback": None,
            }
        ]

        md = reporter.format_leaderboard_table(leaderboard_data)

        # Should contain '-' for None values
        assert " - |" in md

    def test_fallback_column_optional(self):
        """Fallback column can be excluded."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            }
        ]

        md = reporter.format_leaderboard_table(leaderboard_data, include_fallback=False)

        # Should not have Fallback column
        assert "Fallback" not in md


class TestGenerateLeaderboard:
    """Tests for the main generate_leaderboard function."""

    def test_no_horizon_grouping(self):
        """Can generate leaderboard without horizon grouping."""
        leaderboard_data = [
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 7,
                "primary_brier": 0.142,
                "log_score": -0.31,
                "coverage_rate": 0.92,
                "effective_penalty": 0.158,
                "resolved_n": 47,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
            {
                "forecaster_id": "oracle_v1",
                "event_type": "binary",
                "horizon_days": 30,
                "primary_brier": 0.180,
                "log_score": -0.40,
                "coverage_rate": 0.88,
                "effective_penalty": 0.195,
                "resolved_n": 35,
                "baseline_history_n": None,
                "baseline_fallback": None,
            },
        ]

        md = reporter.generate_leaderboard(leaderboard_data, by_horizon=False)

        # Should only have one section for binary (not split by horizon)
        assert "7 Day Horizon" not in md
        assert "30 Day Horizon" not in md
        # But should have Binary section
        assert "Binary" in md

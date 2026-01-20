"""
Tests for src/forecasting/scorer.py - Scoring metrics.
"""

import pytest
import tempfile
from pathlib import Path

from src.forecasting import scorer, ledger
from src.forecasting.scorer import ScoringError


@pytest.fixture
def temp_ledger_dir():
    """Create a temporary ledger directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestBrierScore:
    """Tests for Brier score calculation."""

    def test_brier_score_perfect(self, temp_ledger_dir):
        """Test Brier score with perfect predictions."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 1.0, "NO": 0.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.0, "NO": 1.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        brier = scorer.brier_score(forecasts, resolutions)
        assert brier == 0.0

    def test_brier_score_worst(self, temp_ledger_dir):
        """Test Brier score with worst predictions."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.0, "NO": 1.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 1.0, "NO": 0.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        brier = scorer.brier_score(forecasts, resolutions)
        assert brier == 1.0

    def test_brier_score_random(self, temp_ledger_dir):
        """Test Brier score with 50/50 predictions."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.5, "NO": 0.5}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.5, "NO": 0.5}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        brier = scorer.brier_score(forecasts, resolutions)
        # (0.5 - 1)^2 + (0.5 - 0)^2 = 0.25 + 0.25 = 0.5, avg = 0.25
        assert abs(brier - 0.25) < 1e-6

    def test_brier_score_excludes_unknown(self, temp_ledger_dir):
        """Test that UNKNOWN resolutions are excluded."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 1.0, "NO": 0.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.0, "NO": 1.0}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "UNKNOWN"},
        ]

        brier = scorer.brier_score(forecasts, resolutions)
        # Only f1 counts, perfect prediction
        assert brier == 0.0

    def test_brier_score_excludes_abstained(self, temp_ledger_dir):
        """Test that abstained forecasts are excluded."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 1.0, "NO": 0.0}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.0, "NO": 1.0}, "abstain": True},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        brier = scorer.brier_score(forecasts, resolutions)
        assert brier == 0.0

    def test_brier_score_no_valid_pairs(self, temp_ledger_dir):
        """Test error when no valid forecast-resolution pairs."""
        forecasts = [{"forecast_id": "f1", "abstain": True}]
        resolutions = []

        with pytest.raises(ScoringError, match="No valid"):
            scorer.brier_score(forecasts, resolutions)


class TestBrierSkillScore:
    """Tests for Brier skill score calculation."""

    def test_skill_score_better_than_baseline(self):
        """Test skill score when model is better than baseline."""
        skill = scorer.brier_skill_score(0.1, 0.25)
        # 1 - (0.1 / 0.25) = 0.6
        assert abs(skill - 0.6) < 1e-6

    def test_skill_score_same_as_baseline(self):
        """Test skill score when model equals baseline."""
        skill = scorer.brier_skill_score(0.25, 0.25)
        assert abs(skill - 0.0) < 1e-6

    def test_skill_score_worse_than_baseline(self):
        """Test skill score when model is worse than baseline."""
        skill = scorer.brier_skill_score(0.5, 0.25)
        # 1 - (0.5 / 0.25) = -1.0
        assert abs(skill - (-1.0)) < 1e-6


class TestClimatologyBaseline:
    """Tests for climatology baseline calculation."""

    def test_climatology_bootstrap_small_n(self):
        """Test that small samples return 0.5 bootstrap."""
        resolutions = [
            {"resolved_outcome": "YES"} for _ in range(10)
        ]

        p_clim = scorer.climatology_baseline(resolutions)
        assert p_clim == 0.5  # Bootstrap for N < 20

    def test_climatology_large_n(self):
        """Test climatology with sufficient samples."""
        resolutions = (
            [{"resolved_outcome": "YES"} for _ in range(15)] +
            [{"resolved_outcome": "NO"} for _ in range(5)]
        )

        p_clim = scorer.climatology_baseline(resolutions)
        # 15 YES out of 20 = 0.75
        assert abs(p_clim - 0.75) < 1e-6

    def test_climatology_excludes_unknown(self):
        """Test that UNKNOWN outcomes don't count."""
        resolutions = (
            [{"resolved_outcome": "YES"} for _ in range(20)] +
            [{"resolved_outcome": "UNKNOWN"} for _ in range(10)]
        )

        p_clim = scorer.climatology_baseline(resolutions)
        assert abs(p_clim - 1.0) < 1e-6


class TestCalibrationBins:
    """Tests for calibration binning."""

    def test_calibration_bins_structure(self):
        """Test calibration bins have correct structure."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.15}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.85}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "NO"},
            {"forecast_id": "f2", "resolved_outcome": "YES"},
        ]

        result = scorer.calibration_bins(forecasts, resolutions)

        assert "bins" in result
        assert len(result["bins"]) == 10
        assert "calibration_error" in result
        assert "total_forecasts" in result

    def test_calibration_bins_assignment(self):
        """Test that forecasts go to correct bins."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.05}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.95}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "NO"},
            {"forecast_id": "f2", "resolved_outcome": "YES"},
        ]

        result = scorer.calibration_bins(forecasts, resolutions)
        bins = result["bins"]

        # First bin (0.0-0.1) should have f1
        assert bins[0]["count"] == 1
        # Last bin (0.9-1.0) should have f2
        assert bins[9]["count"] == 1
        # Other bins should be empty
        for i in range(1, 9):
            assert bins[i]["count"] == 0

    def test_calibration_perfect(self):
        """Test calibration error with perfectly calibrated forecasts."""
        # 20 forecasts at 0.5, half resolve YES, half NO
        forecasts = [
            {"forecast_id": f"f{i}", "probabilities": {"YES": 0.5}, "abstain": False}
            for i in range(20)
        ]
        resolutions = (
            [{"forecast_id": f"f{i}", "resolved_outcome": "YES"} for i in range(10)] +
            [{"forecast_id": f"f{i}", "resolved_outcome": "NO"} for i in range(10, 20)]
        )

        result = scorer.calibration_bins(forecasts, resolutions)
        # Perfect calibration: mean_forecast = 0.5, observed_frequency = 0.5
        # All in bin [0.5-0.6), error = 0
        assert result["calibration_error"] < 0.01


class TestPersistenceBaseline:
    """Tests for persistence baseline calculation."""

    def test_persistence_baseline_no_prior(self):
        """Test persistence uses 0.5 when no prior resolution."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "test.event", "as_of_utc": "2026-01-01T00:00:00Z"},
        ]
        resolutions = []

        preds = scorer.persistence_baseline(forecasts, resolutions)
        assert preds["f1"] == 0.5

    def test_persistence_baseline_uses_last_outcome(self):
        """Test persistence uses last resolved outcome."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "test.event", "as_of_utc": "2026-01-01T00:00:00Z"},
            {"forecast_id": "f2", "event_id": "test.event", "as_of_utc": "2026-01-02T00:00:00Z"},
            {"forecast_id": "f3", "event_id": "test.event", "as_of_utc": "2026-01-03T00:00:00Z"},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "NO"},
        ]

        preds = scorer.persistence_baseline(forecasts, resolutions)
        assert preds["f1"] == 0.5  # No prior
        assert preds["f2"] == 1.0  # After f1 resolved YES
        assert preds["f3"] == 0.0  # After f2 resolved NO

    def test_persistence_baseline_per_event(self):
        """Test persistence tracks each event separately."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "econ.test", "as_of_utc": "2026-01-01T00:00:00Z"},
            {"forecast_id": "f2", "event_id": "security.test", "as_of_utc": "2026-01-01T00:00:00Z"},
            {"forecast_id": "f3", "event_id": "econ.test", "as_of_utc": "2026-01-02T00:00:00Z"},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
        ]

        preds = scorer.persistence_baseline(forecasts, resolutions)
        assert preds["f2"] == 0.5  # Different event, no prior
        assert preds["f3"] == 1.0  # Same event (econ.test), uses f1's outcome

    def test_persistence_ignores_unknown(self):
        """Test that UNKNOWN resolutions don't update persistence."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "test.event", "as_of_utc": "2026-01-01T00:00:00Z"},
            {"forecast_id": "f2", "event_id": "test.event", "as_of_utc": "2026-01-02T00:00:00Z"},
            {"forecast_id": "f3", "event_id": "test.event", "as_of_utc": "2026-01-03T00:00:00Z"},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "UNKNOWN"},
        ]

        preds = scorer.persistence_baseline(forecasts, resolutions)
        assert preds["f3"] == 1.0  # Should still be YES from f1, f2 was UNKNOWN


class TestPersistenceBrier:
    """Tests for persistence Brier score."""

    def test_persistence_brier_basic(self):
        """Test persistence Brier score calculation."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "test.event", "as_of_utc": "2026-01-01T00:00:00Z", "abstain": False},
            {"forecast_id": "f2", "event_id": "test.event", "as_of_utc": "2026-01-02T00:00:00Z", "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "YES"},
        ]

        brier = scorer.persistence_brier(forecasts, resolutions)
        # f1: pred=0.5, outcome=1 -> (0.5-1)^2 = 0.25
        # f2: pred=1.0 (from f1), outcome=1 -> (1-1)^2 = 0
        # avg = 0.125
        assert abs(brier - 0.125) < 1e-6


class TestLogScore:
    """Tests for log score calculation."""

    def test_log_score_perfect_yes(self):
        """Test log score with perfect YES prediction."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.99}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
        ]

        log = scorer.log_score(forecasts, resolutions)
        # log(0.99) ≈ -0.01
        assert log > -0.02

    def test_log_score_perfect_no(self):
        """Test log score with perfect NO prediction."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.01}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "NO"},
        ]

        log = scorer.log_score(forecasts, resolutions)
        # log(1-0.01) = log(0.99) ≈ -0.01
        assert log > -0.02

    def test_log_score_bad_prediction(self):
        """Test log score with wrong prediction."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.01}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
        ]

        log = scorer.log_score(forecasts, resolutions)
        # log(0.01) ≈ -4.6
        assert log < -4.0

    def test_log_score_random(self):
        """Test log score with 50/50 prediction."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.5}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
        ]

        log = scorer.log_score(forecasts, resolutions)
        # log(0.5) ≈ -0.693
        assert abs(log - (-0.693)) < 0.01

    def test_log_score_excludes_unknown(self):
        """Test that UNKNOWN resolutions are excluded."""
        forecasts = [
            {"forecast_id": "f1", "probabilities": {"YES": 0.99}, "abstain": False},
            {"forecast_id": "f2", "probabilities": {"YES": 0.01}, "abstain": False},
        ]
        resolutions = [
            {"forecast_id": "f1", "resolved_outcome": "YES"},
            {"forecast_id": "f2", "resolved_outcome": "UNKNOWN"},
        ]

        log = scorer.log_score(forecasts, resolutions)
        # Only f1 counts
        assert log > -0.02


class TestComputeScores:
    """Tests for complete score computation."""

    def test_compute_scores_with_data(self, temp_ledger_dir):
        """Test computing scores with ledger data."""
        # Add forecasts
        for i in range(25):
            ledger.append_forecast({
                "forecast_id": f"fcst_{i}",
                "event_id": "test.event",
                "horizon_days": 7,
                "as_of_utc": f"2026-01-{i+1:02d}T00:00:00Z",
                "probabilities": {"YES": 0.7, "NO": 0.3},
                "abstain": False
            }, temp_ledger_dir)

        # Resolve them (70% YES to match forecast)
        for i in range(25):
            outcome = "YES" if i < 17 else "NO"
            ledger.append_resolution({
                "resolution_id": f"res_{i}",
                "forecast_id": f"fcst_{i}",
                "event_id": "test.event",
                "horizon_days": 7,
                "resolved_outcome": outcome
            }, temp_ledger_dir)

        scores = scorer.compute_scores(temp_ledger_dir)

        assert "brier_score" in scores
        assert "skill_score" in scores
        assert "calibration" in scores
        assert scores["counts"]["resolved"] == 25
        # New metrics from Fix E
        assert "persistence_brier" in scores
        assert "persistence_skill_score" in scores
        assert "log_score" in scores

    def test_compute_scores_no_data(self, temp_ledger_dir):
        """Test computing scores with empty ledger."""
        scores = scorer.compute_scores(temp_ledger_dir)

        assert scores["counts"]["total_forecasts"] == 0
        assert "scoring_note" in scores

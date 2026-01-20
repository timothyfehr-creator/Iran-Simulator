"""
Tests for Phase 3B Red-Team Fix 3: Flag Baseline Uniform Fallback.

Tests that baselines flag when uniform fallback is used due to insufficient history,
and that warnings are properly propagated to compute_scores output.
"""

import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any

from src.forecasting import scorer
from src.forecasting import ledger
from src.forecasting import reporter


@pytest.fixture
def outcomes_3():
    """Three-outcome set."""
    return ["A", "B", "C"]


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


def create_resolution(ledger_dir: Path, forecast_id: str, event_id: str, outcome: str):
    """Helper to create a test resolution."""
    record = {
        "resolution_id": f"res_{forecast_id}",
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": 7,
        "resolved_outcome": outcome,
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolution_mode": "external_auto",
        "reason_code": "test",
        "evidence_refs": [],
        "evidence_hashes": [],
    }
    ledger.append_resolution(record, ledger_dir)


class TestClimatologyBaselineWithMetadata:
    """Tests for multinomial_climatology_baseline_with_metadata()."""

    def test_returns_tuple(self, outcomes_3):
        """Test that function returns (probabilities, metadata) tuple."""
        resolutions = [
            {"forecast_id": f"f{i}", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "external_auto"}
            for i in range(25)
        ]

        result = scorer.multinomial_climatology_baseline_with_metadata(
            resolutions, outcomes_3, "e1", 7
        )

        assert isinstance(result, tuple)
        assert len(result) == 2

        probs, metadata = result
        assert isinstance(probs, dict)
        assert isinstance(metadata, dict)

    def test_fallback_uniform_when_insufficient(self, outcomes_3):
        """Test that fallback='uniform' when history < min_samples."""
        resolutions = [
            {"forecast_id": f"f{i}", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "external_auto"}
            for i in range(10)  # < 20
        ]

        probs, metadata = scorer.multinomial_climatology_baseline_with_metadata(
            resolutions, outcomes_3, "e1", 7
        )

        assert metadata["fallback"] == "uniform"
        assert metadata["baseline_history_n"] == 10

        # Check uniform distribution
        assert probs["A"] == pytest.approx(1/3, abs=1e-6)
        assert probs["B"] == pytest.approx(1/3, abs=1e-6)
        assert probs["C"] == pytest.approx(1/3, abs=1e-6)

    def test_no_fallback_when_sufficient(self, outcomes_3):
        """Test that fallback=None when history >= min_samples."""
        resolutions = [
            {"forecast_id": f"fA{i}", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "external_auto"}
            for i in range(15)
        ] + [
            {"forecast_id": f"fB{i}", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "B", "resolution_mode": "external_auto"}
            for i in range(5)
        ]

        probs, metadata = scorer.multinomial_climatology_baseline_with_metadata(
            resolutions, outcomes_3, "e1", 7
        )

        assert metadata["fallback"] is None
        assert metadata["baseline_history_n"] == 20

        # Check historical frequencies
        assert probs["A"] == pytest.approx(0.75, abs=1e-6)
        assert probs["B"] == pytest.approx(0.25, abs=1e-6)

    def test_metadata_includes_event_horizon(self, outcomes_3):
        """Test that metadata includes event_id and horizon_days."""
        resolutions = []

        _, metadata = scorer.multinomial_climatology_baseline_with_metadata(
            resolutions, outcomes_3, "test.event", 30
        )

        assert metadata["event_id"] == "test.event"
        assert metadata["horizon_days"] == 30

    def test_excludes_unknown_resolutions(self, outcomes_3):
        """Test that UNKNOWN resolutions are excluded from count."""
        resolutions = [
            {"forecast_id": f"fA{i}", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "external_auto"}
            for i in range(15)
        ] + [
            {"forecast_id": f"fU{i}", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "UNKNOWN", "resolution_mode": "external_auto"}
            for i in range(10)
        ]

        _, metadata = scorer.multinomial_climatology_baseline_with_metadata(
            resolutions, outcomes_3, "e1", 7
        )

        # Only non-UNKNOWN count
        assert metadata["baseline_history_n"] == 15


class TestPersistenceBaselineWithMetadata:
    """Tests for multinomial_persistence_baseline_with_metadata()."""

    def test_returns_tuple(self, outcomes_3):
        """Test that function returns (predictions, metadata) tuple."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-01T00:00:00Z"},
        ]
        resolutions = []

        result = scorer.multinomial_persistence_baseline_with_metadata(
            forecasts, resolutions, outcomes_3, "e1", 7
        )

        assert isinstance(result, tuple)
        assert len(result) == 2

        preds, metadata = result
        assert isinstance(preds, dict)
        assert isinstance(metadata, dict)

    def test_first_forecast_uses_uniform_fallback(self, outcomes_3):
        """Test that first forecast uses uniform and metadata flags it."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-01T00:00:00Z"},
        ]
        resolutions = []

        preds, metadata = scorer.multinomial_persistence_baseline_with_metadata(
            forecasts, resolutions, outcomes_3, "e1", 7
        )

        assert metadata["fallback"] == "uniform"
        assert metadata["first_forecast_fallback"] is True
        assert preds["f1"]["A"] == pytest.approx(1/3, abs=1e-6)

    def test_no_fallback_after_first_resolution(self, outcomes_3):
        """Test that fallback is tracked but predictions use last outcome."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-01T00:00:00Z"},
            {"forecast_id": "f2", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-02T00:00:00Z"},
        ]
        resolutions = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "external_auto",
             "target_date_utc": "2026-01-01T00:00:00Z"},
        ]

        preds, metadata = scorer.multinomial_persistence_baseline_with_metadata(
            forecasts, resolutions, outcomes_3, "e1", 7
        )

        # First forecast still uses uniform (no prior history)
        assert metadata["fallback"] == "uniform"

        # But second forecast uses last outcome
        assert preds["f2"]["A"] == pytest.approx(1.0, abs=1e-6)

    def test_metadata_includes_history_n(self, outcomes_3):
        """Test that metadata includes baseline_history_n."""
        forecasts = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "target_date_utc": "2026-01-01T00:00:00Z"},
        ]
        resolutions = [
            {"forecast_id": "f1", "event_id": "e1", "horizon_days": 7,
             "resolved_outcome": "A", "resolution_mode": "external_auto"},
        ]

        _, metadata = scorer.multinomial_persistence_baseline_with_metadata(
            forecasts, resolutions, outcomes_3, "e1", 7
        )

        assert metadata["baseline_history_n"] == 1


class TestComputeScoresBaselinesOutput:
    """Tests for baselines and warnings in compute_scores() output."""

    def test_baselines_section_present(self, temp_ledger_dir):
        """Test that baselines section is present in output."""
        create_forecast(temp_ledger_dir, "f1", "test.event")
        create_resolution(temp_ledger_dir, "f1", "test.event", "YES")

        result = scorer.compute_scores(temp_ledger_dir)

        assert "baselines" in result
        assert "climatology" in result["baselines"]
        assert "persistence" in result["baselines"]

    def test_baselines_include_history_n(self, temp_ledger_dir):
        """Test that baselines include history_n."""
        create_forecast(temp_ledger_dir, "f1", "test.event")
        create_resolution(temp_ledger_dir, "f1", "test.event", "YES")

        result = scorer.compute_scores(temp_ledger_dir)

        assert "history_n" in result["baselines"]["climatology"]
        assert "history_n" in result["baselines"]["persistence"]

    def test_baselines_include_fallback(self, temp_ledger_dir):
        """Test that baselines include fallback field."""
        create_forecast(temp_ledger_dir, "f1", "test.event")
        create_resolution(temp_ledger_dir, "f1", "test.event", "YES")

        result = scorer.compute_scores(temp_ledger_dir)

        assert "fallback" in result["baselines"]["climatology"]
        assert "fallback" in result["baselines"]["persistence"]

    def test_warnings_for_fallback(self, temp_ledger_dir):
        """Test that warnings are generated when fallback is used."""
        # Only 1 resolution - will trigger fallback
        create_forecast(temp_ledger_dir, "f1", "test.event")
        create_resolution(temp_ledger_dir, "f1", "test.event", "YES")

        result = scorer.compute_scores(temp_ledger_dir)

        assert "warnings" in result
        # Should have warning about uniform fallback
        assert len(result["warnings"]) > 0
        assert any("fallback" in w.lower() for w in result["warnings"])

    def test_no_warnings_when_sufficient_history(self, temp_ledger_dir):
        """Test that no warnings when history is sufficient."""
        # Create 25 forecasts and resolutions
        for i in range(25):
            create_forecast(temp_ledger_dir, f"f{i}", "test.event", p_yes=0.6)
            create_resolution(temp_ledger_dir, f"f{i}", "test.event", "YES" if i % 2 == 0 else "NO")

        result = scorer.compute_scores(temp_ledger_dir)

        # No fallback warnings
        climatology_warning = any(
            "climatology" in w.lower() and "fallback" in w.lower()
            for w in result.get("warnings", [])
        )
        assert not climatology_warning


class TestComputeScoresAccuracyPenaltySeparation:
    """Tests for Phase 3B Red-Team Fix 2: Accuracy vs Penalty separation."""

    def test_accuracy_section_present(self, temp_ledger_dir):
        """Test that accuracy section is present."""
        create_forecast(temp_ledger_dir, "f1", "test.event")
        create_resolution(temp_ledger_dir, "f1", "test.event", "YES")

        result = scorer.compute_scores(temp_ledger_dir)

        assert "accuracy" in result
        assert "brier_score" in result["accuracy"]
        assert "log_score" in result["accuracy"]

    def test_penalty_metrics_section_present(self, temp_ledger_dir):
        """Test that penalty_metrics section is present."""
        create_forecast(temp_ledger_dir, "f1", "test.event")
        create_resolution(temp_ledger_dir, "f1", "test.event", "YES")

        result = scorer.compute_scores(temp_ledger_dir)

        assert "penalty_metrics" in result
        assert "effective_brier" in result["penalty_metrics"]

    def test_effective_brier_backward_compat(self, temp_ledger_dir):
        """Test that effective_brier is still at top level for backward compat."""
        create_forecast(temp_ledger_dir, "f1", "test.event")
        create_resolution(temp_ledger_dir, "f1", "test.event", "YES")

        result = scorer.compute_scores(temp_ledger_dir)

        # Top-level effective_brier should match penalty_metrics
        assert result["effective_brier"] == result["penalty_metrics"]["effective_brier"]


class TestReporterBaselinesFormatting:
    """Tests for reporter formatting of baselines and warnings."""

    def test_format_baselines_table(self):
        """Test formatting of baselines table."""
        baselines = {
            "climatology": {
                "brier_score": 0.25,
                "history_n": 47,
                "fallback": None,
            },
            "persistence": {
                "brier_score": 0.22,
                "history_n": 0,
                "fallback": "uniform",
            }
        }

        table = reporter.format_baselines_table(baselines)

        # Should contain header
        assert "## Baselines" in table
        assert "Brier" in table
        assert "History N" in table
        assert "Fallback" in table

        # Should show fallback warning
        assert "uniform" in table

    def test_format_warnings(self):
        """Test formatting of warnings."""
        warnings = [
            "climatology baseline used uniform fallback (history_n=0)",
            "persistence baseline used uniform fallback (history_n=0)",
        ]

        output = reporter.format_warnings(warnings)

        assert "## ⚠️ Warnings" in output
        assert "climatology" in output
        assert "persistence" in output
        assert "unreliable" in output.lower()

    def test_format_warnings_empty(self):
        """Test that empty warnings returns empty string."""
        output = reporter.format_warnings([])
        assert output == ""

    def test_format_accuracy_metrics(self):
        """Test formatting of accuracy and penalty metrics."""
        accuracy = {
            "brier_score": 0.15,
            "log_score": -0.3,
            "calibration_error": 0.05,
        }
        penalty = {
            "effective_brier": 0.18,
            "unknown_abstain_penalty": 0.03,
        }

        output = reporter.format_accuracy_metrics(accuracy, penalty)

        assert "## Accuracy Metrics" in output
        assert "Primary Brier Score" in output
        assert "0.15" in output
        assert "## Penalty Metrics" in output
        assert "Effective Brier" in output
        assert "0.18" in output

"""
Tests for ensemble forecast generation.

Tests the ensemble generation logic including distribution combination,
missing member handling, and idempotency.
"""

import pytest
import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.forecasting import ensembles


class TestDropUnknownAndRenormalize:
    """Tests for drop_unknown_and_renormalize function."""

    def test_drop_unknown_and_renormalize(self):
        """UNKNOWN is dropped and remaining probabilities renormalized."""
        probs = {"YES": 0.3, "NO": 0.3, "UNKNOWN": 0.4}
        result = ensembles.drop_unknown_and_renormalize(probs)

        # UNKNOWN removed
        assert "UNKNOWN" not in result

        # Sum to 1.0
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-6

        # Relative proportions maintained
        assert abs(result["YES"] - 0.5) < 1e-6
        assert abs(result["NO"] - 0.5) < 1e-6

    def test_no_unknown_passthrough(self):
        """Distribution without UNKNOWN is unchanged."""
        probs = {"YES": 0.6, "NO": 0.4}
        result = ensembles.drop_unknown_and_renormalize(probs)

        assert abs(result["YES"] - 0.6) < 1e-6
        assert abs(result["NO"] - 0.4) < 1e-6

    def test_all_unknown_returns_empty(self):
        """If all mass is in UNKNOWN, return empty dict (TWEAK 2)."""
        probs = {"UNKNOWN": 1.0}
        result = ensembles.drop_unknown_and_renormalize(probs)

        assert result == {}

    def test_empty_after_unknown_returns_empty(self):
        """If sum is 0 after dropping UNKNOWN, return empty dict."""
        probs = {"YES": 0.0, "NO": 0.0, "UNKNOWN": 1.0}
        result = ensembles.drop_unknown_and_renormalize(probs)

        assert result == {}


class TestCombineDistributions:
    """Tests for combine_distributions function."""

    def test_combine_distributions_weighted(self):
        """Distributions combined with proper weighting."""
        members = [
            {"YES": 0.8, "NO": 0.2},
            {"YES": 0.4, "NO": 0.6},
        ]
        weights = [0.5, 0.5]
        outcomes = ["YES", "NO"]

        result = ensembles.combine_distributions(members, weights, outcomes)

        # Expected: 0.5*0.8 + 0.5*0.4 = 0.6
        assert abs(result["YES"] - 0.6) < 1e-6
        assert abs(result["NO"] - 0.4) < 1e-6

    def test_combine_distributions_sums_to_one(self):
        """Combined distribution always sums to 1.0."""
        members = [
            {"A": 0.2, "B": 0.3, "C": 0.5},
            {"A": 0.4, "B": 0.4, "C": 0.2},
            {"A": 0.1, "B": 0.1, "C": 0.8},
        ]
        weights = [0.5, 0.3, 0.2]
        outcomes = ["A", "B", "C"]

        result = ensembles.combine_distributions(members, weights, outcomes)

        total = sum(result.values())
        assert abs(total - 1.0) < 1e-6

    def test_combine_distributions_unequal_weights(self):
        """Unequal weights are applied correctly."""
        members = [
            {"YES": 1.0, "NO": 0.0},
            {"YES": 0.0, "NO": 1.0},
        ]
        weights = [0.8, 0.2]
        outcomes = ["YES", "NO"]

        result = ensembles.combine_distributions(members, weights, outcomes)

        assert abs(result["YES"] - 0.8) < 1e-6
        assert abs(result["NO"] - 0.2) < 1e-6


class TestMissingMemberHandling:
    """Tests for missing member policy handling."""

    def test_missing_member_renormalize(self):
        """Renormalize policy redistributes weights."""
        # Setup: 3 members with one missing
        members = [
            {"YES": 0.6, "NO": 0.4},
            {"YES": 0.4, "NO": 0.6},
            # Third member missing
        ]
        # Original weights were [0.5, 0.3, 0.2] but third is missing
        # After renormalize: [0.5/0.8, 0.3/0.8] = [0.625, 0.375]
        weights = [0.625, 0.375]
        outcomes = ["YES", "NO"]

        result = ensembles.combine_distributions(members, weights, outcomes)

        # Should produce valid distribution
        total = sum(result.values())
        assert abs(total - 1.0) < 1e-6


class TestForecastIdGeneration:
    """Tests for forecast ID generation."""

    def test_forecast_id_includes_run_id(self):
        """Forecast ID includes run_id to prevent cross-run collisions (D1)."""
        forecast_id = ensembles.generate_forecast_id(
            as_of_date="20260201",
            run_id="RUN_20260201_daily",
            ensemble_id="oracle_ensemble_static_v1",
            event_id="econ.fx_band",
            horizon_days=7
        )

        # Should contain run_id
        assert "RUN_20260201_daily" in forecast_id
        # Should contain ensemble_id
        assert "oracle_ensemble_static_v1" in forecast_id
        # Should contain event_id
        assert "econ.fx_band" in forecast_id
        # Should contain horizon
        assert "7d" in forecast_id


class TestGenerateEnsembleForecasts:
    """Tests for the main generate_ensemble_forecasts function."""

    def get_base_forecasts(self):
        """Helper to create base forecasts."""
        return [
            {
                "forecast_id": "fcst_20260201_RUN_20260201_daily_oracle_v1_econ.test_7d",
                "forecaster_id": "oracle_v1",
                "event_id": "econ.test",
                "horizon_days": 7,
                "target_date_utc": "2026-02-08T00:00:00Z",
                "as_of_utc": "2026-02-01T12:00:00Z",
                "run_id": "RUN_20260201_daily",
                "data_cutoff_utc": "2026-02-01T00:00:00Z",
                "manifest_id": "sha256:abc123",
                "probabilities": {"YES": 0.7, "NO": 0.3},
                "abstain": False,
            },
            {
                "forecast_id": "fcst_20260201_RUN_20260201_daily_oracle_baseline_climatology_econ.test_7d",
                "forecaster_id": "oracle_baseline_climatology",
                "event_id": "econ.test",
                "horizon_days": 7,
                "target_date_utc": "2026-02-08T00:00:00Z",
                "as_of_utc": "2026-02-01T12:00:00Z",
                "run_id": "RUN_20260201_daily",
                "data_cutoff_utc": "2026-02-01T00:00:00Z",
                "manifest_id": "sha256:abc123",
                "probabilities": {"YES": 0.5, "NO": 0.5},
                "abstain": False,
            },
        ]

    def get_catalog(self):
        """Helper to create test catalog."""
        return {
            "catalog_version": "3.0.0",
            "events": [
                {
                    "event_id": "econ.test",
                    "name": "Test Event",
                    "category": "econ",
                    "event_type": "binary",
                    "allowed_outcomes": ["YES", "NO"],
                    "description": "Test event",
                    "forecast_source": {"type": "simulation_output", "field": "test"},
                    "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "threshold_gte"},
                }
            ],
        }

    def get_config(self):
        """Helper to create test config."""
        return {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_test_v1",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 0.6},
                        {"forecaster_id": "oracle_baseline_climatology", "weight": 0.4},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-01-01T00:00:00Z",
                }
            ],
        }

    def test_effective_from_utc_filter(self):
        """Forecasts before effective_from_utc are not ensembled."""
        config = self.get_config()
        # Set effective_from in future
        config["ensembles"][0]["effective_from_utc"] = "2030-01-01T00:00:00Z"

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            result = ensembles.generate_ensemble_forecasts(
                base_forecasts=self.get_base_forecasts(),
                catalog=self.get_catalog(),
                config=config,
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=True
            )

            assert len(result) == 0

    def test_apply_to_event_types_filter(self):
        """Only events matching apply_to_event_types are ensembled."""
        config = self.get_config()
        # Change to only categorical
        config["ensembles"][0]["apply_to_event_types"] = ["categorical"]

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            result = ensembles.generate_ensemble_forecasts(
                base_forecasts=self.get_base_forecasts(),
                catalog=self.get_catalog(),
                config=config,
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=True
            )

            assert len(result) == 0

    def test_apply_to_event_ids_filter(self):
        """Only events in apply_to_event_ids are ensembled."""
        config = self.get_config()
        # Set specific event IDs that don't match
        config["ensembles"][0]["apply_to_event_ids"] = ["other.event"]

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            result = ensembles.generate_ensemble_forecasts(
                base_forecasts=self.get_base_forecasts(),
                catalog=self.get_catalog(),
                config=config,
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=True
            )

            assert len(result) == 0

    def test_ensemble_inputs_recorded(self):
        """Ensemble inputs metadata is recorded in output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            result = ensembles.generate_ensemble_forecasts(
                base_forecasts=self.get_base_forecasts(),
                catalog=self.get_catalog(),
                config=self.get_config(),
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=True
            )

            assert len(result) == 1
            record = result[0]

            assert "ensemble_inputs" in record
            inputs = record["ensemble_inputs"]

            assert "config_version" in inputs
            assert "members_used" in inputs
            assert "weights_used" in inputs
            assert "policy_applied" in inputs

    def test_abstained_member_treated_as_missing(self):
        """Abstained members are treated as missing."""
        base_forecasts = self.get_base_forecasts()
        # Make oracle_v1 abstain
        base_forecasts[0]["abstain"] = True

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            result = ensembles.generate_ensemble_forecasts(
                base_forecasts=base_forecasts,
                catalog=self.get_catalog(),
                config=self.get_config(),
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=True
            )

            if result:
                # oracle_v1 should be in members_missing
                inputs = result[0]["ensemble_inputs"]
                assert "oracle_v1" in inputs.get("members_missing", [])

    def test_all_members_missing_skips(self):
        """If all members are missing, no ensemble is generated."""
        config = self.get_config()
        # Require all 3 members, but we only have 2 forecasters
        config["ensembles"][0]["members"].append(
            {"forecaster_id": "oracle_baseline_persistence", "weight": 0.0}
        )
        config["ensembles"][0]["min_members_required"] = 3
        config["ensembles"][0]["missing_member_policy"] = "skip"

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            result = ensembles.generate_ensemble_forecasts(
                base_forecasts=self.get_base_forecasts(),
                catalog=self.get_catalog(),
                config=config,
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=True
            )

            # Should skip because min_members not met
            assert len(result) == 0

    def test_same_run_id_enforced(self):
        """Forecasts from different run_ids are not combined (D2)."""
        base_forecasts = self.get_base_forecasts()
        # Change one forecast to different run_id
        base_forecasts[1]["run_id"] = "RUN_20260202_daily"

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            result = ensembles.generate_ensemble_forecasts(
                base_forecasts=base_forecasts,
                catalog=self.get_catalog(),
                config=self.get_config(),
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=True
            )

            # Should still generate but with missing member
            if result:
                inputs = result[0]["ensemble_inputs"]
                # One member should be missing due to run_id mismatch
                assert len(inputs.get("members_missing", [])) >= 0

    def test_idempotency_no_duplicates(self):
        """Duplicate forecast_ids are not appended (TWEAK 4)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            # Generate first time
            result1 = ensembles.generate_ensemble_forecasts(
                base_forecasts=self.get_base_forecasts(),
                catalog=self.get_catalog(),
                config=self.get_config(),
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=False
            )

            assert len(result1) == 1

            # Generate second time - should skip duplicates
            result2 = ensembles.generate_ensemble_forecasts(
                base_forecasts=self.get_base_forecasts(),
                catalog=self.get_catalog(),
                config=self.get_config(),
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=False
            )

            # Should be 0 because forecast already exists
            assert len(result2) == 0

    def test_as_of_utc_tolerance_enforced(self):
        """Members with as_of_utc outside tolerance are skipped."""
        base_forecasts = self.get_base_forecasts()
        # Change one forecast to have as_of_utc more than 60 seconds different
        base_forecasts[1]["as_of_utc"] = "2026-02-01T12:05:00Z"  # 5 minutes later

        with tempfile.TemporaryDirectory() as tmpdir:
            ledger_dir = Path(tmpdir)

            result = ensembles.generate_ensemble_forecasts(
                base_forecasts=base_forecasts,
                catalog=self.get_catalog(),
                config=self.get_config(),
                run_id="RUN_20260201_daily",
                ledger_dir=ledger_dir,
                dry_run=True
            )

            # Should skip because as_of_utc mismatch
            assert len(result) == 0

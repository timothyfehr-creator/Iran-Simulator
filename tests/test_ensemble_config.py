"""
Tests for ensemble configuration validation.

Tests the validate_ensemble_config function against all validation rules.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.forecasting import ensembles


class TestValidConfig:
    """Tests for valid configuration loading."""

    def test_valid_config_loads(self):
        """Valid config returns no errors."""
        config = {
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
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert errors == []

    def test_config_version_required(self):
        """Config version is required."""
        config = {
            "ensembles": [],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("config_version" in e for e in errors)


class TestWeightValidation:
    """Tests for weight validation rules."""

    def test_weights_must_sum_to_one(self):
        """Weights must sum to 1.0."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_bad_weights",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 0.5},
                        {"forecaster_id": "oracle_baseline_climatology", "weight": 0.3},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("sum to" in e for e in errors)

    def test_weights_exact_sum_tolerance(self):
        """Weights within tolerance (1e-6) are accepted."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_tolerance",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 0.333333},
                        {"forecaster_id": "oracle_baseline_climatology", "weight": 0.333333},
                        {"forecaster_id": "oracle_baseline_persistence", "weight": 0.333334},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert errors == []


class TestMemberValidation:
    """Tests for member validation rules."""

    def test_member_forecaster_id_unique(self):
        """Member forecaster_ids must be unique within ensemble."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_duplicate",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 0.5},
                        {"forecaster_id": "oracle_v1", "weight": 0.5},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("unique" in e for e in errors)


class TestPolicyValidation:
    """Tests for missing_member_policy validation."""

    def test_missing_member_policy_valid(self):
        """missing_member_policy must be 'renormalize' or 'skip'."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_bad_policy",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "ignore",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("missing_member_policy" in e for e in errors)


class TestMinMembersValidation:
    """Tests for min_members_required validation."""

    def test_min_members_lte_total_members(self):
        """min_members_required must be <= len(members)."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_too_few",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 5,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("min_members_required" in e for e in errors)


class TestEffectiveFromValidation:
    """Tests for effective_from_utc validation."""

    def test_effective_from_utc_required(self):
        """effective_from_utc is required."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_no_date",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("effective_from_utc" in e for e in errors)

    def test_effective_from_utc_valid_iso(self):
        """effective_from_utc must be valid ISO timestamp."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_bad_date",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "not-a-date",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("effective_from_utc" in e and "ISO" in e for e in errors)


class TestEnsembleIdValidation:
    """Tests for ensemble_id validation."""

    def test_ensemble_id_pattern(self):
        """ensemble_id must match pattern oracle_ensemble_[a-z0-9_]+."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "bad_ensemble_id",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("pattern" in e or "ensemble_id" in e for e in errors)

    def test_ensemble_id_no_conflict_with_reserved(self):
        """ensemble_id must not conflict with reserved names."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_baseline_test",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("reserved" in e or "conflict" in e for e in errors)


class TestApplyToEventIdsValidation:
    """Tests for apply_to_event_ids validation."""

    def test_apply_to_event_ids_optional(self):
        """apply_to_event_ids is optional (null is valid)."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_null_ids",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary"],
                    "apply_to_event_ids": None,
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert errors == []

    def test_apply_to_event_ids_non_empty_if_present(self):
        """If apply_to_event_ids is present, it must be non-empty."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_empty_ids",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary"],
                    "apply_to_event_ids": [],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("non-empty" in e or "apply_to_event_ids" in e for e in errors)


class TestEventTypeValidation:
    """Tests for apply_to_event_types validation."""

    def test_invalid_event_type(self):
        """Invalid event types are rejected."""
        config = {
            "config_version": "1.0.0",
            "ensembles": [
                {
                    "ensemble_id": "oracle_ensemble_bad_type",
                    "enabled": True,
                    "members": [
                        {"forecaster_id": "oracle_v1", "weight": 1.0},
                    ],
                    "apply_to_event_types": ["binary", "invalid_type"],
                    "min_members_required": 1,
                    "missing_member_policy": "renormalize",
                    "effective_from_utc": "2026-02-01T00:00:00Z",
                }
            ],
        }
        errors = ensembles.validate_ensemble_config(config, schema_path=None)
        assert any("invalid" in e.lower() and "event_type" in e.lower() for e in errors)

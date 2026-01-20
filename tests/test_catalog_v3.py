"""
Tests for catalog v3.0.0 features - schema validation and get_forecastable_events() filtering.
"""

import json
import pytest
from pathlib import Path

from src.forecasting import catalog as cat


class TestCatalogV3Validation:
    """Tests for extended v3.0.0 catalog validation."""

    def test_load_v3_catalog(self):
        """Should successfully load the v3.0.0 catalog."""
        catalog_path = Path("config/event_catalog.json")
        catalog_data = cat.load_catalog(catalog_path)
        assert catalog_data["catalog_version"] == "3.0.0"
        assert len(catalog_data["events"]) >= 15  # 5 original + 13 new

    def test_validate_v3_catalog(self):
        """Should successfully validate the v3.0.0 catalog."""
        catalog_path = Path("config/event_catalog.json")
        catalog_data = cat.load_catalog(catalog_path)
        result = cat.validate_catalog(catalog_data)
        assert result is True

    def test_binned_continuous_requires_bin_spec(self):
        """binned_continuous event without bin_spec should fail validation."""
        catalog = {
            "catalog_version": "3.0.0",
            "events": [
                {
                    "event_id": "test.no_bin_spec",
                    "name": "Test Event",
                    "category": "econ",
                    "event_type": "binned_continuous",
                    "allowed_outcomes": ["A", "B", "UNKNOWN"],
                    "description": "Test",
                    "forecast_source": {"type": "baseline_climatology"},
                    "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "bin_map"},
                    "effective_from_utc": "2026-01-20T00:00:00Z"
                }
            ]
        }
        with pytest.raises(cat.CatalogValidationError) as excinfo:
            cat.validate_catalog(catalog, schema_path=None)
        assert "bin_spec" in str(excinfo.value).lower()

    def test_binned_continuous_requires_effective_from_utc(self):
        """binned_continuous event without effective_from_utc should fail validation."""
        catalog = {
            "catalog_version": "3.0.0",
            "events": [
                {
                    "event_id": "test.no_effective",
                    "name": "Test Event",
                    "category": "econ",
                    "event_type": "binned_continuous",
                    "allowed_outcomes": ["A", "B", "UNKNOWN"],
                    "description": "Test",
                    "forecast_source": {"type": "baseline_climatology"},
                    "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "bin_map"},
                    "bin_spec": {
                        "bins": [
                            {"bin_id": "A", "label": "A", "min": None, "max": 100},
                            {"bin_id": "B", "label": "B", "min": 100, "max": None}
                        ]
                    }
                }
            ]
        }
        with pytest.raises(cat.CatalogValidationError) as excinfo:
            cat.validate_catalog(catalog, schema_path=None)
        assert "effective_from_utc" in str(excinfo.value).lower()

    def test_categorical_requires_unknown(self):
        """v3.0.0 categorical event without UNKNOWN should fail validation."""
        catalog = {
            "catalog_version": "3.0.0",
            "events": [
                {
                    "event_id": "test.no_unknown",
                    "name": "Test Event",
                    "category": "info",
                    "event_type": "categorical",
                    "allowed_outcomes": ["A", "B", "C"],  # Missing UNKNOWN
                    "description": "Test",
                    "forecast_source": {"type": "baseline_climatology"},
                    "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "enum_match"},
                    "effective_from_utc": "2026-01-20T00:00:00Z"
                }
            ]
        }
        with pytest.raises(cat.CatalogValidationError) as excinfo:
            cat.validate_catalog(catalog, schema_path=None)
        assert "UNKNOWN" in str(excinfo.value)

    def test_bin_ids_must_match_allowed_outcomes(self):
        """Bin IDs must exactly match allowed_outcomes minus UNKNOWN."""
        catalog = {
            "catalog_version": "3.0.0",
            "events": [
                {
                    "event_id": "test.mismatched",
                    "name": "Test Event",
                    "category": "econ",
                    "event_type": "binned_continuous",
                    "allowed_outcomes": ["A", "B", "C", "UNKNOWN"],
                    "description": "Test",
                    "forecast_source": {"type": "baseline_climatology"},
                    "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "bin_map"},
                    "bin_spec": {
                        "bins": [
                            {"bin_id": "A", "label": "A", "min": None, "max": 100},
                            {"bin_id": "B", "label": "B", "min": 100, "max": None}
                            # Missing C
                        ]
                    },
                    "effective_from_utc": "2026-01-20T00:00:00Z"
                }
            ]
        }
        with pytest.raises(cat.CatalogValidationError) as excinfo:
            cat.validate_catalog(catalog, schema_path=None)
        assert "missing" in str(excinfo.value).lower()

    def test_invalid_horizons_days(self):
        """horizons_days with invalid values should fail validation."""
        catalog = {
            "catalog_version": "3.0.0",
            "events": [
                {
                    "event_id": "test.bad_horizons",
                    "name": "Test Event",
                    "category": "econ",
                    "event_type": "binary",
                    "allowed_outcomes": ["YES", "NO"],
                    "description": "Test",
                    "horizons_days": [1, 7, 99],  # 99 is invalid
                    "forecast_source": {"type": "simulation_output", "field": "test"},
                    "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "threshold_gte", "threshold": 0}
                }
            ]
        }
        with pytest.raises(cat.CatalogValidationError) as excinfo:
            cat.validate_catalog(catalog, schema_path=None)
        assert "horizon" in str(excinfo.value).lower()

    def test_enabled_must_be_boolean(self):
        """enabled flag with non-boolean value should fail validation."""
        catalog = {
            "catalog_version": "3.0.0",
            "events": [
                {
                    "event_id": "test.bad_enabled",
                    "name": "Test Event",
                    "category": "econ",
                    "event_type": "binary",
                    "allowed_outcomes": ["YES", "NO"],
                    "description": "Test",
                    "enabled": "yes",  # Should be boolean
                    "forecast_source": {"type": "simulation_output", "field": "test"},
                    "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "threshold_gte", "threshold": 0}
                }
            ]
        }
        with pytest.raises(cat.CatalogValidationError) as excinfo:
            cat.validate_catalog(catalog, schema_path=None)
        assert "enabled" in str(excinfo.value).lower()

    def test_invalid_forecast_source_type(self):
        """Invalid forecast_source.type should fail validation."""
        catalog = {
            "catalog_version": "3.0.0",
            "events": [
                {
                    "event_id": "test.bad_source",
                    "name": "Test Event",
                    "category": "econ",
                    "event_type": "binary",
                    "allowed_outcomes": ["YES", "NO"],
                    "description": "Test",
                    "forecast_source": {"type": "unknown_type"},
                    "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "threshold_gte", "threshold": 0}
                }
            ]
        }
        with pytest.raises(cat.CatalogValidationError) as excinfo:
            cat.validate_catalog(catalog, schema_path=None)
        assert "forecast_source" in str(excinfo.value).lower()


class TestGetForecastableEvents:
    """Tests for get_forecastable_events() filtering."""

    def test_filters_disabled_events(self):
        """Events with enabled: false should be filtered out."""
        catalog = {
            "events": [
                {
                    "event_id": "enabled.event",
                    "enabled": True,
                    "forecast_source": {"type": "simulation_output"}
                },
                {
                    "event_id": "disabled.event",
                    "enabled": False,
                    "forecast_source": {"type": "simulation_output"}
                },
                {
                    "event_id": "default.enabled",
                    # enabled not specified, defaults to True
                    "forecast_source": {"type": "simulation_output"}
                }
            ]
        }
        forecastable = cat.get_forecastable_events(catalog)
        event_ids = [e["event_id"] for e in forecastable]

        assert "enabled.event" in event_ids
        assert "default.enabled" in event_ids
        assert "disabled.event" not in event_ids

    def test_filters_diagnostic_only_events(self):
        """Events with forecast_source.type=diagnostic_only should be filtered out."""
        catalog = {
            "events": [
                {
                    "event_id": "forecastable.event",
                    "forecast_source": {"type": "simulation_output"}
                },
                {
                    "event_id": "diagnostic.event",
                    "forecast_source": {"type": "diagnostic_only"}
                }
            ]
        }
        forecastable = cat.get_forecastable_events(catalog)
        event_ids = [e["event_id"] for e in forecastable]

        assert "forecastable.event" in event_ids
        assert "diagnostic.event" not in event_ids

    def test_filters_both_disabled_and_diagnostic(self):
        """Events that are both disabled and diagnostic should be filtered out."""
        catalog = {
            "events": [
                {
                    "event_id": "disabled.diagnostic",
                    "enabled": False,
                    "forecast_source": {"type": "diagnostic_only"}
                }
            ]
        }
        forecastable = cat.get_forecastable_events(catalog)
        assert len(forecastable) == 0

    def test_baseline_events_are_forecastable(self):
        """Events with baseline forecast source types should be forecastable if enabled."""
        catalog = {
            "events": [
                {
                    "event_id": "baseline.persistence",
                    "enabled": True,
                    "forecast_source": {"type": "baseline_persistence"}
                },
                {
                    "event_id": "baseline.climatology",
                    "enabled": True,
                    "forecast_source": {"type": "baseline_climatology"}
                }
            ]
        }
        forecastable = cat.get_forecastable_events(catalog)
        event_ids = [e["event_id"] for e in forecastable]

        assert "baseline.persistence" in event_ids
        assert "baseline.climatology" in event_ids

    def test_production_catalog_mvp_events(self):
        """Production catalog should have exactly 3 MVP events enabled."""
        catalog_path = Path("config/event_catalog.json")
        catalog_data = cat.load_catalog(catalog_path)

        # Count enabled events by event_type
        enabled_by_type = {}
        for event in catalog_data["events"]:
            if event.get("enabled", True):
                event_type = event.get("event_type")
                enabled_by_type[event_type] = enabled_by_type.get(event_type, 0) + 1

        # Original 5 binary events + new MVP events
        # econ.fx_band (binned_continuous, enabled)
        # info.internet_level (categorical, enabled)
        # protest.multi_city (binary, enabled but diagnostic_only)
        forecastable = cat.get_forecastable_events(catalog_data)

        # Check that MVP baseline events are forecastable
        mvp_ids = {e["event_id"] for e in forecastable if "effective_from_utc" in e}
        assert "econ.fx_band" in mvp_ids
        assert "info.internet_level" in mvp_ids
        # protest.multi_city is diagnostic_only so not in forecastable


class TestValidateEventBins:
    """Tests for validate_event_bins()"""

    def test_non_binned_event_returns_empty(self):
        """Non-binned_continuous event should return empty errors."""
        event = {"event_type": "binary"}
        errors = cat.validate_event_bins(event)
        assert errors == []

    def test_missing_bin_spec(self):
        """binned_continuous without bin_spec should return error."""
        event = {"event_type": "binned_continuous"}
        errors = cat.validate_event_bins(event)
        assert any("missing" in e.lower() for e in errors)

    def test_bin_ids_mismatch_extra(self):
        """Extra bin IDs not in allowed_outcomes should be flagged."""
        event = {
            "event_type": "binned_continuous",
            "allowed_outcomes": ["A", "UNKNOWN"],
            "bin_spec": {
                "bins": [
                    {"bin_id": "A", "label": "A", "min": None, "max": 100},
                    {"bin_id": "B", "label": "B", "min": 100, "max": None}  # B not in allowed_outcomes
                ]
            }
        }
        errors = cat.validate_event_bins(event)
        assert any("not in allowed_outcomes" in e for e in errors)

    def test_bin_ids_mismatch_missing(self):
        """Missing bin IDs that are in allowed_outcomes should be flagged."""
        event = {
            "event_type": "binned_continuous",
            "allowed_outcomes": ["A", "B", "C", "UNKNOWN"],
            "bin_spec": {
                "bins": [
                    {"bin_id": "A", "label": "A", "min": None, "max": 100},
                    {"bin_id": "B", "label": "B", "min": 100, "max": None}
                    # C is missing
                ]
            }
        }
        errors = cat.validate_event_bins(event)
        assert any("missing from bin_spec" in e for e in errors)


class TestVersionComparison:
    """Tests for version comparison helper."""

    def test_version_gte_equal(self):
        """Equal versions should return True."""
        assert cat._version_gte("3.0.0", "3.0.0") is True

    def test_version_gte_greater_major(self):
        """Greater major version should return True."""
        assert cat._version_gte("4.0.0", "3.0.0") is True

    def test_version_gte_greater_minor(self):
        """Greater minor version should return True."""
        assert cat._version_gte("3.1.0", "3.0.0") is True

    def test_version_gte_greater_patch(self):
        """Greater patch version should return True."""
        assert cat._version_gte("3.0.1", "3.0.0") is True

    def test_version_gte_lesser(self):
        """Lesser version should return False."""
        assert cat._version_gte("2.9.9", "3.0.0") is False

    def test_version_gte_invalid(self):
        """Invalid version should return False."""
        assert cat._version_gte("invalid", "3.0.0") is False

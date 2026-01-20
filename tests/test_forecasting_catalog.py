"""
Tests for src/forecasting/catalog.py - Event catalog loading and validation.
"""

import json
import pytest
import tempfile
from pathlib import Path

from src.forecasting import catalog
from src.forecasting.catalog import CatalogValidationError


class TestLoadCatalog:
    """Tests for catalog loading."""

    def test_load_catalog_success(self):
        """Test loading the default event catalog."""
        cat = catalog.load_catalog(Path("config/event_catalog.json"))

        assert "catalog_version" in cat
        assert "events" in cat
        assert len(cat["events"]) > 0

    def test_load_catalog_file_not_found(self):
        """Test error when catalog file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            catalog.load_catalog(Path("nonexistent/catalog.json"))

    def test_load_catalog_invalid_json(self):
        """Test error when catalog has invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            f.flush()

            with pytest.raises(json.JSONDecodeError):
                catalog.load_catalog(Path(f.name))


class TestValidateCatalog:
    """Tests for catalog validation."""

    def test_validate_catalog_success(self):
        """Test validation of a valid catalog."""
        cat = catalog.load_catalog(Path("config/event_catalog.json"))
        assert catalog.validate_catalog(cat) is True

    def test_validate_catalog_missing_version(self):
        """Test error when catalog_version is missing."""
        cat = {"events": []}
        with pytest.raises(CatalogValidationError, match="catalog_version"):
            catalog.validate_catalog(cat)

    def test_validate_catalog_missing_events(self):
        """Test error when events list is missing."""
        cat = {"catalog_version": "1.0.0"}
        with pytest.raises(CatalogValidationError, match="events"):
            catalog.validate_catalog(cat)

    def test_validate_catalog_events_not_list(self):
        """Test error when events is not a list."""
        cat = {"catalog_version": "1.0.0", "events": "not a list"}
        with pytest.raises(CatalogValidationError, match="must be a list"):
            catalog.validate_catalog(cat)

    def test_validate_catalog_missing_event_field(self):
        """Test error when event is missing required field."""
        cat = {
            "catalog_version": "1.0.0",
            "events": [{"event_id": "test.event"}]  # Missing most required fields
        }
        with pytest.raises(CatalogValidationError, match="missing required field"):
            catalog.validate_catalog(cat)

    def test_validate_catalog_duplicate_event_id(self):
        """Test error when event IDs are duplicated."""
        event = {
            "event_id": "test.duplicate",
            "name": "Test Event",
            "category": "econ",
            "event_type": "binary",
            "allowed_outcomes": ["YES", "NO"],
            "description": "Test",
            "forecast_source": {"type": "diagnostic_only"},
            "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "threshold_gt"}
        }
        cat = {
            "catalog_version": "1.0.0",
            "events": [event, event.copy()]
        }
        with pytest.raises(CatalogValidationError, match="Duplicate event_id"):
            catalog.validate_catalog(cat)

    def test_validate_catalog_invalid_binary_outcomes(self):
        """Test error when binary event has wrong outcomes."""
        cat = {
            "catalog_version": "1.0.0",
            "events": [{
                "event_id": "test.invalid",
                "name": "Test Event",
                "category": "econ",
                "event_type": "binary",
                "allowed_outcomes": ["YES", "NO", "MAYBE"],
                "description": "Test",
                "forecast_source": {"type": "diagnostic_only"},
                "resolution_source": {"type": "compiled_intel", "path": "test", "rule": "threshold_gt"}
            }]
        }
        with pytest.raises(CatalogValidationError, match="binary events must have"):
            catalog.validate_catalog(cat)


class TestGetEvent:
    """Tests for getting events by ID."""

    def test_get_event_found(self):
        """Test getting an existing event."""
        cat = catalog.load_catalog(Path("config/event_catalog.json"))
        event = catalog.get_event(cat, "econ.rial_ge_1_2m")

        assert event is not None
        assert event["event_id"] == "econ.rial_ge_1_2m"
        assert event["category"] == "econ"

    def test_get_event_not_found(self):
        """Test getting a non-existent event."""
        cat = catalog.load_catalog(Path("config/event_catalog.json"))
        event = catalog.get_event(cat, "nonexistent.event")

        assert event is None


class TestListEvents:
    """Tests for listing events."""

    def test_list_events_all(self):
        """Test listing all events."""
        cat = catalog.load_catalog(Path("config/event_catalog.json"))
        events = catalog.list_events(cat)

        assert len(events) == 5
        assert all("event_id" in e for e in events)

    def test_list_events_by_category(self):
        """Test listing events filtered by category."""
        cat = catalog.load_catalog(Path("config/event_catalog.json"))
        econ_events = catalog.list_events(cat, category="econ")

        assert len(econ_events) == 2
        assert all(e["category"] == "econ" for e in econ_events)


class TestEventFiltering:
    """Tests for forecastable vs diagnostic filtering."""

    def test_get_forecastable_events(self):
        """Test getting only forecastable events."""
        cat = catalog.load_catalog(Path("config/event_catalog.json"))
        forecastable = catalog.get_forecastable_events(cat)

        # Should exclude diagnostic_only events
        assert len(forecastable) == 3
        for e in forecastable:
            assert e["forecast_source"]["type"] != "diagnostic_only"

    def test_get_diagnostic_events(self):
        """Test getting only diagnostic events."""
        cat = catalog.load_catalog(Path("config/event_catalog.json"))
        diagnostic = catalog.get_diagnostic_events(cat)

        # Should only include diagnostic_only events
        assert len(diagnostic) == 2
        for e in diagnostic:
            assert e["forecast_source"]["type"] == "diagnostic_only"

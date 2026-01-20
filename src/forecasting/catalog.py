"""
Event catalog loading and validation.

Provides functions to load the event catalog from JSON and validate
event definitions against the expected schema.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

# Try to import jsonschema for full schema validation
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


class CatalogValidationError(Exception):
    """Raised when catalog validation fails."""
    pass


def load_catalog(path: Path = Path("config/event_catalog.json")) -> Dict[str, Any]:
    """
    Load event catalog from JSON file.

    Args:
        path: Path to event_catalog.json

    Returns:
        Parsed catalog dictionary

    Raises:
        FileNotFoundError: If catalog file doesn't exist
        json.JSONDecodeError: If catalog is invalid JSON
    """
    with open(path, 'r') as f:
        return json.load(f)


def validate_catalog(
    catalog: Dict[str, Any],
    schema_path: Optional[Path] = Path("config/schemas/event_catalog.schema.json")
) -> bool:
    """
    Validate catalog against schema and internal consistency rules.

    If jsonschema library is available, performs full JSON Schema validation.
    Otherwise, falls back to manual validation checks:
    - Required top-level fields present
    - Each event has required fields
    - event_id is unique
    - Probabilities in allowed_outcomes are valid
    - resolution_source paths are valid

    Args:
        catalog: Parsed catalog dictionary
        schema_path: Path to JSON schema (default: config/schemas/event_catalog.schema.json)

    Returns:
        True if valid

    Raises:
        CatalogValidationError: If validation fails
    """
    # Use jsonschema if available and schema exists
    if HAS_JSONSCHEMA and schema_path is not None and schema_path.exists():
        try:
            with open(schema_path) as f:
                schema = json.load(f)
            jsonschema.validate(catalog, schema)
        except jsonschema.ValidationError as e:
            # Transform jsonschema errors to our error format
            path = ".".join(str(p) for p in e.absolute_path) if e.absolute_path else ""
            if "is not of type 'array'" in e.message:
                if "events" in path or e.path and "events" in list(e.path):
                    raise CatalogValidationError("'events' must be a list")
            if "is a required property" in e.message:
                prop = e.message.split("'")[1] if "'" in e.message else "unknown"
                if e.absolute_path and len(e.absolute_path) >= 2:
                    event_idx = e.absolute_path[1]
                    raise CatalogValidationError(f"Event {event_idx} missing required field: {prop}")
                raise CatalogValidationError(f"Missing required field: {prop}")
            raise CatalogValidationError(f"Schema validation failed: {e.message}")
        except (IOError, json.JSONDecodeError):
            # Fall through to manual validation if schema can't be loaded
            pass

    # Manual validation (always run for additional consistency checks)
    # Check top-level fields
    required_fields = ["catalog_version", "events"]
    for field in required_fields:
        if field not in catalog:
            raise CatalogValidationError(f"Missing required field: {field}")

    events = catalog.get("events", [])
    if not isinstance(events, list):
        raise CatalogValidationError("'events' must be a list")

    # Check each event
    event_ids = set()
    required_event_fields = [
        "event_id", "name", "category", "event_type",
        "allowed_outcomes", "description", "forecast_source", "resolution_source"
    ]

    for i, event in enumerate(events):
        # Check required fields
        for field in required_event_fields:
            if field not in event:
                raise CatalogValidationError(
                    f"Event {i} missing required field: {field}"
                )

        # Check event_id uniqueness
        event_id = event["event_id"]
        if event_id in event_ids:
            raise CatalogValidationError(f"Duplicate event_id: {event_id}")
        event_ids.add(event_id)

        # Check allowed_outcomes for binary events
        if event["event_type"] == "binary":
            outcomes = event["allowed_outcomes"]
            if set(outcomes) != {"YES", "NO"}:
                raise CatalogValidationError(
                    f"Event {event_id}: binary events must have outcomes ['YES', 'NO']"
                )

        # Check forecast_source has type
        forecast_source = event["forecast_source"]
        if "type" not in forecast_source:
            raise CatalogValidationError(
                f"Event {event_id}: forecast_source missing 'type'"
            )

        # Check resolution_source has required fields
        resolution_source = event["resolution_source"]
        if "type" not in resolution_source:
            raise CatalogValidationError(
                f"Event {event_id}: resolution_source missing 'type'"
            )
        if resolution_source["type"] == "compiled_intel":
            if "path" not in resolution_source:
                raise CatalogValidationError(
                    f"Event {event_id}: compiled_intel resolution requires 'path'"
                )
            if "rule" not in resolution_source:
                raise CatalogValidationError(
                    f"Event {event_id}: compiled_intel resolution requires 'rule'"
                )

    return True


def get_event(catalog: Dict[str, Any], event_id: str) -> Optional[Dict[str, Any]]:
    """
    Get event definition by ID.

    Args:
        catalog: Loaded catalog dictionary
        event_id: Event identifier

    Returns:
        Event definition dict, or None if not found
    """
    for event in catalog.get("events", []):
        if event.get("event_id") == event_id:
            return event
    return None


def list_events(catalog: Dict[str, Any], category: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all events, optionally filtered by category.

    Args:
        catalog: Loaded catalog dictionary
        category: Optional category filter (e.g., "econ", "security")

    Returns:
        List of matching event definitions
    """
    events = catalog.get("events", [])
    if category is None:
        return events
    return [e for e in events if e.get("category") == category]


def get_forecastable_events(catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get events that can be forecasted (not diagnostic-only).

    Args:
        catalog: Loaded catalog dictionary

    Returns:
        List of forecastable event definitions
    """
    events = catalog.get("events", [])
    return [
        e for e in events
        if e.get("forecast_source", {}).get("type") != "diagnostic_only"
    ]


def get_diagnostic_events(catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Get diagnostic-only events (tracked but not scored).

    Args:
        catalog: Loaded catalog dictionary

    Returns:
        List of diagnostic event definitions
    """
    events = catalog.get("events", [])
    return [
        e for e in events
        if e.get("forecast_source", {}).get("type") == "diagnostic_only"
    ]

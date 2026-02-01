"""
Event catalog loading and validation.

Provides functions to load the event catalog from JSON and validate
event definitions against the expected schema.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from . import bins

import jsonschema


# Valid horizons
VALID_HORIZONS = {1, 7, 15, 30}

# Valid forecast source types
VALID_FORECAST_SOURCE_TYPES = {
    "simulation_output",
    "simulation_derived",
    "baseline_persistence",
    "baseline_climatology",
    "diagnostic_only",
}


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
    Otherwise, falls back to manual validation checks.

    Extended validation for v3.0.0 catalogs:
    1. If event_type == "binned_continuous", bin_spec must be present and valid
    2. allowed_outcomes must include "UNKNOWN" for new event types
    3. Bin IDs must match allowed_outcomes (for binned events)
    4. horizons_days must be subset of [1, 7, 15, 30]
    5. forecast_source.type must be valid enum
    6. effective_from_utc required for catalog_version >= 3.0.0 events
    7. enabled flag must be boolean if present

    Args:
        catalog: Parsed catalog dictionary
        schema_path: Path to JSON schema (default: config/schemas/event_catalog.schema.json)

    Returns:
        True if valid

    Raises:
        CatalogValidationError: If validation fails
    """
    # Use jsonschema if available and schema exists
    if schema_path is not None and schema_path.exists():
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

    catalog_version = catalog.get("catalog_version", "1.0.0")
    is_v3_plus = _version_gte(catalog_version, "3.0.0")

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

        event_type = event["event_type"]
        outcomes = event["allowed_outcomes"]

        # Check allowed_outcomes for binary events (allow UNKNOWN for v3+ binary events)
        if event_type == "binary":
            valid_binary = set(outcomes) == {"YES", "NO"} or set(outcomes) == {"YES", "NO", "UNKNOWN"}
            if not valid_binary:
                raise CatalogValidationError(
                    f"Event {event_id}: binary events must have outcomes ['YES', 'NO'] or ['YES', 'NO', 'UNKNOWN']"
                )

        # v3.0.0+ validation: Check allowed_outcomes includes UNKNOWN for new event types
        if is_v3_plus and event_type in ("categorical", "binned_continuous"):
            if "UNKNOWN" not in outcomes:
                raise CatalogValidationError(
                    f"Event {event_id}: {event_type} events must include 'UNKNOWN' in allowed_outcomes"
                )

        # Check forecast_source has type
        forecast_source = event["forecast_source"]
        if "type" not in forecast_source:
            raise CatalogValidationError(
                f"Event {event_id}: forecast_source missing 'type'"
            )

        # Validate forecast_source.type
        fs_type = forecast_source.get("type")
        if fs_type not in VALID_FORECAST_SOURCE_TYPES:
            raise CatalogValidationError(
                f"Event {event_id}: invalid forecast_source.type '{fs_type}'"
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

        # v3.0.0+ validation: horizons_days if present
        if "horizons_days" in event:
            horizons = event["horizons_days"]
            if not isinstance(horizons, list) or len(horizons) < 1:
                raise CatalogValidationError(
                    f"Event {event_id}: horizons_days must be a non-empty array"
                )
            invalid_horizons = set(horizons) - VALID_HORIZONS
            if invalid_horizons:
                raise CatalogValidationError(
                    f"Event {event_id}: invalid horizons_days {invalid_horizons}; valid: {VALID_HORIZONS}"
                )

        # v3.0.0+ validation: enabled flag must be boolean if present
        if "enabled" in event:
            if not isinstance(event["enabled"], bool):
                raise CatalogValidationError(
                    f"Event {event_id}: 'enabled' must be a boolean"
                )

        # v3.0.0+ validation: effective_from_utc required for new events
        if is_v3_plus and event.get("effective_from_utc") is None:
            # Only enforce for new event types (binned_continuous, categorical with UNKNOWN)
            # Existing v2 events don't need it for backward compatibility
            if event_type == "binned_continuous":
                raise CatalogValidationError(
                    f"Event {event_id}: binned_continuous events require 'effective_from_utc'"
                )

        # v3.0.0+ validation: bin_spec for binned_continuous events
        if event_type == "binned_continuous":
            bin_errors = validate_event_bins(event)
            if bin_errors:
                raise CatalogValidationError(
                    f"Event {event_id}: bin validation failed: {'; '.join(bin_errors)}"
                )

    return True


def _version_gte(version: str, target: str) -> bool:
    """
    Check if version >= target using semver comparison.

    Args:
        version: Version string (X.Y.Z)
        target: Target version string (X.Y.Z)

    Returns:
        True if version >= target
    """
    try:
        v_parts = [int(x) for x in version.split(".")[:3]]
        t_parts = [int(x) for x in target.split(".")[:3]]
        # Pad with zeros if needed
        while len(v_parts) < 3:
            v_parts.append(0)
        while len(t_parts) < 3:
            t_parts.append(0)
        return v_parts >= t_parts
    except (ValueError, AttributeError):
        return False


def validate_event_bins(event: Dict[str, Any]) -> List[str]:
    """
    Validate bin_spec if event is binned_continuous.

    Args:
        event: Event definition dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    if event.get("event_type") != "binned_continuous":
        return []

    bin_spec = event.get("bin_spec")
    if not bin_spec:
        return ["binned_continuous event missing bin_spec"]

    errors = bins.validate_bin_spec(bin_spec)

    # Check bin_ids == (allowed_outcomes - {"UNKNOWN"})
    # Must be exact match, not subset - no unused bins or extra outcomes
    bin_ids = {b["bin_id"] for b in bin_spec.get("bins", [])}
    outcomes = set(event.get("allowed_outcomes", []))
    expected_bins = outcomes - {"UNKNOWN"}

    if bin_ids != expected_bins:
        extra_bins = bin_ids - expected_bins
        missing_bins = expected_bins - bin_ids
        if extra_bins:
            errors.append(f"bin_ids {extra_bins} not in allowed_outcomes")
        if missing_bins:
            errors.append(f"allowed_outcomes {missing_bins} missing from bin_spec")

    return errors


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
    Return events that should be processed by forecast generation.

    Filters:
    - enabled == true (or missing, defaults to true)
    - forecast_source.type != "diagnostic_only"

    This prevents non-MVP binned/categorical events from being processed
    before scoring logic exists in Phase 3B.

    Args:
        catalog: Loaded catalog dictionary

    Returns:
        List of forecastable event definitions
    """
    events = []
    for event in catalog.get("events", []):
        # Skip disabled events (default to enabled if not specified)
        if not event.get("enabled", True):
            continue
        # Skip diagnostic-only events
        if event.get("forecast_source", {}).get("type") == "diagnostic_only":
            continue
        events.append(event)
    return events


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

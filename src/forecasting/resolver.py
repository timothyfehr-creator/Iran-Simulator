"""
Resolution logic for forecasts using future runs.

Resolves pending forecasts by examining compiled intelligence from
runs with data cutoff after the target date.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from . import catalog as cat
from . import ledger
from . import evidence
from . import bins
from .ledger import compute_manifest_id
from ..run_utils import (
    list_runs_sorted,
    is_run_valid_for_observe,
    get_run_reliability,
)


class ResolutionError(Exception):
    """Raised when resolution fails."""
    pass


def validate_resolved_outcome(outcome: str, event: Dict[str, Any]) -> bool:
    """
    Validate resolved_outcome against event's allowed_outcomes.

    Args:
        outcome: The resolved outcome string
        event: Event definition from catalog

    Returns:
        True if valid

    Raises:
        ResolutionError: If outcome not in allowed_outcomes
    """
    allowed = set(event.get("allowed_outcomes", []))
    if outcome not in allowed:
        raise ResolutionError(
            f"Invalid resolved_outcome '{outcome}' for event {event.get('event_id')}. "
            f"Allowed: {allowed}"
        )
    return True


def get_resolution_mode(resolution: Dict[str, Any]) -> str:
    """
    Get resolution mode from a resolution record with backward compatibility.

    Old resolutions without resolution_mode are treated as "external_auto"
    for scoring purposes.

    Args:
        resolution: Resolution record dictionary

    Returns:
        Resolution mode string
    """
    return resolution.get("resolution_mode", "external_auto")


def parse_iso_datetime(dt_str: str) -> datetime:
    """
    Parse ISO 8601 datetime string to datetime object.

    Args:
        dt_str: ISO format datetime string

    Returns:
        Parsed datetime with UTC timezone
    """
    # Handle various ISO formats
    dt_str = dt_str.replace('Z', '+00:00')
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def find_resolution_run(
    target_date_utc: datetime,
    runs_dir: Path = Path("runs"),
    max_lag_days: int = 14
) -> Optional[Path]:
    """
    Find a valid run for resolving a forecast.

    Selection criteria:
    1. Run data_cutoff_utc >= target_date_utc
    2. Run data_cutoff_utc <= target_date_utc + max_lag_days
    3. Run passes validity and reliability checks
    4. Returns earliest valid run meeting criteria

    Args:
        target_date_utc: Forecast target date
        runs_dir: Path to runs directory
        max_lag_days: Maximum days after target to accept resolution

    Returns:
        Path to resolution run, or None if not found
    """
    max_cutoff = target_date_utc + timedelta(days=max_lag_days)

    run_names = list_runs_sorted(runs_dir)
    # Reverse to get oldest first (we want earliest valid run after target)
    run_names.reverse()

    for run_name in run_names:
        run_dir = runs_dir / run_name

        # Check basic validity
        if not is_run_valid_for_observe(run_dir):
            continue

        # Check reliability
        is_reliable, _ = get_run_reliability(run_dir)
        if not is_reliable:
            continue

        # Check data cutoff
        manifest_path = run_dir / "run_manifest.json"
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            cutoff_str = manifest.get("data_cutoff_utc")
            if not cutoff_str:
                continue
            cutoff = parse_iso_datetime(cutoff_str)
        except (IOError, json.JSONDecodeError, ValueError):
            continue

        # Check if cutoff is within valid range
        if cutoff >= target_date_utc and cutoff <= max_cutoff:
            return run_dir

    return None


def extract_compiled_value(
    intel: Dict[str, Any],
    path: str
) -> Tuple[Any, bool]:
    """
    Extract value from compiled_intel.json using path.

    Checks both compiled_fields and nested structure.

    Args:
        intel: Compiled intelligence dictionary
        path: Dot-separated path to value

    Returns:
        Tuple of (value, found)
    """
    # First check compiled_fields (flat lookup)
    compiled_fields = intel.get("compiled_fields", {})
    if path in compiled_fields:
        return compiled_fields[path], True

    # Fall back to nested path traversal
    parts = path.split(".")
    current = intel

    for part in parts:
        if not isinstance(current, dict):
            return None, False
        current = current.get(part)
        if current is None:
            return None, False

    return current, True


def apply_resolution_rule(
    value: Any,
    rule: str,
    rule_params: Dict[str, Any],
    event: Dict[str, Any]
) -> Tuple[str, Optional[str]]:
    """
    Apply resolution rule to determine outcome.

    Supported rules:
    - threshold_gte: value >= threshold -> YES
    - threshold_gt: value > threshold -> YES
    - threshold_lte: value <= threshold -> YES
    - threshold_lt: value < threshold -> YES
    - enum_equals: value == target value -> YES
    - enum_in: value in list of values -> YES
    - bin_map: maps numeric value to bin_id using event's bin_spec
    - enum_match: resolved_outcome = value if in allowed_outcomes

    Args:
        value: Value to check
        rule: Rule type
        rule_params: Additional parameters (threshold, values, etc.)
        event: Full event definition (for allowed_outcomes, bin_spec)

    Returns:
        Tuple of (outcome, unknown_reason)
        outcome is "YES", "NO", bin_id, categorical value, or "UNKNOWN"
    """
    if value is None:
        return "UNKNOWN", "missing_value"

    try:
        if rule == "threshold_gte":
            threshold = rule_params.get("threshold")
            return ("YES" if float(value) >= threshold else "NO", None)

        elif rule == "threshold_gt":
            threshold = rule_params.get("threshold")
            return ("YES" if float(value) > threshold else "NO", None)

        elif rule == "threshold_lte":
            threshold = rule_params.get("threshold")
            return ("YES" if float(value) <= threshold else "NO", None)

        elif rule == "threshold_lt":
            threshold = rule_params.get("threshold")
            return ("YES" if float(value) < threshold else "NO", None)

        elif rule == "enum_equals":
            target = rule_params.get("value")
            return ("YES" if str(value).upper() == str(target).upper() else "NO", None)

        elif rule == "enum_in":
            values = rule_params.get("values", [])
            str_value = str(value).upper()
            return ("YES" if str_value in [str(v).upper() for v in values] else "NO", None)

        elif rule == "bin_map":
            # Map numeric value to bin_id using event's bin_spec
            bin_spec = event.get("bin_spec")
            if not bin_spec:
                return "UNKNOWN", "missing_bin_spec"
            bin_id, reason = bins.value_to_bin(value, bin_spec)
            return bin_id, reason

        elif rule == "enum_match":
            # resolved_outcome = value if in allowed_outcomes
            allowed = event.get("allowed_outcomes", [])
            str_value = str(value).upper() if value else None

            if str_value is None:
                return "UNKNOWN", "missing_value"

            # Check if value matches any allowed outcome (case-insensitive)
            for outcome in allowed:
                if str(outcome).upper() == str_value:
                    return outcome, None

            return "UNKNOWN", "value_not_in_outcomes"

        else:
            return "UNKNOWN", f"unsupported_rule:{rule}"

    except (ValueError, TypeError) as e:
        return "UNKNOWN", f"rule_error:{e}"


def resolve_event(
    event: Dict[str, Any],
    forecast: Dict[str, Any],
    resolution_run: Path,
    evidence_dir: Path = evidence.EVIDENCE_DIR
) -> Dict[str, Any]:
    """
    Resolve a single event using a resolution run.

    Args:
        event: Event definition from catalog
        forecast: Forecast record to resolve
        resolution_run: Path to run directory for resolution
        evidence_dir: Directory to store evidence snapshots

    Returns:
        Resolution record dictionary
    """
    event_id = event["event_id"]
    resolution_source = event.get("resolution_source", {})
    auto_resolve = event.get("auto_resolve", False)

    # Load compiled intel from resolution run
    intel_path = resolution_run / "compiled_intel.json"
    try:
        with open(intel_path) as f:
            intel = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        raise ResolutionError(f"Failed to load intel from {resolution_run}: {e}")

    # Load manifest for evidence and compute manifest_id
    manifest_path = resolution_run / "run_manifest.json"
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        resolution_manifest_id = compute_manifest_id(manifest_path)
    except (IOError, json.JSONDecodeError):
        manifest = {}
        resolution_manifest_id = "sha256:unknown"

    # Extract value and apply rule
    source_type = resolution_source.get("type")
    evidence_refs = []
    evidence_hashes = []

    # Determine resolution_mode upfront based on auto_resolve and source_type
    # This is set once and only downgraded for explicit claims_based fallback
    if auto_resolve and source_type == "compiled_intel":
        resolution_mode = "external_auto"
    else:
        resolution_mode = "claims_inferred"

    if source_type == "compiled_intel":
        path = resolution_source.get("path")
        rule = resolution_source.get("rule")

        value, found = extract_compiled_value(intel, path)

        if not found:
            # Check for fallback
            fallback = resolution_source.get("fallback")
            if fallback == "claims_based":
                # Explicit claims_based fallback - downgrade to claims_inferred
                outcome = "UNKNOWN"
                unknown_reason = "requires_claims_resolution"
                resolution_mode = "claims_inferred"
            else:
                # Missing path but NOT claims_based fallback
                # Keep resolution_mode as determined above (external_auto if auto_resolve)
                outcome = "UNKNOWN"
                unknown_reason = "missing_path"
        else:
            # Apply resolution rule
            rule_params = {
                "threshold": resolution_source.get("threshold"),
                "value": resolution_source.get("value"),
                "values": resolution_source.get("values", []),
            }
            outcome, unknown_reason = apply_resolution_rule(value, rule, rule_params, event)
    else:
        outcome = "UNKNOWN"
        unknown_reason = f"unsupported_source_type:{source_type}"
        value = None
        path = None
        rule = None

    # Validate resolved_outcome against catalog
    validate_resolved_outcome(outcome, event)

    # Generate resolution ID
    target_date = forecast.get("target_date_utc", "")[:10].replace("-", "")
    horizon = forecast.get("horizon_days", 0)
    resolution_id = f"res_{target_date}_{event_id}_{horizon}d"

    # Build rule_applied string, handling threshold=0 correctly
    threshold = resolution_source.get("threshold")
    value_param = resolution_source.get("value")
    values_param = resolution_source.get("values")

    if threshold is not None:
        rule_value = threshold
    elif value_param is not None:
        rule_value = value_param
    elif values_param is not None:
        rule_value = values_param
    else:
        rule_value = None

    rule_applied = f"{rule}:{rule_value}" if rule is not None else None

    # Write evidence snapshot for external_auto resolutions
    if resolution_mode == "external_auto" and outcome != "UNKNOWN":
        snapshot_data = {
            "run_id": resolution_run.name,
            "data_cutoff_utc": manifest.get("data_cutoff_utc"),
            "path_used": path,
            "extracted_value": value,
            "rule_applied": rule_applied,
        }
        try:
            ref_path, ref_hash = evidence.write_evidence_snapshot(
                resolution_id, snapshot_data, evidence_dir
            )
            evidence_refs = [ref_path]
            evidence_hashes = [ref_hash]
        except Exception:
            # Evidence write failure shouldn't block resolution
            pass

    # Build resolution record
    record = {
        "resolution_id": resolution_id,
        "forecast_id": forecast["forecast_id"],
        "event_id": event_id,
        "horizon_days": forecast.get("horizon_days"),
        "target_date_utc": forecast.get("target_date_utc"),
        "resolved_outcome": outcome,
        "resolved_value": value,
        "resolved_at_utc": datetime.now(timezone.utc).isoformat(),
        "resolved_by": "oracle_resolver_v2",
        "resolution_mode": resolution_mode,
        "reason_code": rule_applied if rule_applied else "unknown",
        "evidence_refs": evidence_refs,
        "evidence_hashes": evidence_hashes,
        "evidence": {
            "run_id": resolution_run.name,
            "manifest_id": resolution_manifest_id,
            "path_used": resolution_source.get("path"),
            "rule_applied": rule_applied,
        },
        "unknown_reason": unknown_reason,
    }

    return record


def resolve_pending(
    catalog_path: Path = Path("config/event_catalog.json"),
    runs_dir: Path = Path("runs"),
    ledger_dir: Path = ledger.LEDGER_DIR,
    max_lag_days: int = 14,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Resolve all pending forecasts that have reached their target date.

    Events with requires_manual_resolution: true are skipped and left
    in the pending queue for manual adjudication.

    Args:
        catalog_path: Path to event catalog
        runs_dir: Path to runs directory
        ledger_dir: Path to ledger directory
        max_lag_days: Maximum lag for resolution
        dry_run: If True, don't write to ledger

    Returns:
        List of resolution records
    """
    # Load catalog
    catalog_data = cat.load_catalog(catalog_path)

    # Get pending forecasts
    pending = ledger.get_pending_forecasts(ledger_dir)

    now = datetime.now(timezone.utc)
    resolutions = []

    for forecast in pending:
        # Parse target date
        target_str = forecast.get("target_date_utc")
        if not target_str:
            continue

        try:
            target_date = parse_iso_datetime(target_str)
        except ValueError:
            continue

        # Skip if target date not yet reached
        if target_date > now:
            continue

        # Get event definition
        event_id = forecast.get("event_id")
        event = cat.get_event(catalog_data, event_id)
        if event is None:
            continue

        # Skip events requiring manual resolution
        # These stay in the pending queue for manual adjudication
        if event.get("requires_manual_resolution", False):
            continue

        # Find resolution run
        event_max_lag = event.get("max_resolution_lag_days", max_lag_days)
        resolution_run = find_resolution_run(target_date, runs_dir, event_max_lag)

        if resolution_run is None:
            # Can't resolve yet - no valid run with data after target
            continue

        # Resolve
        try:
            record = resolve_event(event, forecast, resolution_run)
            resolutions.append(record)

            if not dry_run:
                ledger.append_resolution(record, ledger_dir)
        except ResolutionError:
            # Skip events that fail to resolve
            continue

    return resolutions

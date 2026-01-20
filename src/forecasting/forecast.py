"""
Forecast generation from simulation outputs.

Generates forecast records for catalog events using simulation results
and compiled intelligence from valid runs.
"""

import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import re

from . import catalog as cat
from . import ledger
from .ledger import compute_manifest_id
from ..run_utils import (
    list_runs_sorted,
    is_run_valid_for_observe,
    is_run_valid_for_simulate,
    get_run_reliability,
)


# Valid forecast horizons in days
VALID_HORIZONS = {1, 7, 15, 30}


class ForecastError(Exception):
    """Raised when forecast generation fails."""
    pass


def hazard_rate_conversion(p_90: float, horizon_days: int) -> float:
    """
    Convert 90-day probability to shorter horizon using hazard rate model.

    Uses exponential model: P_h = 1 - (1 - P_90)^(h/90)

    Args:
        p_90: Probability over 90-day period
        horizon_days: Target horizon in days

    Returns:
        Converted probability for target horizon
    """
    if p_90 <= 0:
        return 0.0
    if p_90 >= 1:
        return 1.0

    return 1.0 - math.pow(1.0 - p_90, horizon_days / 90.0)


def select_valid_run(
    runs_dir: Path = Path("runs"),
    require_simulation: bool = True
) -> Optional[Path]:
    """
    Select the latest valid and reliable run for forecasting.

    Selection algorithm:
    1. Iterate through runs from newest to oldest
    2. Skip runs that fail artifact validation
    3. Skip runs where reliability check fails
    4. Return first passing run

    Args:
        runs_dir: Path to runs directory
        require_simulation: If True, requires simulation_results.json

    Returns:
        Path to selected run directory, or None if no valid run found
    """
    run_names = list_runs_sorted(runs_dir)

    for run_name in run_names:
        run_dir = runs_dir / run_name

        # Check artifact requirements
        if require_simulation:
            if not is_run_valid_for_simulate(run_dir):
                continue
        else:
            if not is_run_valid_for_observe(run_dir):
                continue

        # Check reliability
        is_reliable, _ = get_run_reliability(run_dir)
        if not is_reliable:
            continue

        return run_dir

    return None


def load_run_artifacts(run_dir: Path) -> Dict[str, Any]:
    """
    Load required artifacts from a run directory.

    Args:
        run_dir: Path to run directory

    Returns:
        Dictionary with loaded artifacts:
        - manifest: run_manifest.json content
        - intel: compiled_intel.json content
        - simulation: simulation_results.json content (if exists)

    Raises:
        ForecastError: If required artifacts can't be loaded
    """
    artifacts = {}

    # Load manifest (required)
    manifest_path = run_dir / "run_manifest.json"
    try:
        with open(manifest_path) as f:
            artifacts["manifest"] = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        raise ForecastError(f"Failed to load manifest: {e}")

    # Load compiled intel (required)
    intel_path = run_dir / "compiled_intel.json"
    try:
        with open(intel_path) as f:
            artifacts["intel"] = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        raise ForecastError(f"Failed to load compiled_intel: {e}")

    # Load simulation results (optional)
    sim_path = run_dir / "simulation_results.json"
    if sim_path.exists():
        try:
            with open(sim_path) as f:
                artifacts["simulation"] = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            raise ForecastError(f"Failed to load simulation_results: {e}")

    return artifacts


def extract_nested_value(data: Dict[str, Any], path: str) -> Any:
    """
    Extract value from nested dictionary using dot-separated path.

    Args:
        data: Source dictionary
        path: Dot-separated path (e.g., "economic_analysis.stress_level")

    Returns:
        Value at path, or None if not found
    """
    parts = path.split(".")
    current = data

    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None

    return current


def derive_probability_from_simulation(
    event: Dict[str, Any],
    simulation: Dict[str, Any],
    horizon_days: int
) -> Tuple[float, Optional[str], Any, bool]:
    """
    Derive YES probability from simulation results.

    Args:
        event: Event definition from catalog
        simulation: Simulation results
        horizon_days: Forecast horizon in days

    Returns:
        Tuple of (probability, source_field, raw_value, horizon_converted)
    """
    forecast_source = event.get("forecast_source", {})
    source_type = forecast_source.get("type")

    if source_type == "diagnostic_only":
        # No forecast for diagnostic events
        return 0.0, None, None, False

    if source_type == "simulation_output":
        # Direct field from simulation results
        field = forecast_source.get("field")
        if not field:
            raise ForecastError(f"Event {event['event_id']}: missing 'field' in forecast_source")

        raw_value = extract_nested_value(simulation, field)
        if raw_value is None:
            raise ForecastError(f"Event {event['event_id']}: field '{field}' not found in simulation")

        # Apply hazard rate conversion (simulation rates are 90-day)
        p_horizon = hazard_rate_conversion(float(raw_value), horizon_days)
        return p_horizon, field, raw_value, True

    if source_type == "simulation_derived":
        # Derived from simulation field with custom logic
        field = forecast_source.get("field")
        derivation = forecast_source.get("derivation", "")

        raw_value = extract_nested_value(simulation, field)

        # Parse derivation rules
        # Formats supported:
        # - "if <field> == '<value>' then P(YES)=<p1> else P(YES)=<p2>" (string equality)
        # - "if <field> >= <num> then P(YES)=<p1> else P(YES)=<p2>" (numeric comparison)
        if "if " in derivation and " then " in derivation and " else " in derivation:
            if raw_value is not None:
                try:
                    # Extract probabilities
                    then_match = re.search(r'then P\(YES\)=([0-9.]+)', derivation)
                    else_match = re.search(r'else P\(YES\)=([0-9.]+)', derivation)
                    if not then_match or not else_match:
                        raise ForecastError(f"Event {event['event_id']}: malformed derivation '{derivation}'")

                    p_then = float(then_match.group(1))
                    p_else = float(else_match.group(1))

                    # Parse condition - check for numeric comparisons
                    # Pattern: "if <field_name> <op> <value>"
                    cond_match = re.search(r'if\s+\w+\s*(>=|<=|>|<|==)\s*([\'"]?)([^\'"\s]+)\2', derivation)
                    if cond_match:
                        operator = cond_match.group(1)
                        cond_value = cond_match.group(3)

                        # Try numeric comparison first
                        if operator in ('>=', '<=', '>', '<'):
                            try:
                                num_raw = float(raw_value)
                                num_cond = float(cond_value)
                                if operator == '>=':
                                    condition_met = num_raw >= num_cond
                                elif operator == '<=':
                                    condition_met = num_raw <= num_cond
                                elif operator == '>':
                                    condition_met = num_raw > num_cond
                                elif operator == '<':
                                    condition_met = num_raw < num_cond
                                else:
                                    condition_met = False
                            except (ValueError, TypeError):
                                # Fall back to string comparison
                                condition_met = str(raw_value).lower() == cond_value.lower()
                        elif operator == '==':
                            # String equality (strip quotes if present)
                            condition_met = str(raw_value).lower() == cond_value.lower()
                        else:
                            condition_met = False

                        return (p_then if condition_met else p_else), field, raw_value, False
                except Exception as e:
                    raise ForecastError(f"Event {event['event_id']}: failed to parse derivation '{derivation}': {e}")

        # Fallback: return base probability
        return 0.5, field, raw_value, False

    # Unknown source type
    raise ForecastError(f"Event {event['event_id']}: unknown forecast_source type '{source_type}'")


def generate_forecast_id(
    as_of_date: str,
    run_id: str,
    event_id: str,
    horizon_days: int
) -> str:
    """
    Generate deterministic forecast ID.

    Format: fcst_{as_of_date}_{run_id}_{event_id}_{horizon}d

    Args:
        as_of_date: Date string (YYYYMMDD)
        run_id: Run identifier
        event_id: Event identifier
        horizon_days: Forecast horizon

    Returns:
        Forecast identifier string
    """
    return f"fcst_{as_of_date}_{run_id}_{event_id}_{horizon_days}d"


def generate_forecast_record(
    event: Dict[str, Any],
    run_dir: Path,
    artifacts: Dict[str, Any],
    horizon_days: int,
    as_of_utc: datetime
) -> Dict[str, Any]:
    """
    Generate a complete forecast record for an event.

    Args:
        event: Event definition from catalog
        run_dir: Path to source run directory
        artifacts: Loaded run artifacts
        horizon_days: Forecast horizon in days
        as_of_utc: Timestamp for forecast creation

    Returns:
        Complete forecast record dictionary
    """
    event_id = event["event_id"]
    run_id = run_dir.name
    manifest = artifacts["manifest"]
    simulation = artifacts.get("simulation", {})

    # Compute manifest_id from run_manifest.json contents
    manifest_path = run_dir / "run_manifest.json"
    manifest_id = compute_manifest_id(manifest_path)

    # Derive probability
    forecast_source = event.get("forecast_source", {})
    is_diagnostic = forecast_source.get("type") == "diagnostic_only"

    if is_diagnostic:
        # Diagnostic events don't get probability forecasts
        probabilities = {"YES": 0.5, "NO": 0.5}
        source_field = None
        raw_value = None
        horizon_converted = False
        abstain = True
        abstain_reason = "diagnostic_only"
    else:
        p_yes, source_field, raw_value, horizon_converted = derive_probability_from_simulation(
            event, simulation, horizon_days
        )
        p_no = 1.0 - p_yes
        probabilities = {"YES": round(p_yes, 6), "NO": round(p_no, 6)}
        abstain = False
        abstain_reason = None

    # Calculate target date
    target_date = as_of_utc + timedelta(days=horizon_days)

    # Build forecast record
    as_of_date = as_of_utc.strftime("%Y%m%d")
    forecast_id = generate_forecast_id(as_of_date, run_id, event_id, horizon_days)

    # Extract artifact hashes from manifest
    artifact_hashes = manifest.get("hashes", {})

    record = {
        "forecast_id": forecast_id,
        "event_id": event_id,
        "horizon_days": horizon_days,
        "as_of_utc": as_of_utc.isoformat(),
        "target_date_utc": target_date.isoformat(),
        "run_id": run_id,
        "data_cutoff_utc": manifest.get("data_cutoff_utc"),
        "manifest_id": manifest_id,
        "artifact_hashes": artifact_hashes,
        "seed": manifest.get("seed"),
        "n_sims": simulation.get("n_runs"),
        "forecaster_id": "oracle_v1",
        "forecaster_version": "1.0",
        "distribution_type": event["event_type"],
        "probabilities": probabilities,
        "forecast_source_field": source_field,
        "raw_simulation_value": raw_value,
        "horizon_conversion_applied": horizon_converted,
        "abstain": abstain,
        "abstain_reason": abstain_reason,
    }

    return record


def generate_forecasts(
    catalog_path: Path = Path("config/event_catalog.json"),
    runs_dir: Path = Path("runs"),
    run_dir: Optional[Path] = None,
    horizons: Optional[List[int]] = None,
    ledger_dir: Path = ledger.LEDGER_DIR,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate forecasts for all catalog events.

    Args:
        catalog_path: Path to event catalog
        runs_dir: Path to runs directory
        run_dir: Specific run to use (auto-selects if None)
        horizons: List of horizons to generate (default: all valid)
        ledger_dir: Path to ledger directory
        dry_run: If True, don't write to ledger

    Returns:
        List of generated forecast records

    Raises:
        ForecastError: If no valid run found or generation fails
    """
    # Load catalog
    catalog_data = cat.load_catalog(catalog_path)
    cat.validate_catalog(catalog_data)

    # Select run
    if run_dir is None:
        run_dir = select_valid_run(runs_dir, require_simulation=True)
        if run_dir is None:
            raise ForecastError("No valid run found for forecasting")

    # Load artifacts
    artifacts = load_run_artifacts(run_dir)

    # Default horizons
    if horizons is None:
        horizons = sorted(VALID_HORIZONS)
    else:
        # Validate horizons
        invalid = set(horizons) - VALID_HORIZONS
        if invalid:
            raise ForecastError(f"Invalid horizons: {invalid}. Valid: {VALID_HORIZONS}")

    # Generate forecasts
    as_of_utc = datetime.now(timezone.utc)
    records = []

    for event in catalog_data["events"]:
        for horizon in horizons:
            record = generate_forecast_record(
                event, run_dir, artifacts, horizon, as_of_utc
            )
            records.append(record)

            if not dry_run:
                ledger.append_forecast(record, ledger_dir)

    return records

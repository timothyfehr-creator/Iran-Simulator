"""
Forecast generation from simulation outputs.

Generates forecast records for catalog events using simulation results
and compiled intelligence from valid runs.
"""

import json
import math
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import re

from . import catalog as cat
from . import ledger
from . import ensembles
from .ledger import compute_manifest_id
from ..run_utils import (
    list_runs_sorted,
    is_run_valid_for_observe,
    is_run_valid_for_simulate,
    get_run_reliability,
)

logger = logging.getLogger(__name__)

# Valid forecast horizons in days
VALID_HORIZONS = {1, 7, 15, 30}

# Tolerance for probability sum validation
PROBABILITY_SUM_TOLERANCE = 1e-6


class ForecastError(Exception):
    """Raised when forecast generation fails."""
    pass


def validate_distribution(probs: Dict[str, float], event: Dict[str, Any]) -> List[str]:
    """
    Validate probability distribution against event definition.

    Checks:
    1. All values are valid floats (no NaN, no negative)
    2. All values in range [0.0, 1.0]
    3. Sum to 1.0 (within tolerance 1e-6)
    4. Keys must be subset of allowed_outcomes (UNKNOWN always allowed)
    5. All allowed_outcomes (except UNKNOWN) must be present

    Args:
        probs: Dictionary mapping outcomes to probabilities
        event: Event definition with allowed_outcomes

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    allowed_outcomes = set(event.get("allowed_outcomes", []))

    # Check each probability value
    for outcome, prob in probs.items():
        # Check for NaN
        if prob != prob:  # NaN check
            errors.append(f"probability for {outcome} is NaN")
            continue

        # Check for negative values
        if prob < 0:
            errors.append(f"probability for {outcome} is negative: {prob}")
            continue

        # Check range [0, 1]
        if prob > 1:
            errors.append(f"probability for {outcome} exceeds 1.0: {prob}")
            continue

        # Check if outcome is allowed (UNKNOWN is always allowed)
        if outcome != "UNKNOWN" and outcome not in allowed_outcomes:
            errors.append(f"unexpected outcome '{outcome}' not in allowed_outcomes")

    # Check sum equals 1.0
    total = sum(probs.values())
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        errors.append(f"probabilities sum to {total}, expected 1.0")

    # Check all required outcomes are present (except UNKNOWN)
    required_outcomes = allowed_outcomes - {"UNKNOWN"}
    present_outcomes = set(probs.keys())
    missing = required_outcomes - present_outcomes
    if missing:
        errors.append(f"missing required outcome(s): {missing}")

    return errors


def generate_baseline_distribution(
    event: Dict[str, Any],
    forecast_source_type: str
) -> Dict[str, float]:
    """
    Generate baseline probability distribution for MVP events.

    Phase 3A: Uniform fallback only (no ledger history lookup).
    Full persistence/climatology logic deferred to Phase 3C.

    Args:
        event: Event definition with allowed_outcomes
        forecast_source_type: "baseline_persistence" or "baseline_climatology"

    Returns:
        Uniform distribution: {outcome: 1/K for outcome in allowed_outcomes}
        where K is the number of non-UNKNOWN outcomes
    """
    outcomes = event.get("allowed_outcomes", [])
    # Exclude UNKNOWN from uniform distribution
    non_unknown = [o for o in outcomes if o != "UNKNOWN"]
    k = len(non_unknown)

    if k == 0:
        return {"UNKNOWN": 1.0}

    # Calculate uniform probability
    prob = round(1.0 / k, 6)
    dist = {o: prob for o in non_unknown}

    # Adjust for rounding to ensure sum == 1.0
    total = sum(dist.values())
    if total != 1.0:
        first_key = non_unknown[0]
        dist[first_key] = round(dist[first_key] + (1.0 - total), 6)

    return dist


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
        "record_type": "forecast",
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
    dry_run: bool = False,
    with_ensembles: bool = False,
    ensemble_config_path: Path = Path("config/ensemble_config.json")
) -> List[Dict[str, Any]]:
    """
    Generate forecasts for all forecastable catalog events.

    Uses get_forecastable_events() to filter events by:
    - enabled == true (or missing, defaults to true)
    - forecast_source.type != "diagnostic_only"

    For baseline forecast source types (baseline_persistence, baseline_climatology),
    generates uniform distributions as a Phase 3A fallback.

    Args:
        catalog_path: Path to event catalog
        runs_dir: Path to runs directory
        run_dir: Specific run to use (auto-selects if None)
        horizons: List of horizons to generate (default: all valid)
        ledger_dir: Path to ledger directory
        dry_run: If True, don't write to ledger
        with_ensembles: If True, generate ensemble forecasts after base forecasts
        ensemble_config_path: Path to ensemble configuration file

    Returns:
        List of generated forecast records (includes ensemble forecasts if with_ensembles=True)

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

    # Generate forecasts - use get_forecastable_events() to filter
    as_of_utc = datetime.now(timezone.utc)
    records = []

    for event in cat.get_forecastable_events(catalog_data):
        source_type = event.get("forecast_source", {}).get("type")

        # diagnostic_only events are already filtered out by get_forecastable_events
        # but double-check
        if source_type == "diagnostic_only":
            continue

        # Get event-specific horizons if defined, otherwise use global
        event_horizons = event.get("horizons_days", horizons)
        # Ensure horizons is valid list
        if not isinstance(event_horizons, list):
            event_horizons = horizons

        for horizon in event_horizons:
            # Skip if horizon not in global valid set
            if horizon not in VALID_HORIZONS:
                logger.warning(f"Event {event['event_id']}: skipping invalid horizon {horizon}")
                continue

            # Generate forecast record with appropriate source handling
            if source_type in ("baseline_persistence", "baseline_climatology"):
                # Use minimal baseline (uniform) in Phase 3A
                record = generate_baseline_forecast_record(
                    event, run_dir, artifacts, horizon, as_of_utc, source_type
                )
            else:
                # Use existing simulation-based logic
                record = generate_forecast_record(
                    event, run_dir, artifacts, horizon, as_of_utc
                )

            # Validate distribution before appending
            probs = record.get("probabilities", {})
            errors = validate_distribution(probs, event)
            if errors:
                logger.warning(
                    f"Event {event['event_id']} horizon {horizon}d: "
                    f"distribution validation failed: {errors}"
                )
                continue

            records.append(record)

            if not dry_run:
                ledger.append_forecast(record, ledger_dir)

    # Generate ensemble forecasts if requested
    if with_ensembles:
        try:
            # Load ensemble config
            ensemble_config = ensembles.load_ensemble_config(ensemble_config_path)

            # Get run_id from the run directory
            current_run_id = run_dir.name

            # Generate ensembles from base forecasts
            ensemble_records = ensembles.generate_ensemble_forecasts(
                base_forecasts=records,
                catalog=catalog_data,
                config=ensemble_config,
                run_id=current_run_id,
                ledger_dir=ledger_dir,
                dry_run=dry_run
            )

            # Add ensemble records to output
            records.extend(ensemble_records)

            logger.info(f"Generated {len(ensemble_records)} ensemble forecast(s)")

        except (FileNotFoundError, ensembles.EnsembleError) as e:
            logger.warning(f"Ensemble generation failed: {e}")
            # Continue without ensembles - don't fail the whole operation

    return records


def generate_baseline_forecast_record(
    event: Dict[str, Any],
    run_dir: Path,
    artifacts: Dict[str, Any],
    horizon_days: int,
    as_of_utc: datetime,
    source_type: str
) -> Dict[str, Any]:
    """
    Generate a forecast record for baseline events (persistence/climatology).

    Phase 3A: Uses uniform distribution as fallback.
    Full baseline logic deferred to Phase 3C.

    Args:
        event: Event definition from catalog
        run_dir: Path to source run directory
        artifacts: Loaded run artifacts
        horizon_days: Forecast horizon in days
        as_of_utc: Timestamp for forecast creation
        source_type: "baseline_persistence" or "baseline_climatology"

    Returns:
        Complete forecast record dictionary
    """
    event_id = event["event_id"]
    run_id = run_dir.name
    manifest = artifacts["manifest"]

    # Compute manifest_id from run_manifest.json contents
    manifest_path = run_dir / "run_manifest.json"
    manifest_id = compute_manifest_id(manifest_path)

    # Generate uniform baseline distribution
    probabilities = generate_baseline_distribution(event, source_type)

    # Calculate target date
    target_date = as_of_utc + timedelta(days=horizon_days)

    # Build forecast record
    as_of_date = as_of_utc.strftime("%Y%m%d")
    forecast_id = generate_forecast_id(as_of_date, run_id, event_id, horizon_days)

    # Extract artifact hashes from manifest
    artifact_hashes = manifest.get("hashes", {})

    record = {
        "record_type": "forecast",
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
        "n_sims": None,  # No simulation for baseline
        "forecaster_id": f"oracle_baseline_{source_type.replace('baseline_', '')}",
        "forecaster_version": "1.0",
        "distribution_type": event["event_type"],
        "probabilities": probabilities,
        "forecast_source_field": None,
        "raw_simulation_value": None,
        "horizon_conversion_applied": False,
        "abstain": False,
        "abstain_reason": None,
    }

    return record

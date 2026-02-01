"""
Static ensemble forecaster generation.

Combines multiple base forecasts into weighted ensemble distributions.
Supports configurable weights, missing member policies, and validation.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import jsonschema

from . import catalog as cat_module
from . import ledger

logger = logging.getLogger(__name__)

# Tolerance for probability sum validation
PROBABILITY_SUM_TOLERANCE = 1e-6

# Tolerance for weight sum validation
WEIGHT_SUM_TOLERANCE = 1e-6

# Tolerance for as_of_utc comparison (60 seconds)
AS_OF_UTC_TOLERANCE_SECONDS = 60

# Default config path
DEFAULT_CONFIG_PATH = Path("config/ensemble_config.json")
DEFAULT_SCHEMA_PATH = Path("config/schemas/ensemble_config.schema.json")


class EnsembleError(Exception):
    """Raised when ensemble generation fails."""
    pass


def load_ensemble_config(
    config_path: Path = DEFAULT_CONFIG_PATH
) -> Dict[str, Any]:
    """
    Load ensemble configuration from JSON file.

    Args:
        config_path: Path to ensemble_config.json

    Returns:
        Parsed config dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config is invalid JSON
    """
    with open(config_path, 'r') as f:
        return json.load(f)


def validate_ensemble_config(
    config: Dict[str, Any],
    schema_path: Optional[Path] = DEFAULT_SCHEMA_PATH
) -> List[str]:
    """
    Validate ensemble configuration against schema and business rules.

    Validation rules:
    1. config_version required, must be valid SemVer
    2. weights must sum to 1.0 (tolerance: 1e-6)
    3. members[].forecaster_id must be unique within ensemble
    4. missing_member_policy must be "renormalize" or "skip"
    5. min_members_required <= len(members)
    6. effective_from_utc required, must be valid ISO timestamp
    7. ensemble_id must match pattern oracle_ensemble_[a-z0-9_]+
    8. ensemble_id must not be "oracle_v1" or start with "oracle_baseline_"
    9. apply_to_event_types must only contain valid types
    10. If apply_to_event_ids present, must be non-empty array of strings

    Args:
        config: Parsed config dictionary
        schema_path: Path to JSON schema (optional)

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # JSON Schema validation if available
    if schema_path is not None and schema_path.exists():
        try:
            with open(schema_path) as f:
                schema = json.load(f)
            jsonschema.validate(config, schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation failed: {e.message}")
            return errors
        except (IOError, json.JSONDecodeError):
            pass  # Fall through to manual validation

    # Manual validation

    # 1. config_version required
    config_version = config.get("config_version")
    if not config_version:
        errors.append("config_version is required")
    elif not _is_valid_semver(config_version):
        errors.append(f"config_version '{config_version}' is not valid SemVer")

    ensembles = config.get("ensembles", [])
    if not isinstance(ensembles, list):
        errors.append("ensembles must be a list")
        return errors

    ensemble_ids = set()

    for i, ens in enumerate(ensembles):
        prefix = f"ensembles[{i}]"

        # Check ensemble_id
        ensemble_id = ens.get("ensemble_id", "")
        if not ensemble_id:
            errors.append(f"{prefix}: ensemble_id is required")
        else:
            # 7. Pattern check
            import re
            if not re.match(r"^oracle_ensemble_[a-z0-9_]+$", ensemble_id):
                errors.append(
                    f"{prefix}: ensemble_id '{ensemble_id}' must match pattern oracle_ensemble_[a-z0-9_]+"
                )

            # 8. Reserved names
            if ensemble_id == "oracle_v1" or ensemble_id.startswith("oracle_baseline_"):
                errors.append(
                    f"{prefix}: ensemble_id '{ensemble_id}' conflicts with reserved forecaster names"
                )

            # Check uniqueness
            if ensemble_id in ensemble_ids:
                errors.append(f"{prefix}: duplicate ensemble_id '{ensemble_id}'")
            ensemble_ids.add(ensemble_id)

        # Check members
        members = ens.get("members", [])
        if not members:
            errors.append(f"{prefix}: members is required and must not be empty")
        else:
            # 3. Unique forecaster_ids
            forecaster_ids = [m.get("forecaster_id") for m in members]
            if len(forecaster_ids) != len(set(forecaster_ids)):
                errors.append(f"{prefix}: member forecaster_ids must be unique")

            # 2. Weights sum to 1.0
            weights = [m.get("weight", 0) for m in members]
            weight_sum = sum(weights)
            if abs(weight_sum - 1.0) > WEIGHT_SUM_TOLERANCE:
                errors.append(
                    f"{prefix}: member weights sum to {weight_sum}, expected 1.0"
                )

            # Check weight ranges
            for j, m in enumerate(members):
                weight = m.get("weight", 0)
                if weight < 0 or weight > 1:
                    errors.append(
                        f"{prefix}.members[{j}]: weight {weight} must be in [0, 1]"
                    )

        # 5. min_members_required <= len(members)
        min_members = ens.get("min_members_required", 0)
        if min_members > len(members):
            errors.append(
                f"{prefix}: min_members_required ({min_members}) > len(members) ({len(members)})"
            )

        # 4. missing_member_policy
        policy = ens.get("missing_member_policy")
        if policy not in ("renormalize", "skip"):
            errors.append(
                f"{prefix}: missing_member_policy must be 'renormalize' or 'skip', got '{policy}'"
            )

        # 6. effective_from_utc required and valid
        effective_from = ens.get("effective_from_utc")
        if not effective_from:
            errors.append(f"{prefix}: effective_from_utc is required")
        else:
            try:
                datetime.fromisoformat(effective_from.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                errors.append(
                    f"{prefix}: effective_from_utc '{effective_from}' is not valid ISO timestamp"
                )

        # 9. apply_to_event_types validation
        event_types = ens.get("apply_to_event_types", [])
        valid_types = {"binary", "categorical", "binned_continuous"}
        for et in event_types:
            if et not in valid_types:
                errors.append(
                    f"{prefix}: invalid event_type '{et}' in apply_to_event_types"
                )

        # 10. apply_to_event_ids if present
        event_ids = ens.get("apply_to_event_ids")
        if event_ids is not None:
            if not isinstance(event_ids, list):
                errors.append(f"{prefix}: apply_to_event_ids must be an array or null")
            elif len(event_ids) == 0:
                errors.append(f"{prefix}: apply_to_event_ids must be non-empty if present")

    return errors


def _is_valid_semver(version: str) -> bool:
    """Check if string is valid semver (X.Y.Z format)."""
    import re
    return bool(re.match(r"^\d+\.\d+\.\d+$", version))


def drop_unknown_and_renormalize(probs: Dict[str, float]) -> Dict[str, float]:
    """
    Drop UNKNOWN from probabilities and renormalize to sum=1.0.

    TWEAK 2: If all probability mass is in UNKNOWN (or sum==0 after dropping),
    return empty dict to signal this member should be treated as missing.

    Args:
        probs: Dictionary mapping outcomes to probabilities

    Returns:
        Renormalized distribution without UNKNOWN, or empty dict if degenerate
    """
    # Remove UNKNOWN
    filtered = {k: v for k, v in probs.items() if k != "UNKNOWN"}

    if not filtered:
        return {}

    total = sum(filtered.values())

    # Handle degenerate case where all mass was in UNKNOWN
    if total < PROBABILITY_SUM_TOLERANCE:
        return {}

    # Renormalize
    return {k: v / total for k, v in filtered.items()}


def combine_distributions(
    members: List[Dict[str, float]],
    weights: List[float],
    outcomes: List[str]
) -> Dict[str, float]:
    """
    Combine member distributions using weighted average.

    Args:
        members: List of probability distributions (already renormalized)
        weights: List of weights for each member (must sum to 1.0)
        outcomes: List of valid outcomes (from catalog, excluding UNKNOWN)

    Returns:
        Combined probability distribution

    Raises:
        EnsembleError: If combined distribution doesn't sum to 1.0
    """
    if not members or not weights:
        raise EnsembleError("No members to combine")

    if len(members) != len(weights):
        raise EnsembleError(
            f"Mismatched members ({len(members)}) and weights ({len(weights)})"
        )

    # Initialize result
    result = {outcome: 0.0 for outcome in outcomes}

    # Weighted combination
    for member_probs, weight in zip(members, weights):
        for outcome in outcomes:
            p = member_probs.get(outcome, 0.0)
            result[outcome] += weight * p

    # Validate sum
    total = sum(result.values())
    if abs(total - 1.0) > PROBABILITY_SUM_TOLERANCE:
        raise EnsembleError(
            f"Combined distribution sums to {total}, expected 1.0 (bug indicator)"
        )

    # Round to 6 decimal places for consistency
    return {k: round(v, 6) for k, v in result.items()}


def generate_forecast_id(
    as_of_date: str,
    run_id: str,
    ensemble_id: str,
    event_id: str,
    horizon_days: int
) -> str:
    """
    Generate deterministic ensemble forecast ID.

    Format: fcst_{as_of_date}_{run_id}_{ensemble_id}_{event_id}_{horizon}d

    Decision D1: Include run_id in forecast_id to prevent cross-run collisions.

    Args:
        as_of_date: Date string (YYYYMMDD)
        run_id: Run identifier (from base forecast's run_id field)
        ensemble_id: Ensemble identifier
        event_id: Event identifier
        horizon_days: Forecast horizon

    Returns:
        Forecast identifier string
    """
    return f"fcst_{as_of_date}_{run_id}_{ensemble_id}_{event_id}_{horizon_days}d"


def generate_ensemble_forecasts(
    base_forecasts: List[Dict[str, Any]],
    catalog: Dict[str, Any],
    config: Dict[str, Any],
    run_id: str,
    ledger_dir: Path = ledger.LEDGER_DIR,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Generate ensemble forecasts from base forecasts.

    Decision D2: Ensembles ONLY combine forecasts from the SAME run_id.
    Decision D3: UNKNOWN dropped and renormalized BEFORE combining.

    Args:
        base_forecasts: List of base forecast records (SAME run_id)
        catalog: Loaded event catalog
        config: Ensemble configuration
        run_id: Run ID that all base forecasts must match
        ledger_dir: Path to ledger directory
        dry_run: If True, don't write to ledger

    Returns:
        List of generated ensemble forecast records

    Raises:
        EnsembleError: If config validation fails or generation encounters errors
    """
    # Validate config
    config_errors = validate_ensemble_config(config)
    if config_errors:
        raise EnsembleError(f"Config validation failed: {'; '.join(config_errors)}")

    config_version = config["config_version"]

    # Get existing forecast_ids for idempotency check (TWEAK 4)
    existing_forecast_ids = set()
    if not dry_run:
        existing_forecasts = ledger.get_forecasts(ledger_dir)
        existing_forecast_ids = {f.get("forecast_id") for f in existing_forecasts}

    # Group base forecasts by key: (event_id, horizon_days, target_date_utc)
    # Decision D2: All members must have same run_id
    forecast_groups: Dict[Tuple[str, int, str], Dict[str, Dict[str, Any]]] = {}

    for f in base_forecasts:
        # Verify run_id matches
        if f.get("run_id") != run_id:
            logger.warning(
                f"Skipping forecast {f.get('forecast_id')}: run_id mismatch "
                f"(expected {run_id}, got {f.get('run_id')})"
            )
            continue

        event_id = f.get("event_id")
        horizon_days = f.get("horizon_days")
        target_date = f.get("target_date_utc")
        forecaster_id = f.get("forecaster_id")

        if not all([event_id, horizon_days, target_date, forecaster_id]):
            continue

        key = (event_id, horizon_days, target_date)
        if key not in forecast_groups:
            forecast_groups[key] = {}
        forecast_groups[key][forecaster_id] = f

    # Generate ensemble forecasts
    ensemble_records = []

    for ens_def in config.get("ensembles", []):
        if not ens_def.get("enabled", True):
            continue

        ensemble_id = ens_def["ensemble_id"]
        members_config = ens_def["members"]
        apply_to_types = set(ens_def.get("apply_to_event_types", []))
        apply_to_ids = ens_def.get("apply_to_event_ids")
        min_members = ens_def.get("min_members_required", 1)
        missing_policy = ens_def.get("missing_member_policy", "renormalize")
        effective_from = ens_def.get("effective_from_utc", "")

        # Parse effective_from
        try:
            effective_from_dt = datetime.fromisoformat(
                effective_from.replace('Z', '+00:00')
            )
        except (ValueError, AttributeError):
            logger.warning(f"Ensemble {ensemble_id}: invalid effective_from_utc, skipping")
            continue

        for (event_id, horizon_days, target_date), forecaster_forecasts in forecast_groups.items():
            # TWEAK 3: Look up event_type from CATALOG
            event = cat_module.get_event(catalog, event_id)
            if not event:
                continue

            event_type = event.get("event_type", "binary")

            # Check event_type filter
            if event_type not in apply_to_types:
                continue

            # Check event_id filter (D8)
            if apply_to_ids is not None and event_id not in apply_to_ids:
                continue

            # Get as_of_utc from any member and verify all are within tolerance
            sample_forecast = next(iter(forecaster_forecasts.values()))
            as_of_utc_str = sample_forecast.get("as_of_utc", "")

            try:
                as_of_utc = datetime.fromisoformat(as_of_utc_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                continue

            # Verify all members have as_of_utc within tolerance (D2 enhancement)
            as_of_mismatch = False
            for fcast in forecaster_forecasts.values():
                try:
                    other_str = fcast.get("as_of_utc", "")
                    other_dt = datetime.fromisoformat(other_str.replace('Z', '+00:00'))
                    delta = abs((other_dt - as_of_utc).total_seconds())
                    if delta > AS_OF_UTC_TOLERANCE_SECONDS:
                        logger.warning(
                            f"as_of_utc mismatch in {event_id}/{horizon_days}d: "
                            f"{as_of_utc_str} vs {other_str} (delta={delta}s)"
                        )
                        as_of_mismatch = True
                        break
                except (ValueError, AttributeError):
                    pass
            if as_of_mismatch:
                continue

            # Check effective_from
            if as_of_utc < effective_from_dt:
                continue

            # Get allowed outcomes from catalog (excluding UNKNOWN)
            outcomes = [o for o in event.get("allowed_outcomes", []) if o != "UNKNOWN"]
            if not outcomes:
                continue

            # Collect member distributions
            available_members = []
            available_weights = []
            missing_members = []

            for member_cfg in members_config:
                fid = member_cfg["forecaster_id"]
                weight = member_cfg["weight"]

                forecast = forecaster_forecasts.get(fid)

                # Check if member is missing or abstained
                if forecast is None:
                    missing_members.append(fid)
                    continue

                if forecast.get("abstain", False):
                    missing_members.append(fid)
                    continue

                # Drop UNKNOWN and renormalize (D3)
                probs = forecast.get("probabilities", {})
                normalized = drop_unknown_and_renormalize(probs)

                # TWEAK 2: If degenerate, treat as missing
                if not normalized:
                    missing_members.append(fid)
                    continue

                available_members.append(normalized)
                available_weights.append(weight)

            # Check minimum members requirement
            if len(available_members) < min_members:
                if missing_policy == "skip":
                    logger.debug(
                        f"Ensemble {ensemble_id}: skipping {event_id}/{horizon_days}d "
                        f"(only {len(available_members)}/{min_members} members available)"
                    )
                    continue

            # Handle missing members based on policy
            policy_applied = "none"
            if missing_members:
                if missing_policy == "renormalize":
                    # Renormalize weights among available members
                    weight_sum = sum(available_weights)
                    if weight_sum > 0:
                        available_weights = [w / weight_sum for w in available_weights]
                        policy_applied = "renormalize"
                elif missing_policy == "skip":
                    # Already handled above
                    continue

            # Skip if no members available
            if not available_members:
                logger.debug(
                    f"Ensemble {ensemble_id}: no members available for {event_id}/{horizon_days}d"
                )
                continue

            # Combine distributions
            try:
                combined = combine_distributions(
                    available_members, available_weights, outcomes
                )
            except EnsembleError as e:
                logger.error(
                    f"Ensemble {ensemble_id}: failed to combine for {event_id}/{horizon_days}d: {e}"
                )
                continue

            # Generate forecast ID (D1)
            as_of_date = as_of_utc.strftime("%Y%m%d")
            forecast_id = generate_forecast_id(
                as_of_date, run_id, ensemble_id, event_id, horizon_days
            )

            # Idempotency check (TWEAK 4)
            if forecast_id in existing_forecast_ids:
                logger.debug(f"Ensemble forecast {forecast_id} already exists, skipping")
                continue

            # Build ensemble record
            members_used = [
                m["forecaster_id"] for m in members_config
                if m["forecaster_id"] not in missing_members
            ]

            record = {
                "record_type": "forecast",
                "forecast_id": forecast_id,
                "event_id": event_id,
                "horizon_days": horizon_days,
                "as_of_utc": as_of_utc_str,
                "target_date_utc": target_date,
                "run_id": run_id,
                "data_cutoff_utc": sample_forecast.get("data_cutoff_utc"),
                "manifest_id": sample_forecast.get("manifest_id"),
                "artifact_hashes": sample_forecast.get("artifact_hashes", {}),
                "seed": sample_forecast.get("seed"),
                "n_sims": sample_forecast.get("n_sims"),
                "forecaster_id": ensemble_id,
                "forecaster_version": config_version,
                "distribution_type": event_type,
                "probabilities": combined,
                "forecast_source_field": None,
                "raw_simulation_value": None,
                "horizon_conversion_applied": False,
                "abstain": False,
                "abstain_reason": None,
                "ensemble_inputs": {
                    "config_version": config_version,
                    "members_used": members_used,
                    "weights_used": [round(w, 6) for w in available_weights],
                    "members_missing": missing_members,
                    "policy_applied": policy_applied,
                },
            }

            ensemble_records.append(record)

            # Append to ledger if not dry_run
            if not dry_run:
                ledger.append_forecast(record, ledger_dir)
                existing_forecast_ids.add(forecast_id)

    logger.info(f"Generated {len(ensemble_records)} ensemble forecast(s)")
    return ensemble_records

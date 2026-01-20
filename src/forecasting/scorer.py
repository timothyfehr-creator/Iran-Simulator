"""
Scoring metrics for forecast accuracy.

Computes Brier score, skill scores, and calibration metrics
for resolved forecasts. Supports separation of core scores
(external_auto + external_manual) from claims_inferred scores.
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path

from . import ledger
from . import resolver


class ScoringError(Exception):
    """Raised when scoring fails."""
    pass


def compute_coverage_metrics(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute coverage metrics for forecasts.

    Coverage measures how many due forecasts have been resolved.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records

    Returns:
        Dictionary with coverage metrics:
        - forecasts_due: Count of forecasts where target_date <= now
        - resolved_known: Count with YES/NO outcomes
        - resolved_unknown: Count with UNKNOWN outcomes
        - abstained: Count where forecast abstained
        - unresolved: Count with no resolution yet
        - coverage_rate: resolved_known / forecasts_due
        - unknown_rate: resolved_unknown / forecasts_due
        - abstain_rate: abstained / forecasts_due
    """
    now = datetime.now(timezone.utc)
    resolution_map = {r["forecast_id"]: r for r in resolutions}

    forecasts_due = 0
    resolved_known = 0
    resolved_unknown = 0
    abstained = 0
    unresolved = 0

    for f in forecasts:
        # Check if forecast is due
        target_str = f.get("target_date_utc")
        if not target_str:
            continue

        target_str = target_str.replace('Z', '+00:00')
        try:
            target_date = datetime.fromisoformat(target_str)
            if target_date.tzinfo is None:
                target_date = target_date.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if target_date > now:
            continue

        forecasts_due += 1

        if f.get("abstain"):
            abstained += 1
            continue

        resolution = resolution_map.get(f["forecast_id"])
        if resolution is None:
            unresolved += 1
        elif resolution.get("resolved_outcome") == "UNKNOWN":
            resolved_unknown += 1
        else:
            resolved_known += 1

    return {
        "forecasts_due": forecasts_due,
        "resolved_known": resolved_known,
        "resolved_unknown": resolved_unknown,
        "abstained": abstained,
        "unresolved": unresolved,
        "coverage_rate": resolved_known / forecasts_due if forecasts_due > 0 else 0.0,
        "unknown_rate": resolved_unknown / forecasts_due if forecasts_due > 0 else 0.0,
        "abstain_rate": abstained / forecasts_due if forecasts_due > 0 else 0.0,
    }


def effective_brier_score(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]]
) -> float:
    """
    Compute effective Brier score including UNKNOWN outcomes as outcome=0.5.

    This penalizes overconfidence when resolutions cannot determine the outcome.
    - YES outcome -> 1.0
    - NO outcome -> 0.0
    - UNKNOWN outcome -> 0.5 (penalizes confident predictions that couldn't be verified)
    - Abstained forecasts use p_yes=0.5
    - Unresolved forecasts (no resolution record) are excluded

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records

    Returns:
        Effective Brier score (0.0 to 1.0)

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    resolution_map = {r["forecast_id"]: r for r in resolutions}

    scores = []
    for forecast in forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        # Skip unresolved forecasts (no resolution record)
        if resolution is None:
            continue

        outcome_str = resolution.get("resolved_outcome")

        # Determine outcome value
        if outcome_str == "YES":
            outcome = 1.0
        elif outcome_str == "NO":
            outcome = 0.0
        elif outcome_str == "UNKNOWN":
            # UNKNOWN outcomes treated as 0.5 - penalizes overconfidence
            outcome = 0.5
        else:
            continue

        # Determine p_yes: abstained uses 0.5, otherwise use probabilities
        if forecast.get("abstain"):
            p_yes = 0.5
        else:
            probs = forecast.get("probabilities", {})
            p_yes = probs.get("YES", 0.5)

        sq_error = (p_yes - outcome) ** 2
        scores.append(sq_error)

    if not scores:
        raise ScoringError("No valid forecast-resolution pairs for effective scoring")

    return sum(scores) / len(scores)


def _brier_score_binary(forecasts: List[Dict[str, Any]], resolutions: List[Dict[str, Any]]) -> float:
    """
    Compute Brier score for binary forecasts (internal implementation).

    Brier = (1/N) * Σ (p_forecast - outcome)²

    Where outcome = 1 if YES, 0 if NO.
    Lower is better. Perfect = 0, worst = 1.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records

    Returns:
        Brier score (0.0 to 1.0)

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    # Build resolution lookup
    resolution_map = {r["forecast_id"]: r for r in resolutions}

    scores = []
    for forecast in forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        if resolution is None:
            continue

        # Skip if abstained or unknown outcome
        if forecast.get("abstain"):
            continue

        outcome_str = resolution.get("resolved_outcome")
        if outcome_str == "UNKNOWN":
            continue

        # Convert outcome to binary
        outcome = 1.0 if outcome_str == "YES" else 0.0

        # Get forecast probability for YES
        probs = forecast.get("probabilities", {})
        p_yes = probs.get("YES", 0.5)

        # Compute squared error
        sq_error = (p_yes - outcome) ** 2
        scores.append(sq_error)

    if not scores:
        raise ScoringError("No valid forecast-resolution pairs for scoring")

    return sum(scores) / len(scores)


def brier_score(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    event_type: str = "binary",
    outcomes: Optional[List[str]] = None
) -> Union[float, Tuple[float, float]]:
    """
    Compute Brier score for forecasts.

    BACKWARD COMPATIBLE: Default behavior unchanged.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        event_type: "binary" (default), "categorical", or "binned_continuous"
        outcomes: Required for multi-outcome events (from catalog allowed_outcomes)

    Returns:
        - binary: float [0, 1]
        - multi-outcome: Tuple[raw, normalized] where raw is [0, 2] and normalized is [0, 1]

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    if event_type == "binary" or outcomes is None:
        return _brier_score_binary(forecasts, resolutions)
    else:
        return multinomial_brier_score(forecasts, resolutions, outcomes)


def brier_skill_score(model_brier: float, baseline_brier: float) -> float:
    """
    Compute Brier skill score relative to baseline.

    Skill = 1 - (Brier_model / Brier_baseline)

    Positive = better than baseline
    Zero = same as baseline
    Negative = worse than baseline

    Args:
        model_brier: Model's Brier score
        baseline_brier: Baseline Brier score

    Returns:
        Skill score (-∞ to 1.0)
    """
    if baseline_brier == 0:
        return 0.0 if model_brier == 0 else float('-inf')

    return 1.0 - (model_brier / baseline_brier)


def climatology_baseline(resolutions: List[Dict[str, Any]]) -> float:
    """
    Compute climatology baseline probability.

    Climatology = historical frequency of YES outcomes.
    Bootstrap: Use 0.5 until N >= 20 resolutions.

    Args:
        resolutions: List of resolution records

    Returns:
        Climatology probability
    """
    valid_outcomes = [
        r for r in resolutions
        if r.get("resolved_outcome") in ["YES", "NO"]
    ]

    if len(valid_outcomes) < 20:
        return 0.5

    yes_count = sum(1 for r in valid_outcomes if r["resolved_outcome"] == "YES")
    return yes_count / len(valid_outcomes)


def climatology_brier(resolutions: List[Dict[str, Any]]) -> float:
    """
    Compute Brier score for climatology baseline.

    Args:
        resolutions: List of resolution records

    Returns:
        Brier score for always-predicting-climatology
    """
    p_clim = climatology_baseline(resolutions)

    valid = [r for r in resolutions if r.get("resolved_outcome") in ["YES", "NO"]]
    if not valid:
        return 0.25  # Default: 0.5^2

    scores = []
    for r in valid:
        outcome = 1.0 if r["resolved_outcome"] == "YES" else 0.0
        sq_error = (p_clim - outcome) ** 2
        scores.append(sq_error)

    return sum(scores) / len(scores)


def persistence_baseline(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Compute persistence baseline predictions.

    Persistence uses the last resolved outcome as the prediction for
    subsequent forecasts of the same event. If no prior resolution exists,
    uses 0.5 as the prediction.

    Args:
        forecasts: List of forecast records (sorted by as_of_utc)
        resolutions: List of resolution records

    Returns:
        Dictionary mapping forecast_id to persistence prediction (P(YES))
    """
    # Build resolution lookup by forecast_id
    resolution_map = {r["forecast_id"]: r for r in resolutions}

    # Track last outcome per event
    last_outcome_per_event: Dict[str, float] = {}

    # Sort forecasts by as_of_utc to process in chronological order
    sorted_forecasts = sorted(forecasts, key=lambda f: f.get("as_of_utc", ""))

    persistence_preds: Dict[str, float] = {}

    for forecast in sorted_forecasts:
        forecast_id = forecast["forecast_id"]
        event_id = forecast.get("event_id")

        # Use last known outcome for this event, or 0.5 if none
        persistence_preds[forecast_id] = last_outcome_per_event.get(event_id, 0.5)

        # Update last outcome if this forecast was resolved
        if forecast_id in resolution_map:
            resolution = resolution_map[forecast_id]
            outcome_str = resolution.get("resolved_outcome")
            if outcome_str == "YES":
                last_outcome_per_event[event_id] = 1.0
            elif outcome_str == "NO":
                last_outcome_per_event[event_id] = 0.0
            # UNKNOWN doesn't update the persistence baseline

    return persistence_preds


def persistence_brier(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]]
) -> float:
    """
    Compute Brier score for persistence baseline.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records

    Returns:
        Brier score for persistence baseline

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    resolution_map = {r["forecast_id"]: r for r in resolutions}
    persistence_preds = persistence_baseline(forecasts, resolutions)

    scores = []
    for forecast in forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        if resolution is None:
            continue

        if forecast.get("abstain"):
            continue

        outcome_str = resolution.get("resolved_outcome")
        if outcome_str == "UNKNOWN":
            continue

        outcome = 1.0 if outcome_str == "YES" else 0.0
        p_pred = persistence_preds.get(forecast_id, 0.5)

        sq_error = (p_pred - outcome) ** 2
        scores.append(sq_error)

    if not scores:
        raise ScoringError("No valid forecast-resolution pairs for persistence scoring")

    return sum(scores) / len(scores)


def _log_score_binary(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    epsilon: float = 1e-10
) -> float:
    """
    Compute log score for binary forecasts (internal implementation).

    Log score = (1/N) * Σ log(p_forecast) if outcome=YES
                       Σ log(1-p_forecast) if outcome=NO

    Higher (less negative) is better. Perfect = 0, worst = -∞.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        epsilon: Small value to avoid log(0)

    Returns:
        Mean log score

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    resolution_map = {r["forecast_id"]: r for r in resolutions}

    scores = []
    for forecast in forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        if resolution is None:
            continue

        if forecast.get("abstain"):
            continue

        outcome_str = resolution.get("resolved_outcome")
        if outcome_str == "UNKNOWN":
            continue

        probs = forecast.get("probabilities", {})
        p_yes = probs.get("YES", 0.5)

        # Clamp to avoid log(0)
        p_yes = max(epsilon, min(1 - epsilon, p_yes))

        if outcome_str == "YES":
            log_prob = math.log(p_yes)
        else:
            log_prob = math.log(1 - p_yes)

        scores.append(log_prob)

    if not scores:
        raise ScoringError("No valid forecast-resolution pairs for log scoring")

    return sum(scores) / len(scores)


def log_score(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    epsilon: float = 1e-10,
    event_type: str = "binary",
    outcomes: Optional[List[str]] = None
) -> float:
    """
    Compute log score for forecasts.

    BACKWARD COMPATIBLE: Default behavior unchanged.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        epsilon: Small value to avoid log(0)
        event_type: "binary" (default), "categorical", or "binned_continuous"
        outcomes: Required for multi-outcome events

    Returns:
        Mean log score

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    if event_type == "binary" or outcomes is None:
        return _log_score_binary(forecasts, resolutions, epsilon)
    else:
        return multinomial_log_score(forecasts, resolutions, outcomes, epsilon)


def get_outcomes_from_catalog(
    catalog: Dict[str, Any],
    event_id: str
) -> List[str]:
    """
    Get allowed_outcomes from catalog, excluding UNKNOWN.

    CRITICAL: Use this, NOT union of forecast keys.

    Args:
        catalog: Loaded catalog dictionary
        event_id: Event identifier

    Returns:
        List of outcomes excluding UNKNOWN

    Raises:
        ScoringError: If event not in catalog
    """
    from . import catalog as cat_module
    event = cat_module.get_event(catalog, event_id)
    if not event:
        raise ScoringError(f"Event {event_id} not in catalog")
    outcomes = event.get("allowed_outcomes", [])
    return [o for o in outcomes if o != "UNKNOWN"]


def multinomial_brier_score(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    outcomes: List[str]
) -> Tuple[float, float]:
    """
    Compute Multinomial Brier score for multi-outcome events.

    Formula: BS = (1/N) * Σ Σ_k (p_k - o_k)² where o_k = 1 if outcome=k else 0

    Args:
        forecasts: List of forecast records with probabilities dict
        resolutions: List of resolution records with resolved_outcome
        outcomes: List from catalog allowed_outcomes (excluding UNKNOWN)

    Returns:
        Tuple of (raw_brier, normalized_brier)
        - raw_brier: [0, 2] range
        - normalized_brier: [0, 1] range (raw / 2)

    Raises:
        ScoringError: If no valid forecast-resolution pairs
        ScoringError: If forecast missing probability for any outcome
    """
    resolution_map = {r["forecast_id"]: r for r in resolutions}
    outcomes_set = set(outcomes)

    scores = []
    for forecast in forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        if resolution is None:
            continue

        # Skip if abstained
        if forecast.get("abstain"):
            continue

        resolved_outcome = resolution.get("resolved_outcome")

        # Skip UNKNOWN resolutions
        if resolved_outcome == "UNKNOWN":
            continue

        # Validate resolved outcome is in our outcome set
        if resolved_outcome not in outcomes_set:
            continue

        # Validate forecast has probability for ALL outcomes
        probs = forecast.get("probabilities", {})
        for outcome in outcomes:
            if outcome not in probs:
                raise ScoringError(
                    f"Forecast {forecast_id} missing probability for outcome '{outcome}'"
                )

        # Compute Brier score for this forecast
        # BS = Σ_k (p_k - o_k)² where o_k = 1 if k == resolved else 0
        brier_sum = 0.0
        for outcome in outcomes:
            p_k = probs[outcome]
            o_k = 1.0 if outcome == resolved_outcome else 0.0
            brier_sum += (p_k - o_k) ** 2

        scores.append(brier_sum)

    if not scores:
        raise ScoringError("No valid forecast-resolution pairs for multinomial scoring")

    raw_brier = sum(scores) / len(scores)
    normalized_brier = raw_brier / 2.0

    return (raw_brier, normalized_brier)


def effective_multinomial_brier_score(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    outcomes: List[str]
) -> Tuple[float, float]:
    """
    Compute effective Brier score - UNKNOWN treated as uniform.

    This is the PRIMARY scoring function (not optional).
    Matches Phase 2 behavior of penalizing UNKNOWN/abstain.

    For UNKNOWN resolutions:
        - Compute Brier against uniform distribution over outcomes
        - Score = Σ_k (p_k - 1/K)²

    For abstained forecasts:
        - Use uniform (1/K each) as predicted distribution

    Args:
        forecasts: List of forecast records with probabilities dict
        resolutions: List of resolution records with resolved_outcome
        outcomes: List from catalog allowed_outcomes (excluding UNKNOWN)

    Returns:
        Tuple of (raw_brier, normalized_brier)

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    resolution_map = {r["forecast_id"]: r for r in resolutions}
    outcomes_set = set(outcomes)
    K = len(outcomes)
    uniform_prob = 1.0 / K if K > 0 else 0.0

    scores = []
    for forecast in forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        # Skip unresolved forecasts
        if resolution is None:
            continue

        resolved_outcome = resolution.get("resolved_outcome")

        # Determine predicted probabilities (abstained uses uniform)
        if forecast.get("abstain"):
            probs = {o: uniform_prob for o in outcomes}
        else:
            probs = forecast.get("probabilities", {})
            # Fill missing probs with 0 (but ideally they should all be present)
            for outcome in outcomes:
                if outcome not in probs:
                    probs[outcome] = 0.0

        # Handle UNKNOWN resolution: treat as uniform target
        if resolved_outcome == "UNKNOWN":
            # Score against uniform distribution
            brier_sum = 0.0
            for outcome in outcomes:
                p_k = probs.get(outcome, uniform_prob)
                o_k = uniform_prob  # Target is uniform
                brier_sum += (p_k - o_k) ** 2
            scores.append(brier_sum)
        elif resolved_outcome in outcomes_set:
            # Normal scoring against actual outcome
            brier_sum = 0.0
            for outcome in outcomes:
                p_k = probs.get(outcome, 0.0)
                o_k = 1.0 if outcome == resolved_outcome else 0.0
                brier_sum += (p_k - o_k) ** 2
            scores.append(brier_sum)
        # Skip outcomes not in our outcome set

    if not scores:
        raise ScoringError("No valid forecast-resolution pairs for effective scoring")

    raw_brier = sum(scores) / len(scores)
    normalized_brier = raw_brier / 2.0

    return (raw_brier, normalized_brier)


def multinomial_log_score(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    outcomes: List[str],
    epsilon: float = 1e-10
) -> float:
    """
    Compute multinomial log score.

    Formula: LS = (1/N) * Σ log(p_resolved)

    Uses epsilon to avoid log(0).
    Excludes UNKNOWN resolutions.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        outcomes: List from catalog allowed_outcomes
        epsilon: Small value to avoid log(0)

    Returns:
        Mean log score

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    resolution_map = {r["forecast_id"]: r for r in resolutions}
    outcomes_set = set(outcomes)

    scores = []
    for forecast in forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        if resolution is None:
            continue

        if forecast.get("abstain"):
            continue

        resolved_outcome = resolution.get("resolved_outcome")
        if resolved_outcome == "UNKNOWN":
            continue

        if resolved_outcome not in outcomes_set:
            continue

        probs = forecast.get("probabilities", {})
        p_resolved = probs.get(resolved_outcome, 0.0)

        # Clamp to avoid log(0)
        p_resolved = max(epsilon, min(1 - epsilon, p_resolved))
        log_prob = math.log(p_resolved)
        scores.append(log_prob)

    if not scores:
        raise ScoringError("No valid forecast-resolution pairs for log scoring")

    return sum(scores) / len(scores)


def per_outcome_calibration(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    outcomes: List[str],
    n_bins: int = 10,
    event_id: Optional[str] = None,
    horizon_days: Optional[int] = None,
    forecaster_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Compute calibration per event/horizon/forecaster.

    Bin boundaries: [0.0, 0.1), [0.1, 0.2), ... [0.9, 1.0]
    Note: Last bin INCLUDES 1.0 (closed interval)

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        outcomes: List from catalog allowed_outcomes
        n_bins: Number of bins (default 10)
        event_id: Optional filter by event
        horizon_days: Optional filter by horizon
        forecaster_id: Optional filter by forecaster

    Returns:
        Dictionary with per-outcome calibration and aggregate error
    """
    resolution_map = {r["forecast_id"]: r for r in resolutions}
    bin_width = 1.0 / n_bins

    # Filter forecasts
    filtered_forecasts = forecasts
    if event_id:
        filtered_forecasts = [f for f in filtered_forecasts if f.get("event_id") == event_id]
    if horizon_days:
        filtered_forecasts = [f for f in filtered_forecasts if f.get("horizon_days") == horizon_days]
    if forecaster_id:
        filtered_forecasts = [f for f in filtered_forecasts if f.get("forecaster_id") == forecaster_id]

    # Initialize per-outcome bins
    per_outcome = {}
    for outcome in outcomes:
        per_outcome[outcome] = {
            "bins": [{
                "bin_start": i * bin_width,
                "bin_end": (i + 1) * bin_width,
                "count": 0,
                "sum_forecast": 0.0,
                "sum_outcome": 0.0,
            } for i in range(n_bins)],
            "total_count": 0,
        }

    # Populate bins
    for forecast in filtered_forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        if resolution is None or forecast.get("abstain"):
            continue

        resolved_outcome = resolution.get("resolved_outcome")
        if resolved_outcome == "UNKNOWN":
            continue

        probs = forecast.get("probabilities", {})

        for outcome in outcomes:
            p_k = probs.get(outcome, 0.0)
            o_k = 1.0 if outcome == resolved_outcome else 0.0

            # Find bin (handle edge case at 1.0 - last bin includes 1.0)
            bin_idx = min(int(p_k / bin_width), n_bins - 1)

            per_outcome[outcome]["bins"][bin_idx]["count"] += 1
            per_outcome[outcome]["bins"][bin_idx]["sum_forecast"] += p_k
            per_outcome[outcome]["bins"][bin_idx]["sum_outcome"] += o_k
            per_outcome[outcome]["total_count"] += 1

    # Compute bin statistics and calibration error per outcome
    total_weighted_error = 0.0
    total_count = 0

    for outcome in outcomes:
        outcome_bins = per_outcome[outcome]["bins"]
        outcome_total_error = 0.0
        outcome_total_count = 0

        for b in outcome_bins:
            if b["count"] > 0:
                b["mean_forecast"] = b["sum_forecast"] / b["count"]
                b["observed_frequency"] = b["sum_outcome"] / b["count"]
                b["absolute_error"] = abs(b["mean_forecast"] - b["observed_frequency"])

                outcome_total_error += b["absolute_error"] * b["count"]
                outcome_total_count += b["count"]
            else:
                b["mean_forecast"] = None
                b["observed_frequency"] = None
                b["absolute_error"] = None

            # Clean up intermediate values
            del b["sum_forecast"]
            del b["sum_outcome"]

        # Calibration error for this outcome
        if outcome_total_count > 0:
            per_outcome[outcome]["calibration_error"] = outcome_total_error / outcome_total_count
            total_weighted_error += outcome_total_error
            total_count += outcome_total_count
        else:
            per_outcome[outcome]["calibration_error"] = None

    # Aggregate calibration error (weighted mean across outcomes)
    aggregate_error = total_weighted_error / total_count if total_count > 0 else None

    return {
        "per_outcome": per_outcome,
        "aggregate_calibration_error": aggregate_error,
        "total_forecasts": total_count // len(outcomes) if outcomes else 0,
        "filters_applied": {
            "event_id": event_id,
            "horizon_days": horizon_days,
            "forecaster_id": forecaster_id,
        }
    }


def multinomial_climatology_baseline(
    resolutions: List[Dict[str, Any]],
    outcomes: List[str],
    event_id: str,
    horizon_days: int,
    min_samples: int = 20,
    mode_filter: List[str] = None
) -> Dict[str, float]:
    """
    Historical frequency of each outcome for specific event/horizon.

    CRITICAL:
    - Only uses resolutions with resolution_mode in mode_filter
    - EXCLUDES resolutions with resolved_outcome == "UNKNOWN"
    - Falls back to uniform (1/K each) if N < min_samples

    Args:
        resolutions: All resolution records
        outcomes: From catalog allowed_outcomes (excluding UNKNOWN)
        event_id: Filter to this event
        horizon_days: Filter to this horizon
        min_samples: Minimum before using historical freq
        mode_filter: Only include these resolution modes

    Returns:
        Dictionary mapping outcome -> probability
    """
    if mode_filter is None:
        mode_filter = ["external_auto", "external_manual"]

    # Filter resolutions
    filtered = [
        r for r in resolutions
        if r.get("event_id") == event_id
        and r.get("horizon_days") == horizon_days
        and r.get("resolved_outcome") != "UNKNOWN"
        and resolver.get_resolution_mode(r) in mode_filter
    ]

    K = len(outcomes)
    uniform = 1.0 / K if K > 0 else 0.0

    if len(filtered) < min_samples:
        return {o: uniform for o in outcomes}

    # Count occurrences of each outcome
    counts = {o: 0 for o in outcomes}
    total = 0
    for r in filtered:
        outcome = r.get("resolved_outcome")
        if outcome in counts:
            counts[outcome] += 1
            total += 1

    if total == 0:
        return {o: uniform for o in outcomes}

    return {o: counts[o] / total for o in outcomes}


def multinomial_climatology_brier(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    outcomes: List[str],
    event_id: str,
    horizon_days: int,
    mode_filter: List[str] = None
) -> Tuple[float, float]:
    """
    Brier score for always-predicting-climatology baseline.

    Computes climatology from same resolution subset used for scoring.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        outcomes: From catalog allowed_outcomes (excluding UNKNOWN)
        event_id: Filter to this event
        horizon_days: Filter to this horizon
        mode_filter: Resolution modes to include

    Returns:
        Tuple of (raw_brier, normalized_brier)

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    if mode_filter is None:
        mode_filter = ["external_auto", "external_manual"]

    # Get climatology distribution
    clim_probs = multinomial_climatology_baseline(
        resolutions, outcomes, event_id, horizon_days,
        mode_filter=mode_filter
    )

    # Filter forecasts and resolutions
    filtered_forecasts = [
        f for f in forecasts
        if f.get("event_id") == event_id and f.get("horizon_days") == horizon_days
    ]

    filtered_resolutions = [
        r for r in resolutions
        if r.get("event_id") == event_id
        and r.get("horizon_days") == horizon_days
        and resolver.get_resolution_mode(r) in mode_filter
    ]

    resolution_map = {r["forecast_id"]: r for r in filtered_resolutions}
    outcomes_set = set(outcomes)

    scores = []
    for forecast in filtered_forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        if resolution is None:
            continue

        resolved_outcome = resolution.get("resolved_outcome")
        if resolved_outcome == "UNKNOWN" or resolved_outcome not in outcomes_set:
            continue

        # Compute Brier using climatology as prediction
        brier_sum = 0.0
        for outcome in outcomes:
            p_k = clim_probs[outcome]
            o_k = 1.0 if outcome == resolved_outcome else 0.0
            brier_sum += (p_k - o_k) ** 2

        scores.append(brier_sum)

    if not scores:
        raise ScoringError("No valid pairs for climatology baseline scoring")

    raw_brier = sum(scores) / len(scores)
    normalized_brier = raw_brier / 2.0

    return (raw_brier, normalized_brier)


def multinomial_persistence_baseline(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    outcomes: List[str],
    event_id: str,
    horizon_days: int,
    mode_filter: List[str] = None
) -> Dict[str, Dict[str, float]]:
    """
    Last resolved outcome gets P=1.0, all others P=0.0.
    First forecast (no prior resolution) uses uniform.

    CRITICAL:
    - Only considers resolutions with mode in mode_filter
    - EXCLUDES resolutions with resolved_outcome == "UNKNOWN"
    - SORTS by target_date_utc (ascending) for deterministic "last outcome"

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        outcomes: From catalog allowed_outcomes (excluding UNKNOWN)
        event_id: Filter to this event
        horizon_days: Filter to this horizon
        mode_filter: Resolution modes to include

    Returns:
        Dict[forecast_id -> {outcome: probability}]
    """
    if mode_filter is None:
        mode_filter = ["external_auto", "external_manual"]

    K = len(outcomes)
    uniform = {o: 1.0 / K for o in outcomes} if K > 0 else {}

    # Filter to this event/horizon
    filtered_forecasts = [
        f for f in forecasts
        if f.get("event_id") == event_id and f.get("horizon_days") == horizon_days
    ]

    # Sort forecasts by target_date_utc for deterministic ordering
    sorted_forecasts = sorted(
        filtered_forecasts,
        key=lambda f: f.get("target_date_utc", "")
    )

    # Build resolution lookup, filtered by mode
    filtered_resolutions = [
        r for r in resolutions
        if r.get("event_id") == event_id
        and r.get("horizon_days") == horizon_days
        and r.get("resolved_outcome") != "UNKNOWN"
        and resolver.get_resolution_mode(r) in mode_filter
    ]
    resolution_map = {r["forecast_id"]: r for r in filtered_resolutions}

    # Track last outcome
    last_outcome: Optional[str] = None
    persistence_preds: Dict[str, Dict[str, float]] = {}

    for forecast in sorted_forecasts:
        forecast_id = forecast["forecast_id"]

        # Use last outcome or uniform if none
        if last_outcome is None:
            persistence_preds[forecast_id] = uniform.copy()
        else:
            # Deterministic: P=1 for last outcome, P=0 for others
            persistence_preds[forecast_id] = {
                o: (1.0 if o == last_outcome else 0.0) for o in outcomes
            }

        # Update last outcome if this forecast was resolved
        if forecast_id in resolution_map:
            resolution = resolution_map[forecast_id]
            resolved = resolution.get("resolved_outcome")
            if resolved in outcomes:
                last_outcome = resolved

    return persistence_preds


def multinomial_persistence_brier(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    outcomes: List[str],
    event_id: str,
    horizon_days: int,
    mode_filter: List[str] = None
) -> Tuple[float, float]:
    """
    Compute Brier score for persistence baseline.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        outcomes: From catalog allowed_outcomes (excluding UNKNOWN)
        event_id: Filter to this event
        horizon_days: Filter to this horizon
        mode_filter: Resolution modes to include

    Returns:
        Tuple of (raw_brier, normalized_brier)

    Raises:
        ScoringError: If no valid forecast-resolution pairs
    """
    if mode_filter is None:
        mode_filter = ["external_auto", "external_manual"]

    persistence_preds = multinomial_persistence_baseline(
        forecasts, resolutions, outcomes, event_id, horizon_days,
        mode_filter=mode_filter
    )

    # Filter resolutions by mode
    filtered_resolutions = [
        r for r in resolutions
        if r.get("event_id") == event_id
        and r.get("horizon_days") == horizon_days
        and resolver.get_resolution_mode(r) in mode_filter
    ]
    resolution_map = {r["forecast_id"]: r for r in filtered_resolutions}
    outcomes_set = set(outcomes)

    scores = []
    for forecast_id, pred_probs in persistence_preds.items():
        resolution = resolution_map.get(forecast_id)

        if resolution is None:
            continue

        resolved_outcome = resolution.get("resolved_outcome")
        if resolved_outcome == "UNKNOWN" or resolved_outcome not in outcomes_set:
            continue

        # Compute Brier using persistence as prediction
        brier_sum = 0.0
        for outcome in outcomes:
            p_k = pred_probs.get(outcome, 0.0)
            o_k = 1.0 if outcome == resolved_outcome else 0.0
            brier_sum += (p_k - o_k) ** 2

        scores.append(brier_sum)

    if not scores:
        raise ScoringError("No valid pairs for persistence baseline scoring")

    raw_brier = sum(scores) / len(scores)
    normalized_brier = raw_brier / 2.0

    return (raw_brier, normalized_brier)


def multinomial_climatology_baseline_with_metadata(
    resolutions: List[Dict[str, Any]],
    outcomes: List[str],
    event_id: str,
    horizon_days: int,
    min_samples: int = 20,
    mode_filter: List[str] = None
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Historical frequency with metadata for fallback flagging.

    Phase 3B Red-Team Fix 3: Flag when baseline uses uniform fallback.

    Returns:
        Tuple of (probabilities, metadata)

        metadata = {
            "baseline_history_n": int,  # 0 if fallback
            "fallback": "uniform" | None,
            "event_id": str,
            "horizon_days": int,
        }
    """
    if mode_filter is None:
        mode_filter = ["external_auto", "external_manual"]

    # Filter resolutions
    filtered = [
        r for r in resolutions
        if r.get("event_id") == event_id
        and r.get("horizon_days") == horizon_days
        and r.get("resolved_outcome") != "UNKNOWN"
        and resolver.get_resolution_mode(r) in mode_filter
    ]

    K = len(outcomes)
    uniform = 1.0 / K if K > 0 else 0.0

    metadata = {
        "baseline_history_n": len(filtered),
        "event_id": event_id,
        "horizon_days": horizon_days,
    }

    if len(filtered) < min_samples:
        metadata["fallback"] = "uniform"
        return ({o: uniform for o in outcomes}, metadata)

    # Count occurrences of each outcome
    counts = {o: 0 for o in outcomes}
    total = 0
    for r in filtered:
        outcome = r.get("resolved_outcome")
        if outcome in counts:
            counts[outcome] += 1
            total += 1

    if total == 0:
        metadata["fallback"] = "uniform"
        return ({o: uniform for o in outcomes}, metadata)

    metadata["fallback"] = None
    return ({o: counts[o] / total for o in outcomes}, metadata)


def multinomial_persistence_baseline_with_metadata(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    outcomes: List[str],
    event_id: str,
    horizon_days: int,
    mode_filter: List[str] = None
) -> Tuple[Dict[str, Dict[str, float]], Dict[str, Any]]:
    """
    Persistence baseline with metadata for fallback flagging.

    Phase 3B Red-Team Fix 3: Flag when baseline uses uniform fallback.

    Returns:
        Tuple of (predictions, metadata)

        predictions = {forecast_id: {outcome: probability}}
        metadata = {
            "baseline_history_n": int,  # Number of valid resolutions used
            "fallback": "uniform" | None,  # Set if first forecasts had no prior
            "first_forecast_fallback": bool,  # True if first forecast used uniform
            "event_id": str,
            "horizon_days": int,
        }
    """
    if mode_filter is None:
        mode_filter = ["external_auto", "external_manual"]

    K = len(outcomes)
    uniform = {o: 1.0 / K for o in outcomes} if K > 0 else {}

    # Filter to this event/horizon
    filtered_forecasts = [
        f for f in forecasts
        if f.get("event_id") == event_id and f.get("horizon_days") == horizon_days
    ]

    # Sort forecasts by target_date_utc for deterministic ordering
    sorted_forecasts = sorted(
        filtered_forecasts,
        key=lambda f: f.get("target_date_utc", "")
    )

    # Build resolution lookup, filtered by mode
    filtered_resolutions = [
        r for r in resolutions
        if r.get("event_id") == event_id
        and r.get("horizon_days") == horizon_days
        and r.get("resolved_outcome") != "UNKNOWN"
        and resolver.get_resolution_mode(r) in mode_filter
    ]
    resolution_map = {r["forecast_id"]: r for r in filtered_resolutions}

    metadata = {
        "baseline_history_n": len(filtered_resolutions),
        "event_id": event_id,
        "horizon_days": horizon_days,
        "first_forecast_fallback": len(sorted_forecasts) > 0,  # First always uses uniform
    }

    # Track last outcome
    last_outcome: Optional[str] = None
    persistence_preds: Dict[str, Dict[str, float]] = {}
    fallback_used = False

    for forecast in sorted_forecasts:
        forecast_id = forecast["forecast_id"]

        # Use last outcome or uniform if none
        if last_outcome is None:
            persistence_preds[forecast_id] = uniform.copy()
            fallback_used = True
        else:
            # Deterministic: P=1 for last outcome, P=0 for others
            persistence_preds[forecast_id] = {
                o: (1.0 if o == last_outcome else 0.0) for o in outcomes
            }

        # Update last outcome if this forecast was resolved
        if forecast_id in resolution_map:
            resolution = resolution_map[forecast_id]
            resolved = resolution.get("resolved_outcome")
            if resolved in outcomes:
                last_outcome = resolved

    metadata["fallback"] = "uniform" if fallback_used else None

    return (persistence_preds, metadata)


def group_by_forecaster(
    forecasts: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group forecasts by forecaster_id.

    Args:
        forecasts: List of forecast records

    Returns:
        Dictionary mapping forecaster_id to list of forecasts
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for f in forecasts:
        fid = f.get("forecaster_id", "unknown")
        groups.setdefault(fid, []).append(f)
    return groups


def compute_scores_by_forecaster(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    catalog: Dict[str, Any],
    mode_filter: List[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Compute separate scores for each forecaster_id.

    Prevents baseline forecasts (oracle_baseline_*) from
    polluting main forecaster (oracle_v1) scores.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        catalog: Event catalog dictionary
        mode_filter: Resolution modes to include

    Returns:
        Dictionary mapping forecaster_id to scores
    """
    from . import catalog as cat_module

    if mode_filter is None:
        mode_filter = ["external_auto", "external_manual"]

    groups = group_by_forecaster(forecasts)
    results: Dict[str, Dict[str, Any]] = {}

    for forecaster_id, forecaster_forecasts in groups.items():
        # Count forecasts by event type
        binary_forecasts = []
        multi_forecasts = []

        for f in forecaster_forecasts:
            event_id = f.get("event_id")
            event = cat_module.get_event(catalog, event_id)
            if event is None:
                continue

            event_type = event.get("event_type", "binary")
            if event_type == "binary":
                binary_forecasts.append(f)
            else:
                multi_forecasts.append(f)

        # Compute scores for this forecaster
        forecaster_scores: Dict[str, Any] = {
            "count": len(forecaster_forecasts),
            "binary_count": len(binary_forecasts),
            "multi_count": len(multi_forecasts),
        }

        # Binary Brier score
        if binary_forecasts:
            try:
                bs = brier_score(binary_forecasts, resolutions)
                forecaster_scores["binary_brier_score"] = round(bs, 6)
            except ScoringError:
                forecaster_scores["binary_brier_score"] = None

            try:
                ls = log_score(binary_forecasts, resolutions)
                forecaster_scores["binary_log_score"] = round(ls, 6)
            except ScoringError:
                forecaster_scores["binary_log_score"] = None

        # Multi-outcome scores (aggregate across all multi-outcome events)
        if multi_forecasts:
            multi_brier_scores = []
            multi_log_scores = []

            # Group by event to get proper outcomes
            event_forecasts: Dict[str, List[Dict[str, Any]]] = {}
            for f in multi_forecasts:
                eid = f.get("event_id")
                event_forecasts.setdefault(eid, []).append(f)

            for event_id, ef in event_forecasts.items():
                event = cat_module.get_event(catalog, event_id)
                if not event:
                    continue

                outcomes = get_outcomes_from_catalog(catalog, event_id)
                if not outcomes:
                    continue

                try:
                    raw, norm = effective_multinomial_brier_score(ef, resolutions, outcomes)
                    multi_brier_scores.append((norm, len(ef)))
                except ScoringError:
                    pass

                try:
                    ls = multinomial_log_score(ef, resolutions, outcomes)
                    multi_log_scores.append((ls, len(ef)))
                except ScoringError:
                    pass

            # Weighted average across events
            if multi_brier_scores:
                total_weight = sum(w for _, w in multi_brier_scores)
                weighted_brier = sum(s * w for s, w in multi_brier_scores) / total_weight
                forecaster_scores["multi_brier_score"] = round(weighted_brier, 6)
            else:
                forecaster_scores["multi_brier_score"] = None

            if multi_log_scores:
                total_weight = sum(w for _, w in multi_log_scores)
                weighted_log = sum(s * w for s, w in multi_log_scores) / total_weight
                forecaster_scores["multi_log_score"] = round(weighted_log, 6)
            else:
                forecaster_scores["multi_log_score"] = None

        # Combined Brier (normalized, effective) - use binary if no multi
        if "multi_brier_score" in forecaster_scores and forecaster_scores["multi_brier_score"] is not None:
            if "binary_brier_score" in forecaster_scores and forecaster_scores["binary_brier_score"] is not None:
                # Weighted average of binary and multi
                binary_w = len(binary_forecasts)
                multi_w = len(multi_forecasts)
                total_w = binary_w + multi_w
                combined = (
                    forecaster_scores["binary_brier_score"] * binary_w +
                    forecaster_scores["multi_brier_score"] * multi_w
                ) / total_w
                forecaster_scores["brier_score"] = round(combined, 6)
            else:
                forecaster_scores["brier_score"] = forecaster_scores["multi_brier_score"]
        elif "binary_brier_score" in forecaster_scores:
            forecaster_scores["brier_score"] = forecaster_scores.get("binary_brier_score")

        results[forecaster_id] = forecaster_scores

    return results


def calibration_bins(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    n_bins: int = 10
) -> Dict[str, Any]:
    """
    Compute calibration statistics across probability bins.

    Bins: [0.0-0.1), [0.1-0.2), ..., [0.9-1.0]

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        n_bins: Number of bins (default 10)

    Returns:
        Dictionary with:
        - bins: List of bin statistics
        - calibration_error: Mean absolute deviation from diagonal
    """
    # Build resolution lookup
    resolution_map = {r["forecast_id"]: r for r in resolutions}

    # Initialize bins
    bin_width = 1.0 / n_bins
    bins = [{
        "bin_start": i * bin_width,
        "bin_end": (i + 1) * bin_width,
        "count": 0,
        "sum_forecast": 0.0,
        "sum_outcome": 0.0,
    } for i in range(n_bins)]

    # Populate bins
    for forecast in forecasts:
        forecast_id = forecast["forecast_id"]
        resolution = resolution_map.get(forecast_id)

        if resolution is None or forecast.get("abstain"):
            continue

        outcome_str = resolution.get("resolved_outcome")
        if outcome_str == "UNKNOWN":
            continue

        p_yes = forecast.get("probabilities", {}).get("YES", 0.5)
        outcome = 1.0 if outcome_str == "YES" else 0.0

        # Find bin (handle edge case at 1.0)
        bin_idx = min(int(p_yes / bin_width), n_bins - 1)

        bins[bin_idx]["count"] += 1
        bins[bin_idx]["sum_forecast"] += p_yes
        bins[bin_idx]["sum_outcome"] += outcome

    # Compute bin statistics
    total_error = 0.0
    total_count = 0

    for b in bins:
        if b["count"] > 0:
            b["mean_forecast"] = b["sum_forecast"] / b["count"]
            b["observed_frequency"] = b["sum_outcome"] / b["count"]
            b["absolute_error"] = abs(b["mean_forecast"] - b["observed_frequency"])

            total_error += b["absolute_error"] * b["count"]
            total_count += b["count"]
        else:
            b["mean_forecast"] = None
            b["observed_frequency"] = None
            b["absolute_error"] = None

        # Clean up intermediate values
        del b["sum_forecast"]
        del b["sum_outcome"]

    # Mean calibration error
    calibration_error = total_error / total_count if total_count > 0 else None

    return {
        "bins": bins,
        "calibration_error": calibration_error,
        "total_forecasts": total_count,
    }


def compute_scores(
    ledger_dir: Path = ledger.LEDGER_DIR,
    event_id: Optional[str] = None,
    horizon_days: Optional[int] = None,
    catalog: Optional[Dict[str, Any]] = None,
    mode_filter: List[str] = None
) -> Dict[str, Any]:
    """
    Compute all scoring metrics for resolved forecasts.

    Args:
        ledger_dir: Path to ledger directory
        event_id: Optional filter by event ID
        horizon_days: Optional filter by horizon
        catalog: Optional event catalog (loads config/event_catalog.json if not provided)
        mode_filter: Resolution modes to include (default: external_auto + external_manual)

    Returns:
        Dictionary with:
        - brier_score: Model Brier score (binary events only, float)
        - baseline_brier: Climatology baseline Brier
        - skill_score: Brier skill score
        - calibration: Calibration bin statistics
        - counts: Various counts (resolved, unresolved, abstained)
        - coverage: Coverage metrics (forecasts_due, coverage_rate, etc.)
        - effective_brier: Brier treating UNKNOWN/abstain as p=0.5
        - core_scores: Scores for external_auto + external_manual only
        - claims_inferred_scores: Scores for claims_inferred only
        - combined_scores: All resolutions combined (reference)
        - scores_by_forecaster: Scores grouped by forecaster_id (NEW)
        - scores_by_type: Scores grouped by event_type (NEW)
        - scores_by_event: Scores per event with by_horizon breakdown (NEW)
    """
    from . import catalog as cat_module

    # Load catalog if not provided
    if catalog is None:
        catalog = cat_module.load_catalog(Path("config/event_catalog.json"))

    if mode_filter is None:
        mode_filter = ["external_auto", "external_manual"]

    # Load forecasts and resolutions
    forecasts = ledger.get_forecasts(ledger_dir)
    resolutions = ledger.get_resolutions(ledger_dir)

    # Apply filters
    if event_id:
        forecasts = [f for f in forecasts if f.get("event_id") == event_id]
        resolutions = [r for r in resolutions if r.get("event_id") == event_id]

    if horizon_days:
        forecasts = [f for f in forecasts if f.get("horizon_days") == horizon_days]
        resolutions = [r for r in resolutions if r.get("horizon_days") == horizon_days]

    # Count statistics
    resolution_map = {r["forecast_id"]: r for r in resolutions}

    resolved_count = 0
    unresolved_count = 0
    abstained_count = 0
    unknown_count = 0

    for f in forecasts:
        if f.get("abstain"):
            abstained_count += 1
        elif f["forecast_id"] in resolution_map:
            res = resolution_map[f["forecast_id"]]
            if res.get("resolved_outcome") == "UNKNOWN":
                unknown_count += 1
            else:
                resolved_count += 1
        else:
            unresolved_count += 1

    # Compute scores
    result = {
        "counts": {
            "total_forecasts": len(forecasts),
            "resolved": resolved_count,
            "unresolved": unresolved_count,
            "abstained": abstained_count,
            "unknown": unknown_count,
        },
        "filters": {
            "event_id": event_id,
            "horizon_days": horizon_days,
        }
    }

    # Add coverage metrics
    result["coverage"] = compute_coverage_metrics(forecasts, resolutions)

    # Filter to primary forecaster only for top-level scores
    # Exclude baseline forecasters (oracle_baseline_*) to prevent pollution
    primary_forecasts = [
        f for f in forecasts
        if not f.get("forecaster_id", "").startswith("oracle_baseline_")
    ]

    # NEW Phase 3B Red-Team Fix 2: Separate accuracy from penalty metrics
    # Compute accuracy metrics (primary scores - resolved non-UNKNOWN only)
    accuracy_metrics: Dict[str, Any] = {}
    try:
        # Primary Brier: only resolved, non-UNKNOWN forecasts
        acc_brier = brier_score(primary_forecasts, resolutions)
        accuracy_metrics["brier_score"] = round(acc_brier, 6)
    except ScoringError:
        accuracy_metrics["brier_score"] = None

    try:
        acc_log = log_score(primary_forecasts, resolutions)
        accuracy_metrics["log_score"] = round(acc_log, 6)
    except ScoringError:
        accuracy_metrics["log_score"] = None

    try:
        acc_calib = calibration_bins(primary_forecasts, resolutions)
        accuracy_metrics["calibration_error"] = acc_calib.get("calibration_error")
    except Exception:
        accuracy_metrics["calibration_error"] = None

    result["accuracy"] = accuracy_metrics

    # Compute penalty metrics (UNKNOWN/abstain penalties separately)
    penalty_metrics: Dict[str, Any] = {}

    # Effective Brier: includes UNKNOWN penalty (UNKNOWN treated as outcome=0.5)
    try:
        eff_brier = effective_brier_score(primary_forecasts, resolutions)
        penalty_metrics["effective_brier"] = round(eff_brier, 6)
    except ScoringError:
        penalty_metrics["effective_brier"] = None

    # Compute abstention penalty (what's the Brier hit from abstaining?)
    # This is the difference between effective Brier and primary Brier
    if accuracy_metrics["brier_score"] is not None and penalty_metrics["effective_brier"] is not None:
        penalty_metrics["unknown_abstain_penalty"] = round(
            penalty_metrics["effective_brier"] - accuracy_metrics["brier_score"], 6
        )
    else:
        penalty_metrics["unknown_abstain_penalty"] = None

    # Combined penalty Brier is same as effective Brier (both penalties applied)
    penalty_metrics["combined_penalty_brier"] = penalty_metrics["effective_brier"]

    result["penalty_metrics"] = penalty_metrics

    # Add effective Brier score (primary forecaster only) - backward compat alias
    result["effective_brier"] = penalty_metrics["effective_brier"]

    # Add scores separated by resolution mode (primary forecaster only)
    # Core scores: external_auto + external_manual
    result["core_scores"] = compute_scores_for_mode(
        primary_forecasts, resolutions, ["external_auto", "external_manual"]
    )

    # Claims inferred scores
    result["claims_inferred_scores"] = compute_scores_for_mode(
        primary_forecasts, resolutions, ["claims_inferred"]
    )

    # Combined scores (all modes)
    result["combined_scores"] = compute_scores_for_mode(
        primary_forecasts, resolutions, None
    )

    # Recompute resolved_count for primary forecaster only
    primary_resolved_count = 0
    for f in primary_forecasts:
        if not f.get("abstain") and f["forecast_id"] in resolution_map:
            res = resolution_map[f["forecast_id"]]
            if res.get("resolved_outcome") != "UNKNOWN":
                primary_resolved_count += 1

    if primary_resolved_count > 0:
        try:
            model_brier = brier_score(primary_forecasts, resolutions)
            clim_brier = climatology_brier(resolutions)
            clim_skill = brier_skill_score(model_brier, clim_brier)
            calibration = calibration_bins(primary_forecasts, resolutions)

            result["brier_score"] = round(model_brier, 6)
            result["climatology_brier"] = round(clim_brier, 6)
            result["climatology_skill_score"] = round(clim_skill, 6)
            result["climatology_p"] = round(climatology_baseline(resolutions), 4)

            # Persistence baseline (primary forecaster only)
            try:
                pers_brier = persistence_brier(primary_forecasts, resolutions)
                pers_skill = brier_skill_score(model_brier, pers_brier)
                result["persistence_brier"] = round(pers_brier, 6)
                result["persistence_skill_score"] = round(pers_skill, 6)
            except ScoringError:
                result["persistence_brier"] = None
                result["persistence_skill_score"] = None

            # Log score (primary forecaster only)
            try:
                model_log = log_score(primary_forecasts, resolutions)
                result["log_score"] = round(model_log, 6)
            except ScoringError:
                result["log_score"] = None

            result["calibration"] = calibration

            # Backwards compatibility: keep baseline_brier and skill_score as aliases
            result["baseline_brier"] = result["climatology_brier"]
            result["skill_score"] = result["climatology_skill_score"]
        except ScoringError as e:
            result["scoring_error"] = str(e)
    else:
        result["scoring_note"] = "No resolved forecasts available for scoring"

    # NEW Phase 3B Red-Team Fix 3: Baselines with metadata and fallback flagging
    warnings: List[str] = []

    # Get baseline metadata for binary events (uses simpler baseline functions)
    valid_binary_resolutions = [
        r for r in resolutions
        if r.get("resolved_outcome") in ["YES", "NO"]
    ]
    climatology_history_n = len(valid_binary_resolutions)
    climatology_fallback = "uniform" if climatology_history_n < 20 else None

    # Count valid persistence resolutions
    persistence_history_n = climatology_history_n  # Same set for binary

    baselines_metadata: Dict[str, Dict[str, Any]] = {
        "climatology": {
            "brier_score": result.get("climatology_brier"),
            "history_n": climatology_history_n,
            "fallback": climatology_fallback,
        },
        "persistence": {
            "brier_score": result.get("persistence_brier"),
            "history_n": persistence_history_n,
            "fallback": "uniform" if persistence_history_n == 0 else None,
        }
    }

    # Add warnings for fallback baselines
    if climatology_fallback == "uniform":
        warnings.append(
            f"climatology baseline used uniform fallback (history_n={climatology_history_n})"
        )
    if baselines_metadata["persistence"]["fallback"] == "uniform":
        warnings.append(
            f"persistence baseline used uniform fallback (history_n={persistence_history_n})"
        )

    result["baselines"] = baselines_metadata
    result["warnings"] = warnings

    # NEW: Scores by forecaster
    try:
        result["scores_by_forecaster"] = compute_scores_by_forecaster(
            forecasts, resolutions, catalog, mode_filter
        )
    except Exception:
        result["scores_by_forecaster"] = {}

    # NEW: Scores by event type
    result["scores_by_type"] = _compute_scores_by_type(
        forecasts, resolutions, catalog, mode_filter
    )

    # NEW: Scores by event
    result["scores_by_event"] = _compute_scores_by_event(
        forecasts, resolutions, catalog, mode_filter
    )

    return result


def _compute_scores_by_type(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    catalog: Dict[str, Any],
    mode_filter: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Compute scores grouped by event type.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        catalog: Event catalog
        mode_filter: Resolution modes to include

    Returns:
        Dictionary with scores for each event type
    """
    from . import catalog as cat_module

    # Group forecasts by event type
    type_forecasts: Dict[str, List[Dict[str, Any]]] = {
        "binary": [],
        "categorical": [],
        "binned_continuous": [],
    }

    for f in forecasts:
        event_id = f.get("event_id")
        event = cat_module.get_event(catalog, event_id)
        if event is None:
            continue
        event_type = event.get("event_type", "binary")
        if event_type in type_forecasts:
            type_forecasts[event_type].append(f)

    results: Dict[str, Dict[str, Any]] = {}

    # Binary scores
    binary_forecasts = type_forecasts["binary"]
    if binary_forecasts:
        binary_result: Dict[str, Any] = {"count": len(binary_forecasts)}
        try:
            bs = _brier_score_binary(binary_forecasts, resolutions)
            binary_result["brier_score"] = round(bs, 6)
        except ScoringError:
            binary_result["brier_score"] = None
        try:
            ls = _log_score_binary(binary_forecasts, resolutions)
            binary_result["log_score"] = round(ls, 6)
        except ScoringError:
            binary_result["log_score"] = None
        try:
            eff_bs = effective_brier_score(binary_forecasts, resolutions)
            binary_result["effective_brier"] = round(eff_bs, 6)
        except ScoringError:
            binary_result["effective_brier"] = None
        results["binary"] = binary_result

    # Multi-outcome scores (categorical and binned_continuous)
    for event_type in ["categorical", "binned_continuous"]:
        type_fcsts = type_forecasts[event_type]
        if not type_fcsts:
            continue

        type_result: Dict[str, Any] = {"count": len(type_fcsts)}

        # Group by event to get proper outcomes
        event_groups: Dict[str, List[Dict[str, Any]]] = {}
        for f in type_fcsts:
            eid = f.get("event_id")
            event_groups.setdefault(eid, []).append(f)

        # Aggregate scores across events
        brier_scores = []
        log_scores = []
        total_count = 0

        for event_id, ef in event_groups.items():
            try:
                outcomes = get_outcomes_from_catalog(catalog, event_id)
            except ScoringError:
                continue
            if not outcomes:
                continue

            try:
                raw, norm = effective_multinomial_brier_score(ef, resolutions, outcomes)
                brier_scores.append((norm, len(ef)))
                total_count += len(ef)
            except ScoringError:
                pass

            try:
                ls = multinomial_log_score(ef, resolutions, outcomes)
                log_scores.append((ls, len(ef)))
            except ScoringError:
                pass

        # Weighted average
        if brier_scores:
            total_weight = sum(w for _, w in brier_scores)
            type_result["brier_score"] = round(
                sum(s * w for s, w in brier_scores) / total_weight, 6
            )
        else:
            type_result["brier_score"] = None

        if log_scores:
            total_weight = sum(w for _, w in log_scores)
            type_result["log_score"] = round(
                sum(s * w for s, w in log_scores) / total_weight, 6
            )
        else:
            type_result["log_score"] = None

        # Baselines (aggregate across events - simplified)
        type_result["baselines"] = {
            "climatology_brier": None,
            "persistence_brier": None,
        }
        type_result["skill_scores"] = {
            "vs_climatology": None,
            "vs_persistence": None,
        }

        results[event_type] = type_result

    return results


def _compute_scores_by_event(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    catalog: Dict[str, Any],
    mode_filter: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Compute scores per event with by_horizon breakdown.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        catalog: Event catalog
        mode_filter: Resolution modes to include

    Returns:
        Dictionary with scores for each event_id
    """
    from . import catalog as cat_module

    # Group forecasts by event_id
    event_forecasts: Dict[str, List[Dict[str, Any]]] = {}
    for f in forecasts:
        event_id = f.get("event_id")
        if event_id:
            event_forecasts.setdefault(event_id, []).append(f)

    results: Dict[str, Dict[str, Any]] = {}

    for event_id, ef in event_forecasts.items():
        event = cat_module.get_event(catalog, event_id)
        if event is None:
            continue

        event_type = event.get("event_type", "binary")
        event_result: Dict[str, Any] = {
            "event_type": event_type,
            "count": len(ef),
        }

        # Get outcomes for multi-outcome events
        if event_type != "binary":
            try:
                outcomes = get_outcomes_from_catalog(catalog, event_id)
            except ScoringError:
                outcomes = []
        else:
            outcomes = []

        # Compute scores based on event type
        if event_type == "binary":
            try:
                bs = _brier_score_binary(ef, resolutions)
                event_result["brier_score"] = round(bs, 6)
            except ScoringError:
                event_result["brier_score"] = None
            try:
                cal = calibration_bins(ef, resolutions)
                event_result["calibration"] = cal
            except Exception:
                event_result["calibration"] = None
        elif outcomes:
            try:
                raw, norm = effective_multinomial_brier_score(ef, resolutions, outcomes)
                event_result["brier_score"] = round(norm, 6)
                event_result["brier_score_raw"] = round(raw, 6)
            except ScoringError:
                event_result["brier_score"] = None
                event_result["brier_score_raw"] = None
            try:
                cal = per_outcome_calibration(ef, resolutions, outcomes)
                event_result["calibration"] = cal
            except Exception:
                event_result["calibration"] = None

        # Compute by_horizon breakdown
        horizons = event.get("horizons_days", [1, 7, 15, 30])
        by_horizon: Dict[int, Dict[str, Any]] = {}

        for horizon in horizons:
            horizon_fcsts = [f for f in ef if f.get("horizon_days") == horizon]
            if not horizon_fcsts:
                continue

            horizon_result: Dict[str, Any] = {"count": len(horizon_fcsts)}

            if event_type == "binary":
                try:
                    bs = _brier_score_binary(horizon_fcsts, resolutions)
                    horizon_result["brier_score"] = round(bs, 6)
                except ScoringError:
                    horizon_result["brier_score"] = None
            elif outcomes:
                try:
                    raw, norm = effective_multinomial_brier_score(
                        horizon_fcsts, resolutions, outcomes
                    )
                    horizon_result["brier_score"] = round(norm, 6)
                except ScoringError:
                    horizon_result["brier_score"] = None

            by_horizon[horizon] = horizon_result

        if by_horizon:
            event_result["by_horizon"] = by_horizon

        results[event_id] = event_result

    return results


def compute_scores_for_mode(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    mode_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compute scores for resolutions matching specific modes.

    Args:
        forecasts: List of forecast records
        resolutions: List of resolution records
        mode_filter: List of resolution modes to include (None = all)

    Returns:
        Dictionary with brier_score, log_score, count
    """
    if mode_filter:
        filtered_resolutions = [
            r for r in resolutions
            if resolver.get_resolution_mode(r) in mode_filter
        ]
    else:
        filtered_resolutions = resolutions

    resolution_map = {r["forecast_id"]: r for r in filtered_resolutions}

    # Count valid pairs
    valid_count = 0
    for f in forecasts:
        if f.get("abstain"):
            continue
        res = resolution_map.get(f["forecast_id"])
        if res and res.get("resolved_outcome") in ["YES", "NO"]:
            valid_count += 1

    if valid_count == 0:
        return {
            "brier_score": None,
            "log_score": None,
            "count": 0,
        }

    try:
        bs = brier_score(forecasts, filtered_resolutions)
    except ScoringError:
        bs = None

    try:
        ls = log_score(forecasts, filtered_resolutions)
    except ScoringError:
        ls = None

    return {
        "brier_score": round(bs, 6) if bs is not None else None,
        "log_score": round(ls, 6) if ls is not None else None,
        "count": valid_count,
    }


def compute_event_scores(
    ledger_dir: Path = ledger.LEDGER_DIR
) -> Dict[str, Dict[str, Any]]:
    """
    Compute scores broken down by event.

    Args:
        ledger_dir: Path to ledger directory

    Returns:
        Dictionary mapping event_id to score results
    """
    forecasts = ledger.get_forecasts(ledger_dir)

    # Get unique event IDs
    event_ids = set(f.get("event_id") for f in forecasts if f.get("event_id"))

    results = {}
    for event_id in sorted(event_ids):
        results[event_id] = compute_scores(ledger_dir, event_id=event_id)

    return results

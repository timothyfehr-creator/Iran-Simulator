"""
Scoring metrics for forecast accuracy.

Computes Brier score, skill scores, and calibration metrics
for resolved forecasts. Supports separation of core scores
(external_auto + external_manual) from claims_inferred scores.
"""

import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Tuple
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


def brier_score(forecasts: List[Dict[str, Any]], resolutions: List[Dict[str, Any]]) -> float:
    """
    Compute Brier score for binary forecasts.

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


def log_score(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    epsilon: float = 1e-10
) -> float:
    """
    Compute log score (logarithmic scoring rule) for binary forecasts.

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
    horizon_days: Optional[int] = None
) -> Dict[str, Any]:
    """
    Compute all scoring metrics for resolved forecasts.

    Args:
        ledger_dir: Path to ledger directory
        event_id: Optional filter by event ID
        horizon_days: Optional filter by horizon

    Returns:
        Dictionary with:
        - brier_score: Model Brier score
        - baseline_brier: Climatology baseline Brier
        - skill_score: Brier skill score
        - calibration: Calibration bin statistics
        - counts: Various counts (resolved, unresolved, abstained)
        - coverage: Coverage metrics (forecasts_due, coverage_rate, etc.)
        - effective_brier: Brier treating UNKNOWN/abstain as p=0.5
        - core_scores: Scores for external_auto + external_manual only
        - claims_inferred_scores: Scores for claims_inferred only
        - combined_scores: All resolutions combined (reference)
    """
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

    # Add effective Brier score
    try:
        eff_brier = effective_brier_score(forecasts, resolutions)
        result["effective_brier"] = round(eff_brier, 6)
    except ScoringError:
        result["effective_brier"] = None

    # Add scores separated by resolution mode
    # Core scores: external_auto + external_manual
    result["core_scores"] = compute_scores_for_mode(
        forecasts, resolutions, ["external_auto", "external_manual"]
    )

    # Claims inferred scores
    result["claims_inferred_scores"] = compute_scores_for_mode(
        forecasts, resolutions, ["claims_inferred"]
    )

    # Combined scores (all modes)
    result["combined_scores"] = compute_scores_for_mode(
        forecasts, resolutions, None
    )

    if resolved_count > 0:
        try:
            model_brier = brier_score(forecasts, resolutions)
            clim_brier = climatology_brier(resolutions)
            clim_skill = brier_skill_score(model_brier, clim_brier)
            calibration = calibration_bins(forecasts, resolutions)

            result["brier_score"] = round(model_brier, 6)
            result["climatology_brier"] = round(clim_brier, 6)
            result["climatology_skill_score"] = round(clim_skill, 6)
            result["climatology_p"] = round(climatology_baseline(resolutions), 4)

            # Persistence baseline
            try:
                pers_brier = persistence_brier(forecasts, resolutions)
                pers_skill = brier_skill_score(model_brier, pers_brier)
                result["persistence_brier"] = round(pers_brier, 6)
                result["persistence_skill_score"] = round(pers_skill, 6)
            except ScoringError:
                result["persistence_brier"] = None
                result["persistence_skill_score"] = None

            # Log score
            try:
                model_log = log_score(forecasts, resolutions)
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

    return result


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

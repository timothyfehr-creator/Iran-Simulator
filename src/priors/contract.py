"""
Priors contract resolver + QA

This module makes probability semantics explicit and machine-checkable:
- time_basis: window | instant | daily
- anchor: how to align windows in the simulator
- start_offset_days, window_days
It also validates probability triplets and emits warnings for semantic mismatches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple, List, Optional


TIME_BASIS_ALLOWED = {"window", "instant", "daily"}
ANCHOR_ALLOWED = {
    "t0",
    "t0_plus_30",
    "escalation_start",
    "crackdown_start",
    "concessions_start",
    "defection_day",
    "ethnic_uprising_day",
    "khamenei_death_day",
    "collapse_day",
}

DEFAULT_DIST = "beta_pert"


def _get_triplet(prob: Dict[str, Any]) -> Tuple[float, float, float]:
    low = float(prob.get("low"))
    mode = float(prob.get("mode", prob.get("point")))
    high = float(prob.get("high"))
    return low, mode, high


def _validate_prob_triplet(path: str, prob: Dict[str, Any], errors: List[str]) -> None:
    try:
        low, mode, high = _get_triplet(prob)
    except Exception as e:
        errors.append(f"{path}: missing/invalid low/mode/high ({e})")
        return
    for v in (low, mode, high):
        if not (0.0 <= v <= 1.0):
            errors.append(f"{path}: probability out of [0,1]: {v}")
    if not (low <= mode <= high):
        errors.append(f"{path}: expected low<=mode<=high, got {low}, {mode}, {high}")


def resolve_priors(priors: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Resolve priors into a semantically explicit form, and produce QA output.

    Returns:
      (priors_resolved, qa)
    """
    pri = dict(priors)  # shallow copy
    warnings: List[str] = []
    errors: List[str] = []

    # Ensure regime_outcomes role
    if "regime_outcomes" in pri:
        pri["regime_outcomes"]["role"] = pri["regime_outcomes"].get("role", "diagnostic_only")
    else:
        warnings.append("Missing regime_outcomes section; continuing.")

    # Required keys based on current simulator usage
    required_transition_keys = [
        "khamenei_death_90d",
        "orderly_succession_given_khamenei_death",
        "protests_escalate_14d",
        "protests_sustain_30d",
        "mass_casualty_crackdown_given_escalation",
        "protests_collapse_given_crackdown_30d",
        "protests_collapse_given_concessions_30d",
        "meaningful_concessions_given_protests_30d",
        "security_force_defection_given_protests_30d",
        "regime_collapse_given_defection",
        "ethnic_coordination_given_protests_30d",
        "fragmentation_outcome_given_ethnic_uprising",
    ]
    required_us_keys = [
        "information_ops",
        "economic_escalation",
        "covert_support_given_protests_30d",
        "cyber_attack_given_crackdown",
        "kinetic_strike_given_crackdown",
        "ground_intervention_given_collapse",
    ]

    # Helper to resolve a probability dict
    def resolve_prob(path: str, prob: Dict[str, Any]) -> Dict[str, Any]:
        if "dist" not in prob:
            prob["dist"] = DEFAULT_DIST
        if "mode" not in prob and "point" in prob:
            prob["mode"] = prob["point"]

        # Infer time_basis if absent
        if "time_basis" not in prob:
            if "window_days" in prob:
                prob["time_basis"] = "window"
            else:
                prob["time_basis"] = "instant"

        tb = prob.get("time_basis")
        if tb not in TIME_BASIS_ALLOWED:
            errors.append(f"{path}: invalid time_basis {tb}")
        if tb == "window":
            wd = prob.get("window_days")
            if wd is None:
                errors.append(f"{path}: time_basis=window but missing window_days")
            else:
                try:
                    wd_int = int(wd)
                    if wd_int <= 0:
                        errors.append(f"{path}: window_days must be > 0, got {wd_int}")
                    prob["window_days"] = wd_int
                except Exception:
                    errors.append(f"{path}: invalid window_days {wd}")
            # anchor required for windows
            anchor = prob.get("anchor")
            if anchor is None:
                errors.append(f"{path}: time_basis=window but missing anchor")
            else:
                if anchor not in ANCHOR_ALLOWED:
                    warnings.append(f"{path}: anchor '{anchor}' not in allowed set; simulator may ignore it")

            # default offset
            prob["start_offset_days"] = int(prob.get("start_offset_days", 0))

            # Check if window extends beyond simulation horizon (90 days)
            anchor = prob.get("anchor")
            start_offset = prob.get("start_offset_days", 0)
            wd_int = prob.get("window_days", 0)
            if anchor in ("t0", "t0_plus_30"):
                anchor_day = 1 if anchor == "t0" else 31
                window_end = anchor_day + start_offset + wd_int - 1
                if window_end > 90:
                    warnings.append(
                        f"{path}: window extends beyond day 90 (ends on day {window_end}); "
                        f"will be truncated by simulation horizon"
                    )
        else:
            # still normalize offset
            prob["start_offset_days"] = int(prob.get("start_offset_days", 0))
            if "window_days" not in prob:
                prob["window_days"] = int(prob.get("window_days", 1))

        _validate_prob_triplet(path, prob, errors)

        # naming warning: *_30d but window_days differs
        name = path.split(".")[-2] if path.endswith(".probability") else path.split(".")[-1]
        if "_30d" in name and int(prob.get("window_days", 0)) not in (0, 30):
            warnings.append(f"{path}: name suggests 30d but window_days={prob.get('window_days')}")

        return prob

    # Resolve transition probabilities
    tp = pri.get("transition_probabilities", {})
    for k in required_transition_keys:
        if k not in tp:
            errors.append(f"Missing transition_probabilities.{k}")
        else:
            prob = tp[k].get("probability")
            if not isinstance(prob, dict):
                errors.append(f"transition_probabilities.{k}.probability missing or not dict")
            else:
                resolve_prob(f"transition_probabilities.{k}.probability", prob)

    # Resolve US intervention probabilities
    up = pri.get("us_intervention_probabilities", {})
    for k in required_us_keys:
        if k not in up:
            errors.append(f"Missing us_intervention_probabilities.{k}")
        else:
            prob = up[k].get("probability")
            if not isinstance(prob, dict):
                errors.append(f"us_intervention_probabilities.{k}.probability missing or not dict")
            else:
                resolve_prob(f"us_intervention_probabilities.{k}.probability", prob)

    # Warn about unused sections
    if "regional_cascade_probabilities" in pri and pri["regional_cascade_probabilities"]:
        warnings.append("regional_cascade_probabilities present but currently unused by simulator.")

    qa: Dict[str, Any] = {
        "errors": errors,
        "warnings": warnings,
        "status": "FAIL" if errors else "OK",
    }
    return pri, qa

"""Classification rules with hysteresis for Live Wire signals.

All classifiers return None when input is None -- no fabrication.
rule_version is always read from config, never hardcoded.
"""

from typing import Optional


def classify_economic_stress(
    rate: Optional[float], thresholds: dict
) -> Optional[str]:
    """Classify economic stress from IRR/USD rate.

    Args:
        rate: Exchange rate in IRR per USD, or None
        thresholds: dict with 'pressured' and 'critical' keys (IRR values)

    Returns:
        "STABLE", "PRESSURED", "CRITICAL", or None if rate is None
    """
    if rate is None:
        return None
    if rate >= thresholds["critical"]:
        return "CRITICAL"
    if rate >= thresholds["pressured"]:
        return "PRESSURED"
    return "STABLE"


def classify_internet(
    index: Optional[float], thresholds: dict
) -> Optional[str]:
    """Classify internet status from IODA connectivity index (0-100).

    Args:
        index: Connectivity index 0-100, or None
        thresholds: dict with functional/partial/severely_degraded keys

    Returns:
        Classification string or None
    """
    if index is None:
        return None
    if index >= thresholds["functional"]:
        return "FUNCTIONAL"
    if index >= thresholds["partial"]:
        return "PARTIAL"
    if index >= thresholds["severely_degraded"]:
        return "SEVERELY_DEGRADED"
    return "BLACKOUT"


def classify_news(
    count_24h: Optional[float],
    baseline_ema: Optional[float],
    thresholds: dict,
) -> Optional[str]:
    """Classify news activity from 24h article count vs EMA baseline.

    Args:
        count_24h: Number of articles in last 24h, or None
        baseline_ema: EMA baseline count, or None
        thresholds: dict with elevated_ratio and surge_ratio keys

    Returns:
        "NORMAL", "ELEVATED", "SURGE", or None
    """
    if count_24h is None:
        return None
    if baseline_ema is None or baseline_ema <= 0:
        return "NORMAL"
    ratio = count_24h / baseline_ema
    if ratio >= thresholds["surge_ratio"]:
        return "SURGE"
    if ratio >= thresholds["elevated_ratio"]:
        return "ELEVATED"
    return "NORMAL"


def apply_hysteresis(
    raw_state: Optional[str],
    prev_hysteresis: Optional[dict],
    required_cycles: int,
) -> dict:
    """Apply N-cycle hysteresis to a classification.

    State must sustain required_cycles consecutive cycles to transition.

    Args:
        raw_state: Current raw classification (or None)
        prev_hysteresis: Previous hysteresis state dict from state.json
        required_cycles: Number of cycles required for transition

    Returns:
        dict with confirmed_state, pending_state, pending_count
    """
    prev = prev_hysteresis or {}
    confirmed = prev.get("confirmed_state")
    pending = prev.get("pending_state")
    pending_count = prev.get("pending_count", 0)

    if raw_state is None:
        # No data - hold confirmed state, reset pending
        return {
            "confirmed_state": confirmed,
            "pending_state": None,
            "pending_count": 0,
        }

    if raw_state == confirmed:
        # Same as confirmed - reset any pending transition
        return {
            "confirmed_state": confirmed,
            "pending_state": None,
            "pending_count": 0,
        }

    if raw_state == pending:
        # Continuing pending transition
        new_count = pending_count + 1
        if new_count >= required_cycles:
            # Transition confirmed
            return {
                "confirmed_state": raw_state,
                "pending_state": None,
                "pending_count": 0,
            }
        return {
            "confirmed_state": confirmed,
            "pending_state": raw_state,
            "pending_count": new_count,
        }

    # New pending state (different from both confirmed and previous pending)
    return {
        "confirmed_state": confirmed,
        "pending_state": raw_state,
        "pending_count": 1,
    }

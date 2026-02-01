"""Exponential moving average computation for Live Wire signals."""

from typing import Optional


def compute_ema(
    current: Optional[float],
    previous_ema: Optional[float],
    alpha: float,
    last_good: Optional[float] = None,
) -> Optional[float]:
    """Compute EMA, injecting last-good value for failed signals.

    Args:
        current: Current signal value (None if failed)
        previous_ema: Previous EMA value (None on first run)
        alpha: Smoothing factor (0-1). Higher = more weight on current.
        last_good: Last known good value to inject on failure

    Returns:
        Updated EMA value, or None if no data available at all
    """
    # Use last_good as fallback when current is None
    effective = current if current is not None else last_good

    if effective is None:
        return previous_ema

    if previous_ema is None:
        return effective

    return alpha * effective + (1 - alpha) * previous_ema

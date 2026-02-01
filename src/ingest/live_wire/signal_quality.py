"""Signal quality tracking with last-good carry-forward."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SignalStatus(str, Enum):
    OK = "OK"
    STALE = "STALE"
    FAILED = "FAILED"


@dataclass
class SignalQuality:
    status: SignalStatus
    value: Optional[float]
    fetched_at_utc: str
    source_timestamp_utc: Optional[str]
    freshness: str  # "source_verified" or "fetch_time_only"
    confidence: str  # "high", "medium", "low"
    last_good_value: Optional[float]
    last_good_at: Optional[str]
    consecutive_failures: int


def update_signal_quality(
    prev: Optional[dict],
    value: Optional[float],
    fetched_at: datetime,
    stale_threshold_hours: float,
    source_timestamp_utc: Optional[datetime] = None,
) -> SignalQuality:
    """Compute signal quality from current fetch result and previous state.

    Args:
        prev: Previous signal quality dict from state.json (None on first run)
        value: Fetched value, or None if fetch failed
        fetched_at: When the fetch occurred
        stale_threshold_hours: Hours after which a signal is considered stale
        source_timestamp_utc: Timestamp from the source API, if available

    Returns:
        Updated SignalQuality
    """
    prev = prev or {}
    prev_last_good = prev.get("last_good_value")
    prev_last_good_at = prev.get("last_good_at")
    prev_failures = prev.get("consecutive_failures", 0)

    fetched_at_str = fetched_at.isoformat()

    # Determine freshness mode
    if source_timestamp_utc is not None:
        freshness = "source_verified"
        staleness_ref = source_timestamp_utc
    else:
        freshness = "fetch_time_only"
        staleness_ref = fetched_at

    source_ts_str = source_timestamp_utc.isoformat() if source_timestamp_utc else None

    if value is None:
        # Fetch failed
        return SignalQuality(
            status=SignalStatus.FAILED,
            value=prev_last_good,
            fetched_at_utc=fetched_at_str,
            source_timestamp_utc=source_ts_str,
            freshness=freshness,
            confidence="low",
            last_good_value=prev_last_good,
            last_good_at=prev_last_good_at,
            consecutive_failures=prev_failures + 1,
        )

    # Value fetched successfully - check staleness
    age_hours = (fetched_at - staleness_ref).total_seconds() / 3600
    if age_hours > stale_threshold_hours:
        # Stale source data
        max_confidence = "medium" if freshness == "fetch_time_only" else "medium"
        return SignalQuality(
            status=SignalStatus.STALE,
            value=value,
            fetched_at_utc=fetched_at_str,
            source_timestamp_utc=source_ts_str,
            freshness=freshness,
            confidence=max_confidence,
            last_good_value=value,
            last_good_at=fetched_at_str,
            consecutive_failures=0,
        )

    # Fresh and OK
    confidence = "high" if freshness == "source_verified" else "medium"
    return SignalQuality(
        status=SignalStatus.OK,
        value=value,
        fetched_at_utc=fetched_at_str,
        source_timestamp_utc=source_ts_str,
        freshness=freshness,
        confidence=confidence,
        last_good_value=value,
        last_good_at=fetched_at_str,
        consecutive_failures=0,
    )


def quality_to_dict(q: SignalQuality) -> dict:
    """Serialize SignalQuality to JSON-safe dict."""
    return {
        "status": q.status.value,
        "value": q.value,
        "fetched_at_utc": q.fetched_at_utc,
        "source_timestamp_utc": q.source_timestamp_utc,
        "freshness": q.freshness,
        "confidence": q.confidence,
        "last_good_value": q.last_good_value,
        "last_good_at": q.last_good_at,
        "consecutive_failures": q.consecutive_failures,
    }

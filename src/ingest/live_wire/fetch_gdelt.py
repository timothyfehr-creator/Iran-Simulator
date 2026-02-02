"""GDELT Doc API fetcher for Iran news volume (24h article count only).

Tone is skipped (unused by classifiers). Stored as null for forward-compat.
Returns None count on empty results.
"""

import logging
import time
import requests
from datetime import datetime, timezone
from typing import Optional, Tuple


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF = 2  # seconds, doubled each attempt

logger = logging.getLogger("live_wire.gdelt")


def fetch_gdelt_iran_count() -> Tuple[Optional[int], Optional[datetime]]:
    """Fetch 24h Iran article count from GDELT Doc API.

    Retries up to MAX_RETRIES times with exponential backoff on failure.

    Returns:
        (article_count, fetched_at) or (None, fetched_at) on failure/empty
    """
    now = datetime.now(timezone.utc)

    params = {
        "query": "iran",
        "mode": "artcount",
        "timespan": "24h",
        "format": "json",
    }

    last_exc = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(GDELT_DOC_URL, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()

            # GDELT artcount mode returns a timeline with counts
            timeline = data.get("timeline", [])
            if not timeline:
                return None, now

            # Sum all series data points for total count
            total = 0
            for series in timeline:
                for point in series.get("data", []):
                    total += point.get("value", 0)

            if total == 0:
                return None, now

            return total, now
        except Exception as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = RETRY_BACKOFF * (2 ** attempt)
                logger.warning(f"GDELT fetch attempt {attempt + 1} failed: {exc}, retrying in {delay}s")
                time.sleep(delay)

    logger.error(f"GDELT fetch failed after {MAX_RETRIES + 1} attempts: {last_exc}")
    return None, now

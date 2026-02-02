"""GDELT Doc API fetcher for Iran news volume (24h article count only).

Tone is skipped (unused by classifiers). Stored as null for forward-compat.
Returns None count on empty results.
"""

import requests
from datetime import datetime, timezone
from typing import Optional, Tuple


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
REQUEST_TIMEOUT = 30


def fetch_gdelt_iran_count() -> Tuple[Optional[int], Optional[datetime]]:
    """Fetch 24h Iran article count from GDELT Doc API.

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
    except Exception:
        return None, now

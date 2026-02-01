"""IODA (Internet Outage Detection & Analysis) fetcher for Iran connectivity data.

IODA is maintained by Georgia Tech's Internet Intelligence Lab and provides
real-time internet connectivity measurements using BGP, Active Probing, and
Darknet data.

API Documentation: https://api.ioda.inetintel.cc.gatech.edu/v2/
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from .base_fetcher import BaseFetcher, FetchError

logger = logging.getLogger(__name__)

# IODA API configuration
IODA_BASE_URL = "https://api.ioda.inetintel.cc.gatech.edu/v2"
IRAN_COUNTRY_CODE = "IR"
REQUEST_TIMEOUT = (10, 30)

# Session-level retry for network transients
_retry = Retry(total=1, allowed_methods=["GET"], backoff_factor=1, status_forcelist=[502, 503, 504])
_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=_retry))


class IODAFetcher(BaseFetcher):
    """Fetch Iran internet connectivity data from IODA API."""

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch latest connectivity signals for Iran.

        Args:
            since: Only fetch data after this time (default: last 24 hours)

        Returns:
            List of evidence docs with connectivity data
        """
        # Default to last 24 hours
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=24)

        # Ensure since is timezone-aware
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        # URL from config/sources.yaml, falling back to module default
        url = self.config.get("urls", [f"{IODA_BASE_URL}/signals/raw/country/{IRAN_COUNTRY_CODE}"])[0]
        params = {
            "from": int(since.timestamp()),
            "until": int(now.timestamp()),
        }

        try:
            response = _session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise FetchError(self.source_id, f"IODA API request failed: {e}", e) from e

        # IODA API returns: {"data": [[dict1, dict2, ...]]} - list containing list of signal dicts
        raw_data = data.get("data", [])
        if not raw_data or not raw_data[0]:
            # No data available - return empty
            return []

        # Extract signal dicts from nested structure
        signals = raw_data[0] if isinstance(raw_data[0], list) else raw_data

        # Find the normalized score datasource (gtr-norm) for best connectivity metric
        norm_signal = None
        for signal in signals:
            if isinstance(signal, dict) and signal.get("datasource") == "gtr-norm":
                norm_signal = signal
                break

        # Fall back to first valid signal if gtr-norm not found
        if not norm_signal:
            for signal in signals:
                if isinstance(signal, dict) and "values" in signal:
                    norm_signal = signal
                    break

        if not norm_signal:
            return []

        # Get connectivity score from the most recent non-null value
        values = norm_signal.get("values", [])
        connectivity_score = None
        for v in reversed(values):
            if v is not None:
                # gtr-norm values are 0-1 scale, convert to 0-100
                if norm_signal.get("datasource") == "gtr-norm":
                    connectivity_score = v * 100
                else:
                    connectivity_score = v
                break

        if connectivity_score is None:
            connectivity_score = 100.0  # Default to normal if no data

        # Get timestamp from signal
        signal_timestamp = norm_signal.get("until", 0)
        if signal_timestamp:
            published_at = datetime.fromtimestamp(signal_timestamp, tz=timezone.utc)
        else:
            published_at = now

        # Build descriptive text
        datasource_name = norm_signal.get("datasource", "unknown")
        datasource_str = f"{datasource_name} (Google Transparency Report normalized)"

        raw_text = (
            f"Iran Internet Connectivity Index: {connectivity_score:.1f}/100\n"
            f"Measurement timestamp: {published_at.isoformat()}\n"
            f"Data sources: {datasource_str}\n"
            f"Source: IODA/Georgia Tech Internet Intelligence Lab\n"
            f"\n"
            f"A score of 100 indicates normal baseline connectivity. "
            f"Scores below 80 suggest partial degradation. "
            f"Scores below 50 indicate significant outages."
        )

        # Create evidence doc
        doc = self.create_evidence_doc(
            url=f"{IODA_BASE_URL}/signals/raw/country/{IRAN_COUNTRY_CODE}",
            title=f"Iran Internet Connectivity - {published_at.strftime('%Y-%m-%d')}",
            published_at=published_at.isoformat(),
            raw_text=raw_text,
            language="en"
        )

        # Add structured data for claim extraction
        doc["structured_data"] = {
            "connectivity_index": connectivity_score,
            "measurement_timestamp": signal_timestamp,
            "datasource": datasource_name,
            "country_code": IRAN_COUNTRY_CODE,
        }

        return [doc]

    def _normalize_score(self, signal: dict) -> float:
        """Normalize IODA signal to 0-100 scale.

        IODA provides relative scores compared to a baseline. We normalize
        the value/baseline ratio to a 0-100 scale where 100 is normal.

        Args:
            signal: Signal dict with 'value' and 'baseline' keys

        Returns:
            Normalized score 0-100
        """
        value = signal.get("value", 100)
        baseline = signal.get("baseline", 100)

        # Avoid division by zero
        if baseline == 0:
            return 100.0

        # Calculate ratio and convert to 0-100 scale
        ratio = (value / baseline) * 100

        # Clamp to valid range
        return min(100.0, max(0.0, ratio))


def fetch(source_config: dict, since: Optional[datetime] = None) -> List[Dict]:
    """Entry point for IODA fetching (legacy interface).

    Args:
        source_config: Source configuration dict
        since: Only fetch data after this time

    Returns:
        List of evidence docs

    Raises:
        Exception: If fetch fails after retries
    """
    fetcher = IODAFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

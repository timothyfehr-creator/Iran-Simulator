"""Nobitex exchange fetcher for USDT/IRT rate.

Nobitex is Iran's largest crypto exchange. The USDT/IRT pair provides
a real-time proxy for the USD/IRR black market rate.

API returns values in Rials natively for the usdt-rls pair.
"""

import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_fetcher import BaseFetcher


NOBITEX_STATS_URL = "https://api.nobitex.ir/market/stats"
REQUEST_TIMEOUT = 30


class NobitexFetcher(BaseFetcher):
    """Fetch USDT/IRT rate from Nobitex API."""

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch current USDT/IRT stats from Nobitex.

        Returns:
            List with single evidence doc containing rate data
        """
        resp = requests.post(
            NOBITEX_STATS_URL,
            json={"srcCurrency": "usdt", "dstCurrency": "rls"},
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        stats = data.get("stats", {}).get("usdt-rls")
        if not stats:
            return []

        # Nobitex returns Rials natively for rls pairs
        latest = float(stats.get("latest", 0))
        day_open = float(stats.get("dayOpen", 0))
        day_close = float(stats.get("dayClose", 0))
        day_high = float(stats.get("dayHigh", 0))
        day_low = float(stats.get("dayLow", 0))
        volume = float(stats.get("volume", 0))

        if latest == 0:
            return []

        # dayClose timestamp as source_timestamp
        day_close_ts = stats.get("date")
        if day_close_ts:
            try:
                pub_date = datetime.fromtimestamp(float(day_close_ts) / 1000, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                pub_date = datetime.now(timezone.utc)
        else:
            pub_date = datetime.now(timezone.utc)

        raw_text = (
            f"Nobitex USDT/IRT Exchange Rate\n"
            f"Latest: {latest:,.0f} IRR\n"
            f"Day Open: {day_open:,.0f} IRR\n"
            f"Day Close: {day_close:,.0f} IRR\n"
            f"Day High: {day_high:,.0f} IRR\n"
            f"Day Low: {day_low:,.0f} IRR\n"
            f"Volume (24h): {volume:,.2f} USDT\n"
        )

        doc = self.create_evidence_doc(
            url=NOBITEX_STATS_URL,
            title=f"Nobitex USDT/IRT - {pub_date.strftime('%Y-%m-%d %H:%M')}",
            published_at=pub_date.isoformat(),
            raw_text=raw_text,
            language="en",
        )

        doc["structured_data"] = {
            "usdt_irt_rate": {
                "latest": latest,
                "day_open": day_open,
                "day_close": day_close,
                "day_high": day_high,
                "day_low": day_low,
                "volume_usdt": volume,
            },
            "units": "IRR",
            "source": "nobitex",
            "source_timestamp_utc": pub_date.isoformat(),
        }

        return [doc]


def fetch(source_config: dict, since: Optional[datetime] = None) -> List[Dict]:
    """Entry point for Nobitex fetching (legacy interface)."""
    fetcher = NobitexFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

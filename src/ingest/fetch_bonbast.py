"""Bonbast exchange rate fetcher for Iran Rial rates.

Bonbast provides real-time black market exchange rates for the Iranian Rial.
The site uses a token-based API that requires:
1. Fetching the main page to extract a dynamic token
2. POSTing to /json with the token to get rate data

Note: Rates are displayed in Toman (1 Toman = 10 Rials). We convert to Rials
for consistency with the simulation schema.
"""

import re
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base_fetcher import BaseFetcher


# Request configuration
REQUEST_TIMEOUT = 30
BONBAST_URL = "https://www.bonbast.com/"
BONBAST_JSON_URL = "https://www.bonbast.com/json"

# Toman to Rial conversion
TOMAN_TO_RIAL = 10


class BonbastFetcher(BaseFetcher):
    """Fetch Iranian Rial exchange rates from Bonbast."""

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch current exchange rates from Bonbast.

        Args:
            since: Not used (rates are always current)

        Returns:
            List with single evidence doc containing rate data
        """
        session = requests.Session()

        # Headers for browser-like requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        # Step 1: Fetch main page to get token
        resp = session.get(BONBAST_URL, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        # Extract the param token from JavaScript
        match = re.search(r"param:\s*['\"]([^'\"]+)['\"]", resp.text)
        if not match:
            raise ValueError("Could not find Bonbast API token in page")

        param_token = match.group(1)

        # Step 2: Request JSON data with token
        json_headers = {
            'User-Agent': headers['User-Agent'],
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://www.bonbast.com',
            'Referer': BONBAST_URL,
        }

        resp = session.post(
            BONBAST_JSON_URL,
            data={'param': param_token},
            headers=json_headers,
            timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()

        data = resp.json()

        # Check for valid response (should have currency keys)
        if 'usd1' not in data:
            raise ValueError(f"Invalid Bonbast response: {data}")

        # Extract key rates (values are in Toman, convert to Rial)
        usd_sell = int(data.get('usd1', 0)) * TOMAN_TO_RIAL
        usd_buy = int(data.get('usd2', 0)) * TOMAN_TO_RIAL
        usd_mid = (usd_sell + usd_buy) // 2

        eur_sell = int(data.get('eur1', 0)) * TOMAN_TO_RIAL
        eur_buy = int(data.get('eur2', 0)) * TOMAN_TO_RIAL

        # Gold prices (already in Toman, convert to Rial)
        gold_18k = int(data.get('gol18', 0)) * TOMAN_TO_RIAL
        gold_mithqal = int(data.get('mithqal', 0)) * TOMAN_TO_RIAL

        # Bitcoin (in USD, no conversion needed)
        bitcoin_usd = float(data.get('bitcoin', 0))

        # Get timestamp
        last_modified = data.get('last_modified', '')
        try:
            # Parse "January 17, 2026 16:28" format
            pub_date = datetime.strptime(last_modified, "%B %d, %Y %H:%M")
            pub_date = pub_date.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            pub_date = datetime.now(timezone.utc)

        # Build descriptive text
        raw_text = f"""Iranian Rial Exchange Rates (Bonbast - Black Market)
Last Updated: {last_modified}

USD/IRR (US Dollar):
  Sell: {usd_sell:,} IRR
  Buy:  {usd_buy:,} IRR
  Mid:  {usd_mid:,} IRR

EUR/IRR (Euro):
  Sell: {eur_sell:,} IRR
  Buy:  {eur_buy:,} IRR

Gold Prices:
  18K Gold: {gold_18k:,} IRR per gram
  Mithqal:  {gold_mithqal:,} IRR

Bitcoin: ${bitcoin_usd:,.2f} USD

Source: Bonbast.com - Iran's free market exchange rates
Note: Rates reflect black market/unofficial rates, not official CBI rates.
"""

        # Create evidence doc
        doc = self.create_evidence_doc(
            url=BONBAST_URL,
            title=f"Iran Exchange Rates - {pub_date.strftime('%Y-%m-%d %H:%M')}",
            published_at=pub_date.isoformat(),
            raw_text=raw_text,
            language="en"
        )

        # Add structured data for direct use by simulation
        doc["structured_data"] = {
            "rial_usd_rate": {
                "sell": usd_sell,
                "buy": usd_buy,
                "market": usd_mid,  # Mid-point for simulation use
            },
            "rial_eur_rate": {
                "sell": eur_sell,
                "buy": eur_buy,
            },
            "gold_18k_rial": gold_18k,
            "gold_mithqal_rial": gold_mithqal,
            "bitcoin_usd": bitcoin_usd,
            "last_modified": last_modified,
            "source": "bonbast",
        }

        return [doc]


def fetch(source_config: dict, since: Optional[datetime] = None) -> List[Dict]:
    """Entry point for Bonbast fetching (legacy interface).

    Args:
        source_config: Source configuration dict
        since: Not used for Bonbast (always returns current rates)

    Returns:
        List of evidence docs

    Raises:
        Exception: If fetch fails after retries
    """
    fetcher = BonbastFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

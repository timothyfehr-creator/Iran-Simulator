"""OONI (Open Observatory of Network Interference) fetcher for Iran censorship data."""

import logging
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from .base_fetcher import BaseFetcher, FetchError

logger = logging.getLogger(__name__)

# Request timeout (connect, read) in seconds
REQUEST_TIMEOUT = (10, 30)

# Session-level retry for network transients
_retry = Retry(total=1, allowed_methods=["GET"], backoff_factor=1, status_forcelist=[502, 503, 504])
_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=_retry))


class OONIFetcher(BaseFetcher):
    """Fetcher for OONI censorship measurement data."""

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch censorship measurements from OONI API."""
        evidence_docs = []

        # Calculate date range
        if since is None:
            since = datetime.now(timezone.utc) - timedelta(hours=72)

        since_str = since.strftime("%Y-%m-%d")
        until_str = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

        # Fetch all measurements for Iran (filter locally for anomalies)
        params = {
            "probe_cc": "IR",
            "since": since_str,
            "until": until_str,
            "limit": 200  # Fetch more, filter locally
        }

        try:
            api_url = self._require_url()
            response = _session.get(
                api_url,
                params=params,
                timeout=REQUEST_TIMEOUT,
                headers={'User-Agent': 'IranSimulator/1.0'}
            )
            response.raise_for_status()
        except requests.RequestException as e:
            raise FetchError(self.source_id, f"OONI API request failed: {e}", e) from e

        data = response.json()
        results = data.get('results', [])

        # Group by domain to avoid duplicates
        domains_seen = set()

        for result in results:
            test_name = result.get('test_name', 'unknown')
            input_url = result.get('input', '')

            # For tests without input (like psiphon, facebook_messenger), use test name
            if input_url:
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(input_url).netloc or input_url
                except Exception as e:
                    logger.debug(f"URL parse failed for {input_url}: {e}")
                    domain = input_url
            else:
                domain = test_name

            # Skip if we've already seen this domain/test
            key = f"{domain}_{result.get('probe_asn', '')}"
            if key in domains_seen:
                continue
            domains_seen.add(key)

            # Parse measurement time
            measurement_time = result.get('measurement_start_time', '')
            if measurement_time:
                try:
                    pub_date = datetime.fromisoformat(measurement_time.replace('Z', '+00:00'))
                except ValueError:
                    pub_date = datetime.now(timezone.utc)
            else:
                pub_date = datetime.now(timezone.utc)

            # Determine block status
            is_confirmed = result.get('confirmed', False)
            is_anomaly = result.get('anomaly', False)

            if is_confirmed:
                status = "Confirmed block"
            elif is_anomaly:
                status = "Anomaly detected"
            else:
                continue  # Skip non-anomalous results

            # Create evidence doc
            title = f"{status}: {domain} in Iran"
            raw_text = (
                f"OONI censorship measurement.\n\n"
                f"Test: {test_name}\n"
                f"Target: {domain}\n"
                f"URL: {input_url or 'N/A'}\n"
                f"Probe ASN: {result.get('probe_asn', 'Unknown')}\n"
                f"Measurement ID: {result.get('measurement_uid', 'N/A')}\n"
                f"Status: {status}\n"
                f"Confirmed: {is_confirmed}\n"
                f"Anomaly: {is_anomaly}\n"
            )

            doc = self.create_evidence_doc(
                url=result.get('measurement_url', f"https://explorer.ooni.org/measurement/{result.get('measurement_uid', '')}"),
                title=title,
                published_at=pub_date.isoformat(),
                raw_text=raw_text,
                language="en"
            )

            evidence_docs.append(doc)

        return evidence_docs


def fetch(source_config: Dict[str, Any], since: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Entry point for OONI fetching (legacy interface)."""
    fetcher = OONIFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

"""Web scraper for evidence collection using CSS selectors."""

import logging
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import time
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from .base_fetcher import BaseFetcher, FetchError

logger = logging.getLogger(__name__)

# Request timeout (connect, read) in seconds
REQUEST_TIMEOUT = (10, 30)

# Session-level retry for network transients
_retry = Retry(total=1, allowed_methods=["GET"], backoff_factor=1, status_forcelist=[502, 503, 504])
_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=_retry))
_session.mount("http://", HTTPAdapter(max_retries=_retry))

# Delay between requests to avoid rate limiting (seconds)
REQUEST_DELAY = 1.0

# Realistic browser headers to avoid blocking
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}


class WebFetcher(BaseFetcher):
    """Fetcher for web pages using CSS selectors."""

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch from web pages (internal implementation with no retry logic)."""
        evidence_docs = []

        for i, page_url in enumerate(self.config.get('urls', [])):
            # Add delay between requests to avoid rate limiting
            if i > 0:
                time.sleep(REQUEST_DELAY)

            # Fetch page
            try:
                response = _session.get(
                    page_url,
                    timeout=REQUEST_TIMEOUT,
                    headers=DEFAULT_HEADERS
                )
                response.raise_for_status()
            except requests.RequestException as e:
                raise FetchError(self.source_id, f"Web fetch failed for {page_url}: {e}", e) from e

            soup = BeautifulSoup(response.text, 'lxml')

            # Get selectors
            selectors = self.config.get('selectors', {})
            article_selector = selectors.get('article', 'article')
            title_selector = selectors.get('title', 'h2')
            date_selector = selectors.get('date', 'time')
            content_selector = selectors.get('content', 'p')

            # Find articles
            articles = soup.select(article_selector)

            for article in articles:
                # Extract title
                title_elem = article.select_one(title_selector)
                title = title_elem.get_text(strip=True) if title_elem else 'Untitled'

                # Extract URL
                link_elem = title_elem.find('a') if title_elem else None
                url = link_elem.get('href', '') if link_elem else page_url
                if url.startswith('/'):
                    from urllib.parse import urljoin
                    url = urljoin(page_url, url)

                # Extract date
                date_elem = article.select_one(date_selector)
                pub_date = None
                if date_elem and date_elem.has_attr('datetime'):
                    try:
                        pub_date = datetime.fromisoformat(date_elem['datetime'].replace('Z', '+00:00'))
                    except ValueError:
                        pass

                if not pub_date:
                    pub_date = datetime.now(timezone.utc)

                # Filter by date
                if since and pub_date < since:
                    continue

                # Extract content
                content_elem = article.select_one(content_selector)
                raw_text = content_elem.get_text(separator='\n', strip=True) if content_elem else ''

                # Create evidence doc
                doc = self.create_evidence_doc(
                    url=url,
                    title=title,
                    published_at=pub_date.isoformat(),
                    raw_text=raw_text,
                    language=self.config.get('language', 'en')
                )

                evidence_docs.append(doc)

        return evidence_docs


def fetch(source_config: Dict[str, Any], since: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Entry point for web scraping (legacy interface)."""
    fetcher = WebFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

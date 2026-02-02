"""Specialized Tasnim fetcher - scrapes homepage for Iran articles."""

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import re
from urllib.parse import urljoin
from .base_fetcher import BaseFetcher, FetchError, MAX_DOC_TEXT_LENGTH

logger = logging.getLogger(__name__)


class TasnimFetcher(BaseFetcher):
    """Fetcher for Tasnim News Agency (web scraping)."""

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch Tasnim Iran articles from homepage."""
        evidence_docs = []

        url = self._require_url()
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # Find all article links containing "/en/news/"
        article_links = soup.find_all('a', href=re.compile(r'/en/news/\d{4}/\d{2}/\d{2}/'))

        # Deduplicate by URL
        seen_urls = set()

        for link in article_links:
            try:
                article_url = link.get('href', '')

                # Make absolute URL
                if article_url.startswith('/'):
                    article_url = urljoin(url, article_url)

                # Skip if already processed
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)

                # Get title from link text or find nearby title
                title = link.get_text(strip=True)

                # If title is too short (like an image alt), try to find associated text
                if len(title) < 20:
                    # Look for title in parent or nearby elements
                    parent = link.find_parent()
                    if parent:
                        # Try to find title text in parent
                        for text_elem in parent.find_all(text=True):
                            text = text_elem.strip()
                            if len(text) > 20 and text != title:
                                title = text
                                break

                # Extract date from URL: /en/news/2026/01/11/3492402/...
                pub_date = None
                date_match = re.search(r'/en/news/(\d{4})/(\d{2})/(\d{2})/', article_url)
                if date_match:
                    year, month, day = date_match.groups()
                    try:
                        pub_date = datetime(int(year), int(month), int(day), tzinfo=timezone.utc)
                    except ValueError:
                        pass

                if not pub_date:
                    pub_date = datetime.now(timezone.utc)

                # Filter by date
                if since and pub_date < since:
                    continue

                # Fetch full article content
                raw_text = self._fetch_article_content(article_url)

                # Skip if no content
                if not raw_text or len(raw_text) < 100:
                    continue

                # Create evidence doc
                doc = self.create_evidence_doc(
                    url=article_url,
                    title=title if title else "Tasnim Article",
                    published_at=pub_date.isoformat(),
                    raw_text=raw_text,
                    language='en'
                )

                evidence_docs.append(doc)

            except Exception as e:
                logger.warning(f"Error processing Tasnim link: {e}", exc_info=True)
                continue

        return evidence_docs

    def _fetch_article_content(self, url: str) -> str:
        """Fetch full article text from Tasnim article page."""
        try:
            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # Try multiple possible content containers
            content = None

            # Try main story div
            content = soup.find('div', class_='story')

            if not content:
                # Try article tag
                content = soup.find('article')

            if not content:
                # Try common content classes
                content = soup.find('div', class_='content') or \
                         soup.find('div', class_='article-content') or \
                         soup.find('div', class_='post-content')

            if content:
                # Remove script, style, and nav tags
                for tag in content.find_all(['script', 'style', 'nav', 'footer', 'aside']):
                    tag.decompose()

                text = content.get_text(separator='\n', strip=True)
                return text[:MAX_DOC_TEXT_LENGTH]

            return ""

        except Exception as e:
            logger.warning(f"Error fetching article content from {url}: {e}", exc_info=True)
            return ""


def fetch(source_config: Dict[str, Any], since: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Entry point for Tasnim fetching (legacy interface)."""
    fetcher = TasnimFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

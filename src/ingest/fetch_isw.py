"""Specialized ISW fetcher - scrapes backgrounder page since RSS is blocked."""

import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from .base_fetcher import BaseFetcher, FetchError, MAX_DOC_TEXT_LENGTH

logger = logging.getLogger(__name__)


class ISWFetcher(BaseFetcher):
    """Fetcher for ISW backgrounders (web scraping)."""

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch ISW Iran Updates from homepage."""
        evidence_docs = []

        # URL from config/sources.yaml, falling back to default
        url = self.config.get("urls", ["https://understandingwar.org/"])[0]
        response = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'lxml')

        # Find all links containing "iran-update" in the URL
        iran_links = soup.find_all('a', href=lambda x: x and 'iran-update' in x.lower())

        # Deduplicate by URL
        seen_urls = set()

        for link in iran_links:
            try:
                article_url = link.get('href', '')

                # Skip if already processed
                if article_url in seen_urls:
                    continue
                seen_urls.add(article_url)

                # Get title from link text
                title = link.get_text(strip=True)
                if not title or len(title) < 10:
                    # Try to construct title from URL
                    url_parts = article_url.split('/')
                    title = url_parts[-2].replace('-', ' ').title() if len(url_parts) > 2 else "ISW Iran Update"

                # Extract date from URL: .../iran-update-january-11-2026/
                pub_date = None
                import re
                date_match = re.search(r'iran-update-(\w+)-(\d+)-(\d{4})', article_url)
                if date_match:
                    month, day, year = date_match.groups()
                    try:
                        pub_date = datetime.strptime(f"{month} {day} {year}", '%B %d %Y')
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass

                if not pub_date:
                    pub_date = datetime.now(timezone.utc)

                # Filter by date
                if since and pub_date < since:
                    continue

                # Fetch full article content
                raw_text = self._fetch_article_content(article_url)

                # Create evidence doc
                doc = self.create_evidence_doc(
                    url=article_url,
                    title=title,
                    published_at=pub_date.isoformat(),
                    raw_text=raw_text,
                    language='en'
                )

                evidence_docs.append(doc)

            except Exception as e:
                logger.warning(f"Error processing ISW card: {e}", exc_info=True)
                continue

        return evidence_docs

    def _fetch_article_content(self, url: str) -> str:
        """Fetch full article text from ISW article page."""
        try:
            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # ISW articles are in <article> tag or main content div
            # Try multiple selectors
            content = None

            # Try main article tag
            article = soup.find('article')
            if article:
                content = article
            else:
                # Try common content containers
                content = soup.find('div', class_='entry-content') or \
                         soup.find('div', class_='article-content') or \
                         soup.find('div', class_='post-content')

            if content:
                # Remove script and style tags
                for tag in content.find_all(['script', 'style', 'nav', 'footer']):
                    tag.decompose()

                text = content.get_text(separator='\n', strip=True)
                return text[:MAX_DOC_TEXT_LENGTH]

            return ""

        except Exception as e:
            logger.warning(f"Error fetching article content from {url}: {e}", exc_info=True)
            return ""


def fetch(source_config: Dict[str, Any], since: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Entry point for ISW fetching (legacy interface - returns docs only)."""
    fetcher = ISWFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

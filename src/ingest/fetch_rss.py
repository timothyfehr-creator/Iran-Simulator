"""RSS/Atom feed fetcher for evidence collection."""

import feedparser
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from .base_fetcher import BaseFetcher


class RSSFetcher(BaseFetcher):
    """Fetcher for RSS/Atom feeds."""

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch from RSS feed (internal implementation with no retry logic)."""
        evidence_docs = []

        for feed_url in self.config.get('urls', []):
            # Fetch feed - may raise exception
            feed = feedparser.parse(feed_url)

            # Check for feed errors
            if feed.bozo and not feed.entries:
                raise Exception(f"Feed parse error: {feed.bozo_exception}")

            for entry in feed.entries:
                # Parse published date
                pub_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                # Filter by date if requested
                if since and pub_date and pub_date < since:
                    continue

                # Apply keyword filters (if configured)
                filters = self.config.get('filters', [])
                if filters:
                    title_lower = entry.get('title', '').lower()
                    summary_lower = entry.get('summary', '').lower()
                    if not any(f.get('keyword', '').lower() in title_lower or
                               f.get('keyword', '').lower() in summary_lower
                               for f in filters):
                        continue

                # Extract content
                title = entry.get('title', 'Untitled')
                url = entry.get('link', '')

                # Get full text (summary or content)
                raw_text = entry.get('content', [{}])[0].get('value', '') if 'content' in entry else entry.get('summary', '')

                # Clean HTML tags
                from bs4 import BeautifulSoup
                raw_text = BeautifulSoup(raw_text, 'html.parser').get_text(separator='\n', strip=True)

                # Create evidence doc
                doc = self.create_evidence_doc(
                    url=url,
                    title=title,
                    published_at=pub_date.isoformat() if pub_date else datetime.now(timezone.utc).isoformat(),
                    raw_text=raw_text,
                    language=self.config.get('language', 'en')
                )

                evidence_docs.append(doc)

        return evidence_docs


def fetch(source_config: Dict[str, Any], since: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Entry point for RSS fetching (legacy interface)."""
    fetcher = RSSFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

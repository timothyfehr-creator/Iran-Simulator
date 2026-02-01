"""Playwright-based fetcher for JS-rendered sites (Cloudflare, Arvancloud)."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

from .base_fetcher import BaseFetcher

logger = logging.getLogger(__name__)

# Timeout for page load in milliseconds
PAGE_LOAD_TIMEOUT_MS = 30000

# Wait after navigation for JS challenges to resolve
CHALLENGE_WAIT_MS = 10000


class PlaywrightFetcher(BaseFetcher):
    """Fetcher for sites behind JS challenges (Cloudflare, Arvancloud).

    Uses Playwright with headless Chromium to render pages before extracting
    articles with CSS selectors (same pattern as WebFetcher).

    Falls back gracefully if playwright is not installed.
    """

    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Fetch from JS-rendered pages using Playwright."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError(
                "playwright is not installed. Run: "
                "pip install playwright && playwright install chromium"
            )

        evidence_docs = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 720},
            )

            try:
                for page_url in self.config.get("urls", []):
                    docs = self._fetch_page(context, page_url, since)
                    evidence_docs.extend(docs)
            finally:
                context.close()
                browser.close()

        return evidence_docs

    def _fetch_page(self, context, page_url: str, since: Optional[datetime]) -> List[Dict[str, Any]]:
        """Fetch and parse a single page."""
        from bs4 import BeautifulSoup

        page = context.new_page()
        try:
            # Navigate and wait for network to settle (handles JS challenges)
            page.goto(page_url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="networkidle")

            # Extra wait for Cloudflare/Arvancloud challenge resolution
            page.wait_for_timeout(CHALLENGE_WAIT_MS)

            # Wait for article content to appear if selector is configured
            selectors = self.config.get("selectors", {})
            article_selector = selectors.get("article", "article")
            try:
                page.wait_for_selector(article_selector, timeout=10000)
            except Exception:
                logger.warning(
                    "%s: selector '%s' not found on %s, parsing available content",
                    self.source_id, article_selector, page_url,
                )

            html = page.content()
        finally:
            page.close()

        soup = BeautifulSoup(html, "lxml")

        title_selector = selectors.get("title", "h2")
        date_selector = selectors.get("date", "time")
        content_selector = selectors.get("content", "p")

        articles = soup.select(article_selector)
        evidence_docs = []

        for article in articles:
            # Title
            title_elem = article.select_one(title_selector)
            title = title_elem.get_text(strip=True) if title_elem else "Untitled"

            # URL — title element may itself be an <a>, or contain one
            link_elem = None
            if title_elem:
                if title_elem.name == "a":
                    link_elem = title_elem
                else:
                    link_elem = title_elem.find("a")
            url = link_elem.get("href", "") if link_elem else page_url
            if url.startswith("/"):
                url = urljoin(page_url, url)

            # Date
            date_elem = article.select_one(date_selector)
            pub_date = None
            if date_elem and date_elem.has_attr("datetime"):
                try:
                    pub_date = datetime.fromisoformat(
                        date_elem["datetime"].replace("Z", "+00:00")
                    )
                except ValueError:
                    pass
            if not pub_date:
                pub_date = datetime.now(timezone.utc)

            # Filter by date
            if since and pub_date < since:
                continue

            # Content
            content_elem = article.select_one(content_selector)
            raw_text = (
                content_elem.get_text(separator="\n", strip=True)
                if content_elem
                else ""
            )

            # Apply keyword filters if configured
            filters = self.config.get("filters", [])
            if filters:
                text_lower = (title + " " + raw_text).lower()
                if not any(f.get("keyword", "").lower() in text_lower for f in filters):
                    continue

            doc = self.create_evidence_doc(
                url=url,
                title=title,
                published_at=pub_date.isoformat(),
                raw_text=raw_text,
                language=self.config.get("language", "en"),
            )
            evidence_docs.append(doc)

        return evidence_docs


def fetch(source_config: Dict[str, Any], since: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Entry point for Playwright fetching (legacy interface)."""
    fetcher = PlaywrightFetcher(source_config)
    docs, error = fetcher.fetch(since)
    if error:
        raise Exception(error)
    return docs

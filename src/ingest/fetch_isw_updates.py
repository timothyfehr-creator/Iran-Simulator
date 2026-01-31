#!/usr/bin/env python3
"""
Fetch ISW/CTP Iran updates and convert to evidence_docs format.

Usage:
    # Seed mode: backfill initial 15 URLs
    python -m src.ingest.fetch_isw_updates --seed

    # Latest mode: fetch 3 most recent pages
    python -m src.ingest.fetch_isw_updates --latest 3

    # Custom output location
    python -m src.ingest.fetch_isw_updates --seed --output runs/backfill_isw/
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

import requests
import yaml
from bs4 import BeautifulSoup

# User agent to identify requests
USER_AGENT = "IranSimulator/1.0 (OSINT Research; +https://github.com/your-org/iran-sim)"


def load_config(config_path: str = "config/sources_isw.yaml") -> Dict[str, Any]:
    """Load ISW source configuration."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def fetch_page(url: str, timeout: int = 30, max_retries: int = 3) -> Optional[str]:
    """
    Fetch page HTML with retries.

    Returns:
        HTML content or None if failed
    """
    headers = {'User-Agent': USER_AGENT}

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt == max_retries - 1:
                print(f"ERROR: Failed to fetch {url} after {max_retries} attempts")
                return None
    return None


def extract_title(soup: BeautifulSoup, selector: str) -> str:
    """Extract page title."""
    title_elem = soup.select_one(selector)
    return title_elem.get_text(strip=True) if title_elem else "Untitled"


def extract_published_date(soup: BeautifulSoup, selector: str) -> Optional[str]:
    """
    Extract published date from datetime attribute or text.

    Returns:
        ISO 8601 timestamp or None
    """
    date_elem = soup.select_one(selector)
    if date_elem and date_elem.has_attr('datetime'):
        # ISO 8601 format already
        return date_elem['datetime']
    # Fallback: try to parse text content (not implemented - return None)
    return None


def extract_toplines(soup: BeautifulSoup, keywords: List[str]) -> Optional[str]:
    """
    Extract 'Key Takeaways' or 'Toplines' section.

    Returns:
        Toplines text or None if not found
    """
    # Find heading containing keywords
    headings = soup.find_all(['h2', 'h3', 'h4'])
    for heading in headings:
        heading_text = heading.get_text(strip=True)
        if any(kw.lower() in heading_text.lower() for kw in keywords):
            # Extract content until next heading
            content = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ['h2', 'h3', 'h4']:
                    break
                content.append(sibling.get_text(strip=True))
            return "\n\n".join(content)
    return None


def extract_main_content(soup: BeautifulSoup, selector: str) -> str:
    """Extract main article content."""
    content_elem = soup.select_one(selector)
    if content_elem:
        # Remove scripts, styles
        for tag in content_elem(['script', 'style', 'nav', 'footer']):
            tag.decompose()
        return content_elem.get_text(separator='\n', strip=True)
    return ""


def truncate_text(text: str, max_length: int) -> str:
    """Truncate text to max_length."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "\n\n[TRUNCATED]"


def create_evidence_doc(
    url: str,
    html: str,
    config: Dict[str, Any],
    retrieved_at: str
) -> Dict[str, Any]:
    """
    Create evidence_doc from scraped HTML.

    Returns:
        evidence_doc dict conforming to schema
    """
    soup = BeautifulSoup(html, 'lxml')

    # Extract metadata
    title = extract_title(soup, config['content_selectors']['title'])
    published_at = extract_published_date(soup, config['content_selectors']['published_date'])

    # If no published date, use retrieved date as fallback
    if not published_at:
        published_at = retrieved_at

    # Extract content
    raw_text = extract_main_content(soup, config['content_selectors']['main_content'])
    raw_text = truncate_text(raw_text, config['extraction']['max_raw_text_length'])

    # Extract toplines
    toplines_text = extract_toplines(soup, config['extraction']['toplines_keywords'])

    # Generate IDs
    # doc_id format: ISW_YYYYMMDD_HHMM_URL_HASH
    timestamp = datetime.fromisoformat(retrieved_at.replace('Z', '+00:00'))
    # Create a simple hash from URL to make doc_id unique
    url_hash = str(abs(hash(url)))[:6]
    doc_id = f"ISW_{timestamp.strftime('%Y%m%d_%H%M')}_{url_hash}"

    # Key excerpts
    key_excerpts = []

    if toplines_text:
        key_excerpts.append({
            "excerpt_id": f"{doc_id}_toplines",
            "excerpt": toplines_text,
            "text_original": toplines_text,
            "text_en": toplines_text,
            "page_or_timestamp": "Toplines section",
            "claim_types": ["assessment"],
            "notes": "Key takeaways from ISW analysis"
        })

    # Add first N words as excerpt if no toplines
    if not toplines_text:
        words = raw_text.split()[:config['extraction']['first_n_words']]
        excerpt_text = ' '.join(words)
        key_excerpts.append({
            "excerpt_id": f"{doc_id}_excerpt1",
            "excerpt": excerpt_text,
            "text_original": excerpt_text,
            "text_en": excerpt_text,
            "page_or_timestamp": "First 400 words",
            "claim_types": ["context"],
            "notes": "Opening paragraphs"
        })

    # Construct evidence_doc
    evidence_doc = {
        "doc_id": doc_id,
        "source_id": config['source_id'],
        "organization": config['organization'],
        "title": title,
        "url": url,
        "published_at_utc": published_at,
        "retrieved_at_utc": retrieved_at,
        "language": config['language'],
        "raw_text": raw_text,
        "translation_en": None,  # Already English
        "translation_confidence": None,
        "access_grade": config['default_access_grade'],
        "bias_grade": config['default_bias_grade'],
        "kiq_tags": [],
        "topic_tags": ["isw_update", "osint"],
        "key_excerpts": key_excerpts
    }

    return evidence_doc


def fetch_seed_urls(config: Dict[str, Any], output_dir: str):
    """
    Fetch all seed URLs and create evidence_docs.

    Outputs:
        - evidence_docs_isw.jsonl
        - source_index_isw.json
        - ingest_report.json
    """
    print(f"Fetching {len(config['seed_urls'])} seed URLs...")

    evidence_docs = []
    errors = []
    retrieved_at = datetime.now(timezone.utc).isoformat()

    for i, url in enumerate(config['seed_urls'], 1):
        print(f"[{i}/{len(config['seed_urls'])}] Fetching {url}...")
        html = fetch_page(url)

        if html:
            try:
                doc = create_evidence_doc(url, html, config, retrieved_at)
                evidence_docs.append(doc)
                print(f"  ✓ Created {doc['doc_id']}")
            except Exception as e:
                errors.append({"url": url, "error": str(e)})
                print(f"  ✗ Error: {e}")
        else:
            errors.append({"url": url, "error": "Failed to fetch"})

    # Write outputs
    os.makedirs(output_dir, exist_ok=True)

    # evidence_docs.jsonl
    docs_path = os.path.join(output_dir, "evidence_docs_isw.jsonl")
    with open(docs_path, 'w') as f:
        for doc in evidence_docs:
            f.write(json.dumps(doc) + '\n')
    print(f"\nWrote {len(evidence_docs)} docs to {docs_path}")

    # source_index.json
    source_index = [{
        "source_id": config['source_id'],
        "organization": config['organization'],
        "default_access_grade": config['default_access_grade'],
        "default_bias_grade": config['default_bias_grade'],
        "language": config['language'],
        "notes": f"Institute for the Study of War - {config['bucket']}"
    }]

    source_path = os.path.join(output_dir, "source_index_isw.json")
    with open(source_path, 'w') as f:
        json.dump(source_index, f, indent=2)
    print(f"Wrote source index to {source_path}")

    # ingest_report.json
    report = {
        "fetched_at": retrieved_at,
        "total_urls": len(config['seed_urls']),
        "successful": len(evidence_docs),
        "failed": len(errors),
        "errors": errors
    }

    report_path = os.path.join(output_dir, "ingest_report.json")
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"Wrote ingest report to {report_path}")

    print(f"\n✓ Seed ingestion complete: {len(evidence_docs)}/{len(config['seed_urls'])} successful")


def fetch_latest_n(config: Dict[str, Any], n: int, output_dir: str):
    """
    Fetch latest N pages from ISW (requires index page scraping).

    NOT IMPLEMENTED IN MVP - requires discovering URLs from ISW's index page.
    For now, just print a placeholder message.
    """
    print(f"fetch_latest_n(n={n}) - NOT IMPLEMENTED YET")
    print("To implement:")
    print("1. Scrape ISW's /research/middle-east page")
    print("2. Extract links matching url_patterns")
    print("3. Sort by date, take N most recent")
    print("4. Call fetch_seed_urls() with discovered URLs")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Fetch ISW Iran updates as evidence_docs")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--seed', action='store_true', help="Fetch all seed URLs")
    mode.add_argument('--latest', type=int, metavar='N', help="Fetch latest N updates")

    parser.add_argument('--config', default='config/sources_isw.yaml', help="Config file path")
    parser.add_argument('--output', default='ingest/isw_output', help="Output directory")

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Execute mode
    if args.seed:
        fetch_seed_urls(config, args.output)
    elif args.latest:
        fetch_latest_n(config, args.latest, args.output)


if __name__ == '__main__':
    main()

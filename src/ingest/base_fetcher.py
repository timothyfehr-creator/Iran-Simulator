"""Abstract base class for all evidence fetchers with retry logic."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
import hashlib
import os
import time

import yaml

logger = logging.getLogger(__name__)

# Maximum length for raw document text (bytes). Truncated in create_evidence_doc().
MAX_DOC_TEXT_LENGTH = 50_000


# Default retry configuration (can be overridden by config/ingest.yaml)
DEFAULT_MAX_RETRIES = 3
DEFAULT_INITIAL_BACKOFF_SECONDS = 2
DEFAULT_BACKOFF_MULTIPLIER = 2


def load_ingest_config() -> Dict[str, Any]:
    """
    Load ingestion guardrail configuration from config/ingest.yaml.

    Returns:
        Config dict or empty dict if file not found
    """
    config_paths = [
        "config/ingest.yaml",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config/ingest.yaml"),
    ]

    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                logger.warning(f"Failed to load ingest config from {path}: {e}")

    return {}


def get_retry_config() -> Dict[str, Any]:
    """
    Get retry configuration, preferring config/ingest.yaml over defaults.

    Returns:
        Dict with max_retries, initial_backoff_seconds, backoff_multiplier
    """
    config = load_ingest_config()
    retry_config = config.get('retry', {})

    return {
        'max_retries': retry_config.get('max_retries', DEFAULT_MAX_RETRIES),
        'initial_backoff_seconds': retry_config.get('initial_backoff_seconds', DEFAULT_INITIAL_BACKOFF_SECONDS),
        'backoff_multiplier': retry_config.get('backoff_multiplier', DEFAULT_BACKOFF_MULTIPLIER),
    }


# Load at module level for backwards compatibility
_retry_config = get_retry_config()
MAX_RETRIES = _retry_config['max_retries']
INITIAL_BACKOFF_SECONDS = _retry_config['initial_backoff_seconds']
BACKOFF_MULTIPLIER = _retry_config['backoff_multiplier']


class FetchError(Exception):
    """Exception raised when a fetch fails after retries."""
    def __init__(self, source_id: str, message: str, original_error: Optional[Exception] = None):
        self.source_id = source_id
        self.message = message
        self.original_error = original_error
        super().__init__(f"{source_id}: {message}")


class BaseFetcher(ABC):
    """Abstract base for all evidence fetchers with built-in retry logic."""

    def __init__(self, source_config: Dict[str, Any]):
        self.source_id = source_config['id']
        self.name = source_config['name']
        self.bucket = source_config.get('bucket', 'unknown')
        self.access_grade = source_config.get('access_grade', 'C')
        self.bias_grade = source_config.get('bias_grade', 3)
        self.config = source_config

    @abstractmethod
    def _fetch_impl(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Internal fetch implementation - to be overridden by subclasses.

        Args:
            since: Only fetch docs published after this time (None = fetch all)

        Returns:
            List of evidence_doc dictionaries

        Raises:
            Exception on fetch failure
        """
        pass

    def fetch(self, since: Optional[datetime] = None) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Fetch with automatic retries and exponential backoff.

        Args:
            since: Only fetch docs published after this time (None = fetch all)

        Returns:
            Tuple of (docs, error_message)
            - On success: (docs, None)
            - On failure: ([], error_message)
        """
        last_error = None
        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                docs = self._fetch_impl(since)
                return docs, None
            except Exception as e:
                last_error = str(e)
                if attempt < MAX_RETRIES:
                    logger.warning(f"Retry {attempt}/{MAX_RETRIES} for {self.source_id} in {backoff}s: {e}")
                    time.sleep(backoff)
                    backoff *= BACKOFF_MULTIPLIER
                else:
                    logger.error(f"Failed after {MAX_RETRIES} attempts for {self.source_id}: {e}")

        return [], last_error

    def create_evidence_doc(
        self,
        url: str,
        title: str,
        published_at: str,
        raw_text: str,
        language: str = "en",
        key_excerpts: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create standardized evidence_doc.

        Args:
            url: Source URL
            title: Article title
            published_at: ISO 8601 timestamp
            raw_text: Full article text
            language: ISO 639-1 code (en, fa, ar, etc.)
            key_excerpts: Optional list of key excerpts

        Returns:
            evidence_doc dict conforming to schema
        """
        retrieved_at = datetime.now(timezone.utc).isoformat()

        # Generate doc_id: SRCID_YYYYMMDD_HHMM_HASH
        timestamp = datetime.fromisoformat(retrieved_at.replace('Z', '+00:00'))
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        doc_id = f"{self.source_id.upper()}_{timestamp.strftime('%Y%m%d_%H%M')}_{url_hash}"

        # For non-English sources, set translation_confidence to 0.0 (no translation done yet)
        translation_confidence = 0.0 if language != "en" else None

        return {
            "doc_id": doc_id,
            "source_id": f"SRC_{self.source_id.upper()}",
            "organization": self.name,
            "title": title,
            "url": url,
            "published_at_utc": published_at,
            "retrieved_at_utc": retrieved_at,
            "language": language,
            "raw_text": raw_text[:MAX_DOC_TEXT_LENGTH],
            "translation_en": None,  # TODO: Add automatic translation
            "translation_confidence": translation_confidence,
            "access_grade": self.access_grade,
            "bias_grade": self.bias_grade,
            "kiq_tags": [],
            "topic_tags": [self.bucket],
            "key_excerpts": key_excerpts or []
        }

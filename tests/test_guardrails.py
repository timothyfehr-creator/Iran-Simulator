"""
Tests for automation guardrails: caps, cache, and FAIL behavior.

Workstream 5: Automation Guardrails
Verifies per-bucket caps, document caching, and coverage FAIL handling.
"""

import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta, timezone

from src.ingest.base_fetcher import (
    load_ingest_config,
    get_retry_config,
    DEFAULT_MAX_RETRIES,
    DEFAULT_INITIAL_BACKOFF_SECONDS,
    DEFAULT_BACKOFF_MULTIPLIER
)
from src.ingest.coordinator import (
    DocCache,
    apply_per_bucket_caps
)


class TestIngestConfigLoading:
    """Tests for loading ingest guardrail configuration."""

    def test_load_default_config(self):
        """Should load config from config/ingest.yaml if it exists."""
        config = load_ingest_config()

        # Config should be a dict (even if empty)
        assert isinstance(config, dict)

    def test_get_retry_config_has_required_fields(self):
        """Retry config should have all required fields."""
        config = get_retry_config()

        assert "max_retries" in config
        assert "initial_backoff_seconds" in config
        assert "backoff_multiplier" in config

    def test_retry_config_uses_defaults_when_missing(self):
        """Should use defaults when config file is missing fields."""
        config = get_retry_config()

        # Should be positive integers
        assert config["max_retries"] >= 1
        assert config["initial_backoff_seconds"] >= 1
        assert config["backoff_multiplier"] >= 1


class TestDocCache:
    """Tests for document caching functionality."""

    def test_compute_doc_hash_deterministic(self):
        """Same doc should produce same hash."""
        doc = {
            "url": "https://example.com/article1",
            "published_at_utc": "2026-01-19T12:00:00Z",
            "title": "Test Article"
        }

        hash1 = DocCache.compute_doc_hash(doc)
        hash2 = DocCache.compute_doc_hash(doc)

        assert hash1 == hash2

    def test_compute_doc_hash_different_for_different_docs(self):
        """Different docs should produce different hashes."""
        doc1 = {
            "url": "https://example.com/article1",
            "published_at_utc": "2026-01-19T12:00:00Z",
            "title": "Test Article 1"
        }
        doc2 = {
            "url": "https://example.com/article2",
            "published_at_utc": "2026-01-19T12:00:00Z",
            "title": "Test Article 2"
        }

        hash1 = DocCache.compute_doc_hash(doc1)
        hash2 = DocCache.compute_doc_hash(doc2)

        assert hash1 != hash2

    def test_cache_add_and_check(self):
        """Should detect cached documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "cache.json")
            cache = DocCache(cache_path)

            doc = {
                "url": "https://example.com/article",
                "published_at_utc": "2026-01-19T12:00:00Z",
                "title": "Test"
            }

            # Initially not cached
            assert not cache.is_cached(doc)

            # Add to cache
            cache.add(doc)

            # Now should be cached
            assert cache.is_cached(doc)

    def test_cache_persistence(self):
        """Cache should persist to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "cache.json")

            # Create and populate cache
            cache1 = DocCache(cache_path)
            doc = {
                "url": "https://example.com/article",
                "published_at_utc": "2026-01-19T12:00:00Z",
                "title": "Test"
            }
            cache1.add(doc)
            cache1.save()

            # Load in new instance
            cache2 = DocCache(cache_path)

            # Should still be cached
            assert cache2.is_cached(doc)

    def test_cache_add_all(self):
        """Should add multiple documents at once."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "cache.json")
            cache = DocCache(cache_path)

            docs = [
                {"url": f"https://example.com/article{i}",
                 "published_at_utc": "2026-01-19T12:00:00Z",
                 "title": f"Article {i}"}
                for i in range(5)
            ]

            cache.add_all(docs)

            for doc in docs:
                assert cache.is_cached(doc)


class TestPerBucketCaps:
    """Tests for per-bucket document caps."""

    def test_apply_caps_keeps_newest(self):
        """Should keep newest docs when capping."""
        source_config = {
            "isw": {"bucket": "osint_thinktank"},
        }

        # Create 5 docs, cap at 3
        docs = [
            {
                "doc_id": f"doc_{i}",
                "source_id": "SRC_ISW",
                "published_at_utc": f"2026-01-{10+i:02d}T12:00:00Z",  # Older to newer
                "title": f"Article {i}"
            }
            for i in range(5)
        ]

        capped = apply_per_bucket_caps(docs, source_config, max_per_bucket=3)

        assert len(capped) == 3

        # Should have newest 3 (dates 12, 13, 14)
        dates = sorted([d["published_at_utc"] for d in capped])
        assert "2026-01-10" not in dates[0]  # Oldest should be removed
        assert "2026-01-11" not in dates[0]

    def test_apply_caps_per_bucket_independent(self):
        """Each bucket should be capped independently."""
        source_config = {
            "isw": {"bucket": "osint_thinktank"},
            "hrana": {"bucket": "ngo_rights"},
        }

        docs = []
        # 5 docs for osint_thinktank
        for i in range(5):
            docs.append({
                "doc_id": f"isw_{i}",
                "source_id": "SRC_ISW",
                "published_at_utc": f"2026-01-{10+i:02d}T12:00:00Z",
            })
        # 5 docs for ngo_rights
        for i in range(5):
            docs.append({
                "doc_id": f"hrana_{i}",
                "source_id": "SRC_HRANA",
                "published_at_utc": f"2026-01-{10+i:02d}T12:00:00Z",
            })

        capped = apply_per_bucket_caps(docs, source_config, max_per_bucket=3)

        # Should have 3 from each bucket = 6 total
        assert len(capped) == 6

        isw_docs = [d for d in capped if "isw" in d["doc_id"]]
        hrana_docs = [d for d in capped if "hrana" in d["doc_id"]]
        assert len(isw_docs) == 3
        assert len(hrana_docs) == 3

    def test_apply_caps_no_change_when_under_limit(self):
        """Should not remove docs when under cap."""
        source_config = {
            "isw": {"bucket": "osint_thinktank"},
        }

        docs = [
            {
                "doc_id": f"doc_{i}",
                "source_id": "SRC_ISW",
                "published_at_utc": f"2026-01-{10+i:02d}T12:00:00Z",
            }
            for i in range(3)
        ]

        capped = apply_per_bucket_caps(docs, source_config, max_per_bucket=10)

        assert len(capped) == 3

    def test_apply_caps_handles_unknown_bucket(self):
        """Should handle docs with unknown buckets."""
        source_config = {
            "isw": {"bucket": "osint_thinktank"},
        }

        docs = [
            {
                "doc_id": "unknown_1",
                "source_id": "SRC_UNKNOWN",
                "published_at_utc": "2026-01-15T12:00:00Z",
            }
        ]

        capped = apply_per_bucket_caps(docs, source_config, max_per_bucket=10)

        # Should still include the doc (in "unknown" bucket)
        assert len(capped) == 1


class TestCoverageFailBehavior:
    """Tests for coverage FAIL handling."""

    def test_config_has_on_coverage_fail_option(self):
        """Config should have on_coverage_fail option."""
        config = load_ingest_config()

        # Should have the option (or use default)
        on_fail = config.get("on_coverage_fail", "skip_simulation")
        assert on_fail in ["skip_simulation", "warn_only", "fail_fast"]


class TestGuardrailsIntegration:
    """Integration tests for guardrails working together."""

    def test_cache_and_caps_work_together(self):
        """Cache filtering should happen before cap filtering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "cache.json")
            cache = DocCache(cache_path)

            source_config = {
                "isw": {"bucket": "osint_thinktank"},
            }

            # Create 10 docs
            all_docs = [
                {
                    "doc_id": f"doc_{i}",
                    "source_id": "SRC_ISW",
                    "url": f"https://example.com/article{i}",
                    "published_at_utc": f"2026-01-{10+i:02d}T12:00:00Z",
                    "title": f"Article {i}"
                }
                for i in range(10)
            ]

            # Cache the first 5
            cache.add_all(all_docs[:5])
            cache.save()

            # Filter by cache first
            uncached = [doc for doc in all_docs if not cache.is_cached(doc)]
            assert len(uncached) == 5

            # Then apply caps
            capped = apply_per_bucket_caps(uncached, source_config, max_per_bucket=3)
            assert len(capped) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

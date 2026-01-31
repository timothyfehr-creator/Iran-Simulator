"""
Tests for coverage window configuration.

Workstream 1: Rolling-Window Coverage Gates
Verifies that BUCKET_WINDOWS values are correct, including the 72h internet_monitoring window.
"""

import pytest
from datetime import datetime, timedelta, timezone

from src.ingest.coverage import (
    evaluate_coverage,
    BUCKET_WINDOWS,
    CRITICAL_BUCKETS,
    BUCKET_NAMES
)


class TestBucketWindowConfiguration:
    """Tests for BUCKET_WINDOWS configuration values."""

    def test_internet_monitoring_window_is_72h(self):
        """internet_monitoring bucket should have 72h window (changed from 168h)."""
        assert BUCKET_WINDOWS["internet_monitoring"] == 72, (
            f"internet_monitoring window should be 72h, got {BUCKET_WINDOWS['internet_monitoring']}"
        )

    def test_osint_thinktank_window_is_36h(self):
        """osint_thinktank bucket should have 36h window."""
        assert BUCKET_WINDOWS["osint_thinktank"] == 36

    def test_ngo_rights_window_is_72h(self):
        """ngo_rights bucket should have 72h window."""
        assert BUCKET_WINDOWS["ngo_rights"] == 72

    def test_regime_outlets_window_is_72h(self):
        """regime_outlets bucket should have 72h window."""
        assert BUCKET_WINDOWS["regime_outlets"] == 72

    def test_persian_services_window_is_72h(self):
        """persian_services bucket should have 72h window."""
        assert BUCKET_WINDOWS["persian_services"] == 72

    def test_econ_fx_window_is_72h(self):
        """econ_fx bucket should have 72h window."""
        assert BUCKET_WINDOWS["econ_fx"] == 72

    def test_all_buckets_have_windows(self):
        """All expected buckets should have window definitions."""
        expected_buckets = {
            "osint_thinktank",
            "ngo_rights",
            "regime_outlets",
            "persian_services",
            "internet_monitoring",
            "econ_fx",
        }
        assert set(BUCKET_WINDOWS.keys()) == expected_buckets

    def test_all_buckets_have_display_names(self):
        """All buckets should have display names defined."""
        for bucket in BUCKET_WINDOWS:
            assert bucket in BUCKET_NAMES, f"Missing display name for bucket: {bucket}"


class TestCriticalBuckets:
    """Tests for CRITICAL_BUCKETS configuration."""

    def test_critical_buckets_defined(self):
        """Critical buckets should include the 4 key intelligence buckets."""
        expected_critical = {
            "osint_thinktank",
            "ngo_rights",
            "regime_outlets",
            "persian_services",
        }
        assert CRITICAL_BUCKETS == expected_critical

    def test_internet_monitoring_not_critical(self):
        """internet_monitoring should NOT be critical (crowdsourced, less frequent)."""
        assert "internet_monitoring" not in CRITICAL_BUCKETS

    def test_econ_fx_not_critical(self):
        """econ_fx should NOT be critical (supplementary data)."""
        assert "econ_fx" not in CRITICAL_BUCKETS


class TestInternetMonitoring72hWindow:
    """Tests specifically for the 72h internet_monitoring window behavior."""

    def test_doc_at_60h_counts_for_internet_monitoring(self):
        """Doc published 60h ago should count for internet_monitoring bucket."""
        now = datetime.now(timezone.utc)

        docs = [
            {
                "doc_id": "NETBLOCKS_001",
                "source_id": "SRC_NETBLOCKS",
                "published_at_utc": (now - timedelta(hours=60)).isoformat()
            }
        ]

        source_config = {"netblocks": {"bucket": "internet_monitoring"}}
        report = evaluate_coverage(docs, source_config, reference_time=now)

        assert "internet_monitoring" in report.buckets_present
        assert report.counts_by_bucket.get("internet_monitoring", 0) == 1

    def test_doc_at_72h_counts_for_internet_monitoring(self):
        """Doc at exactly 72h boundary should count for internet_monitoring."""
        now = datetime.now(timezone.utc)

        docs = [
            {
                "doc_id": "OONI_001",
                "source_id": "SRC_OONI",
                "published_at_utc": (now - timedelta(hours=72)).isoformat()
            }
        ]

        source_config = {"ooni": {"bucket": "internet_monitoring"}}
        report = evaluate_coverage(docs, source_config, reference_time=now)

        assert "internet_monitoring" in report.buckets_present

    def test_doc_at_73h_does_not_count_for_internet_monitoring(self):
        """Doc at 73h (outside 72h window) should NOT count for internet_monitoring."""
        now = datetime.now(timezone.utc)

        docs = [
            {
                "doc_id": "NETBLOCKS_001",
                "source_id": "SRC_NETBLOCKS",
                "published_at_utc": (now - timedelta(hours=73)).isoformat()
            }
        ]

        source_config = {"netblocks": {"bucket": "internet_monitoring"}}
        report = evaluate_coverage(docs, source_config, reference_time=now)

        assert "internet_monitoring" in report.buckets_missing
        assert report.counts_by_bucket.get("internet_monitoring", 0) == 0

    def test_doc_at_100h_does_not_count_for_internet_monitoring(self):
        """Doc at 100h (would have counted under old 168h window) should NOT count."""
        now = datetime.now(timezone.utc)

        docs = [
            {
                "doc_id": "NETBLOCKS_001",
                "source_id": "SRC_NETBLOCKS",
                "published_at_utc": (now - timedelta(hours=100)).isoformat()
            }
        ]

        source_config = {"netblocks": {"bucket": "internet_monitoring"}}
        report = evaluate_coverage(docs, source_config, reference_time=now)

        # Under old 168h window, this would have counted
        # Under new 72h window, it should NOT count
        assert "internet_monitoring" in report.buckets_missing

    def test_doc_at_168h_does_not_count_for_internet_monitoring(self):
        """Doc at 168h (old window limit) should NOT count under new 72h window."""
        now = datetime.now(timezone.utc)

        docs = [
            {
                "doc_id": "NETBLOCKS_001",
                "source_id": "SRC_NETBLOCKS",
                "published_at_utc": (now - timedelta(hours=168)).isoformat()
            }
        ]

        source_config = {"netblocks": {"bucket": "internet_monitoring"}}
        report = evaluate_coverage(docs, source_config, reference_time=now)

        assert "internet_monitoring" in report.buckets_missing


class TestWindowBoundaryBehavior:
    """Tests for edge cases at window boundaries."""

    def test_docs_exactly_at_each_bucket_boundary(self):
        """Docs at exactly window boundary should count for each bucket."""
        now = datetime.now(timezone.utc)

        docs = [
            # At osint_thinktank boundary (36h)
            {
                "doc_id": "ISW_001",
                "source_id": "SRC_ISW",
                "published_at_utc": (now - timedelta(hours=36)).isoformat()
            },
            # At ngo_rights boundary (72h)
            {
                "doc_id": "HRANA_001",
                "source_id": "SRC_HRANA",
                "published_at_utc": (now - timedelta(hours=72)).isoformat()
            },
            # At internet_monitoring boundary (72h)
            {
                "doc_id": "NETBLOCKS_001",
                "source_id": "SRC_NETBLOCKS",
                "published_at_utc": (now - timedelta(hours=72)).isoformat()
            },
        ]

        source_config = {
            "isw": {"bucket": "osint_thinktank"},
            "hrana": {"bucket": "ngo_rights"},
            "netblocks": {"bucket": "internet_monitoring"},
        }

        report = evaluate_coverage(docs, source_config, reference_time=now)

        assert "osint_thinktank" in report.buckets_present
        assert "ngo_rights" in report.buckets_present
        assert "internet_monitoring" in report.buckets_present

    def test_doc_one_second_after_boundary_does_not_count(self):
        """Doc 1 second after window boundary should NOT count."""
        now = datetime.now(timezone.utc)

        # 72 hours and 1 second ago
        docs = [
            {
                "doc_id": "NETBLOCKS_001",
                "source_id": "SRC_NETBLOCKS",
                "published_at_utc": (now - timedelta(hours=72, seconds=1)).isoformat()
            }
        ]

        source_config = {"netblocks": {"bucket": "internet_monitoring"}}
        report = evaluate_coverage(docs, source_config, reference_time=now)

        # Technically this depends on floating point precision
        # The implementation uses hours, so 72.0002777... hours
        # This should be outside the <= 72 window
        assert "internet_monitoring" in report.buckets_missing


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

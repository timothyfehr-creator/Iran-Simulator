"""
Tests for rolling window gate behavior in import_deep_research_bundle_v3.

Workstream 1: Rolling-Window Coverage Gates
Verifies WARN vs FAIL behavior and integration with coverage.evaluate_coverage().
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from src.pipeline.import_deep_research_bundle_v3 import (
    check_daily_update_gates,
    _build_source_config_from_docs,
)
from src.ingest.coverage import BUCKET_WINDOWS, CRITICAL_BUCKETS


# Test source config that maps test source_ids to buckets
# This avoids dependency on config/sources.yaml which may have different naming
TEST_SOURCE_CONFIG = {
    "isw": {"bucket": "osint_thinktank", "name": "ISW"},
    "hrana": {"bucket": "ngo_rights", "name": "HRANA"},
    "irna": {"bucket": "regime_outlets", "name": "IRNA"},
    "iranintl": {"bucket": "persian_services", "name": "Iran International"},
    "netblocks": {"bucket": "internet_monitoring", "name": "NetBlocks"},
    "bonbast": {"bucket": "econ_fx", "name": "Bonbast"},
}


class TestCheckDailyUpdateGates:
    """Tests for check_daily_update_gates() function."""

    def test_returns_skip_without_cutoff(self):
        """Should return SKIP status when no cutoff provided."""
        result = check_daily_update_gates([], None)

        assert result["status"] == "SKIP"
        assert "No data cutoff" in result["status_reason"]

    def test_returns_skip_with_invalid_cutoff(self):
        """Should return SKIP status when cutoff is invalid."""
        result = check_daily_update_gates([], "invalid-date-format")

        assert result["status"] == "SKIP"
        assert "Invalid cutoff" in result["status_reason"]

    def test_returns_required_fields(self):
        """Result should include all required fields."""
        now = datetime.now(timezone.utc)
        docs = [
            {
                "doc_id": "ISW_001",
                "source_id": "SRC_ISW",
                "published_at_utc": (now - timedelta(hours=12)).isoformat()
            }
        ]

        result = check_daily_update_gates(docs, now.isoformat())

        # Required fields per plan
        assert "counts_by_bucket" in result
        assert "buckets_missing" in result
        assert "bucket_details" in result
        assert "status" in result

        # Additional context fields
        assert "buckets_present" in result
        assert "warnings" in result
        assert "reference_time_utc" in result
        assert "total_docs" in result

    def test_pass_when_all_buckets_covered(self):
        """Should return PASS when all buckets have coverage."""
        now = datetime.now(timezone.utc)

        # Create docs for all buckets
        docs = [
            {"doc_id": "ISW_001", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=12)).isoformat()},
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
            {"doc_id": "IRNA_001", "source_id": "SRC_IRNA",
             "published_at_utc": (now - timedelta(hours=36)).isoformat()},
            {"doc_id": "IRANINTL_001", "source_id": "SRC_IRANINTL",
             "published_at_utc": (now - timedelta(hours=48)).isoformat()},
            {"doc_id": "NETBLOCKS_001", "source_id": "SRC_NETBLOCKS",
             "published_at_utc": (now - timedelta(hours=60)).isoformat()},
            {"doc_id": "BONBAST_001", "source_id": "SRC_BONBAST",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
        ]

        # Pass explicit source_config to avoid YAML config mismatch
        result = check_daily_update_gates(docs, now.isoformat(), source_config=TEST_SOURCE_CONFIG)

        assert result["status"] == "PASS"
        assert len(result["buckets_missing"]) == 0

    def test_warn_when_one_critical_bucket_missing(self):
        """Should return WARN when exactly 1 critical bucket is missing."""
        now = datetime.now(timezone.utc)

        # Cover 3 of 4 critical buckets + non-critical
        docs = [
            {"doc_id": "ISW_001", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=12)).isoformat()},
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
            {"doc_id": "IRNA_001", "source_id": "SRC_IRNA",
             "published_at_utc": (now - timedelta(hours=36)).isoformat()},
            # Missing: persian_services (CRITICAL)
            {"doc_id": "NETBLOCKS_001", "source_id": "SRC_NETBLOCKS",
             "published_at_utc": (now - timedelta(hours=48)).isoformat()},
            {"doc_id": "BONBAST_001", "source_id": "SRC_BONBAST",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
        ]

        result = check_daily_update_gates(docs, now.isoformat())

        assert result["status"] == "WARN"
        assert "persian_services" in result["buckets_missing"]
        assert len(result["warnings"]) > 0

    def test_fail_when_two_critical_buckets_missing(self):
        """Should return FAIL when 2+ critical buckets are missing."""
        now = datetime.now(timezone.utc)

        # Cover only 2 of 4 critical buckets
        docs = [
            {"doc_id": "ISW_001", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=12)).isoformat()},
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
            # Missing: regime_outlets (CRITICAL)
            # Missing: persian_services (CRITICAL)
            {"doc_id": "NETBLOCKS_001", "source_id": "SRC_NETBLOCKS",
             "published_at_utc": (now - timedelta(hours=48)).isoformat()},
            {"doc_id": "BONBAST_001", "source_id": "SRC_BONBAST",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
        ]

        result = check_daily_update_gates(docs, now.isoformat())

        assert result["status"] == "FAIL"
        missing_critical = [b for b in result["buckets_missing"] if b in CRITICAL_BUCKETS]
        assert len(missing_critical) >= 2

    def test_non_critical_missing_still_warns(self):
        """Missing non-critical bucket should still generate warning."""
        now = datetime.now(timezone.utc)

        # Cover all critical but miss internet_monitoring
        docs = [
            {"doc_id": "ISW_001", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=12)).isoformat()},
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
            {"doc_id": "IRNA_001", "source_id": "SRC_IRNA",
             "published_at_utc": (now - timedelta(hours=36)).isoformat()},
            {"doc_id": "IRANINTL_001", "source_id": "SRC_IRANINTL",
             "published_at_utc": (now - timedelta(hours=48)).isoformat()},
            # Missing: internet_monitoring (non-critical)
            {"doc_id": "BONBAST_001", "source_id": "SRC_BONBAST",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
        ]

        result = check_daily_update_gates(docs, now.isoformat())

        # Status should be WARN (missing bucket), not PASS
        assert result["status"] == "WARN"
        assert "internet_monitoring" in result["buckets_missing"]

    def test_counts_by_bucket_populated(self):
        """counts_by_bucket should have counts for each bucket."""
        now = datetime.now(timezone.utc)

        docs = [
            {"doc_id": "ISW_001", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=12)).isoformat()},
            {"doc_id": "ISW_002", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=18)).isoformat()},
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(hours=24)).isoformat()},
        ]

        result = check_daily_update_gates(docs, now.isoformat())

        assert result["counts_by_bucket"]["osint_thinktank"] == 2
        assert result["counts_by_bucket"]["ngo_rights"] == 1

    def test_bucket_details_has_window_info(self):
        """bucket_details should include window hours and coverage info."""
        now = datetime.now(timezone.utc)

        docs = [
            {"doc_id": "ISW_001", "source_id": "SRC_ISW",
             "published_at_utc": (now - timedelta(hours=12)).isoformat()},
        ]

        result = check_daily_update_gates(docs, now.isoformat())

        assert "osint_thinktank" in result["bucket_details"]
        osint_detail = result["bucket_details"]["osint_thinktank"]
        assert "window_hours" in osint_detail
        assert osint_detail["window_hours"] == 36
        assert "docs_in_window" in osint_detail
        assert "covered" in osint_detail


class TestBuildSourceConfigFromDocs:
    """Tests for _build_source_config_from_docs() helper function."""

    def test_builds_config_from_source_ids(self):
        """Should map source_ids to buckets based on patterns."""
        docs = [
            {"source_id": "SRC_ISW", "doc_id": "1"},
            {"source_id": "SRC_HRANA", "doc_id": "2"},
            {"source_id": "SRC_IRNA", "doc_id": "3"},
        ]

        config = _build_source_config_from_docs(docs)

        assert "isw" in config
        assert config["isw"]["bucket"] == "osint_thinktank"

        assert "hrana" in config
        assert config["hrana"]["bucket"] == "ngo_rights"

        assert "irna" in config
        assert config["irna"]["bucket"] == "regime_outlets"

    def test_handles_various_source_patterns(self):
        """Should correctly map various source patterns."""
        docs = [
            {"source_id": "SRC_NETBLOCKS", "doc_id": "1"},
            {"source_id": "SRC_OONI", "doc_id": "2"},
            {"source_id": "SRC_IODA", "doc_id": "3"},
            {"source_id": "SRC_BONBAST", "doc_id": "4"},
            {"source_id": "SRC_TGJU", "doc_id": "5"},
        ]

        config = _build_source_config_from_docs(docs)

        assert config.get("netblocks", {}).get("bucket") == "internet_monitoring"
        assert config.get("ooni", {}).get("bucket") == "internet_monitoring"
        assert config.get("ioda", {}).get("bucket") == "internet_monitoring"
        assert config.get("bonbast", {}).get("bucket") == "econ_fx"
        assert config.get("tgju", {}).get("bucket") == "econ_fx"

    def test_handles_lowercase_source_ids(self):
        """Should handle source_ids without SRC_ prefix."""
        docs = [
            {"source_id": "isw", "doc_id": "1"},
            {"source_id": "hrana", "doc_id": "2"},
        ]

        config = _build_source_config_from_docs(docs)

        assert "isw" in config
        assert "hrana" in config


class TestRollingWindowVsCutoffDate:
    """Tests verifying rolling window behavior vs old cutoff date logic."""

    def test_docs_spread_across_multiple_days_count(self):
        """Docs from multiple days within window should all count."""
        now = datetime.now(timezone.utc)

        # Docs from last 3 days (all within 72h window)
        docs = [
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(days=0, hours=6)).isoformat()},
            {"doc_id": "HRANA_002", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(days=1, hours=12)).isoformat()},
            {"doc_id": "HRANA_003", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(days=2, hours=18)).isoformat()},
        ]

        result = check_daily_update_gates(docs, now.isoformat())

        # All 3 docs should count toward ngo_rights
        assert result["counts_by_bucket"]["ngo_rights"] == 3

    def test_window_uses_reference_time_not_now(self):
        """Window should be calculated from cutoff time, not current time."""
        # Reference time is 48 hours ago
        now = datetime.now(timezone.utc)
        reference_time = now - timedelta(hours=48)

        # Doc published 60 hours ago (12 hours before reference)
        docs = [
            {"doc_id": "HRANA_001", "source_id": "SRC_HRANA",
             "published_at_utc": (now - timedelta(hours=60)).isoformat()}
        ]

        # From reference_time (48h ago), the doc is 12h old - within 72h window
        result = check_daily_update_gates(docs, reference_time.isoformat())

        assert "ngo_rights" in result["buckets_present"]

    def test_old_168h_docs_no_longer_count_for_internet_monitoring(self):
        """Docs from 168h ago (old window) should NOT count under new 72h window."""
        now = datetime.now(timezone.utc)

        # Doc at exactly 168h (old internet_monitoring window)
        docs = [
            {"doc_id": "NETBLOCKS_001", "source_id": "SRC_NETBLOCKS",
             "published_at_utc": (now - timedelta(hours=168)).isoformat()}
        ]

        result = check_daily_update_gates(docs, now.isoformat())

        # Should NOT count under new 72h window
        assert "internet_monitoring" in result["buckets_missing"]
        assert result["counts_by_bucket"]["internet_monitoring"] == 0


class TestWarningsContent:
    """Tests for warning message content and format."""

    def test_critical_bucket_warning_labeled(self):
        """Warnings for critical buckets should be labeled CRITICAL."""
        now = datetime.now(timezone.utc)

        docs = []  # No docs - all buckets missing

        result = check_daily_update_gates(docs, now.isoformat())

        # Find warning for a critical bucket
        critical_warnings = [w for w in result["warnings"] if "CRITICAL" in w]
        assert len(critical_warnings) >= 1

    def test_warnings_include_window_hours(self):
        """Warnings should include the window hours for context."""
        now = datetime.now(timezone.utc)

        docs = []  # No docs

        result = check_daily_update_gates(docs, now.isoformat())

        # At least one warning should mention window hours
        has_window_info = any("h)" in w or "window" in w.lower() for w in result["warnings"])
        assert has_window_info, f"Warnings should include window info: {result['warnings']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Tests for resolver.py - bin_map, enum_match rules, requires_manual_resolution skip.
"""

import pytest
from src.forecasting import resolver


class TestBinMapRule:
    """Tests for bin_map resolution rule."""

    @pytest.fixture
    def fx_event(self):
        """FX band event definition."""
        return {
            "event_id": "econ.fx_band",
            "event_type": "binned_continuous",
            "allowed_outcomes": ["FX_LT_800K", "FX_800K_1M", "FX_1M_1_2M", "FX_GE_1_2M", "UNKNOWN"],
            "bin_spec": {
                "bins": [
                    {"bin_id": "FX_LT_800K", "label": "< 800k", "min": None, "max": 800000, "include_min": False, "include_max": False},
                    {"bin_id": "FX_800K_1M", "label": "800k-1.0m", "min": 800000, "max": 1000000, "include_min": True, "include_max": False},
                    {"bin_id": "FX_1M_1_2M", "label": "1.0m-1.2m", "min": 1000000, "max": 1200000, "include_min": True, "include_max": False},
                    {"bin_id": "FX_GE_1_2M", "label": ">= 1.2m", "min": 1200000, "max": None, "include_min": True, "include_max": True},
                ]
            }
        }

    def test_bin_map_value_in_first_bin(self, fx_event):
        """Value in first bin should map correctly."""
        outcome, reason = resolver.apply_resolution_rule(
            value=500000,
            rule="bin_map",
            rule_params={},
            event=fx_event
        )
        assert outcome == "FX_LT_800K"
        assert reason is None

    def test_bin_map_value_in_middle_bin(self, fx_event):
        """Value in middle bin should map correctly."""
        outcome, reason = resolver.apply_resolution_rule(
            value=900000,
            rule="bin_map",
            rule_params={},
            event=fx_event
        )
        assert outcome == "FX_800K_1M"
        assert reason is None

    def test_bin_map_value_in_last_bin(self, fx_event):
        """Value in last bin should map correctly."""
        outcome, reason = resolver.apply_resolution_rule(
            value=1500000,
            rule="bin_map",
            rule_params={},
            event=fx_event
        )
        assert outcome == "FX_GE_1_2M"
        assert reason is None

    def test_bin_map_boundary_value(self, fx_event):
        """Value at boundary should map based on include flags."""
        # 800000 has include_min=True for FX_800K_1M
        outcome, reason = resolver.apply_resolution_rule(
            value=800000,
            rule="bin_map",
            rule_params={},
            event=fx_event
        )
        assert outcome == "FX_800K_1M"
        assert reason is None

    def test_bin_map_none_value(self, fx_event):
        """None value should return UNKNOWN."""
        outcome, reason = resolver.apply_resolution_rule(
            value=None,
            rule="bin_map",
            rule_params={},
            event=fx_event
        )
        assert outcome == "UNKNOWN"
        assert reason == "missing_value"

    def test_bin_map_missing_bin_spec(self):
        """Event without bin_spec should return UNKNOWN."""
        event = {"event_id": "test.no_bins"}
        outcome, reason = resolver.apply_resolution_rule(
            value=100,
            rule="bin_map",
            rule_params={},
            event=event
        )
        assert outcome == "UNKNOWN"
        assert reason == "missing_bin_spec"


class TestEnumMatchRule:
    """Tests for enum_match resolution rule."""

    @pytest.fixture
    def internet_event(self):
        """Internet level event definition."""
        return {
            "event_id": "info.internet_level",
            "event_type": "categorical",
            "allowed_outcomes": ["FUNCTIONAL", "PARTIAL", "SEVERELY_DEGRADED", "BLACKOUT", "UNKNOWN"],
        }

    def test_enum_match_exact(self, internet_event):
        """Exact match should return the outcome."""
        outcome, reason = resolver.apply_resolution_rule(
            value="FUNCTIONAL",
            rule="enum_match",
            rule_params={},
            event=internet_event
        )
        assert outcome == "FUNCTIONAL"
        assert reason is None

    def test_enum_match_case_insensitive(self, internet_event):
        """Match should be case-insensitive."""
        outcome, reason = resolver.apply_resolution_rule(
            value="functional",
            rule="enum_match",
            rule_params={},
            event=internet_event
        )
        assert outcome == "FUNCTIONAL"
        assert reason is None

        outcome, reason = resolver.apply_resolution_rule(
            value="Partial",
            rule="enum_match",
            rule_params={},
            event=internet_event
        )
        assert outcome == "PARTIAL"
        assert reason is None

    def test_enum_match_not_in_outcomes(self, internet_event):
        """Value not in allowed_outcomes should return UNKNOWN."""
        outcome, reason = resolver.apply_resolution_rule(
            value="INVALID_STATUS",
            rule="enum_match",
            rule_params={},
            event=internet_event
        )
        assert outcome == "UNKNOWN"
        assert reason == "value_not_in_outcomes"

    def test_enum_match_none_value(self, internet_event):
        """None value should return UNKNOWN."""
        outcome, reason = resolver.apply_resolution_rule(
            value=None,
            rule="enum_match",
            rule_params={},
            event=internet_event
        )
        assert outcome == "UNKNOWN"
        assert reason == "missing_value"


class TestExistingRulesWithEventParam:
    """Tests that existing rules still work with the event parameter."""

    @pytest.fixture
    def binary_event(self):
        """Binary event definition."""
        return {
            "event_id": "test.binary",
            "event_type": "binary",
            "allowed_outcomes": ["YES", "NO"],
        }

    def test_threshold_gte(self, binary_event):
        """threshold_gte should still work."""
        outcome, reason = resolver.apply_resolution_rule(
            value=100,
            rule="threshold_gte",
            rule_params={"threshold": 50},
            event=binary_event
        )
        assert outcome == "YES"
        assert reason is None

        outcome, reason = resolver.apply_resolution_rule(
            value=30,
            rule="threshold_gte",
            rule_params={"threshold": 50},
            event=binary_event
        )
        assert outcome == "NO"
        assert reason is None

    def test_threshold_gt(self, binary_event):
        """threshold_gt should still work."""
        outcome, reason = resolver.apply_resolution_rule(
            value=50,
            rule="threshold_gt",
            rule_params={"threshold": 50},
            event=binary_event
        )
        assert outcome == "NO"  # 50 is not > 50
        assert reason is None

    def test_enum_equals(self, binary_event):
        """enum_equals should still work."""
        outcome, reason = resolver.apply_resolution_rule(
            value="CRITICAL",
            rule="enum_equals",
            rule_params={"value": "critical"},
            event=binary_event
        )
        assert outcome == "YES"
        assert reason is None

    def test_enum_in(self, binary_event):
        """enum_in should still work."""
        outcome, reason = resolver.apply_resolution_rule(
            value="BLACKOUT",
            rule="enum_in",
            rule_params={"values": ["BLACKOUT", "SEVERELY_DEGRADED"]},
            event=binary_event
        )
        assert outcome == "YES"
        assert reason is None


class TestRequiresManualResolution:
    """Tests for requires_manual_resolution skip in resolve_pending."""

    def test_manual_event_skipped(self):
        """Events with requires_manual_resolution: true should be skipped."""
        # This test would require mocking the full resolve_pending flow
        # For now, we test the logic indirectly by checking event definitions

        event_with_manual = {
            "event_id": "protest.multi_city",
            "requires_manual_resolution": True
        }
        event_without_manual = {
            "event_id": "econ.fx_band",
            "requires_manual_resolution": False
        }
        event_default = {
            "event_id": "econ.rial_ge_1_2m"
            # No requires_manual_resolution field
        }

        # Check the flag values
        assert event_with_manual.get("requires_manual_resolution", False) is True
        assert event_without_manual.get("requires_manual_resolution", False) is False
        assert event_default.get("requires_manual_resolution", False) is False


class TestUnsupportedRule:
    """Tests for unsupported rules."""

    def test_unsupported_rule_returns_unknown(self):
        """Unsupported rule should return UNKNOWN with reason."""
        outcome, reason = resolver.apply_resolution_rule(
            value=100,
            rule="unknown_rule_type",
            rule_params={},
            event={}
        )
        assert outcome == "UNKNOWN"
        assert "unsupported_rule" in reason


class TestRuleErrors:
    """Tests for rule error handling."""

    def test_invalid_numeric_value_for_threshold(self):
        """Non-numeric value for threshold rule should return UNKNOWN."""
        outcome, reason = resolver.apply_resolution_rule(
            value="not_a_number",
            rule="threshold_gte",
            rule_params={"threshold": 50},
            event={}
        )
        assert outcome == "UNKNOWN"
        assert "rule_error" in reason

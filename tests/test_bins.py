"""
Tests for bins.py - bin validation and value-to-bin mapping.
"""

import pytest
from src.forecasting import bins


class TestBinValidation:
    """Tests for validate_bin_spec()"""

    def test_valid_bin_spec(self):
        """Valid bin spec with contiguous non-overlapping bins should pass."""
        spec = {
            "bins": [
                {"bin_id": "LOW", "label": "< 100", "min": None, "max": 100, "include_min": False, "include_max": False},
                {"bin_id": "MEDIUM", "label": "100-200", "min": 100, "max": 200, "include_min": True, "include_max": False},
                {"bin_id": "HIGH", "label": ">= 200", "min": 200, "max": None, "include_min": True, "include_max": True},
            ]
        }
        errors = bins.validate_bin_spec(spec)
        assert errors == []

    def test_overlapping_bins_rejected(self):
        """Overlapping bins should be rejected."""
        spec = {
            "bins": [
                {"bin_id": "LOW", "label": "< 150", "min": None, "max": 150, "include_min": False, "include_max": True},
                {"bin_id": "HIGH", "label": ">= 100", "min": 100, "max": None, "include_min": True, "include_max": True},
            ]
        }
        errors = bins.validate_bin_spec(spec)
        assert any("overlap" in e.lower() for e in errors)

    def test_gap_in_bins_rejected(self):
        """Gaps between bins should be rejected."""
        spec = {
            "bins": [
                {"bin_id": "LOW", "label": "< 100", "min": None, "max": 100, "include_min": False, "include_max": False},
                {"bin_id": "HIGH", "label": "> 200", "min": 200, "max": None, "include_min": False, "include_max": True},
            ]
        }
        errors = bins.validate_bin_spec(spec)
        assert any("gap" in e.lower() for e in errors)

    def test_single_bin_rejected(self):
        """Single bin should be rejected (minimum 2 bins required)."""
        spec = {
            "bins": [
                {"bin_id": "ONLY", "label": "All values", "min": None, "max": None, "include_min": True, "include_max": True},
            ]
        }
        errors = bins.validate_bin_spec(spec)
        assert any("at least 2" in e.lower() for e in errors)

    def test_missing_bins_array(self):
        """Missing bins array should be rejected."""
        spec = {}
        errors = bins.validate_bin_spec(spec)
        assert any("bins" in e.lower() for e in errors)

    def test_duplicate_bin_ids_rejected(self):
        """Duplicate bin IDs should be rejected."""
        spec = {
            "bins": [
                {"bin_id": "LOW", "label": "< 100", "min": None, "max": 100, "include_min": False, "include_max": False},
                {"bin_id": "LOW", "label": ">= 100", "min": 100, "max": None, "include_min": True, "include_max": True},
            ]
        }
        errors = bins.validate_bin_spec(spec)
        assert any("duplicate" in e.lower() for e in errors)


class TestValueToBin:
    """Tests for value_to_bin()"""

    @pytest.fixture
    def fx_bin_spec(self):
        """FX rate bin specification from the catalog."""
        return {
            "bins": [
                {"bin_id": "FX_LT_800K", "label": "< 800k", "min": None, "max": 800000, "include_min": False, "include_max": False},
                {"bin_id": "FX_800K_1M", "label": "800k-1.0m", "min": 800000, "max": 1000000, "include_min": True, "include_max": False},
                {"bin_id": "FX_1M_1_2M", "label": "1.0m-1.2m", "min": 1000000, "max": 1200000, "include_min": True, "include_max": False},
                {"bin_id": "FX_GE_1_2M", "label": ">= 1.2m", "min": 1200000, "max": None, "include_min": True, "include_max": True},
            ]
        }

    def test_value_in_middle_of_bin(self, fx_bin_spec):
        """Value in the middle of a bin should map correctly."""
        bin_id, reason = bins.value_to_bin(500000, fx_bin_spec)
        assert bin_id == "FX_LT_800K"
        assert reason is None

        bin_id, reason = bins.value_to_bin(900000, fx_bin_spec)
        assert bin_id == "FX_800K_1M"
        assert reason is None

        bin_id, reason = bins.value_to_bin(1100000, fx_bin_spec)
        assert bin_id == "FX_1M_1_2M"
        assert reason is None

        bin_id, reason = bins.value_to_bin(1500000, fx_bin_spec)
        assert bin_id == "FX_GE_1_2M"
        assert reason is None

    def test_value_at_lower_boundary_included(self, fx_bin_spec):
        """Value at boundary with include_min=True should be in that bin."""
        # 800000 has include_min=True for FX_800K_1M
        bin_id, reason = bins.value_to_bin(800000, fx_bin_spec)
        assert bin_id == "FX_800K_1M"
        assert reason is None

    def test_value_at_lower_boundary_excluded(self):
        """Value at boundary with include_min=False should not be in that bin."""
        spec = {
            "bins": [
                {"bin_id": "LOW", "label": "< 100", "min": None, "max": 100, "include_min": False, "include_max": True},
                {"bin_id": "HIGH", "label": "> 100", "min": 100, "max": None, "include_min": False, "include_max": True},
            ]
        }
        # Value 100 should go to LOW (include_max=True), not HIGH (include_min=False)
        bin_id, reason = bins.value_to_bin(100, spec)
        assert bin_id == "LOW"
        assert reason is None

    def test_value_at_upper_boundary_included(self):
        """Value at boundary with include_max=True should be in that bin."""
        spec = {
            "bins": [
                {"bin_id": "LOW", "label": "<= 100", "min": None, "max": 100, "include_min": False, "include_max": True},
                {"bin_id": "HIGH", "label": "> 100", "min": 100, "max": None, "include_min": False, "include_max": True},
            ]
        }
        bin_id, reason = bins.value_to_bin(100, spec)
        assert bin_id == "LOW"
        assert reason is None

    def test_value_at_upper_boundary_excluded(self, fx_bin_spec):
        """Value at boundary with include_max=False should go to next bin."""
        # 1000000 has include_max=False for FX_800K_1M, should go to FX_1M_1_2M
        bin_id, reason = bins.value_to_bin(1000000, fx_bin_spec)
        assert bin_id == "FX_1M_1_2M"
        assert reason is None

    def test_none_value_returns_unknown(self, fx_bin_spec):
        """None value should return UNKNOWN with missing_value reason."""
        bin_id, reason = bins.value_to_bin(None, fx_bin_spec)
        assert bin_id == "UNKNOWN"
        assert reason == "missing_value"

    def test_out_of_range_returns_unknown(self):
        """Value out of range with no overflow bin should return UNKNOWN."""
        spec = {
            "bins": [
                {"bin_id": "ONLY", "label": "50-100", "min": 50, "max": 100, "include_min": True, "include_max": False},
                {"bin_id": "ONLY2", "label": "100-150", "min": 100, "max": 150, "include_min": True, "include_max": True},
            ]
        }
        # Value below all bins
        bin_id, reason = bins.value_to_bin(25, spec)
        assert bin_id == "UNKNOWN"
        assert reason == "out_of_range"

        # Value above all bins
        bin_id, reason = bins.value_to_bin(200, spec)
        assert bin_id == "UNKNOWN"
        assert reason == "out_of_range"

    def test_underflow_bin_catches_low_values(self):
        """Bin with min=None should catch all low values."""
        spec = {
            "bins": [
                {"bin_id": "UNDERFLOW", "label": "< 100", "min": None, "max": 100, "include_min": False, "include_max": False},
                {"bin_id": "NORMAL", "label": ">= 100", "min": 100, "max": None, "include_min": True, "include_max": True},
            ]
        }
        bin_id, reason = bins.value_to_bin(-1000000, spec)
        assert bin_id == "UNDERFLOW"
        assert reason is None

    def test_overflow_bin_catches_high_values(self, fx_bin_spec):
        """Bin with max=None should catch all high values."""
        bin_id, reason = bins.value_to_bin(10000000, fx_bin_spec)
        assert bin_id == "FX_GE_1_2M"
        assert reason is None

    def test_invalid_numeric_value(self, fx_bin_spec):
        """Non-numeric value should return UNKNOWN."""
        bin_id, reason = bins.value_to_bin("not_a_number", fx_bin_spec)
        assert bin_id == "UNKNOWN"
        assert reason == "invalid_numeric_value"

    def test_string_numeric_value(self, fx_bin_spec):
        """String representation of number should be converted."""
        bin_id, reason = bins.value_to_bin("900000", fx_bin_spec)
        assert bin_id == "FX_800K_1M"
        assert reason is None


class TestBinHelpers:
    """Tests for helper functions."""

    def test_get_bin_ids(self):
        """get_bin_ids should return list of bin IDs in order."""
        spec = {
            "bins": [
                {"bin_id": "A", "label": "A"},
                {"bin_id": "B", "label": "B"},
                {"bin_id": "C", "label": "C"},
            ]
        }
        assert bins.get_bin_ids(spec) == ["A", "B", "C"]

    def test_get_bin_by_id(self):
        """get_bin_by_id should return the correct bin definition."""
        spec = {
            "bins": [
                {"bin_id": "A", "label": "Label A", "min": None, "max": 100},
                {"bin_id": "B", "label": "Label B", "min": 100, "max": None},
            ]
        }
        bin_def = bins.get_bin_by_id(spec, "A")
        assert bin_def["label"] == "Label A"

        bin_def = bins.get_bin_by_id(spec, "B")
        assert bin_def["label"] == "Label B"

        bin_def = bins.get_bin_by_id(spec, "C")
        assert bin_def is None


class TestBinsHaveOverlap:
    """Tests for bins_have_overlap()"""

    def test_no_overlap(self):
        """Non-overlapping bins should return False."""
        spec = {
            "bins": [
                {"bin_id": "A", "min": None, "max": 100, "include_min": True, "include_max": False},
                {"bin_id": "B", "min": 100, "max": None, "include_min": True, "include_max": True},
            ]
        }
        assert bins.bins_have_overlap(spec) is False

    def test_overlap_at_boundary_both_inclusive(self):
        """Bins overlapping at boundary (both inclusive) should return True."""
        spec = {
            "bins": [
                {"bin_id": "A", "min": None, "max": 100, "include_min": True, "include_max": True},
                {"bin_id": "B", "min": 100, "max": None, "include_min": True, "include_max": True},
            ]
        }
        assert bins.bins_have_overlap(spec) is True

    def test_no_overlap_at_boundary_exclusive(self):
        """Bins touching at boundary (one exclusive) should return False."""
        spec = {
            "bins": [
                {"bin_id": "A", "min": None, "max": 100, "include_min": True, "include_max": False},
                {"bin_id": "B", "min": 100, "max": None, "include_min": True, "include_max": True},
            ]
        }
        assert bins.bins_have_overlap(spec) is False


class TestBinsHaveGaps:
    """Tests for bins_have_gaps()"""

    def test_no_gaps(self):
        """Contiguous bins should return False."""
        spec = {
            "bins": [
                {"bin_id": "A", "min": None, "max": 100, "include_min": True, "include_max": False},
                {"bin_id": "B", "min": 100, "max": 200, "include_min": True, "include_max": False},
                {"bin_id": "C", "min": 200, "max": None, "include_min": True, "include_max": True},
            ]
        }
        assert bins.bins_have_gaps(spec) is False

    def test_gap_between_bins(self):
        """Non-contiguous bins should return True."""
        spec = {
            "bins": [
                {"bin_id": "A", "min": None, "max": 100, "include_min": True, "include_max": True},
                {"bin_id": "B", "min": 200, "max": None, "include_min": True, "include_max": True},
            ]
        }
        assert bins.bins_have_gaps(spec) is True

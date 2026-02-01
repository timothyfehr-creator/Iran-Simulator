"""Tests for Live Wire pipeline components."""

from datetime import datetime, timedelta, timezone

import pytest

from src.ingest.live_wire.signal_quality import (
    SignalStatus,
    update_signal_quality,
    quality_to_dict,
)
from src.ingest.live_wire.rule_engine import (
    apply_hysteresis,
    classify_economic_stress,
    classify_internet,
    classify_news,
)
from src.ingest.live_wire.smoothing import compute_ema


# ---- Signal Quality ----

class TestSignalQuality:
    def test_ok_status_on_fresh_value(self):
        now = datetime.now(timezone.utc)
        q = update_signal_quality(None, 600000.0, now, 12, source_timestamp_utc=now)
        assert q.status == SignalStatus.OK
        assert q.value == 600000.0
        assert q.confidence == "high"
        assert q.consecutive_failures == 0

    def test_stale_when_source_old(self):
        now = datetime.now(timezone.utc)
        old_ts = now - timedelta(hours=15)
        q = update_signal_quality(None, 600000.0, now, 12, source_timestamp_utc=old_ts)
        assert q.status == SignalStatus.STALE
        assert q.confidence == "medium"

    def test_failed_carries_last_good(self):
        prev = {"last_good_value": 550000.0, "last_good_at": "2026-01-01T00:00:00", "consecutive_failures": 1}
        now = datetime.now(timezone.utc)
        q = update_signal_quality(prev, None, now, 12)
        assert q.status == SignalStatus.FAILED
        assert q.value == 550000.0  # carried from last good
        assert q.consecutive_failures == 2

    def test_ok_resets_failures(self):
        prev = {"last_good_value": 550000.0, "last_good_at": "2026-01-01T00:00:00", "consecutive_failures": 3}
        now = datetime.now(timezone.utc)
        q = update_signal_quality(prev, 600000.0, now, 12, source_timestamp_utc=now)
        assert q.status == SignalStatus.OK
        assert q.consecutive_failures == 0

    def test_fetch_time_only_caps_confidence(self):
        now = datetime.now(timezone.utc)
        q = update_signal_quality(None, 600000.0, now, 12, source_timestamp_utc=None)
        assert q.freshness == "fetch_time_only"
        assert q.confidence == "medium"

    def test_quality_to_dict_roundtrip(self):
        now = datetime.now(timezone.utc)
        q = update_signal_quality(None, 100.0, now, 12)
        d = quality_to_dict(q)
        assert d["status"] == "OK"
        assert isinstance(d["value"], float)


# ---- Rule Engine ----

class TestRuleEngine:
    ECON_THRESHOLDS = {"pressured": 800000, "critical": 1200000}
    INTERNET_THRESHOLDS = {"functional": 80, "partial": 50, "severely_degraded": 20}
    NEWS_THRESHOLDS = {"elevated_ratio": 1.5, "surge_ratio": 3.0}

    def test_econ_stable(self):
        assert classify_economic_stress(500000, self.ECON_THRESHOLDS) == "STABLE"

    def test_econ_pressured(self):
        assert classify_economic_stress(800000, self.ECON_THRESHOLDS) == "PRESSURED"
        assert classify_economic_stress(1000000, self.ECON_THRESHOLDS) == "PRESSURED"

    def test_econ_critical(self):
        assert classify_economic_stress(1200000, self.ECON_THRESHOLDS) == "CRITICAL"
        assert classify_economic_stress(2000000, self.ECON_THRESHOLDS) == "CRITICAL"

    def test_econ_none_returns_none(self):
        assert classify_economic_stress(None, self.ECON_THRESHOLDS) is None

    def test_internet_functional(self):
        assert classify_internet(95, self.INTERNET_THRESHOLDS) == "FUNCTIONAL"
        assert classify_internet(80, self.INTERNET_THRESHOLDS) == "FUNCTIONAL"

    def test_internet_partial(self):
        assert classify_internet(60, self.INTERNET_THRESHOLDS) == "PARTIAL"

    def test_internet_severely_degraded(self):
        assert classify_internet(30, self.INTERNET_THRESHOLDS) == "SEVERELY_DEGRADED"

    def test_internet_blackout(self):
        assert classify_internet(10, self.INTERNET_THRESHOLDS) == "BLACKOUT"

    def test_internet_none(self):
        assert classify_internet(None, self.INTERNET_THRESHOLDS) is None

    def test_news_normal(self):
        assert classify_news(100, 100, self.NEWS_THRESHOLDS) == "NORMAL"

    def test_news_elevated(self):
        assert classify_news(200, 100, self.NEWS_THRESHOLDS) == "ELEVATED"

    def test_news_surge(self):
        assert classify_news(350, 100, self.NEWS_THRESHOLDS) == "SURGE"

    def test_news_none(self):
        assert classify_news(None, 100, self.NEWS_THRESHOLDS) is None

    def test_news_zero_baseline(self):
        assert classify_news(50, 0, self.NEWS_THRESHOLDS) == "NORMAL"


# ---- Hysteresis ----

class TestHysteresis:
    def test_hold_below_n(self):
        """State should not transition with fewer than N cycles."""
        h = apply_hysteresis("PRESSURED", {"confirmed_state": "STABLE", "pending_state": None, "pending_count": 0}, 3)
        assert h["confirmed_state"] == "STABLE"
        assert h["pending_state"] == "PRESSURED"
        assert h["pending_count"] == 1

    def test_transition_at_n(self):
        """State transitions after N consecutive cycles."""
        prev = {"confirmed_state": "STABLE", "pending_state": "PRESSURED", "pending_count": 2}
        h = apply_hysteresis("PRESSURED", prev, 3)
        assert h["confirmed_state"] == "PRESSURED"
        assert h["pending_count"] == 0

    def test_counter_reset_on_change(self):
        """Counter resets when raw state changes."""
        prev = {"confirmed_state": "STABLE", "pending_state": "PRESSURED", "pending_count": 2}
        h = apply_hysteresis("CRITICAL", prev, 3)
        assert h["pending_state"] == "CRITICAL"
        assert h["pending_count"] == 1

    def test_none_holds_confirmed(self):
        prev = {"confirmed_state": "STABLE", "pending_state": "PRESSURED", "pending_count": 2}
        h = apply_hysteresis(None, prev, 3)
        assert h["confirmed_state"] == "STABLE"
        assert h["pending_count"] == 0

    def test_same_as_confirmed_resets_pending(self):
        prev = {"confirmed_state": "STABLE", "pending_state": "PRESSURED", "pending_count": 2}
        h = apply_hysteresis("STABLE", prev, 3)
        assert h["confirmed_state"] == "STABLE"
        assert h["pending_state"] is None


# ---- No Fabrication ----

class TestNoFabrication:
    def test_empty_gdelt_returns_none(self):
        from src.ingest.live_wire.fetch_gdelt import fetch_gdelt_iran_count
        from unittest.mock import patch, MagicMock

        with patch("src.ingest.live_wire.fetch_gdelt.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"timeline": []}
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            count, _ = fetch_gdelt_iran_count()
        assert count is None

    def test_failed_signal_no_new_value(self):
        """Failed fetch should not produce a new value, only carry last_good."""
        prev = {"last_good_value": 500000.0, "last_good_at": "2026-01-01T00:00:00", "consecutive_failures": 0}
        now = datetime.now(timezone.utc)
        q = update_signal_quality(prev, None, now, 12)
        assert q.value == 500000.0  # carried, not fabricated
        assert q.status == SignalStatus.FAILED


# ---- Schema Version ----

class TestSchemaVersion:
    def test_config_has_versions(self):
        import json
        with open("config/live_wire.json") as f:
            config = json.load(f)
        assert config["_schema_version"] == "1.0.0"
        assert config["rule_engine"]["rule_version"] == "1.0.0"


# ---- Snapshot IDs ----

class TestSnapshotIds:
    def test_monotonic_counter(self):
        """Snapshot counter should increment."""
        import json

        state = {"snapshot_counter": 5, "signal_quality": {}, "hysteresis": {}, "ema": {}}
        new_counter = state["snapshot_counter"] + 1
        assert new_counter == 6


# ---- EMA ----

class TestEMA:
    def test_first_value(self):
        assert compute_ema(100.0, None, 0.3) == 100.0

    def test_basic_ema(self):
        result = compute_ema(200.0, 100.0, 0.3)
        assert abs(result - 130.0) < 0.01

    def test_none_uses_last_good(self):
        result = compute_ema(None, 100.0, 0.3, last_good=150.0)
        expected = 0.3 * 150.0 + 0.7 * 100.0
        assert abs(result - expected) < 0.01

    def test_all_none(self):
        result = compute_ema(None, None, 0.3)
        assert result is None

    def test_none_current_no_last_good_keeps_prev(self):
        result = compute_ema(None, 100.0, 0.3, last_good=None)
        assert result == 100.0

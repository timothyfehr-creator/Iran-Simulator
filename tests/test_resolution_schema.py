"""
Tests for resolution record schema validation.

Validates that new resolution fields (resolution_mode, reason_code,
evidence_refs, evidence_hashes) work correctly.
"""

import pytest
import json
import jsonschema
from pathlib import Path


SCHEMA_PATH = Path("config/schemas/resolution_record.schema.json")


@pytest.fixture
def resolution_schema():
    """Load the resolution record schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def test_schema_loads():
    """Test that schema file exists and loads."""
    assert SCHEMA_PATH.exists()
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    assert schema["title"] == "Resolution Record"


def test_resolution_mode_required(resolution_schema):
    """Test that resolution_mode is required."""
    assert "resolution_mode" in resolution_schema["required"]


def test_reason_code_required(resolution_schema):
    """Test that reason_code is required."""
    assert "reason_code" in resolution_schema["required"]


def test_resolution_mode_enum(resolution_schema):
    """Test resolution_mode enum values."""
    mode_schema = resolution_schema["properties"]["resolution_mode"]
    assert mode_schema["enum"] == ["external_auto", "external_manual", "claims_inferred"]


def test_evidence_refs_array(resolution_schema):
    """Test evidence_refs is an array of strings."""
    refs_schema = resolution_schema["properties"]["evidence_refs"]
    assert refs_schema["type"] == "array"
    assert refs_schema["items"]["type"] == "string"


def test_evidence_hashes_pattern(resolution_schema):
    """Test evidence_hashes has sha256 pattern."""
    hashes_schema = resolution_schema["properties"]["evidence_hashes"]
    assert hashes_schema["type"] == "array"
    assert "sha256:[a-f0-9]{64}" in hashes_schema["items"]["pattern"]


def test_valid_external_auto_resolution(resolution_schema):
    """Test valid external_auto resolution validates."""
    record = {
        "record_type": "resolution",
        "resolution_id": "res_20260120_econ.rial_ge_1_2m_7d",
        "forecast_id": "fcst_20260113_RUN_20260113_econ.rial_ge_1_2m_7d",
        "event_id": "econ.rial_ge_1_2m",
        "horizon_days": 7,
        "target_date_utc": "2026-01-20T00:00:00Z",
        "resolved_outcome": "YES",
        "resolved_value": 1500000,
        "resolved_at_utc": "2026-01-20T12:00:00Z",
        "resolved_by": "oracle_resolver_v2",
        "resolution_mode": "external_auto",
        "reason_code": "threshold_gte:1200000",
        "evidence_refs": ["forecasting/evidence/res_20260120_econ.rial_ge_1_2m_7d.json"],
        "evidence_hashes": ["sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"],
        "evidence": {
            "run_id": "RUN_20260120",
            "manifest_id": "sha256:1234",
            "path_used": "current_state.economic_conditions.rial_usd_rate.market",
            "rule_applied": "threshold_gte:1200000"
        }
    }
    jsonschema.validate(record, resolution_schema)


def test_valid_external_manual_resolution(resolution_schema):
    """Test valid external_manual resolution with adjudicator_id validates."""
    record = {
        "record_type": "resolution",
        "resolution_id": "res_20260120_event.security_defection_7d",
        "forecast_id": "fcst_20260113_RUN_20260113_event.security_defection_7d",
        "event_id": "event.security_defection",
        "horizon_days": 7,
        "target_date_utc": "2026-01-20T00:00:00Z",
        "resolved_outcome": "NO",
        "resolved_at_utc": "2026-01-20T12:00:00Z",
        "resolved_by": "oracle_resolver_v2",
        "resolution_mode": "external_manual",
        "adjudicator_id": "analyst_001",
        "reason_code": "manual_review",
        "evidence_refs": [],
        "evidence_hashes": [],
        "evidence": {
            "run_id": "RUN_20260120"
        }
    }
    jsonschema.validate(record, resolution_schema)


def test_external_manual_requires_adjudicator(resolution_schema):
    """Test that external_manual mode requires adjudicator_id."""
    record = {
        "record_type": "resolution",
        "resolution_id": "res_20260120_event.security_defection_7d",
        "forecast_id": "fcst_20260113_RUN_20260113_event.security_defection_7d",
        "event_id": "event.security_defection",
        "horizon_days": 7,
        "target_date_utc": "2026-01-20T00:00:00Z",
        "resolved_outcome": "NO",
        "resolved_at_utc": "2026-01-20T12:00:00Z",
        "resolved_by": "oracle_resolver_v2",
        "resolution_mode": "external_manual",
        "reason_code": "manual_review",
        "evidence_refs": [],
        "evidence_hashes": [],
        "evidence": {}
    }
    # This should fail validation due to missing adjudicator_id
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, resolution_schema)


def test_valid_claims_inferred_resolution(resolution_schema):
    """Test valid claims_inferred resolution validates."""
    record = {
        "record_type": "resolution",
        "resolution_id": "res_20260120_state.protests_escalating_7d",
        "forecast_id": "fcst_20260113_RUN_20260113_state.protests_escalating_7d",
        "event_id": "state.protests_escalating",
        "horizon_days": 7,
        "target_date_utc": "2026-01-20T00:00:00Z",
        "resolved_outcome": "UNKNOWN",
        "resolved_at_utc": "2026-01-20T12:00:00Z",
        "resolved_by": "oracle_resolver_v2",
        "resolution_mode": "claims_inferred",
        "reason_code": "missing_path",
        "evidence_refs": [],
        "evidence_hashes": [],
        "evidence": {},
        "unknown_reason": "missing_path"
    }
    jsonschema.validate(record, resolution_schema)


def test_invalid_resolution_mode_rejected(resolution_schema):
    """Test that invalid resolution_mode is rejected."""
    record = {
        "record_type": "resolution",
        "resolution_id": "res_20260120_econ.rial_ge_1_2m_7d",
        "forecast_id": "fcst_20260113_RUN_20260113_econ.rial_ge_1_2m_7d",
        "event_id": "econ.rial_ge_1_2m",
        "horizon_days": 7,
        "target_date_utc": "2026-01-20T00:00:00Z",
        "resolved_outcome": "YES",
        "resolved_at_utc": "2026-01-20T12:00:00Z",
        "resolved_by": "oracle_resolver_v2",
        "resolution_mode": "invalid_mode",  # Invalid
        "reason_code": "test",
        "evidence_refs": [],
        "evidence_hashes": [],
        "evidence": {}
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, resolution_schema)


def test_invalid_evidence_hash_pattern_rejected(resolution_schema):
    """Test that invalid evidence hash pattern is rejected."""
    record = {
        "record_type": "resolution",
        "resolution_id": "res_20260120_econ.rial_ge_1_2m_7d",
        "forecast_id": "fcst_20260113_RUN_20260113_econ.rial_ge_1_2m_7d",
        "event_id": "econ.rial_ge_1_2m",
        "horizon_days": 7,
        "target_date_utc": "2026-01-20T00:00:00Z",
        "resolved_outcome": "YES",
        "resolved_at_utc": "2026-01-20T12:00:00Z",
        "resolved_by": "oracle_resolver_v2",
        "resolution_mode": "external_auto",
        "reason_code": "test",
        "evidence_refs": [],
        "evidence_hashes": ["invalid_hash"],  # Should be sha256:...
        "evidence": {}
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, resolution_schema)

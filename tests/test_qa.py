"""Tests for src/pipeline/qa.py and STRICT_QA soft-fail behavior."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pipeline.qa import qa_compiled_intel


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_compiled(claims=None, schema_version="0.1.0"):
    """Build a minimal compiled_intel dict."""
    return {
        "_schema_version": schema_version,
        "claims_ledger": {
            "claims": claims or []
        },
    }


VALID_CLAIM = {
    "claim_id": "CLM_TEST_0001",
    "path": "current_state.casualties.protesters.killed.mid",
    "value": 5,
    "source_grade": "B2",
    "confidence": "MEDIUM",
}

NULL_CLAIM_WITH_REASON = {
    "claim_id": "CLM_TEST_0002",
    "path": "current_state.casualties.protesters.killed.mid",
    "value": None,
    "null_reason": "CONFLICT: 2 claims with same source_grade",
    "source_grade": "B2",
    "confidence": "MEDIUM",
}

NULL_CLAIM_NO_REASON = {
    "claim_id": "CLM_TEST_0003",
    "path": "current_state.casualties.protesters.killed.mid",
    "value": None,
    "source_grade": "B2",
    "confidence": "MEDIUM",
}


# ---------------------------------------------------------------------------
# Tests for qa_compiled_intel
# ---------------------------------------------------------------------------

class TestQACompiledIntel:
    def test_valid_intel_returns_ok(self):
        compiled = _make_compiled([VALID_CLAIM])
        result = qa_compiled_intel(compiled)
        assert result["status"] == "OK"
        assert result["errors"] == []

    def test_missing_schema_version(self):
        compiled = _make_compiled([VALID_CLAIM])
        del compiled["_schema_version"]
        result = qa_compiled_intel(compiled)
        assert result["status"] == "FAIL"
        assert any("_schema_version" in e for e in result["errors"])

    def test_empty_claims_ledger(self):
        compiled = _make_compiled([])
        result = qa_compiled_intel(compiled)
        assert result["status"] == "FAIL"
        assert any("claims_ledger.claims" in e for e in result["errors"])

    def test_duplicate_claim_id(self):
        claim1 = dict(VALID_CLAIM)
        claim2 = dict(VALID_CLAIM)  # same claim_id
        compiled = _make_compiled([claim1, claim2])
        result = qa_compiled_intel(compiled)
        assert result["status"] == "FAIL"
        assert any("Duplicate" in e for e in result["errors"])

    def test_null_value_with_reason_ok(self):
        compiled = _make_compiled([NULL_CLAIM_WITH_REASON])
        result = qa_compiled_intel(compiled)
        assert result["status"] == "OK"

    def test_null_value_without_reason_fails(self):
        compiled = _make_compiled([NULL_CLAIM_NO_REASON])
        result = qa_compiled_intel(compiled)
        assert result["status"] == "FAIL"
        assert any("null value" in e for e in result["errors"])

    def test_missing_claim_id(self):
        claim = {"path": "test.path", "value": 1}
        compiled = _make_compiled([claim])
        result = qa_compiled_intel(compiled)
        assert result["status"] == "FAIL"
        assert any("missing claim_id" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# Tests for STRICT_QA exit(2) behavior
# ---------------------------------------------------------------------------

class TestStrictQASoftFail:
    """Test that compile_intel_v2 exits with code 2 under STRICT_QA=1 when QA fails."""

    def test_strict_qa_writes_report_then_exits_2(self):
        """Under STRICT_QA=1 with malformed intel, qa_report.json should be written
        and the process should exit with code 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a minimal claims file with a bad claim (null value, no reason)
            claims_path = os.path.join(tmpdir, "claims_deep_research.jsonl")
            bad_claim = {
                "claim_id": "CLM_BAD_0001",
                "path": "current_state.casualties.protesters.killed.mid",
                "value": None,
                # Missing null_reason — this should trigger QA FAIL
            }
            with open(claims_path, "w") as f:
                f.write(json.dumps(bad_claim) + "\n")

            # Create a minimal template
            template_path = os.path.join(tmpdir, "template.json")
            with open(template_path, "w") as f:
                json.dump({"_schema_version": "0.1.0"}, f)

            # Run compile_intel_v2 with STRICT_QA=1
            env = os.environ.copy()
            env["STRICT_QA"] = "1"

            result = subprocess.run(
                [
                    sys.executable, "-m", "src.pipeline.compile_intel_v2",
                    "--claims", claims_path,
                    "--template", template_path,
                    "--outdir", tmpdir,
                ],
                capture_output=True,
                text=True,
                env=env,
                cwd=str(Path(__file__).resolve().parent.parent),
            )

            # Should exit with code 2 (soft fail)
            assert result.returncode == 2, f"Expected exit 2, got {result.returncode}. stderr: {result.stderr}"

            # qa_report.json should exist (written BEFORE exit)
            qa_report_path = os.path.join(tmpdir, "qa_report.json")
            assert os.path.exists(qa_report_path), "qa_report.json should be written before exit(2)"

            with open(qa_report_path, "r") as f:
                qa = json.load(f)
            assert qa["status"] == "FAIL"


# ---------------------------------------------------------------------------
# Tests for validate_econ_priors (Sprint 2)
# ---------------------------------------------------------------------------

# Import from daily_update — safe because function is defined before main()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from daily_update import validate_econ_priors


def _write_priors(tmpdir, data):
    """Write a priors JSON file and return its path."""
    path = os.path.join(tmpdir, "priors.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path


class TestValidateEconPriors:
    """Tests for the pre-simulation economic priors gate."""

    VALID_PRIORS = {
        "economic_thresholds": {
            "rial_critical_threshold": 1200000,
            "rial_pressured_threshold": 800000,
            "inflation_critical_threshold": 50,
            "inflation_pressured_threshold": 30,
        },
        "economic_modifiers": {
            "critical_protest_escalation_multiplier": 1.20,
        },
    }

    def test_valid_priors_ok(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = _write_priors(tmpdir, self.VALID_PRIORS)
            status, errors = validate_econ_priors(path)
            assert status == "OK"
            assert errors == []

    def test_missing_thresholds_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = dict(self.VALID_PRIORS)
            del data["economic_thresholds"]
            path = _write_priors(tmpdir, data)
            status, errors = validate_econ_priors(path)
            assert status == "FAIL"
            assert any("economic_thresholds" in e for e in errors)

    def test_missing_modifiers_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = dict(self.VALID_PRIORS)
            del data["economic_modifiers"]
            path = _write_priors(tmpdir, data)
            status, errors = validate_econ_priors(path)
            assert status == "FAIL"
            assert any("economic_modifiers" in e for e in errors)

    def test_missing_sub_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = json.loads(json.dumps(self.VALID_PRIORS))
            del data["economic_thresholds"]["rial_critical_threshold"]
            path = _write_priors(tmpdir, data)
            status, errors = validate_econ_priors(path)
            assert status == "FAIL"
            assert any("rial_critical_threshold" in e for e in errors)

    def test_non_numeric_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = json.loads(json.dumps(self.VALID_PRIORS))
            data["economic_thresholds"]["rial_critical_threshold"] = "not_a_number"
            path = _write_priors(tmpdir, data)
            status, errors = validate_econ_priors(path)
            assert status == "FAIL"
            assert any("not numeric" in e for e in errors)

    def test_inverted_thresholds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data = json.loads(json.dumps(self.VALID_PRIORS))
            # Swap pressured > critical
            data["economic_thresholds"]["rial_pressured_threshold"] = 2000000
            data["economic_thresholds"]["rial_critical_threshold"] = 800000
            path = _write_priors(tmpdir, data)
            status, errors = validate_econ_priors(path)
            assert status == "FAIL"
            assert any("must be <" in e for e in errors)

    def test_missing_file(self):
        status, errors = validate_econ_priors("/nonexistent/path.json")
        assert status == "FAIL"
        assert any("Could not read" in e for e in errors)

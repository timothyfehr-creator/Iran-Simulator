"""
Tests for claims pipeline resilience fixes:
- Incremental JSONL writes in extract_claims
- Lenient per-claim validation in validate_candidate_claims
- Partial claims file handling in bundle creation
"""

import json
import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from src.pipeline.import_deep_research_bundle_v3 import validate_candidate_claims


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_claim(claim_id="CLM_001", path="current_state.casualties.protesters.killed.mid",
                value=100, units="people", claim_class="HARD_FACT",
                as_of_utc="2026-01-10T00:00:00Z", source_grade="B2",
                source_doc_refs=None, **overrides):
    """Build a minimal valid claim dict."""
    claim = {
        "claim_id": claim_id,
        "path": path,
        "value": value,
        "units": units,
        "claim_class": claim_class,
        "as_of_utc": as_of_utc,
        "source_grade": source_grade,
        "source_doc_refs": source_doc_refs or [{"doc_id": "DOC_001", "quote": "x"}],
        "confidence": "MEDIUM",
        "triangulated": False,
    }
    claim.update(overrides)
    return claim


def _mock_registry():
    """Return a mock PathRegistry that accepts known test paths."""
    registry = MagicMock()
    valid_paths = {
        "current_state.casualties.protesters.killed.mid",
        "current_state.economic_conditions.rial_usd_rate.market",
        "current_state.information_environment.internet_status.current",
        "current_state.protest_metrics.current_snapshot.intensity_trend",
    }
    registry.is_valid_path.side_effect = lambda p: p in valid_paths
    registry.get_path_info.return_value = {"units": "people"}
    registry.validate_claim_path.side_effect = lambda c: (dict(c), [])
    return registry


# ---------------------------------------------------------------------------
# Test: all-dropped yields empty set + warning (finding 1)
# ---------------------------------------------------------------------------

class TestAllClaimsDropped:
    """When every claim is invalid, return empty list — don't raise."""

    @patch("src.pipeline.import_deep_research_bundle_v3.load_v2_registry")
    def test_all_invalid_returns_empty(self, mock_load):
        mock_load.return_value = _mock_registry()

        bad_claims = [
            _make_claim(claim_id="C1", path="bogus.path"),
            _make_claim(claim_id="C2", path="also.bogus"),
        ]

        normalized, warnings = validate_candidate_claims(
            bad_claims, valid_doc_ids={"DOC_001"}
        )

        assert normalized == []
        dropped = [w for w in warnings if w.get("type") == "dropped_claim"]
        assert len(dropped) == 2

    @patch("src.pipeline.import_deep_research_bundle_v3.load_v2_registry")
    def test_single_bad_claim_does_not_kill_batch(self, mock_load):
        mock_load.return_value = _mock_registry()

        claims = [
            _make_claim(claim_id="GOOD_1"),
            _make_claim(claim_id="BAD_1", path="bogus.path"),
            _make_claim(claim_id="GOOD_2"),
        ]

        normalized, warnings = validate_candidate_claims(
            claims, valid_doc_ids={"DOC_001"}
        )

        ids = [c["claim_id"] for c in normalized]
        assert "GOOD_1" in ids
        assert "GOOD_2" in ids
        assert "BAD_1" not in ids
        dropped = [w for w in warnings if w.get("type") == "dropped_claim"]
        assert len(dropped) == 1


# ---------------------------------------------------------------------------
# Test: warnings schema (finding 4)
# ---------------------------------------------------------------------------

class TestWarningsSchema:
    """Warnings for dropped claims must contain type, claim_id, reason."""

    @patch("src.pipeline.import_deep_research_bundle_v3.load_v2_registry")
    def test_dropped_claim_warning_has_required_keys(self, mock_load):
        mock_load.return_value = _mock_registry()

        claims = [_make_claim(claim_id="C1", path="bogus.path")]

        _, warnings = validate_candidate_claims(
            claims, valid_doc_ids={"DOC_001"}
        )

        dropped = [w for w in warnings if w.get("type") == "dropped_claim"]
        assert len(dropped) == 1
        w = dropped[0]
        assert "type" in w
        assert "claim_id" in w
        assert "reason" in w

    @patch("src.pipeline.import_deep_research_bundle_v3.load_v2_registry")
    def test_missing_fields_warning(self, mock_load):
        mock_load.return_value = _mock_registry()

        claim = _make_claim(claim_id="C1")
        del claim["as_of_utc"]  # remove required field

        _, warnings = validate_candidate_claims(
            [claim], valid_doc_ids={"DOC_001"}
        )

        dropped = [w for w in warnings if w.get("type") == "dropped_claim"]
        assert len(dropped) == 1
        assert "missing required fields" in dropped[0]["reason"]

    @patch("src.pipeline.import_deep_research_bundle_v3.load_v2_registry")
    def test_wrong_units_warning(self, mock_load):
        reg = _mock_registry()
        reg.get_path_info.return_value = {"units": "people"}
        mock_load.return_value = reg

        claim = _make_claim(claim_id="C1", units="kg")

        _, warnings = validate_candidate_claims(
            [claim], valid_doc_ids={"DOC_001"}
        )

        dropped = [w for w in warnings if w.get("type") == "dropped_claim"]
        assert len(dropped) == 1
        assert "units" in dropped[0]["reason"]

    @patch("src.pipeline.import_deep_research_bundle_v3.load_v2_registry")
    def test_unknown_claim_class_warning(self, mock_load):
        mock_load.return_value = _mock_registry()

        claim = _make_claim(claim_id="C1", claim_class="TOTALLY_MADE_UP")

        _, warnings = validate_candidate_claims(
            [claim], valid_doc_ids={"DOC_001"}
        )

        dropped = [w for w in warnings if w.get("type") == "dropped_claim"]
        assert len(dropped) == 1
        assert "claim_class" in dropped[0]["reason"]

    @patch("src.pipeline.import_deep_research_bundle_v3.load_v2_registry")
    def test_duplicate_claim_id_dropped(self, mock_load):
        mock_load.return_value = _mock_registry()

        claims = [
            _make_claim(claim_id="DUP"),
            _make_claim(claim_id="DUP"),
        ]

        normalized, warnings = validate_candidate_claims(
            claims, valid_doc_ids={"DOC_001"}
        )

        assert len(normalized) == 1
        dropped = [w for w in warnings if w.get("type") == "dropped_claim"]
        assert len(dropped) == 1
        assert "duplicate" in dropped[0]["reason"]


# ---------------------------------------------------------------------------
# Test: partial JSONL — truncated last line (finding 2)
# ---------------------------------------------------------------------------

class TestPartialJsonlHandling:
    """Bundle creation should skip malformed trailing lines."""

    def test_truncated_last_line_skipped(self):
        from scripts.daily_update import create_bundle_from_ingest

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write evidence_docs.jsonl
            evidence_path = os.path.join(tmpdir, "evidence_docs.jsonl")
            with open(evidence_path, "w") as f:
                f.write(json.dumps({"doc_id": "D1", "title": "t"}) + "\n")

            # Write claims with a truncated last line
            claims_path = os.path.join(tmpdir, "claims_extracted.jsonl")
            good_claim = {"claim_id": "C1", "path": "p", "value": 1}
            with open(claims_path, "w") as f:
                f.write(json.dumps(good_claim) + "\n")
                f.write('{"claim_id": "C2", "trunc')  # truncated

            bundle_path = create_bundle_from_ingest(
                tmpdir, "2026-01-10T00:00:00Z", claims_path, claims_partial=True
            )

            with open(bundle_path) as f:
                bundle = json.load(f)

            assert len(bundle["candidate_claims"]) == 1
            assert bundle["candidate_claims"][0]["claim_id"] == "C1"
            assert bundle["run_manifest"]["claims_partial"] is True

    def test_clean_file_no_partial_flag(self):
        from scripts.daily_update import create_bundle_from_ingest

        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_path = os.path.join(tmpdir, "evidence_docs.jsonl")
            with open(evidence_path, "w") as f:
                f.write(json.dumps({"doc_id": "D1", "title": "t"}) + "\n")

            claims_path = os.path.join(tmpdir, "claims_extracted.jsonl")
            with open(claims_path, "w") as f:
                f.write(json.dumps({"claim_id": "C1"}) + "\n")

            bundle_path = create_bundle_from_ingest(
                tmpdir, "2026-01-10T00:00:00Z", claims_path
            )

            with open(bundle_path) as f:
                bundle = json.load(f)

            assert bundle["run_manifest"]["claims_partial"] is False


# ---------------------------------------------------------------------------
# Test: incremental write in extract_claims (finding 2)
# ---------------------------------------------------------------------------

class TestIncrementalExtraction:
    """Claims from earlier docs survive even if a later doc crashes."""

    @patch("src.ingest.extract_claims.ClaimExtractor.extract_from_doc")
    def test_partial_write_on_crash(self, mock_extract):
        from src.ingest.extract_claims import ClaimExtractor

        # First doc returns claims, second doc raises
        mock_extract.side_effect = [
            [{"claim_id": "C1", "value": 1}],
            Exception("GPT blew up"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            evidence_path = os.path.join(tmpdir, "evidence.jsonl")
            output_path = os.path.join(tmpdir, "claims.jsonl")

            with open(evidence_path, "w") as f:
                f.write(json.dumps({"doc_id": "D1"}) + "\n")
                f.write(json.dumps({"doc_id": "D2"}) + "\n")

            extractor = ClaimExtractor.__new__(ClaimExtractor)

            with pytest.raises(Exception, match="GPT blew up"):
                extractor.extract_from_jsonl(evidence_path, output_path)

            # First doc's claims should have been flushed to disk
            assert os.path.exists(output_path)
            with open(output_path) as f:
                lines = [l for l in f if l.strip()]
            assert len(lines) == 1
            assert json.loads(lines[0])["claim_id"] == "C1"

"""Tests for src/ingest/extract_claims.py."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ingest.extract_claims import ClaimExtractor, normalize_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_EVIDENCE_DOC = {
    "doc_id": "ISW_20260112_1234_abcdef01",
    "source_id": "SRC_ISW",
    "organization": "ISW",
    "title": "Iran Update - January 12 2026",
    "url": "https://understandingwar.org/iran-update-january-12-2026",
    "published_at_utc": "2026-01-12T00:00:00+00:00",
    "raw_text": "Protests continued in Tehran with security forces deployed. 5 killed, 200 detained.",
    "language": "en",
}

MOCK_GPT_RESPONSE = json.dumps({
    "claims": [
        {
            "claim_id": "CLM_20260112_0001",
            "claim_class": "HARD_FACT",
            "path": "current_state.casualties.protesters.killed.mid",
            "value": 5,
            "units": "people",
            "as_of_utc": "2026-01-12T00:00:00Z",
            "source_doc_refs": [{"doc_id": "ISW_20260112_1234_abcdef01", "quote": "5 killed"}],
            "source_grade": "B2",
            "confidence": "MEDIUM",
            "triangulated": False,
            "notes": "Reported by ISW",
        },
        {
            "claim_id": "CLM_20260112_0002",
            "claim_class": "HARD_FACT",
            "path": "current_state.casualties.protesters.detained.estimate",
            "value": 200,
            "units": "people",
            "as_of_utc": "2026-01-12T00:00:00Z",
            "source_doc_refs": [{"doc_id": "ISW_20260112_1234_abcdef01", "quote": "200 detained"}],
            "source_grade": "B2",
            "confidence": "MEDIUM",
            "triangulated": False,
            "notes": "Reported by ISW",
        },
    ]
})


def _mock_completion(content: str):
    """Create a mock OpenAI ChatCompletion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    return mock_response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestNormalizePath:
    def test_known_alias(self):
        # "deaths" should alias to a canonical path if registry exists
        result = normalize_path("current_state.casualties.protesters.killed.mid")
        assert result == "current_state.casualties.protesters.killed.mid"

    def test_unknown_path_passthrough(self):
        assert normalize_path("nonexistent.path") == "nonexistent.path"


class TestClaimExtractor:
    @patch("src.ingest.extract_claims.OpenAI")
    def test_extract_from_doc_success(self, MockOpenAI):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_completion(MOCK_GPT_RESPONSE)
        MockOpenAI.return_value = mock_client

        extractor = ClaimExtractor(api_key="test-key")
        extractor.client = mock_client

        claims = extractor.extract_from_doc(SAMPLE_EVIDENCE_DOC)

        assert len(claims) == 2
        # claim_ids should be regenerated with doc hash
        assert claims[0]["claim_id"].startswith("CLM_")
        assert claims[0]["value"] == 5
        assert claims[1]["value"] == 200

    @patch("src.ingest.extract_claims.OpenAI")
    def test_extract_from_doc_api_error_retries(self, MockOpenAI):
        """API errors should be retried up to 3 times and logged."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        MockOpenAI.return_value = mock_client

        extractor = ClaimExtractor(api_key="test-key")
        extractor.client = mock_client

        claims = extractor.extract_from_doc(SAMPLE_EVIDENCE_DOC)

        assert claims == []
        assert mock_client.chat.completions.create.call_count == 3

    @patch("src.ingest.extract_claims.OpenAI")
    def test_extract_from_doc_empty_claims(self, MockOpenAI):
        """GPT returning 0 claims should return empty list."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_completion('{"claims": []}')
        MockOpenAI.return_value = mock_client

        extractor = ClaimExtractor(api_key="test-key")
        extractor.client = mock_client

        claims = extractor.extract_from_doc(SAMPLE_EVIDENCE_DOC)
        assert claims == []

    @patch("src.ingest.extract_claims.OpenAI")
    def test_claim_id_generation(self, MockOpenAI):
        """claim_ids should incorporate doc_id hash."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_completion(MOCK_GPT_RESPONSE)
        MockOpenAI.return_value = mock_client

        extractor = ClaimExtractor(api_key="test-key")
        extractor.client = mock_client

        claims = extractor.extract_from_doc(SAMPLE_EVIDENCE_DOC)
        doc_hash = SAMPLE_EVIDENCE_DOC["doc_id"][-8:]
        assert claims[0]["claim_id"] == f"CLM_{doc_hash}_0001"
        assert claims[1]["claim_id"] == f"CLM_{doc_hash}_0002"

    @patch("src.ingest.extract_claims.OpenAI")
    def test_extract_from_jsonl(self, MockOpenAI):
        """End-to-end test: JSONL in -> claims JSONL out."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_completion(MOCK_GPT_RESPONSE)
        MockOpenAI.return_value = mock_client

        extractor = ClaimExtractor(api_key="test-key")
        extractor.client = mock_client

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "evidence_docs.jsonl")
            output_path = os.path.join(tmpdir, "claims.jsonl")

            with open(input_path, "w") as f:
                f.write(json.dumps(SAMPLE_EVIDENCE_DOC) + "\n")

            extractor.extract_from_jsonl(input_path, output_path)

            with open(output_path, "r") as f:
                claims = [json.loads(line) for line in f]

            assert len(claims) == 2

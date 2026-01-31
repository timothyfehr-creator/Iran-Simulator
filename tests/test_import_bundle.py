"""
Tests for import_deep_research_bundle.py
"""

import os
import sys
import json
import unittest
import tempfile
import shutil

# Ensure src is on path
HERE = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from pipeline.import_deep_research_bundle import (
    validate_evidence_docs,
    validate_candidate_claims,
    import_bundle
)


class TestImportBundle(unittest.TestCase):

    def setUp(self):
        """Create temp directory for test outputs"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp directory"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_validate_evidence_docs_duplicate_doc_id(self):
        """Fails on duplicate doc_id"""
        evidence_docs = [
            {"doc_id": "doc_001", "language": "en"},
            {"doc_id": "doc_001", "language": "en"}
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_evidence_docs(evidence_docs)
        self.assertIn("duplicate doc_id", str(ctx.exception))

    def test_validate_evidence_docs_missing_translation_confidence(self):
        """Fails when language != 'en' but translation_confidence missing"""
        evidence_docs = [
            {
                "doc_id": "doc_001",
                "language": "fa",
                "translation_en": "Some translation"
                # Missing translation_confidence
            }
        ]
        with self.assertRaises(ValueError) as ctx:
            validate_evidence_docs(evidence_docs)
        self.assertIn("missing translation_confidence", str(ctx.exception))

    def test_validate_evidence_docs_english_no_translation_ok(self):
        """Allows translation_en=null for English docs"""
        evidence_docs = [
            {
                "doc_id": "doc_001",
                "language": "en",
                "translation_en": None,
                "translation_confidence": None
            }
        ]
        # Should not raise
        result = validate_evidence_docs(evidence_docs)
        doc_ids = result[0] if isinstance(result, tuple) else result
        self.assertEqual(doc_ids, {"doc_001"})

    def test_validate_candidate_claims_duplicate_claim_id(self):
        """Fails on duplicate claim_id"""
        candidate_claims = [
            {
                "claim_id": "claim_001",
                "path": "current_situation.protest_status.active",
                "value": True,
                "as_of_utc": "2026-01-11T12:00:00Z",
                "source_grade": "A1",
                "source_doc_refs": [{"doc_id": "doc_001", "excerpt_id": "exc_001"}],
                "claim_class": "FACTUAL"
            },
            {
                "claim_id": "claim_001",
                "path": "current_situation.protest_status.duration_days",
                "value": 45,
                "as_of_utc": "2026-01-11T12:00:00Z",
                "source_grade": "A1",
                "source_doc_refs": [{"doc_id": "doc_001", "excerpt_id": "exc_001"}],
                "claim_class": "FACTUAL"
            }
        ]
        valid_doc_ids = {"doc_001"}
        with self.assertRaises(ValueError) as ctx:
            validate_candidate_claims(candidate_claims, valid_doc_ids)
        self.assertIn("duplicate claim_id", str(ctx.exception))

    def test_validate_candidate_claims_missing_doc_ref(self):
        """Fails when claim references non-existent doc_id"""
        candidate_claims = [
            {
                "claim_id": "claim_001",
                "path": "current_situation.protest_status.active",
                "value": True,
                "as_of_utc": "2026-01-11T12:00:00Z",
                "source_grade": "A1",
                "source_doc_refs": [{"doc_id": "doc_999", "excerpt_id": "exc_001"}],
                "claim_class": "FACTUAL"
            }
        ]
        valid_doc_ids = {"doc_001"}  # doc_999 doesn't exist
        with self.assertRaises(ValueError) as ctx:
            validate_candidate_claims(candidate_claims, valid_doc_ids)
        self.assertIn("unknown doc_id 'doc_999'", str(ctx.exception))

    def test_validate_candidate_claims_null_without_reason(self):
        """Fails when value is null but null_reason is empty"""
        candidate_claims = [
            {
                "claim_id": "claim_001",
                "path": "current_situation.protest_status.active",
                "value": None,
                "null_reason": "",  # Empty!
                "as_of_utc": "2026-01-11T12:00:00Z",
                "source_grade": "A1",
                "source_doc_refs": [{"doc_id": "doc_001", "excerpt_id": "exc_001"}],
                "claim_class": "FACTUAL"
            }
        ]
        valid_doc_ids = {"doc_001"}
        with self.assertRaises(ValueError) as ctx:
            validate_candidate_claims(candidate_claims, valid_doc_ids)
        self.assertIn("null but null_reason is empty", str(ctx.exception))

    def test_validate_candidate_claims_empty_source_doc_refs(self):
        """Fails when source_doc_refs is empty"""
        candidate_claims = [
            {
                "claim_id": "claim_001",
                "path": "current_situation.protest_status.duration_days",
                "value": 42,
                "as_of_utc": "2026-01-11T12:00:00Z",
                "source_grade": "A1",
                "source_doc_refs": [],  # Empty!
                "claim_class": "FACTUAL"
            }
        ]
        valid_doc_ids = {"doc_001"}
        with self.assertRaises(ValueError) as ctx:
            validate_candidate_claims(candidate_claims, valid_doc_ids)
        self.assertIn("source_doc_refs is empty", str(ctx.exception))

    def test_import_bundle_valid_minimal(self):
        """Successfully imports a minimal valid bundle"""
        bundle = {
            "run_manifest": {
                "run_id": "test_001",
                "query": "Test",
                "executed_at_utc": "2026-01-11T12:00:00Z",
                "data_cutoff_utc": "2026-01-11T12:00:00Z",
                "time_horizon_days": 90,
                "researcher": "Test"
            },
            "source_index": [
                {
                    "source_id": "src_001",
                    "organization": "Test",
                    "title": "Test",
                    "url": "https://example.com",
                    "published_at_utc": "2026-01-11T12:00:00Z",
                    "access_grade": "A",
                    "bias_grade": "1",
                    "language": "en"
                }
            ],
            "evidence_docs": [
                {
                    "doc_id": "doc_001",
                    "source_id": "src_001",
                    "title": "Test Doc",
                    "url": "https://example.com",
                    "published_at_utc": "2026-01-11T12:00:00Z",
                    "retrieved_at_utc": "2026-01-11T12:00:00Z",
                    "language": "en",
                    "raw_text": "Test",
                    "translation_en": None,
                    "translation_confidence": None,
                    "key_excerpts": []
                }
            ],
            "candidate_claims": [
                {
                    "claim_id": "claim_001",
                    "path": "current_situation.regime_response.arrests",
                    "selector": None,
                    "value": 42,
                    "units": "count",
                    "null_reason": None,
                    "as_of_utc": "2026-01-11T12:00:00Z",
                    "source_grade": "A1",
                    "source_doc_refs": [{"doc_id": "doc_001", "excerpt_id": "exc_001"}],
                    "claim_class": "FACTUAL",
                    "confidence": "HIGH",
                    "triangulated": False,
                    "notes": ""
                }
            ]
        }

        # Write bundle to temp file
        bundle_path = os.path.join(self.temp_dir, "bundle.json")
        with open(bundle_path, "w") as f:
            json.dump(bundle, f)

        # Import
        out_dir = os.path.join(self.temp_dir, "output")
        import_bundle(bundle_path, out_dir)

        # Check outputs exist
        self.assertTrue(os.path.exists(os.path.join(out_dir, "evidence_docs.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "claims_deep_research.jsonl")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "source_index.json")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "run_manifest.json")))

        # Check JSONL format
        with open(os.path.join(out_dir, "evidence_docs.jsonl"), "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            doc = json.loads(lines[0])
            self.assertEqual(doc["doc_id"], "doc_001")

        with open(os.path.join(out_dir, "claims_deep_research.jsonl"), "r") as f:
            lines = f.readlines()
            self.assertEqual(len(lines), 1)
            claim = json.loads(lines[0])
            self.assertEqual(claim["claim_id"], "claim_001")


if __name__ == "__main__":
    unittest.main()

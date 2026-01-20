"""
Tests for evidence snapshot storage.

Validates snapshot write, sha256 hash verification, and file operations.
"""

import pytest
import json
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, timezone

from src.forecasting import evidence


@pytest.fixture
def temp_evidence_dir(tmp_path):
    """Create a temporary evidence directory."""
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    return evidence_dir


class TestComputeHash:
    """Tests for hash computation functions."""

    def test_compute_content_hash(self):
        """Test content hash computation."""
        content = b"test content"
        result = evidence.compute_content_hash(content)

        assert result.startswith("sha256:")
        assert len(result) == 71  # "sha256:" + 64 hex chars

        # Verify against direct computation
        expected = f"sha256:{hashlib.sha256(content).hexdigest()}"
        assert result == expected

    def test_compute_content_hash_deterministic(self):
        """Test that hash is deterministic."""
        content = b"same content"
        hash1 = evidence.compute_content_hash(content)
        hash2 = evidence.compute_content_hash(content)
        assert hash1 == hash2

    def test_compute_content_hash_different_for_different_content(self):
        """Test that different content produces different hashes."""
        hash1 = evidence.compute_content_hash(b"content1")
        hash2 = evidence.compute_content_hash(b"content2")
        assert hash1 != hash2

    def test_compute_file_hash(self, tmp_path):
        """Test file hash computation."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"file content")

        result = evidence.compute_file_hash(test_file)

        assert result.startswith("sha256:")
        expected = f"sha256:{hashlib.sha256(b'file content').hexdigest()}"
        assert result == expected


class TestWriteEvidenceSnapshot:
    """Tests for evidence snapshot writing."""

    def test_write_evidence_snapshot_creates_file(self, temp_evidence_dir):
        """Test that write creates a JSON file."""
        resolution_id = "res_20260120_econ.rial_ge_1_2m_7d"
        snapshot_data = {
            "run_id": "RUN_20260120",
            "data_cutoff_utc": "2026-01-20T00:00:00Z",
            "path_used": "current_state.economic_conditions.rial_usd_rate.market",
            "extracted_value": 1500000,
            "rule_applied": "threshold_gte:1200000",
        }

        ref_path, ref_hash = evidence.write_evidence_snapshot(
            resolution_id, snapshot_data, temp_evidence_dir
        )

        # Check file exists
        expected_file = temp_evidence_dir / f"{resolution_id}.json"
        assert expected_file.exists()

    def test_write_evidence_snapshot_returns_path_and_hash(self, temp_evidence_dir):
        """Test that write returns path and hash."""
        resolution_id = "res_20260120_econ.rial_ge_1_2m_7d"
        snapshot_data = {"test": "data"}

        ref_path, ref_hash = evidence.write_evidence_snapshot(
            resolution_id, snapshot_data, temp_evidence_dir
        )

        assert resolution_id in ref_path
        assert ref_hash.startswith("sha256:")
        assert len(ref_hash) == 71

    def test_write_evidence_snapshot_adds_timestamp(self, temp_evidence_dir):
        """Test that write adds snapshot_utc timestamp."""
        resolution_id = "res_20260120_econ.rial_ge_1_2m_7d"
        snapshot_data = {"test": "data"}

        evidence.write_evidence_snapshot(
            resolution_id, snapshot_data, temp_evidence_dir
        )

        # Read back and check
        file_path = temp_evidence_dir / f"{resolution_id}.json"
        with open(file_path) as f:
            saved = json.load(f)

        assert "snapshot_utc" in saved
        # Should be valid ISO format
        datetime.fromisoformat(saved["snapshot_utc"].replace('Z', '+00:00'))

    def test_write_evidence_snapshot_deterministic_content(self, temp_evidence_dir):
        """Test that content is deterministic (sorted keys)."""
        resolution_id = "res_20260120_econ.rial_ge_1_2m_7d"
        snapshot_data = {
            "z_field": "last",
            "a_field": "first",
            "m_field": "middle",
        }

        evidence.write_evidence_snapshot(
            resolution_id, snapshot_data, temp_evidence_dir
        )

        file_path = temp_evidence_dir / f"{resolution_id}.json"
        content = file_path.read_text()

        # Check keys are sorted
        lines = content.split('\n')
        key_lines = [l for l in lines if '": ' in l]
        assert 'a_field' in key_lines[0]  # a_field should come first

    def test_write_evidence_snapshot_hash_matches_file(self, temp_evidence_dir):
        """Test that returned hash matches file content."""
        resolution_id = "res_20260120_econ.rial_ge_1_2m_7d"
        snapshot_data = {"test": "data"}

        _, ref_hash = evidence.write_evidence_snapshot(
            resolution_id, snapshot_data, temp_evidence_dir
        )

        file_path = temp_evidence_dir / f"{resolution_id}.json"
        actual_hash = evidence.compute_file_hash(file_path)

        assert ref_hash == actual_hash


class TestReadEvidenceSnapshot:
    """Tests for reading evidence snapshots."""

    def test_read_evidence_snapshot_returns_data(self, temp_evidence_dir):
        """Test that read returns the snapshot data."""
        resolution_id = "res_20260120_econ.rial_ge_1_2m_7d"
        snapshot_data = {
            "run_id": "RUN_20260120",
            "extracted_value": 1500000,
        }

        evidence.write_evidence_snapshot(
            resolution_id, snapshot_data, temp_evidence_dir
        )

        result = evidence.read_evidence_snapshot(resolution_id, temp_evidence_dir)

        assert result is not None
        assert result["run_id"] == "RUN_20260120"
        assert result["extracted_value"] == 1500000

    def test_read_evidence_snapshot_missing_returns_none(self, temp_evidence_dir):
        """Test that reading missing snapshot returns None."""
        result = evidence.read_evidence_snapshot(
            "nonexistent_resolution", temp_evidence_dir
        )
        assert result is None


class TestVerifyEvidenceHash:
    """Tests for hash verification."""

    def test_verify_evidence_hash_valid(self, temp_evidence_dir):
        """Test verification passes with correct hash."""
        resolution_id = "res_20260120_econ.rial_ge_1_2m_7d"
        snapshot_data = {"test": "data"}

        _, ref_hash = evidence.write_evidence_snapshot(
            resolution_id, snapshot_data, temp_evidence_dir
        )

        result = evidence.verify_evidence_hash(
            resolution_id, ref_hash, temp_evidence_dir
        )
        assert result is True

    def test_verify_evidence_hash_invalid(self, temp_evidence_dir):
        """Test verification fails with wrong hash."""
        resolution_id = "res_20260120_econ.rial_ge_1_2m_7d"
        snapshot_data = {"test": "data"}

        evidence.write_evidence_snapshot(
            resolution_id, snapshot_data, temp_evidence_dir
        )

        wrong_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        result = evidence.verify_evidence_hash(
            resolution_id, wrong_hash, temp_evidence_dir
        )
        assert result is False

    def test_verify_evidence_hash_missing_file(self, temp_evidence_dir):
        """Test verification fails for missing file."""
        result = evidence.verify_evidence_hash(
            "nonexistent",
            "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            temp_evidence_dir
        )
        assert result is False


class TestListEvidenceFiles:
    """Tests for listing evidence files."""

    def test_list_evidence_files_empty(self, temp_evidence_dir):
        """Test listing empty directory."""
        result = evidence.list_evidence_files(temp_evidence_dir)
        assert result == []

    def test_list_evidence_files_returns_resolution_ids(self, temp_evidence_dir):
        """Test that list returns resolution IDs."""
        # Create some evidence files
        for i in range(3):
            resolution_id = f"res_2026012{i}_econ.rial_ge_1_2m_7d"
            evidence.write_evidence_snapshot(
                resolution_id, {"index": i}, temp_evidence_dir
            )

        result = evidence.list_evidence_files(temp_evidence_dir)

        assert len(result) == 3
        assert all(r.startswith("res_") for r in result)

    def test_list_evidence_files_sorted(self, temp_evidence_dir):
        """Test that results are sorted."""
        ids = [
            "res_20260122_econ.rial_ge_1_2m_7d",
            "res_20260120_econ.rial_ge_1_2m_7d",
            "res_20260121_econ.rial_ge_1_2m_7d",
        ]
        for resolution_id in ids:
            evidence.write_evidence_snapshot(
                resolution_id, {}, temp_evidence_dir
            )

        result = evidence.list_evidence_files(temp_evidence_dir)

        assert result == sorted(ids)

    def test_list_evidence_files_missing_directory(self, tmp_path):
        """Test listing nonexistent directory returns empty."""
        nonexistent = tmp_path / "nonexistent"
        result = evidence.list_evidence_files(nonexistent)
        assert result == []

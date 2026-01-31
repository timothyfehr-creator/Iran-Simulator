"""
Tests for shared run validation helpers.

Workstream 7: Shared Run Validation Helpers
Verifies validation logic with mock run directories.
"""

import pytest
import os
import json
import tempfile
from pathlib import Path

from src.run_utils import (
    list_runs_sorted,
    list_runs_sorted_with_test,
    required_artifacts,
    check_artifacts_exist,
    is_run_valid_for_observe,
    is_run_valid_for_simulate,
    get_run_status,
    get_run_reliability,
    get_run_info,
    find_latest_valid_run,
    OBSERVE_ARTIFACTS,
    SIMULATE_ARTIFACTS
)


class TestListRunsSorted:
    """Tests for list_runs_sorted function."""

    def test_sorts_by_date_descending(self):
        """Runs should be sorted with newest first."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            # Create run directories
            (runs_dir / "RUN_20260115_daily").mkdir()
            (runs_dir / "RUN_20260112_daily").mkdir()
            (runs_dir / "RUN_20260118_daily").mkdir()

            runs = list_runs_sorted(runs_dir)

            assert runs[0] == "RUN_20260118_daily"
            assert runs[1] == "RUN_20260115_daily"
            assert runs[2] == "RUN_20260112_daily"

    def test_excludes_meta_directory(self):
        """_meta directory should be excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            (runs_dir / "RUN_20260115_daily").mkdir()
            (runs_dir / "_meta").mkdir()

            runs = list_runs_sorted(runs_dir)

            assert "_meta" not in runs
            assert len(runs) == 1

    def test_excludes_test_directories(self):
        """TEST_* directories should be excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            (runs_dir / "RUN_20260115_daily").mkdir()
            (runs_dir / "TEST_20260115_0001").mkdir()

            runs = list_runs_sorted(runs_dir)

            assert "TEST_20260115_0001" not in runs
            assert len(runs) == 1

    def test_returns_empty_for_nonexistent_dir(self):
        """Should return empty list for nonexistent directory."""
        runs = list_runs_sorted(Path("/nonexistent/path"))

        assert runs == []

    def test_includes_adhoc_runs(self):
        """ADHOC_* runs should be included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            (runs_dir / "RUN_20260115_daily").mkdir()
            (runs_dir / "ADHOC_20260115_1200").mkdir()

            runs = list_runs_sorted(runs_dir)

            assert "ADHOC_20260115_1200" in runs
            assert len(runs) == 2


class TestListRunsSortedWithTest:
    """Tests for list_runs_sorted_with_test function."""

    def test_includes_test_directories(self):
        """Should include TEST_* directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            (runs_dir / "RUN_20260115_daily").mkdir()
            (runs_dir / "TEST_20260115_0001").mkdir()

            runs = list_runs_sorted_with_test(runs_dir)

            assert "TEST_20260115_0001" in runs
            assert len(runs) == 2


class TestRequiredArtifacts:
    """Tests for required_artifacts function."""

    def test_observe_mode_artifacts(self):
        """Observe mode should require specific artifacts."""
        artifacts = required_artifacts("observe")

        assert "run_manifest.json" in artifacts
        assert "compiled_intel.json" in artifacts
        assert "coverage_report.json" in artifacts

    def test_simulate_mode_artifacts(self):
        """Simulate mode should require specific artifacts."""
        artifacts = required_artifacts("simulate")

        assert "run_manifest.json" in artifacts
        assert "compiled_intel.json" in artifacts
        assert "priors_resolved.json" in artifacts
        assert "simulation_results.json" in artifacts

    def test_invalid_mode_raises_error(self):
        """Unknown mode should raise ValueError."""
        with pytest.raises(ValueError):
            required_artifacts("invalid_mode")

    def test_returns_copy(self):
        """Should return a copy to prevent modification."""
        artifacts1 = required_artifacts("observe")
        artifacts1.append("extra.json")

        artifacts2 = required_artifacts("observe")

        assert "extra.json" not in artifacts2


class TestCheckArtifactsExist:
    """Tests for check_artifacts_exist function."""

    def test_all_exist(self):
        """Should return (True, []) when all artifacts exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            (run_dir / "file1.json").touch()
            (run_dir / "file2.json").touch()

            all_exist, missing = check_artifacts_exist(run_dir, ["file1.json", "file2.json"])

            assert all_exist == True
            assert missing == []

    def test_some_missing(self):
        """Should return (False, [missing]) when some artifacts missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            (run_dir / "file1.json").touch()

            all_exist, missing = check_artifacts_exist(run_dir, ["file1.json", "file2.json"])

            assert all_exist == False
            assert "file2.json" in missing


class TestIsRunValidForObserve:
    """Tests for is_run_valid_for_observe function."""

    def test_valid_when_all_artifacts_present(self):
        """Should return True when all observe artifacts exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            for artifact in OBSERVE_ARTIFACTS:
                (run_dir / artifact).touch()

            assert is_run_valid_for_observe(run_dir) == True

    def test_invalid_when_missing_artifact(self):
        """Should return False when any observe artifact missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            # Create all but one
            for artifact in OBSERVE_ARTIFACTS[:-1]:
                (run_dir / artifact).touch()

            assert is_run_valid_for_observe(run_dir) == False


class TestIsRunValidForSimulate:
    """Tests for is_run_valid_for_simulate function."""

    def test_valid_when_all_artifacts_present(self):
        """Should return True when all simulate artifacts exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            for artifact in SIMULATE_ARTIFACTS:
                (run_dir / artifact).touch()

            assert is_run_valid_for_simulate(run_dir) == True

    def test_invalid_when_missing_artifact(self):
        """Should return False when any simulate artifact missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            # Create all but simulation_results
            for artifact in SIMULATE_ARTIFACTS:
                if artifact != "simulation_results.json":
                    (run_dir / artifact).touch()

            assert is_run_valid_for_simulate(run_dir) == False


class TestGetRunStatus:
    """Tests for get_run_status function."""

    def test_returns_comprehensive_status(self):
        """Should return status for all artifact types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            (run_dir / "run_manifest.json").touch()
            (run_dir / "compiled_intel.json").touch()

            status = get_run_status(run_dir)

            assert status["has_manifest"] == True
            assert status["has_intel"] == True
            assert status["has_coverage"] == False
            assert status["has_simulation"] == False

    def test_includes_validation_results(self):
        """Should include valid_for_observe and valid_for_simulate."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            status = get_run_status(run_dir)

            assert "valid_for_observe" in status
            assert "valid_for_simulate" in status
            assert "missing_for_observe" in status
            assert "missing_for_simulate" in status


class TestGetRunReliability:
    """Tests for get_run_reliability function."""

    def test_reliable_when_manifest_says_so(self):
        """Should return (True, None) when manifest.run_reliable is True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            manifest = {"run_reliable": True}
            with open(run_dir / "run_manifest.json", 'w') as f:
                json.dump(manifest, f)

            is_reliable, reason = get_run_reliability(run_dir)

            assert is_reliable == True
            assert reason is None

    def test_unreliable_with_reason(self):
        """Should return (False, reason) when manifest says unreliable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            manifest = {
                "run_reliable": False,
                "unreliable_reason": "Coverage gates failed"
            }
            with open(run_dir / "run_manifest.json", 'w') as f:
                json.dump(manifest, f)

            is_reliable, reason = get_run_reliability(run_dir)

            assert is_reliable == False
            assert "Coverage" in reason

    def test_assumes_reliable_when_no_manifest(self):
        """Should assume reliable when no manifest exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)

            is_reliable, reason = get_run_reliability(run_dir)

            assert is_reliable == True
            assert reason is None


class TestGetRunInfo:
    """Tests for get_run_info function."""

    def test_extracts_manifest_fields(self):
        """Should extract key fields from manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            run_dir = Path(tmpdir) / "RUN_20260119_daily"
            run_dir.mkdir()

            manifest = {
                "data_cutoff_utc": "2026-01-19T12:00:00Z",
                "coverage_status": "PASS",
                "run_reliable": True,
                "git_commit": "abc123def456"
            }
            with open(run_dir / "run_manifest.json", 'w') as f:
                json.dump(manifest, f)

            info = get_run_info(run_dir)

            assert info["run_id"] == "RUN_20260119_daily"
            assert info["data_cutoff_utc"] == "2026-01-19T12:00:00Z"
            assert info["coverage_status"] == "PASS"
            assert info["run_reliable"] == True

    def test_fallback_to_coverage_report(self):
        """Should check coverage_report.json if manifest missing coverage_status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "RUN_20260119_daily"
            run_dir.mkdir()

            coverage = {"status": "WARN"}
            with open(run_dir / "coverage_report.json", 'w') as f:
                json.dump(coverage, f)

            info = get_run_info(run_dir)

            assert info["coverage_status"] == "WARN"


class TestFindLatestValidRun:
    """Tests for find_latest_valid_run function."""

    def test_finds_latest_valid_observe_run(self):
        """Should find most recent run valid for observe."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            # Older valid run
            older = runs_dir / "RUN_20260115_daily"
            older.mkdir()
            for a in OBSERVE_ARTIFACTS:
                (older / a).touch()

            # Newer invalid run
            newer = runs_dir / "RUN_20260118_daily"
            newer.mkdir()
            # Only create some artifacts (invalid)
            (newer / "compiled_intel.json").touch()

            result = find_latest_valid_run(runs_dir, "observe")

            assert result is not None
            assert result.name == "RUN_20260115_daily"

    def test_returns_none_when_no_valid_runs(self):
        """Should return None when no valid runs exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runs_dir = Path(tmpdir)

            # Create invalid run
            invalid = runs_dir / "RUN_20260115_daily"
            invalid.mkdir()

            result = find_latest_valid_run(runs_dir, "observe")

            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

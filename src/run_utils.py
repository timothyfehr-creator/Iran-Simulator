"""
Shared run validation helpers for frontend and backend.

Provides utilities for:
- Listing and sorting run directories
- Validating runs for observe/simulate modes
- Checking run reliability from manifest
"""

import json
import os
from pathlib import Path
from typing import List, Optional, Tuple, Literal


# Required artifacts for each mode
OBSERVE_ARTIFACTS = [
    "run_manifest.json",
    "compiled_intel.json",
    "coverage_report.json",
]

SIMULATE_ARTIFACTS = [
    "run_manifest.json",
    "compiled_intel.json",
    "priors_resolved.json",
    "simulation_results.json",
]


def list_runs_sorted(runs_dir: Path = Path("runs")) -> List[str]:
    """
    Return run folder names sorted by date descending.

    Excludes:
    - _meta folder
    - TEST_* folders (unless show_test=True)
    - Non-directory entries

    Args:
        runs_dir: Path to runs directory

    Returns:
        List of run folder names sorted by date descending
    """
    if not runs_dir.exists() or not runs_dir.is_dir():
        return []

    runs = []
    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue

        name = entry.name

        # Skip _meta folder
        if name == "_meta":
            continue

        # Skip TEST_* folders
        if name.startswith("TEST_"):
            continue

        # Skip ADHOC_* folders by default (they're ad-hoc dashboard runs)
        # Actually keep them - they're legitimate runs

        runs.append(name)

    # Sort by name descending (RUN_YYYYMMDD format sorts chronologically)
    # More recent dates come first
    runs.sort(reverse=True)

    return runs


def list_runs_sorted_with_test(runs_dir: Path = Path("runs")) -> List[str]:
    """
    Return run folder names including TEST_* folders, sorted by date descending.

    Args:
        runs_dir: Path to runs directory

    Returns:
        List of run folder names sorted by date descending
    """
    if not runs_dir.exists() or not runs_dir.is_dir():
        return []

    runs = []
    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue

        name = entry.name

        # Skip _meta folder only
        if name == "_meta":
            continue

        runs.append(name)

    runs.sort(reverse=True)
    return runs


def required_artifacts(mode: Literal["observe", "simulate"]) -> List[str]:
    """
    Return list of required artifact filenames for given mode.

    Args:
        mode: "observe" or "simulate"

    Returns:
        List of required artifact filenames

    Raises:
        ValueError: If mode is not "observe" or "simulate"
    """
    if mode == "observe":
        return OBSERVE_ARTIFACTS.copy()
    elif mode == "simulate":
        return SIMULATE_ARTIFACTS.copy()
    else:
        raise ValueError(f"Unknown mode: {mode}. Must be 'observe' or 'simulate'")


def check_artifacts_exist(run_dir: Path, artifacts: List[str]) -> Tuple[bool, List[str]]:
    """
    Check which artifacts exist in a run directory.

    Args:
        run_dir: Path to run directory
        artifacts: List of artifact filenames to check

    Returns:
        Tuple of (all_exist, missing_artifacts)
    """
    missing = []
    for artifact in artifacts:
        path = run_dir / artifact
        if not path.exists():
            missing.append(artifact)

    return len(missing) == 0, missing


def is_run_valid_for_observe(run_dir: Path) -> bool:
    """
    Check if run has required artifacts for observe mode.

    Required: run_manifest.json, compiled_intel.json, coverage_report.json

    Args:
        run_dir: Path to run directory

    Returns:
        True if run is valid for observe mode
    """
    all_exist, _ = check_artifacts_exist(run_dir, OBSERVE_ARTIFACTS)
    return all_exist


def is_run_valid_for_simulate(run_dir: Path) -> bool:
    """
    Check if run has required artifacts for simulate mode.

    Required: run_manifest.json, compiled_intel.json, priors_resolved.json, simulation_results.json

    Args:
        run_dir: Path to run directory

    Returns:
        True if run is valid for simulate mode
    """
    all_exist, _ = check_artifacts_exist(run_dir, SIMULATE_ARTIFACTS)
    return all_exist


def get_run_status(run_dir: Path) -> dict:
    """
    Get comprehensive status of a run directory.

    Returns:
        Dict with:
        - has_manifest: bool
        - has_intel: bool
        - has_coverage: bool
        - has_simulation: bool
        - has_priors: bool
        - valid_for_observe: bool
        - valid_for_simulate: bool
        - missing_for_observe: List[str]
        - missing_for_simulate: List[str]
    """
    status = {
        "has_manifest": (run_dir / "run_manifest.json").exists(),
        "has_intel": (run_dir / "compiled_intel.json").exists(),
        "has_coverage": (run_dir / "coverage_report.json").exists(),
        "has_simulation": (run_dir / "simulation_results.json").exists(),
        "has_priors": (run_dir / "priors_resolved.json").exists() or (run_dir / "analyst_priors.json").exists(),
        "has_claims": (run_dir / "claims_deep_research.jsonl").exists(),
    }

    valid_observe, missing_observe = check_artifacts_exist(run_dir, OBSERVE_ARTIFACTS)
    valid_simulate, missing_simulate = check_artifacts_exist(run_dir, SIMULATE_ARTIFACTS)

    status["valid_for_observe"] = valid_observe
    status["valid_for_simulate"] = valid_simulate
    status["missing_for_observe"] = missing_observe
    status["missing_for_simulate"] = missing_simulate

    return status


def get_run_reliability(run_dir: Path) -> Tuple[bool, Optional[str]]:
    """
    Return (is_reliable, reason) from run_manifest.json.

    Args:
        run_dir: Path to run directory

    Returns:
        Tuple of (is_reliable, reason)
        - If manifest exists: returns (run_reliable, unreliable_reason) from manifest
        - If no manifest: returns (True, None) - assume reliable if no manifest
    """
    manifest_path = run_dir / "run_manifest.json"

    if not manifest_path.exists():
        # No manifest - can't determine reliability, assume OK
        return True, None

    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        is_reliable = manifest.get("run_reliable", True)
        reason = manifest.get("unreliable_reason", None)

        return is_reliable, reason

    except (json.JSONDecodeError, KeyError) as e:
        # Error reading manifest - assume unreliable
        return False, f"Error reading manifest: {e}"


def get_run_info(run_dir: Path) -> dict:
    """
    Get summary info about a run from its manifest.

    Args:
        run_dir: Path to run directory

    Returns:
        Dict with run info (cutoff, coverage_status, reliability, etc.)
    """
    info = {
        "run_id": run_dir.name,
        "data_cutoff_utc": None,
        "coverage_status": None,
        "run_reliable": True,
        "unreliable_reason": None,
        "git_commit": None,
    }

    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            info["data_cutoff_utc"] = manifest.get("data_cutoff_utc")
            info["coverage_status"] = manifest.get("coverage_status")
            info["run_reliable"] = manifest.get("run_reliable", True)
            info["unreliable_reason"] = manifest.get("unreliable_reason")
            info["git_commit"] = manifest.get("git_commit")

        except (json.JSONDecodeError, KeyError):
            pass

    # Also check coverage_report.json for coverage status
    coverage_path = run_dir / "coverage_report.json"
    if coverage_path.exists() and info["coverage_status"] is None:
        try:
            with open(coverage_path, 'r') as f:
                coverage = json.load(f)
            info["coverage_status"] = coverage.get("status")
        except (json.JSONDecodeError, KeyError):
            pass

    return info


def find_latest_valid_run(
    runs_dir: Path = Path("runs"),
    mode: Literal["observe", "simulate"] = "observe"
) -> Optional[Path]:
    """
    Find the most recent run that is valid for the given mode.

    Args:
        runs_dir: Path to runs directory
        mode: "observe" or "simulate"

    Returns:
        Path to latest valid run directory, or None if none found
    """
    runs = list_runs_sorted(runs_dir)

    for run_name in runs:
        run_dir = runs_dir / run_name

        if mode == "observe" and is_run_valid_for_observe(run_dir):
            return run_dir
        elif mode == "simulate" and is_run_valid_for_simulate(run_dir):
            return run_dir

    return None

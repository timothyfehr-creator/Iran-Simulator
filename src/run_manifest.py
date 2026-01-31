"""
Run manifest generation for reproducibility tracking.

Generates run_manifest.json with:
- git_commit: Current git commit hash
- data_cutoff_utc: Cutoff timestamp for evidence
- ingest_since_utc: Start of evidence window
- seed: Random seed for simulation
- deterministic_tiebreak_policy: Order of merge tiebreaks
- hashes: SHA256 hashes of key artifacts
- coverage_status: PASS/WARN/FAIL
- run_reliable: Boolean indicating if run can be trusted
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict


# Import the deterministic tiebreak policy from compile_intel_v2
try:
    from src.pipeline.compile_intel_v2 import DETERMINISTIC_TIEBREAK_POLICY
except ImportError:
    try:
        from pipeline.compile_intel_v2 import DETERMINISTIC_TIEBREAK_POLICY
    except ImportError:
        # Fallback if not importable
        DETERMINISTIC_TIEBREAK_POLICY = [
            "source_grade",
            "triangulated",
            "confidence",
            "latest_published_at",
            "claim_id"
        ]


@dataclass
class RunManifest:
    """Complete run manifest for reproducibility."""
    git_commit: str
    data_cutoff_utc: str
    ingest_since_utc: str
    seed: int
    deterministic_tiebreaks: List[str]  # Spec: use "deterministic_tiebreaks" not "policy"
    hashes: Dict[str, str]
    coverage_status: str
    run_reliable: bool
    generated_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    run_id: str = ""
    unreliable_reason: Optional[str] = None
    as_of_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    n_sims: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        # Remove None values
        return {k: v for k, v in d.items() if v is not None}


def compute_file_hash(file_path: str) -> Optional[str]:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to file

    Returns:
        "sha256:<hash>" or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return None

    sha256_hash = hashlib.sha256()

    with open(file_path, 'rb') as f:
        # Read in chunks for large files
        for chunk in iter(lambda: f.read(8192), b''):
            sha256_hash.update(chunk)

    return f"sha256:{sha256_hash.hexdigest()}"


def get_git_commit() -> str:
    """
    Get current git commit hash.

    Returns:
        Commit hash or "unknown" if not in a git repo
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return "unknown"


def compute_run_hashes(run_dir: str) -> Dict[str, str]:
    """
    Compute hashes for key artifacts in a run directory.

    Args:
        run_dir: Path to run directory

    Returns:
        Dict mapping artifact name to hash
    """
    artifacts = [
        "evidence_docs.jsonl",
        "claims_deep_research.jsonl",
        "compiled_intel.json",
        "priors_resolved.json",
        "simulation_results.json",
    ]

    hashes = {}
    for artifact in artifacts:
        path = os.path.join(run_dir, artifact)
        hash_value = compute_file_hash(path)
        if hash_value:
            hashes[artifact] = hash_value

    # Add claims.jsonl alias per spec (derived from claims_deep_research.jsonl or claims_extracted.jsonl)
    if "claims_deep_research.jsonl" in hashes:
        hashes["claims.jsonl"] = hashes["claims_deep_research.jsonl"]
    else:
        # Try claims_extracted.jsonl as fallback
        extracted_path = os.path.join(run_dir, "claims_extracted.jsonl")
        extracted_hash = compute_file_hash(extracted_path)
        if extracted_hash:
            hashes["claims.jsonl"] = extracted_hash
            hashes["claims_extracted.jsonl"] = extracted_hash

    return hashes


def determine_run_reliability(
    coverage_status: str,
    coverage_report: Optional[Dict] = None
) -> tuple:
    """
    Determine if a run is reliable based on coverage status.

    Args:
        coverage_status: PASS/WARN/FAIL
        coverage_report: Full coverage report for details

    Returns:
        (is_reliable, reason) tuple
    """
    if coverage_status == "FAIL":
        reason = "Coverage gates failed"
        if coverage_report:
            missing = coverage_report.get("buckets_missing", [])
            if missing:
                reason = f"Coverage FAIL: missing buckets {missing}"
        return False, reason

    if coverage_status == "WARN":
        # WARN is still considered reliable but with caveats
        return True, None

    return True, None


def generate_run_manifest(
    run_dir: str,
    data_cutoff_utc: str,
    ingest_since_utc: str,
    seed: int = 42,
    coverage_status: str = "UNKNOWN",
    coverage_report: Optional[Dict] = None,
    run_id: str = "",
    as_of_utc: Optional[str] = None,
    n_sims: Optional[int] = None
) -> RunManifest:
    """
    Generate a complete run manifest.

    Args:
        run_dir: Path to run directory
        data_cutoff_utc: Data cutoff timestamp
        ingest_since_utc: Ingest start timestamp
        seed: Random seed used for simulation
        coverage_status: PASS/WARN/FAIL from coverage gates
        coverage_report: Full coverage report dict
        run_id: Run identifier
        as_of_utc: Snapshot time - when manifest represents state of world (defaults to now)
        n_sims: Number of simulation runs (None if simulation not run)

    Returns:
        RunManifest dataclass
    """
    git_commit = get_git_commit()
    hashes = compute_run_hashes(run_dir)
    is_reliable, unreliable_reason = determine_run_reliability(coverage_status, coverage_report)

    # Default as_of_utc to now if not provided
    if as_of_utc is None:
        as_of_utc = datetime.now(timezone.utc).isoformat()

    manifest = RunManifest(
        git_commit=git_commit,
        data_cutoff_utc=data_cutoff_utc,
        ingest_since_utc=ingest_since_utc,
        seed=seed,
        deterministic_tiebreaks=DETERMINISTIC_TIEBREAK_POLICY,
        hashes=hashes,
        coverage_status=coverage_status,
        run_reliable=is_reliable,
        run_id=run_id,
        unreliable_reason=unreliable_reason,
        as_of_utc=as_of_utc,
        n_sims=n_sims
    )

    return manifest


def write_run_manifest(manifest: RunManifest, run_dir: str) -> str:
    """
    Write run manifest to JSON file.

    Args:
        manifest: RunManifest to write
        run_dir: Directory to write to

    Returns:
        Path to written manifest file
    """
    manifest_path = os.path.join(run_dir, "run_manifest.json")

    with open(manifest_path, 'w') as f:
        json.dump(manifest.to_dict(), f, indent=2)

    return manifest_path


def load_run_manifest(run_dir: str) -> Optional[RunManifest]:
    """
    Load run manifest from a run directory.

    Args:
        run_dir: Path to run directory

    Returns:
        RunManifest or None if not found
    """
    manifest_path = os.path.join(run_dir, "run_manifest.json")

    if not os.path.exists(manifest_path):
        return None

    try:
        with open(manifest_path, 'r') as f:
            data = json.load(f)

        return RunManifest(
            git_commit=data.get("git_commit", "unknown"),
            data_cutoff_utc=data.get("data_cutoff_utc", ""),
            ingest_since_utc=data.get("ingest_since_utc", ""),
            seed=data.get("seed", 42),
            deterministic_tiebreaks=data.get("deterministic_tiebreaks", data.get("deterministic_tiebreak_policy", DETERMINISTIC_TIEBREAK_POLICY)),
            hashes=data.get("hashes", {}),
            coverage_status=data.get("coverage_status", "UNKNOWN"),
            run_reliable=data.get("run_reliable", True),
            generated_at_utc=data.get("generated_at_utc", ""),
            run_id=data.get("run_id", ""),
            unreliable_reason=data.get("unreliable_reason"),
            as_of_utc=data.get("as_of_utc", data.get("generated_at_utc", "")),
            n_sims=data.get("n_sims")
        )

    except (json.JSONDecodeError, KeyError) as e:
        print(f"Warning: Could not load run manifest: {e}")
        return None


def update_run_manifest(
    run_dir: str,
    updates: Dict[str, Any]
) -> Optional[RunManifest]:
    """
    Update existing run manifest with new values.

    Args:
        run_dir: Path to run directory
        updates: Dict of fields to update

    Returns:
        Updated RunManifest or None if not found
    """
    manifest = load_run_manifest(run_dir)

    if manifest is None:
        return None

    # Update fields
    for key, value in updates.items():
        if hasattr(manifest, key):
            setattr(manifest, key, value)

    # Recompute hashes if needed
    if "hashes" not in updates:
        manifest.hashes = compute_run_hashes(run_dir)

    # Update timestamp
    manifest.generated_at_utc = datetime.now(timezone.utc).isoformat()

    # Write back
    write_run_manifest(manifest, run_dir)

    return manifest

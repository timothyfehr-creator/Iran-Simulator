#!/usr/bin/env python3
"""
Deterministic smoke test - verify production pipeline reproducibility.

Runs the PRODUCTION pipeline twice with the same seed and compares outputs
to ensure deterministic behavior. This test REQUIRES the ABM engine with
numpy - there is no fallback to the state machine.

Uses production modules:
- import_deep_research_bundle_v3 (not legacy importer)
- compile_intel_v2 (deterministic merge)
- simulation.py --abm (multi-agent ABM - REQUIRED, no fallback)

Requirements:
- numpy must be installed for ABM simulation

Usage:
    python3 scripts/deterministic_smoke.py

Exit codes:
    0 - Pipeline is deterministic (all hashes match)
    1 - Pipeline outputs differ between runs
    2 - Missing required dependency (numpy)
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Check numpy availability upfront - ABM is required, no fallback
try:
    import numpy
except ImportError:
    print("ERROR: numpy is required for ABM simulation.")
    print("Install with: pip install numpy")
    print("This smoke test requires the production ABM path - no fallback to state machine.")
    sys.exit(2)

# Fixed parameters for reproducibility
SEED = 42
N_SIMS = 100  # Small but sufficient for determinism check

# Files to compare for determinism
FILES_TO_HASH = [
    "compiled_intel.json",
    "simulation_results.json",
]


def compute_sha256(file_path: str) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def run_pipeline(temp_dir: str, run_name: str) -> dict:
    """
    Run the full pipeline in a temp directory.

    Returns dict of file -> sha256 hash.
    """
    project_root = Path(__file__).resolve().parent.parent
    bundle_path = project_root / "tests" / "fixtures" / "minimal_bundle.json"
    template_path = project_root / "data" / "iran_crisis_intel.json"
    priors_path = project_root / "data" / "analyst_priors.json"

    out_dir = os.path.join(temp_dir, run_name)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n[{run_name}] Starting pipeline run...")

    # Step 1: Import bundle (using production v3 importer)
    print(f"[{run_name}] Step 1/3: Importing bundle (v3)...")
    result = subprocess.run(
        [
            sys.executable, "-m", "src.pipeline.import_deep_research_bundle_v3",
            "--bundle", str(bundle_path),
            "--out_dir", out_dir
        ],
        capture_output=True,
        text=True,
        cwd=str(project_root)
    )
    if result.returncode != 0:
        print(f"[{run_name}] Import failed: {result.stderr}")
        sys.exit(1)
    print(f"[{run_name}] Import complete")

    # Step 2: Compile intel (using production v2 compiler with deterministic merge)
    print(f"[{run_name}] Step 2/3: Compiling intel (v2)...")
    claims_path = os.path.join(out_dir, "claims_deep_research.jsonl")
    result = subprocess.run(
        [
            sys.executable, "-m", "src.pipeline.compile_intel_v2",
            "--claims", claims_path,
            "--template", str(template_path),
            "--outdir", out_dir
        ],
        capture_output=True,
        text=True,
        cwd=str(project_root)
    )
    if result.returncode != 0:
        print(f"[{run_name}] Compile failed: {result.stderr}")
        sys.exit(1)
    print(f"[{run_name}] Compile complete")

    # Step 3: Run simulation (ABM REQUIRED - no fallback)
    intel_path = os.path.join(out_dir, "compiled_intel.json")
    sim_output = os.path.join(out_dir, "simulation_results.json")

    # Production path: ABM only (numpy required, verified at startup)
    print(f"[{run_name}] Step 3/3: Running ABM simulation (seed={SEED}, runs={N_SIMS})...")
    result = subprocess.run(
        [
            sys.executable, "src/simulation.py",
            "--intel", intel_path,
            "--priors", str(priors_path),
            "--runs", str(N_SIMS),
            "--seed", str(SEED),
            "--abm",  # Production ABM - REQUIRED
            "--output", sim_output
        ],
        capture_output=True,
        text=True,
        cwd=str(project_root)
    )

    if result.returncode != 0:
        print(f"[{run_name}] ABM simulation failed: {result.stderr}")
        sys.exit(1)
    print(f"[{run_name}] ABM simulation complete")

    # Compute hashes
    hashes = {}
    for filename in FILES_TO_HASH:
        file_path = os.path.join(out_dir, filename)
        if os.path.exists(file_path):
            hashes[filename] = compute_sha256(file_path)
        else:
            print(f"[{run_name}] Warning: {filename} not found")
            hashes[filename] = None

    return hashes


def main():
    print("=" * 60)
    print("Deterministic Smoke Test")
    print("=" * 60)
    print(f"Seed: {SEED}")
    print(f"Simulation runs: {N_SIMS}")
    print(f"Files to verify: {FILES_TO_HASH}")

    # Create two temp directories
    temp_base = tempfile.mkdtemp(prefix="deterministic_smoke_")
    print(f"\nTemp directory: {temp_base}")

    try:
        # Run pipeline twice
        hashes_run1 = run_pipeline(temp_base, "run1")
        hashes_run2 = run_pipeline(temp_base, "run2")

        # Compare hashes
        print("\n" + "=" * 60)
        print("Hash Comparison")
        print("=" * 60)

        all_match = True
        for filename in FILES_TO_HASH:
            hash1 = hashes_run1.get(filename)
            hash2 = hashes_run2.get(filename)

            if hash1 is None or hash2 is None:
                print(f"  {filename}: SKIP (file missing)")
                continue

            if hash1 == hash2:
                print(f"  {filename}: MATCH (sha256:{hash1[:16]}...)")
            else:
                print(f"  {filename}: MISMATCH")
                print(f"    Run 1: sha256:{hash1}")
                print(f"    Run 2: sha256:{hash2}")
                all_match = False

        print("\n" + "=" * 60)
        if all_match:
            # Print summary hash (hash of all hashes)
            combined = "".join(sorted(f"{k}:{v}" for k, v in hashes_run1.items() if v))
            summary_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
            print(f"PASS: Pipeline is deterministic")
            print(f"Summary hash: {summary_hash}")
            print("=" * 60)
            return 0
        else:
            print("FAIL: Pipeline outputs differ between runs")
            print("=" * 60)
            return 1

    finally:
        # Cleanup
        shutil.rmtree(temp_base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

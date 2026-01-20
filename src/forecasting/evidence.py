"""
Evidence snapshot storage for forecast resolutions.

Writes immutable evidence snapshots with SHA256 hashes for
auditability and reproducibility.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple, Optional


EVIDENCE_DIR = Path("forecasting/evidence")


def ensure_evidence_dir(evidence_dir: Path = EVIDENCE_DIR) -> None:
    """Create evidence directory if it doesn't exist."""
    evidence_dir.mkdir(parents=True, exist_ok=True)


def compute_file_hash(file_path: Path) -> str:
    """
    Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file to hash

    Returns:
        String in format "sha256:<hex_digest>"
    """
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        # Read in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return f"sha256:{hasher.hexdigest()}"


def compute_content_hash(content: bytes) -> str:
    """
    Compute SHA256 hash of content bytes.

    Args:
        content: Bytes to hash

    Returns:
        String in format "sha256:<hex_digest>"
    """
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def write_evidence_snapshot(
    resolution_id: str,
    snapshot_data: Dict[str, Any],
    evidence_dir: Path = EVIDENCE_DIR
) -> Tuple[str, str]:
    """
    Write evidence snapshot and return path and hash.

    The snapshot is written as a JSON file with a deterministic filename
    based on the resolution_id. The content includes:
    - run_id: The run used for resolution
    - data_cutoff_utc: When the data was cut off
    - path_used: The data path queried
    - extracted_value: The actual value extracted
    - rule_applied: The resolution rule applied
    - snapshot_utc: When this snapshot was created

    Args:
        resolution_id: Unique resolution identifier
        snapshot_data: Dictionary containing evidence data
        evidence_dir: Directory to store evidence files

    Returns:
        Tuple of (repo_relative_path, "sha256:<hash>")
    """
    ensure_evidence_dir(evidence_dir)

    # Add snapshot timestamp
    snapshot_data["snapshot_utc"] = datetime.now(timezone.utc).isoformat()

    # Serialize with sorted keys for deterministic output
    content = json.dumps(snapshot_data, indent=2, sort_keys=True, ensure_ascii=False)
    content_bytes = content.encode('utf-8')

    # Compute hash before writing
    content_hash = compute_content_hash(content_bytes)

    # Generate filename from resolution_id
    filename = f"{resolution_id}.json"
    file_path = evidence_dir / filename

    # Write atomically (write to temp then rename)
    temp_path = file_path.with_suffix('.tmp')
    try:
        with open(temp_path, 'wb') as f:
            f.write(content_bytes)
        temp_path.rename(file_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    # Return repo-relative path
    repo_relative_path = str(file_path)

    return repo_relative_path, content_hash


def read_evidence_snapshot(
    resolution_id: str,
    evidence_dir: Path = EVIDENCE_DIR
) -> Optional[Dict[str, Any]]:
    """
    Read an evidence snapshot by resolution ID.

    Args:
        resolution_id: Resolution identifier
        evidence_dir: Directory containing evidence files

    Returns:
        Evidence snapshot dictionary, or None if not found
    """
    filename = f"{resolution_id}.json"
    file_path = evidence_dir / filename

    if not file_path.exists():
        return None

    with open(file_path, 'r') as f:
        return json.load(f)


def verify_evidence_hash(
    resolution_id: str,
    expected_hash: str,
    evidence_dir: Path = EVIDENCE_DIR
) -> bool:
    """
    Verify that an evidence file matches its expected hash.

    Args:
        resolution_id: Resolution identifier
        expected_hash: Expected SHA256 hash
        evidence_dir: Directory containing evidence files

    Returns:
        True if hash matches, False otherwise
    """
    filename = f"{resolution_id}.json"
    file_path = evidence_dir / filename

    if not file_path.exists():
        return False

    actual_hash = compute_file_hash(file_path)
    return actual_hash == expected_hash


def list_evidence_files(evidence_dir: Path = EVIDENCE_DIR) -> list:
    """
    List all evidence files in the evidence directory.

    Args:
        evidence_dir: Directory containing evidence files

    Returns:
        List of resolution IDs with evidence snapshots
    """
    if not evidence_dir.exists():
        return []

    resolution_ids = []
    for file_path in evidence_dir.glob("res_*.json"):
        # Extract resolution_id from filename
        resolution_ids.append(file_path.stem)

    return sorted(resolution_ids)

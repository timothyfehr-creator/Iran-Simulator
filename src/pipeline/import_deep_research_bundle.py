"""
Import Deep Research JSON bundle into JSONL format for compilation.

Usage:
    python -m src.pipeline.import_deep_research_bundle \
        --bundle <bundle.json> \
        --out_dir <runs/RUN_YYYYMMDD_HHMM/>

Outputs:
    - evidence_docs.jsonl
    - claims_deep_research.jsonl
    - source_index.json
    - run_manifest.json

Validation (fail-fast):
    - doc_id unique across evidence_docs
    - claim_id unique across candidate_claims
    - each claim references at least one doc via source_doc_refs
    - every referenced doc_id exists in evidence_docs
    - translation_confidence required for non-English docs
    - null claims must have non-empty null_reason
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Set, List, Any, Optional

# Import path registry
try:
    from pipeline.path_registry import load_default_registry
except ImportError:
    # Handle when run as script
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from pipeline.path_registry import load_default_registry


def validate_evidence_docs(
    evidence_docs: List[Dict[str, Any]],
    data_cutoff_utc: Optional[str] = None
) -> Tuple[Set[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate evidence_docs array and return set of valid doc_ids, kept docs, and warnings.

    Args:
        evidence_docs: List of evidence documents
        data_cutoff_utc: Data cutoff timestamp from run_manifest

    Returns:
        (valid_doc_ids, kept_docs, warnings)

    Raises:
        ValueError: If validation fails
    """
    doc_ids: Set[str] = set()
    errors: List[str] = []
    warnings: List[Dict[str, Any]] = []
    kept_docs: List[Dict[str, Any]] = []

    for i, doc in enumerate(evidence_docs):
        doc_id = doc.get("doc_id")
        if not doc_id:
            errors.append(f"evidence_docs[{i}]: missing doc_id")
            continue

        if doc_id in doc_ids:
            errors.append(f"evidence_docs[{i}]: duplicate doc_id '{doc_id}'")
            continue

        # STRICT CUTOFF ENFORCEMENT
        published_at = doc.get("published_at_utc")
        retrieved_at = doc.get("retrieved_at_utc")

        drop_reason = None
        if data_cutoff_utc:
            if published_at and published_at > data_cutoff_utc:
                drop_reason = f"published_at_utc ({published_at}) > data_cutoff_utc ({data_cutoff_utc})"
            elif retrieved_at and retrieved_at > data_cutoff_utc:
                drop_reason = f"retrieved_at_utc ({retrieved_at}) > data_cutoff_utc ({data_cutoff_utc})"

        if drop_reason:
            warnings.append({
                "type": "dropped_evidence_doc",
                "doc_id": doc_id,
                "reason": drop_reason
            })
            continue

        # TIMESTAMP QA WARNINGS
        if published_at and retrieved_at and retrieved_at < published_at:
            warnings.append({
                "type": "timestamp_anomaly",
                "doc_id": doc_id,
                "issue": f"retrieved_at_utc ({retrieved_at}) < published_at_utc ({published_at})"
            })

        # Check language and translation_confidence
        language = doc.get("language", "en")
        translation_en = doc.get("translation_en")
        translation_confidence = doc.get("translation_confidence")

        if language != "en":
            if not translation_confidence:
                errors.append(
                    f"evidence_docs[{i}] (doc_id={doc_id}): "
                    f"language='{language}' but missing translation_confidence"
                )

        # translation_en can be null for English sources
        if language == "en" and translation_en is None:
            # This is allowed
            pass

        doc_ids.add(doc_id)
        kept_docs.append(doc)

    if errors:
        raise ValueError(
            f"Evidence docs validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return doc_ids, kept_docs, warnings


def validate_candidate_claims(
    candidate_claims: List[Dict[str, Any]],
    valid_doc_ids: Set[str],
    data_cutoff_utc: Optional[str] = None,
    normalize_enums: bool = True
) -> List[Dict[str, Any]]:
    """
    Validate candidate_claims array and normalize enum values.

    Args:
        candidate_claims: List of claims to validate
        valid_doc_ids: Set of valid document IDs
        data_cutoff_utc: Optional data cutoff timestamp from run_manifest
        normalize_enums: Whether to normalize enum values to uppercase

    Returns:
        List of normalized claims

    Raises:
        ValueError: If validation fails
    """
    claim_ids: Set[str] = set()
    errors: List[str] = []
    normalized_claims: List[Dict[str, Any]] = []

    # Load path registry for validation
    try:
        registry = load_default_registry()
    except Exception as e:
        errors.append(f"Failed to load path registry: {e}")
        # Continue without registry validation if it fails to load

    for i, claim in enumerate(candidate_claims):
        claim_id = claim.get("claim_id")
        if not claim_id:
            errors.append(f"candidate_claims[{i}]: missing claim_id")
            continue

        if claim_id in claim_ids:
            errors.append(f"candidate_claims[{i}]: duplicate claim_id '{claim_id}'")
        claim_ids.add(claim_id)

        # Required fields
        required = ["path", "as_of_utc", "source_grade", "source_doc_refs", "claim_class"]
        for field in required:
            if field not in claim:
                errors.append(f"candidate_claims[{i}] (claim_id={claim_id}): missing '{field}'")

        # Check value and null_reason
        value = claim.get("value")
        null_reason = claim.get("null_reason", "")
        if value is None and not null_reason:
            errors.append(
                f"candidate_claims[{i}] (claim_id={claim_id}): "
                f"value is null but null_reason is empty"
            )

        # Validate timestamp: as_of_utc <= data_cutoff_utc
        if data_cutoff_utc:
            as_of_utc = claim.get("as_of_utc", "")
            if as_of_utc and as_of_utc > data_cutoff_utc:
                errors.append(
                    f"candidate_claims[{i}] (claim_id={claim_id}): "
                    f"as_of_utc '{as_of_utc}' is after data_cutoff_utc '{data_cutoff_utc}'"
                )

        # Check source_doc_refs
        source_doc_refs = claim.get("source_doc_refs", [])
        if not source_doc_refs:
            errors.append(
                f"candidate_claims[{i}] (claim_id={claim_id}): "
                f"source_doc_refs is empty (must reference at least one doc)"
            )

        # Validate each doc ref
        for j, ref in enumerate(source_doc_refs):
            if not isinstance(ref, dict):
                errors.append(
                    f"candidate_claims[{i}] (claim_id={claim_id}): "
                    f"source_doc_refs[{j}] is not a dict"
                )
                continue

            ref_doc_id = ref.get("doc_id")
            if not ref_doc_id:
                errors.append(
                    f"candidate_claims[{i}] (claim_id={claim_id}): "
                    f"source_doc_refs[{j}] missing doc_id"
                )
                continue

            if ref_doc_id not in valid_doc_ids:
                errors.append(
                    f"candidate_claims[{i}] (claim_id={claim_id}): "
                    f"source_doc_refs[{j}] references unknown doc_id '{ref_doc_id}'"
                )

        # Validate and normalize using path registry
        if normalize_enums and 'registry' in locals():
            normalized_claim, claim_errors = registry.validate_claim_path(claim)
            if claim_errors:
                for err in claim_errors:
                    errors.append(f"candidate_claims[{i}]: {err}")
            normalized_claims.append(normalized_claim)
        else:
            normalized_claims.append(claim)

    if errors:
        raise ValueError(
            f"Candidate claims validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return normalized_claims


def import_bundle(bundle_path: str, out_dir: str) -> None:
    """
    Import a Deep Research bundle into JSONL format.

    Args:
        bundle_path: Path to bundle JSON file
        out_dir: Output directory for JSONL files

    Raises:
        ValueError: If validation fails
        FileNotFoundError: If bundle file not found
    """
    # Load bundle
    with open(bundle_path, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    # Check top-level keys
    required_keys = ["run_manifest", "source_index", "evidence_docs", "candidate_claims"]
    missing = [k for k in required_keys if k not in bundle]
    if missing:
        raise ValueError(f"Bundle missing required keys: {', '.join(missing)}")

    run_manifest = bundle["run_manifest"]
    source_index = bundle["source_index"]
    evidence_docs = bundle["evidence_docs"]
    candidate_claims = bundle["candidate_claims"]

    # Extract data_cutoff for timestamp validation
    data_cutoff_utc = run_manifest.get("data_cutoff_utc")

    # Validate
    print(f"Validating {len(evidence_docs)} evidence docs...")
    valid_doc_ids = validate_evidence_docs(evidence_docs)

    print(f"Validating {len(candidate_claims)} candidate claims...")
    print(f"  - Checking path registry and normalizing enums...")
    normalized_claims = validate_candidate_claims(candidate_claims, valid_doc_ids, data_cutoff_utc)

    # Use normalized claims for output
    candidate_claims = normalized_claims

    # Create output directory
    os.makedirs(out_dir, exist_ok=True)

    # Write evidence_docs.jsonl
    evidence_path = os.path.join(out_dir, "evidence_docs.jsonl")
    with open(evidence_path, "w", encoding="utf-8") as f:
        for doc in evidence_docs:
            f.write(json.dumps(doc) + "\n")
    print(f"Wrote {len(evidence_docs)} evidence docs to {evidence_path}")

    # Write claims_deep_research.jsonl
    claims_path = os.path.join(out_dir, "claims_deep_research.jsonl")
    with open(claims_path, "w", encoding="utf-8") as f:
        for claim in candidate_claims:
            f.write(json.dumps(claim) + "\n")
    print(f"Wrote {len(candidate_claims)} claims to {claims_path}")

    # Write source_index.json
    source_index_path = os.path.join(out_dir, "source_index.json")
    with open(source_index_path, "w", encoding="utf-8") as f:
        json.dump(source_index, f, indent=2)
    print(f"Wrote source index to {source_index_path}")

    # Write run_manifest.json
    manifest_path = os.path.join(out_dir, "run_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(run_manifest, f, indent=2)
    print(f"Wrote run manifest to {manifest_path}")

    print(f"\n✓ Import successful. Output in {out_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Import Deep Research JSON bundle into JSONL format"
    )
    parser.add_argument(
        "--bundle",
        required=True,
        help="Path to Deep Research bundle JSON file"
    )
    parser.add_argument(
        "--out_dir",
        required=True,
        help="Output directory for JSONL files (e.g., runs/RUN_20260111_1200)"
    )

    args = parser.parse_args()

    try:
        import_bundle(args.bundle, args.out_dir)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

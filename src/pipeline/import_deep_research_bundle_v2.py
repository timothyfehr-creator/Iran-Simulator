"""
Import Deep Research JSON bundle into JSONL format for compilation.

NEW IN V2:
- Strict cutoff enforcement (drop docs/claims after cutoff)
- claim_class normalization ("FACT" -> "HARD_FACT")
- Specific enum validation (internet_status, intensity_trend)
- Null claims handling with defaults
- Timestamp QA warnings
- import_warnings.json output

Usage:
    python -m src.pipeline.import_deep_research_bundle_v2 \
        --bundle <bundle.json> \
        --out_dir <runs/RUN_YYYYMMDD_HHMM/>

Outputs:
    - evidence_docs.jsonl
    - claims_deep_research.jsonl
    - source_index.json
    - run_manifest.json
    - import_warnings.json (NEW)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Set, List, Any, Optional, Tuple

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

    STRICT CUTOFF ENFORCEMENT:
    - Drop docs where published_at_utc > data_cutoff_utc
    - Drop docs where retrieved_at_utc > data_cutoff_utc
    - Warn about timestamp anomalies (retrieved < published)

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
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate candidate_claims array and normalize enum values.

    NEW BEHAVIORS:
    - Drop claims referencing dropped docs
    - Normalize claim_class: "FACT" -> "HARD_FACT"
    - Validate specific enums (internet_status, intensity_trend)
    - Allow null claims with empty source_doc_refs if null_reason provided
    - Fill defaults for null claims (source_grade=C3, confidence=LOW, triangulated=false)

    Args:
        candidate_claims: List of claims to validate
        valid_doc_ids: Set of valid document IDs (after cutoff filtering)
        data_cutoff_utc: Optional data cutoff timestamp from run_manifest
        normalize_enums: Whether to normalize enum values to uppercase

    Returns:
        (normalized_claims, warnings)

    Raises:
        ValueError: If validation fails
    """
    claim_ids: Set[str] = set()
    errors: List[str] = []
    warnings: List[Dict[str, Any]] = []
    normalized_claims: List[Dict[str, Any]] = []

    # Load path registry for validation
    try:
        registry = load_default_registry()
    except Exception as e:
        errors.append(f"Failed to load path registry: {e}")
        registry = None

    # Define allowed enums for specific paths
    ENUM_RULES = {
        "current_state.information_environment.internet_status.current": {
            "allowed": ["BLACKOUT", "SEVERELY_DEGRADED", "PARTIAL", "FUNCTIONAL"]
        },
        "current_state.protest_metrics.current_snapshot.intensity_trend": {
            "allowed": ["ESCALATING", "PLATEAUED", "DECLINING"]
        }
    }

    for i, claim in enumerate(candidate_claims):
        claim_id = claim.get("claim_id")
        if not claim_id:
            errors.append(f"candidate_claims[{i}]: missing claim_id")
            continue

        if claim_id in claim_ids:
            errors.append(f"candidate_claims[{i}]: duplicate claim_id '{claim_id}'")
        claim_ids.add(claim_id)

        # Create a mutable copy
        claim = dict(claim)

        # CLAIM_CLASS NORMALIZATION
        claim_class = claim.get("claim_class")
        if claim_class == "FACT":
            claim["claim_class"] = "HARD_FACT"
            warnings.append({
                "type": "normalized_claim_class",
                "claim_id": claim_id,
                "original": "FACT",
                "normalized": "HARD_FACT"
            })
        elif claim_class not in ["HARD_FACT", "ESTIMATED", "FACTUAL", "SPECULATIVE", "ASSESSMENT", None]:
            errors.append(
                f"candidate_claims[{i}] (claim_id={claim_id}): "
                f"unknown claim_class '{claim_class}'"
            )

        # Required fields
        required = ["path", "as_of_utc", "source_grade", "claim_class"]
        for field in required:
            if field not in claim:
                errors.append(f"candidate_claims[{i}] (claim_id={claim_id}): missing '{field}'")

        # NULL CLAIMS HANDLING
        value = claim.get("value")
        null_reason = claim.get("null_reason", "")
        source_doc_refs = claim.get("source_doc_refs", [])

        if value is None:
            if not null_reason:
                errors.append(
                    f"candidate_claims[{i}] (claim_id={claim_id}): "
                    f"value is null but null_reason is empty"
                )
            else:
                # Allow empty source_doc_refs for null claims with reason
                if not source_doc_refs:
                    # Fill defaults for null claims
                    defaults_applied = {}
                    if "source_grade" not in claim or not claim["source_grade"]:
                        claim["source_grade"] = "C3"
                        defaults_applied["source_grade"] = "C3"
                    if "confidence" not in claim or not claim["confidence"]:
                        claim["confidence"] = "LOW"
                        defaults_applied["confidence"] = "LOW"
                    if "triangulated" not in claim:
                        claim["triangulated"] = False
                        defaults_applied["triangulated"] = False

                    if defaults_applied:
                        warnings.append({
                            "type": "null_claim_defaults_applied",
                            "claim_id": claim_id,
                            "defaults": defaults_applied
                        })
        else:
            # Non-null claims must have source_doc_refs
            if not source_doc_refs:
                errors.append(
                    f"candidate_claims[{i}] (claim_id={claim_id}): "
                    f"source_doc_refs is empty (must reference at least one doc)"
                )

        # Validate timestamp: as_of_utc <= data_cutoff_utc
        if data_cutoff_utc:
            as_of_utc = claim.get("as_of_utc", "")
            if as_of_utc and as_of_utc > data_cutoff_utc:
                errors.append(
                    f"candidate_claims[{i}] (claim_id={claim_id}): "
                    f"as_of_utc '{as_of_utc}' is after data_cutoff_utc '{data_cutoff_utc}'"
                )

        # Validate each doc ref and check for dropped docs
        dropped_refs = []
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
                dropped_refs.append(ref_doc_id)

        # DROP CLAIMS referencing dropped docs
        if dropped_refs:
            warnings.append({
                "type": "dropped_claim",
                "claim_id": claim_id,
                "reason": f"references dropped doc_id(s): {', '.join(dropped_refs)}"
            })
            continue  # Skip this claim

        # ENUM VALIDATION AND NORMALIZATION
        path = claim.get("path", "")
        if path in ENUM_RULES and value is not None:
            allowed_values = ENUM_RULES[path]["allowed"]
            if isinstance(value, str):
                original_value = value
                normalized_value = value.upper()
                if normalized_value in allowed_values:
                    if normalized_value != original_value:
                        claim["value"] = normalized_value
                        warnings.append({
                            "type": "normalized_enum",
                            "claim_id": claim_id,
                            "path": path,
                            "original": original_value,
                            "normalized": normalized_value
                        })
                    else:
                        claim["value"] = normalized_value
                else:
                    errors.append(
                        f"candidate_claims[{i}] (claim_id={claim_id}): "
                        f"path '{path}' has invalid enum value '{value}' (allowed: {allowed_values})"
                    )

        # Validate and normalize using path registry (OPTIONAL - only for registered paths)
        # NOTE: We don't reject unknown paths, only validate/normalize known ones
        if normalize_enums and registry:
            path_info = registry.get_path_info(path)
            if path_info:
                # Path is registered, validate it
                normalized_claim, claim_errors = registry.validate_claim_path(claim)
                if claim_errors:
                    for err in claim_errors:
                        warnings.append({
                            "type": "path_registry_warning",
                            "claim_id": claim_id,
                            "warning": err
                        })
                normalized_claims.append(normalized_claim)
            else:
                # Path not registered, but that's OK - just pass through
                normalized_claims.append(claim)
        else:
            normalized_claims.append(claim)

    if errors:
        raise ValueError(
            f"Candidate claims validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return normalized_claims, warnings


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

    # Validate evidence docs (with cutoff enforcement)
    print(f"Validating {len(evidence_docs)} evidence docs...")
    valid_doc_ids, kept_docs, doc_warnings = validate_evidence_docs(evidence_docs, data_cutoff_utc)
    print(f"  - Kept {len(kept_docs)} docs, dropped {len(evidence_docs) - len(kept_docs)} docs")

    # Validate claims (with normalization and dropped doc filtering)
    print(f"Validating {len(candidate_claims)} candidate claims...")
    print(f"  - Checking path registry and normalizing enums...")
    normalized_claims, claim_warnings = validate_candidate_claims(
        candidate_claims, valid_doc_ids, data_cutoff_utc
    )
    print(f"  - Kept {len(normalized_claims)} claims, dropped {len(candidate_claims) - len(normalized_claims)} claims")

    # Combine all warnings
    all_warnings = doc_warnings + claim_warnings

    # Create output directory
    os.makedirs(out_dir, exist_ok=True)

    # Write evidence_docs.jsonl (only kept docs)
    evidence_path = os.path.join(out_dir, "evidence_docs.jsonl")
    with open(evidence_path, "w", encoding="utf-8") as f:
        for doc in kept_docs:
            f.write(json.dumps(doc) + "\n")
    print(f"Wrote {len(kept_docs)} evidence docs to {evidence_path}")

    # Write claims_deep_research.jsonl (only kept claims)
    claims_path = os.path.join(out_dir, "claims_deep_research.jsonl")
    with open(claims_path, "w", encoding="utf-8") as f:
        for claim in normalized_claims:
            f.write(json.dumps(claim) + "\n")
    print(f"Wrote {len(normalized_claims)} claims to {claims_path}")

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

    # Write import_warnings.json (NEW)
    warnings_path = os.path.join(out_dir, "import_warnings.json")
    with open(warnings_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_warnings": len(all_warnings),
            "warnings": all_warnings,
            "summary": {
                "dropped_docs": len([w for w in all_warnings if w["type"] == "dropped_evidence_doc"]),
                "dropped_claims": len([w for w in all_warnings if w["type"] == "dropped_claim"]),
                "normalized_claim_classes": len([w for w in all_warnings if w["type"] == "normalized_claim_class"]),
                "normalized_enums": len([w for w in all_warnings if w["type"] == "normalized_enum"]),
                "null_claim_defaults": len([w for w in all_warnings if w["type"] == "null_claim_defaults_applied"]),
                "timestamp_anomalies": len([w for w in all_warnings if w["type"] == "timestamp_anomaly"])
            }
        }, f, indent=2)
    print(f"Wrote import warnings to {warnings_path}")

    print(f"\n✓ Import successful. Output in {out_dir}")
    if all_warnings:
        print(f"  ⚠ {len(all_warnings)} warnings recorded in import_warnings.json")


def main():
    parser = argparse.ArgumentParser(
        description="Import Deep Research JSON bundle into JSONL format (v2 with strict cutoff enforcement)"
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

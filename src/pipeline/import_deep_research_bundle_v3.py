"""
Import Deep Research JSON bundle into JSONL format for compilation.

NEW IN V3:
- STRICT path registry enforcement (hard fail for unknown paths)
- Units validation per path
- Coverage gates (min docs, Farsi requirement, source diversity)
- All V2 features (cutoff, normalization, null handling)

Usage:
    python -m src.pipeline.import_deep_research_bundle_v3 \
        --bundle <bundle.json> \
        --out_dir <runs/RUN_YYYYMMDD_HHMM/>

Outputs:
    - evidence_docs.jsonl
    - claims_deep_research.jsonl
    - source_index.json
    - run_manifest.json
    - import_warnings.json
    - coverage_report.json (NEW)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Dict, Set, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Import path registry
try:
    from pipeline.path_registry import PathRegistry
except ImportError:
    # Handle when run as script
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from pipeline.path_registry import PathRegistry


def load_v2_registry() -> PathRegistry:
    """Load path registry v2 with strict enforcement."""
    current_dir = os.path.dirname(__file__)
    repo_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    registry_path = os.path.join(repo_root, "config", "path_registry_v2.json")

    if not os.path.exists(registry_path):
        raise FileNotFoundError(f"Path registry v2 not found at {registry_path}")

    return PathRegistry(registry_path)


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
            # Check for None specifically (0.0 is a valid value meaning "no translation done")
            if translation_confidence is None:
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


def check_coverage_gates(
    kept_docs: List[Dict[str, Any]],
    source_index: List[Dict[str, Any]],
    registry_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Check coverage gates for evidence quality.

    Gates:
    - Minimum total docs (default: 40)
    - Minimum Farsi docs (default: 10)
    - Source diversity buckets (wires, NGOs, regime, Persian services, OSINT, internet monitoring)

    Returns:
        Coverage report with status and details
    """
    gates = registry_config.get("coverage_gates", {})
    min_docs = gates.get("min_evidence_docs", 40)
    min_farsi = gates.get("min_farsi_docs", 10)
    min_buckets = gates.get("min_buckets", 3)

    # Count docs by language
    total_docs = len(kept_docs)
    farsi_docs = sum(1 for doc in kept_docs if doc.get("language") == "fa")

    # Map sources to buckets
    bucket_mapping = registry_config.get("source_type_buckets", {}).get("bucket_mapping", {})
    source_to_bucket = {}
    for bucket, orgs in bucket_mapping.items():
        for org in orgs:
            source_to_bucket[org.lower()] = bucket

    # Count buckets represented
    buckets_found = set()
    for doc in kept_docs:
        org = doc.get("organization", "")
        # Try exact match first, then partial match
        for source_key, bucket in source_to_bucket.items():
            if source_key in org.lower():
                buckets_found.add(bucket)
                break

    # Build report
    failures = []
    warnings = []

    if total_docs < min_docs:
        failures.append(f"Insufficient evidence: {total_docs} docs (minimum: {min_docs})")

    if farsi_docs < min_farsi:
        failures.append(f"Insufficient Farsi docs: {farsi_docs} (minimum: {min_farsi})")

    if len(buckets_found) < min_buckets:
        warnings.append(
            f"Limited source diversity: {len(buckets_found)} buckets (recommended: {min_buckets}+)"
        )

    status = "FAIL" if failures else ("WARN" if warnings else "PASS")

    return {
        "status": status,
        "total_docs": total_docs,
        "farsi_docs": farsi_docs,
        "buckets_found": sorted(list(buckets_found)),
        "bucket_count": len(buckets_found),
        "gates": {
            "min_evidence_docs": min_docs,
            "min_farsi_docs": min_farsi,
            "min_buckets": min_buckets
        },
        "failures": failures,
        "warnings": warnings
    }


def check_daily_update_gates(
    kept_docs: List[Dict[str, Any]],
    data_cutoff_utc: Optional[str],
    source_config: Optional[Dict[str, Dict]] = None
) -> Dict[str, Any]:
    """
    Rolling-window coverage gates using src/ingest/coverage.evaluate_coverage().

    UPDATED: Now uses window-based coverage instead of date-specific checks.
    Each bucket has a rolling window (36h-72h) to accommodate varying publication frequencies.

    Gates:
    - Each bucket checked against its BUCKET_WINDOWS threshold (e.g., 72h for most)
    - Non-critical bucket misses → WARN
    - Critical bucket misses (≥2) → FAIL

    Args:
        kept_docs: List of validated evidence documents
        data_cutoff_utc: Data cutoff timestamp (ISO 8601) - used as reference time
        source_config: Optional source configuration mapping source_id -> config.
                       If not provided, loads from config/sources.yaml.

    Returns:
        Coverage report with counts_by_bucket, buckets_missing, bucket_details, status
    """
    from datetime import datetime, timezone

    # Import coverage module
    try:
        from src.ingest.coverage import (
            evaluate_coverage,
            load_source_config_from_yaml,
            BUCKET_WINDOWS,
            CRITICAL_BUCKETS
        )
    except ImportError:
        # Handle when run as script
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        from src.ingest.coverage import (
            evaluate_coverage,
            load_source_config_from_yaml,
            BUCKET_WINDOWS,
            CRITICAL_BUCKETS
        )

    if not data_cutoff_utc:
        return {
            "counts_by_bucket": {},
            "buckets_missing": [],
            "bucket_details": {},
            "status": "SKIP",
            "status_reason": "No data cutoff specified, skipping coverage gates",
            "warnings": ["No data cutoff specified"]
        }

    # Parse reference time from cutoff
    try:
        reference_time = datetime.fromisoformat(data_cutoff_utc.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return {
            "counts_by_bucket": {},
            "buckets_missing": [],
            "bucket_details": {},
            "status": "SKIP",
            "status_reason": f"Invalid cutoff format: {data_cutoff_utc}",
            "warnings": [f"Invalid cutoff format: {data_cutoff_utc}"]
        }

    # Load source config if not provided
    if source_config is None:
        try:
            source_config = load_source_config_from_yaml()
        except Exception as e:
            # Fallback: create minimal config from doc source_ids
            source_config = _build_source_config_from_docs(kept_docs)

    # Run window-based coverage evaluation
    report = evaluate_coverage(
        docs=kept_docs,
        source_config=source_config,
        reference_time=reference_time,
        run_id=data_cutoff_utc[:10] if data_cutoff_utc else ""
    )

    # Build warnings for non-critical missing buckets
    warnings = []
    for bucket in report.buckets_missing:
        window_hours = BUCKET_WINDOWS.get(bucket, 72)
        if bucket in CRITICAL_BUCKETS:
            warnings.append(f"CRITICAL: No docs in {bucket} bucket (window: {window_hours}h)")
        else:
            warnings.append(f"No docs in {bucket} bucket (window: {window_hours}h)")

    return {
        "counts_by_bucket": report.counts_by_bucket,
        "buckets_missing": report.buckets_missing,
        "buckets_present": report.buckets_present,
        "bucket_details": report.bucket_details,
        "status": report.status,
        "status_reason": report.status_reason,
        "warnings": warnings,
        "reference_time_utc": report.reference_time_utc,
        "total_docs": report.total_docs
    }


def _build_source_config_from_docs(docs: List[Dict[str, Any]]) -> Dict[str, Dict]:
    """
    Build minimal source config from document source_ids for coverage evaluation.
    Maps common source patterns to buckets.
    """
    # Default bucket mappings based on common source patterns
    PATTERN_TO_BUCKET = {
        "isw": "osint_thinktank",
        "ctp": "osint_thinktank",
        "hrana": "ngo_rights",
        "amnesty": "ngo_rights",
        "hrw": "ngo_rights",
        "ihr": "ngo_rights",
        "irna": "regime_outlets",
        "fars": "regime_outlets",
        "tasnim": "regime_outlets",
        "mehr": "regime_outlets",
        "presstv": "regime_outlets",
        "iranintl": "persian_services",
        "radiofarda": "persian_services",
        "bbcpersian": "persian_services",
        "netblocks": "internet_monitoring",
        "ooni": "internet_monitoring",
        "ioda": "internet_monitoring",
        "bonbast": "econ_fx",
        "tgju": "econ_fx",
    }

    source_config = {}
    for doc in docs:
        source_id = doc.get("source_id", "").lower()
        if source_id.startswith("src_"):
            source_id = source_id[4:]

        # Find matching bucket
        bucket = None
        for pattern, b in PATTERN_TO_BUCKET.items():
            if pattern in source_id:
                bucket = b
                break

        if bucket and source_id not in source_config:
            source_config[source_id] = {"bucket": bucket, "name": source_id}

    return source_config


def _load_health_summary() -> Optional[Dict[str, Any]]:
    """
    Load health summary from the latest tracker state if available.

    Returns:
        Health summary dict or None if not available
    """
    health_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "runs", "_meta", "sources_health.json"
    )

    if not os.path.exists(health_path):
        return None

    try:
        with open(health_path, 'r') as f:
            health_data = json.load(f)

        # Build summary from health data
        sources_ok = []
        sources_degraded = []
        sources_down = []

        for source_id, source_health in health_data.items():
            status = source_health.get('status', 'OK')
            if status == 'DOWN':
                sources_down.append(source_id)
            elif status == 'DEGRADED':
                sources_degraded.append(source_id)
            else:
                sources_ok.append(source_id)

        # Determine overall status
        if sources_down:
            overall_status = 'DOWN'
        elif sources_degraded:
            overall_status = 'DEGRADED'
        else:
            overall_status = 'OK'

        return {
            'overall_status': overall_status,
            'sources_ok': len(sources_ok),
            'sources_degraded': len(sources_degraded),
            'sources_down': len(sources_down),
            'degraded_sources': sources_degraded,
            'down_sources': sources_down
        }
    except Exception:
        return None


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
    """
    claim_ids: Set[str] = set()
    warnings: List[Dict[str, Any]] = []
    normalized_claims: List[Dict[str, Any]] = []

    # Load V2 path registry for STRICT validation
    try:
        registry = load_v2_registry()
    except Exception as e:
        raise ValueError(f"Failed to load path registry v2: {e}")

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
            warnings.append({
                "type": "dropped_claim",
                "claim_id": f"candidate_claims[{i}]",
                "reason": "missing claim_id"
            })
            continue

        if claim_id in claim_ids:
            warnings.append({
                "type": "dropped_claim",
                "claim_id": claim_id,
                "reason": f"duplicate claim_id '{claim_id}'"
            })
            continue
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
            warnings.append({
                "type": "dropped_claim",
                "claim_id": claim_id,
                "reason": f"unknown claim_class '{claim_class}'"
            })
            continue

        # STRICT PATH VALIDATION (V3)
        path = claim.get("path", "")
        if not registry.is_valid_path(path):
            warnings.append({
                "type": "dropped_claim",
                "claim_id": claim_id,
                "reason": f"unknown path '{path}' (not in path_registry_v2.json)"
            })
            continue

        # UNITS VALIDATION (V3)
        units = claim.get("units")
        path_info = registry.get_path_info(path)
        if path_info:
            expected_units = path_info.get("units")
            if expected_units and units != expected_units:
                warnings.append({
                    "type": "dropped_claim",
                    "claim_id": claim_id,
                    "reason": f"path '{path}' has units '{units}' but expected '{expected_units}'"
                })
                continue

        # Required fields
        required = ["path", "as_of_utc", "source_grade", "claim_class"]
        missing_fields = [field for field in required if field not in claim]
        if missing_fields:
            warnings.append({
                "type": "dropped_claim",
                "claim_id": claim_id,
                "reason": f"missing required fields: {', '.join(missing_fields)}"
            })
            continue

        # NULL CLAIMS HANDLING
        value = claim.get("value")
        null_reason = claim.get("null_reason", "")
        source_doc_refs = claim.get("source_doc_refs", [])

        if value is None:
            if not null_reason:
                warnings.append({
                    "type": "dropped_claim",
                    "claim_id": claim_id,
                    "reason": "value is null but null_reason is empty"
                })
                continue
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
                warnings.append({
                    "type": "dropped_claim",
                    "claim_id": claim_id,
                    "reason": "source_doc_refs is empty (must reference at least one doc)"
                })
                continue

        # Validate timestamp: as_of_utc <= data_cutoff_utc
        if data_cutoff_utc:
            as_of_utc = claim.get("as_of_utc", "")
            if as_of_utc and as_of_utc > data_cutoff_utc:
                warnings.append({
                    "type": "dropped_claim",
                    "claim_id": claim_id,
                    "reason": f"as_of_utc '{as_of_utc}' is after data_cutoff_utc '{data_cutoff_utc}'"
                })
                continue

        # Validate each doc ref and check for dropped docs
        dropped_refs = []
        bad_ref_format = False
        for j, ref in enumerate(source_doc_refs):
            if not isinstance(ref, dict):
                warnings.append({
                    "type": "dropped_claim",
                    "claim_id": claim_id,
                    "reason": f"source_doc_refs[{j}] is not a dict"
                })
                bad_ref_format = True
                break

            ref_doc_id = ref.get("doc_id")
            if not ref_doc_id:
                warnings.append({
                    "type": "dropped_claim",
                    "claim_id": claim_id,
                    "reason": f"source_doc_refs[{j}] missing doc_id"
                })
                bad_ref_format = True
                break

            if ref_doc_id not in valid_doc_ids:
                dropped_refs.append(ref_doc_id)

        if bad_ref_format:
            continue

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
                    warnings.append({
                        "type": "dropped_claim",
                        "claim_id": claim_id,
                        "reason": f"path '{path}' has invalid enum value '{value}' (allowed: {allowed_values})"
                    })
                    continue

        # Validate and normalize using path registry (V3: STRICT - already validated above)
        # At this point, path is guaranteed to be valid (or we would have continued earlier)
        if normalize_enums:
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
            normalized_claims.append(claim)

    total_input = len(candidate_claims)
    dropped_count = len([w for w in warnings if w.get("type") == "dropped_claim"])
    if dropped_count:
        drop_rate = dropped_count / total_input if total_input else 0
        logger.warning(
            f"Dropped {dropped_count}/{total_input} claims "
            f"({drop_rate:.0%}) — see warnings"
        )
    if not normalized_claims and total_input > 0:
        logger.error(
            f"All {total_input} candidate claims were dropped during validation"
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

    # Extract data_cutoff for timestamp validation (check both run_manifest and top-level)
    data_cutoff_utc = run_manifest.get("data_cutoff_utc") or bundle.get("data_cutoff_utc")

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

    # CHECK QUALITY GATES (min-docs, farsi, buckets)
    print(f"Checking quality gates...")
    registry = load_v2_registry()
    registry_config = json.load(open(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config", "path_registry_v2.json"
    )))
    quality_gates = check_coverage_gates(kept_docs, source_index, registry_config)
    print(f"  - Quality gates status: {quality_gates['status']}")
    if quality_gates['failures']:
        print(f"  - FAILURES:")
        for failure in quality_gates['failures']:
            print(f"    ✗ {failure}")
    if quality_gates['warnings']:
        print(f"  - WARNINGS:")
        for warning in quality_gates['warnings']:
            print(f"    ⚠ {warning}")

    # CHECK ROLLING-WINDOW COVERAGE (primary coverage status)
    print(f"Checking rolling-window coverage...")
    window_coverage = check_daily_update_gates(kept_docs, data_cutoff_utc)
    print(f"  - Window coverage status: {window_coverage['status']}")
    if window_coverage['warnings']:
        for warning in window_coverage['warnings']:
            print(f"    ⚠ {warning}")
    if window_coverage.get('buckets_present'):
        print(f"  - Buckets present: {', '.join(window_coverage['buckets_present'])}")
    if window_coverage.get('buckets_missing'):
        print(f"  - Buckets missing: {', '.join(window_coverage['buckets_missing'])}")

    # Load health summary from tracker if available
    health_summary = _load_health_summary()

    # BUILD UNIFIED COVERAGE REPORT (window-based at top level)
    coverage_report = {
        # Top-level: rolling-window coverage (primary status)
        "status": window_coverage.get('status', 'UNKNOWN'),
        "status_reason": window_coverage.get('status_reason', ''),
        "counts_by_bucket": window_coverage.get('counts_by_bucket', {}),
        "buckets_missing": window_coverage.get('buckets_missing', []),
        "buckets_present": window_coverage.get('buckets_present', []),
        "bucket_details": window_coverage.get('bucket_details', {}),
        "reference_time_utc": window_coverage.get('reference_time_utc', ''),
        "total_docs": window_coverage.get('total_docs', len(kept_docs)),
        "warnings": window_coverage.get('warnings', []),
        # Quality gates (min-docs, farsi, buckets) under separate field
        "quality_gates": quality_gates,
        # Health summary if available
        "health_summary": health_summary
    }

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

    # Write coverage_report.json (V3 NEW)
    coverage_path = os.path.join(out_dir, "coverage_report.json")
    with open(coverage_path, "w", encoding="utf-8") as f:
        json.dump(coverage_report, f, indent=2)
    print(f"Wrote coverage report to {coverage_path}")

    print(f"\n✓ Import successful. Output in {out_dir}")
    if all_warnings:
        print(f"  ⚠ {len(all_warnings)} warnings recorded in import_warnings.json")
    if coverage_report['status'] == 'FAIL':
        print(f"  ✗ COVERAGE GATES FAILED - see coverage_report.json")
    elif coverage_report['status'] == 'WARN':
        print(f"  ⚠ Coverage warnings - see coverage_report.json")


def main():
    parser = argparse.ArgumentParser(
        description="Import Deep Research JSON bundle into JSONL format (v3 with strict path/units validation and coverage gates)"
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

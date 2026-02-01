"""
Compile claims into a compiled_intel.json artifact (V2).

NEW IN V2:
- Sophisticated merge logic with priority ordering
- Conflict handling for same-grade competing values
- Enhanced QA report with import warnings
- Uses import_deep_research_bundle_v2

Merge priority (per path+selector):
  1. Best source_grade (A1 > A2 > B1 > B2 > C1 > C2 > C3 > D4)
  2. triangulated=true
  3. Highest confidence (HIGH > MODERATE > LOW)
  4. Latest published_at_utc from supporting evidence
  5. Lexicographic claim_id (stable tiebreak)

Conflict handling:
  - If conflict_group exists AND competing values differ materially:
    - If one has strictly better source_grade: take it
    - If source_grade ties: set value to null, record in merge_report

Always emits:
  - compiled_intel.json
  - merge_report.json
  - qa_report.json
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # add src/ to path

import argparse
import json
import tempfile
from typing import Any, Dict, List, Tuple, Optional
from collections import defaultdict

from pipeline.qa import qa_compiled_intel
from pipeline.import_deep_research_bundle_v3 import import_bundle


# Deterministic tiebreak policy for reproducibility
# This is the exact order used when selecting winner from competing claims
DETERMINISTIC_TIEBREAK_POLICY = [
    "source_grade",      # A1 > A2 > B1 > B2 > C1 > C2 > C3 > D4
    "triangulated",      # True > False
    "confidence",        # HIGH > MODERATE > LOW
    "latest_published_at",  # Newer wins (ISO timestamp comparison)
    "claim_id"           # Lexicographic (stable final tiebreak)
]


def _grade_score(source_grade: str) -> int:
    """
    Convert combined grade like 'A1', 'B2' to a score where higher is better.
    Access is primary (A>B>C>D), bias is secondary (1 best).

    A1=44, A2=43, A3=42, A4=41
    B1=34, B2=33, B3=32, B4=31
    C1=24, C2=23, C3=22, C4=21
    D1=14, D2=13, D3=12, D4=11
    """
    if not source_grade or len(source_grade) < 2:
        return 0
    access = source_grade[0].upper()
    bias = source_grade[1]
    access_score = {"A": 4, "B": 3, "C": 2, "D": 1}.get(access, 0)
    try:
        bias_score = 5 - int(bias)  # 1->4, 4->1
    except Exception:
        bias_score = 0
    return access_score * 10 + bias_score


def _confidence_score(confidence: str) -> int:
    """Convert confidence to numeric score (higher is better)."""
    return {"HIGH": 3, "MODERATE": 2, "MEDIUM": 2, "LOW": 1}.get(confidence, 0)


def _get_latest_published_at(claim: Dict[str, Any], evidence_docs: List[Dict[str, Any]]) -> str:
    """
    Get the latest published_at_utc from any evidence doc referenced by this claim.
    Returns empty string if no dates found.
    """
    source_doc_refs = claim.get("source_doc_refs", [])
    doc_id_to_date = {doc["doc_id"]: doc.get("published_at_utc", "") for doc in evidence_docs}

    dates = []
    for ref in source_doc_refs:
        doc_id = ref.get("doc_id")
        if doc_id and doc_id in doc_id_to_date:
            date = doc_id_to_date[doc_id]
            if date:
                dates.append(date)

    return max(dates) if dates else ""


def _merge_claims(
    claims: List[Dict[str, Any]],
    evidence_docs: List[Dict[str, Any]]
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Select winner from competing claims for the same (path, selector).

    Priority:
      1. Best source_grade
      2. triangulated=true
      3. Highest confidence
      4. Latest published_at_utc
      5. Lexicographic claim_id

    Conflict handling:
      - If conflict_group exists and values differ with tied source_grade: null value

    Returns:
        (winner_claim, merge_note)
    """
    if len(claims) == 1:
        return claims[0], {"conflict": False, "candidates": 1}

    # Check for conflict_group and material differences
    conflict_group = claims[0].get("conflict_group")
    if conflict_group:
        # Check if all claims have same conflict_group
        same_group = all(c.get("conflict_group") == conflict_group for c in claims)
        if same_group:
            # Check if values differ materially
            values = [c.get("value") for c in claims]
            if len(set(str(v) for v in values)) > 1:
                # Values differ - check if source_grades tie
                grades = [_grade_score(c.get("source_grade", "")) for c in claims]
                if len(set(grades)) == 1 or max(grades) - min(grades) == 0:
                    # Source grades tie - return null value
                    null_claim = dict(claims[0])
                    null_claim["value"] = None
                    null_claim["null_reason"] = f"CONFLICT: {len(claims)} claims with same source_grade have materially different values"
                    return null_claim, {
                        "conflict": True,
                        "reason": "source_grade tie with materially different values",
                        "candidates": len(claims),
                        "conflicting_values": values
                    }

    # Normal merge with priority ordering
    def sort_key(c):
        return (
            _grade_score(c.get("source_grade", "")),  # Higher is better
            c.get("triangulated", False),  # True > False
            _confidence_score(c.get("confidence", "")),  # Higher is better
            _get_latest_published_at(c, evidence_docs),  # Latest first (lexicographic)
            c.get("claim_id", "")  # Stable tiebreak
        )

    claims_sorted = sorted(claims, key=sort_key, reverse=True)
    winner = claims_sorted[0]

    merge_note = {
        "conflict": False,
        "candidates": len(claims),
        "winner_reasons": {
            "source_grade": winner.get("source_grade"),
            "triangulated": winner.get("triangulated"),
            "confidence": winner.get("confidence"),
            "latest_published": _get_latest_published_at(winner, evidence_docs),
            "claim_id": winner.get("claim_id")
        },
        "all_candidates": [
            {
                "claim_id": c.get("claim_id"),
                "source_grade": c.get("source_grade"),
                "triangulated": c.get("triangulated"),
                "confidence": c.get("confidence"),
                "value": c.get("value")
            }
            for c in claims_sorted
        ]
    }

    return winner, merge_note


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main():
    p = argparse.ArgumentParser(description="Compile claims into compiled intel JSON (v2)")

    # Mutually exclusive: --claims OR --bundle
    input_group = p.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--claims", nargs="+", help="One or more claims_*.jsonl files")
    input_group.add_argument("--bundle", help="Deep Research bundle JSON (shortcut: imports then compiles)")

    p.add_argument("--template", required=True, help="Template intel JSON to copy metadata/shape from")
    p.add_argument("--outdir", default="runs/compiled", help="Output directory")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # If --bundle provided, import it first
    import_warnings = None
    evidence_docs = []

    if args.bundle:
        print(f"Importing bundle: {args.bundle}")
        temp_import_dir = os.path.join(args.outdir, "_bundle_import")
        import_bundle(args.bundle, temp_import_dir)

        # Use the imported claims
        claims_files = [os.path.join(temp_import_dir, "claims_deep_research.jsonl")]
        print(f"Bundle imported. Compiling claims from {claims_files[0]}")

        # Load import warnings for QA report
        warnings_path = os.path.join(temp_import_dir, "import_warnings.json")
        if os.path.exists(warnings_path):
            with open(warnings_path, "r") as f:
                import_warnings = json.load(f)

        # Load evidence docs for merge logic
        evidence_path = os.path.join(temp_import_dir, "evidence_docs.jsonl")
        if os.path.exists(evidence_path):
            evidence_docs = load_jsonl(evidence_path)
    else:
        claims_files = args.claims

    template = json.load(open(args.template, "r", encoding="utf-8"))
    compiled: Dict[str, Any] = dict(template)
    compiled["_schema_version"] = compiled.get("_schema_version", "0.1.0")
    compiled["claims_ledger"] = {"claims": []}

    all_claims: List[Dict[str, Any]] = []
    for cpath in claims_files:
        all_claims.extend(load_jsonl(cpath))

    # Group by (path, selector_json)
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for c in all_claims:
        sel = c.get("selector")
        sel_key = json.dumps(sel, sort_keys=True) if sel is not None else "null"
        groups[(c.get("path"), sel_key)].append(c)

    winners: List[Dict[str, Any]] = []
    merge_notes: List[Dict[str, Any]] = []

    for (path_key, sel_key), claims in groups.items():
        winner, merge_note = _merge_claims(claims, evidence_docs)
        winners.append(winner)

        merge_notes.append({
            "path": path_key,
            "selector": None if sel_key == "null" else json.loads(sel_key),
            "winner_claim_id": winner.get("claim_id"),
            **merge_note
        })

    compiled["claims_ledger"]["claims"] = winners

    # Optional: materialize selector-less claims into a flat dict for convenience
    compiled_fields: Dict[str, Any] = {}
    for c in winners:
        if c.get("selector") in (None, {}):
            compiled_fields[c.get("path")] = c.get("value")
    compiled["compiled_fields"] = compiled_fields

    compiled_path = os.path.join(args.outdir, "compiled_intel.json")
    with open(compiled_path, "w", encoding="utf-8") as f:
        json.dump(compiled, f, indent=2)

    merge_report_path = os.path.join(args.outdir, "merge_report.json")
    with open(merge_report_path, "w", encoding="utf-8") as f:
        json.dump({
            "merge_notes": merge_notes,
            "claim_count": len(all_claims),
            "winner_count": len(winners),
            "conflicts_detected": sum(1 for n in merge_notes if n.get("conflict")),
            "gap_notes": [n for n in merge_notes if n.get("conflict")]
        }, f, indent=2)

    # Enhanced QA report
    qa = qa_compiled_intel(compiled)

    # Add import warnings to QA report if available
    if import_warnings:
        qa["import_summary"] = import_warnings.get("summary", {})
        qa["import_warnings_count"] = import_warnings.get("total_warnings", 0)
        qa["dropped_docs"] = len([w for w in import_warnings.get("warnings", []) if w["type"] == "dropped_evidence_doc"])
        qa["dropped_claims"] = len([w for w in import_warnings.get("warnings", []) if w["type"] == "dropped_claim"])
        qa["normalized_fields"] = {
            "claim_classes": len([w for w in import_warnings.get("warnings", []) if w["type"] == "normalized_claim_class"]),
            "enums": len([w for w in import_warnings.get("warnings", []) if w["type"] == "normalized_enum"]),
            "null_defaults": len([w for w in import_warnings.get("warnings", []) if w["type"] == "null_claim_defaults_applied"])
        }
        qa["timestamp_anomalies"] = len([w for w in import_warnings.get("warnings", []) if w["type"] == "timestamp_anomaly"])

        # Include specific details
        qa["import_warnings_details"] = import_warnings.get("warnings", [])

    qa_report_path = os.path.join(args.outdir, "qa_report.json")
    with open(qa_report_path, "w", encoding="utf-8") as f:
        json.dump(qa, f, indent=2)

    if qa["status"] != "OK":
        print(f"QA warnings present: {'; '.join(qa.get('errors', []))}")

        # Under STRICT_QA=1, soft-fail (exit 2) — qa_report.json is already written above
        if os.environ.get("STRICT_QA") == "1":
            print("STRICT_QA=1: exiting with soft-fail (exit code 2)")
            sys.exit(2)

    print(f"Wrote: {compiled_path}")
    print(f"Wrote: {merge_report_path}")
    print(f"Wrote: {qa_report_path}")


if __name__ == "__main__":
    main()

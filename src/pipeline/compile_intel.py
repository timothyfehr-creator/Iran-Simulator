"""
Compile claims into a compiled_intel.json artifact.

MVP:
- No web scraping
- Merge rule: best source_grade wins per (path, selector)
- Always emits:
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
from pipeline.import_deep_research_bundle import import_bundle


def _grade_score(source_grade: str) -> int:
    """
    Convert combined grade like 'A1', 'B2' to a score where higher is better.
    Access is primary (A>B>C>D), bias is secondary (1 best).
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
    p = argparse.ArgumentParser(description="Compile claims into compiled intel JSON")

    # Mutually exclusive: --claims OR --bundle
    input_group = p.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--claims", nargs="+", help="One or more claims_*.jsonl files")
    input_group.add_argument("--bundle", help="Deep Research bundle JSON (shortcut: imports then compiles)")

    p.add_argument("--template", required=True, help="Template intel JSON to copy metadata/shape from")
    p.add_argument("--outdir", default="runs/compiled", help="Output directory")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # If --bundle provided, import it first
    if args.bundle:
        print(f"Importing bundle: {args.bundle}")
        temp_import_dir = os.path.join(args.outdir, "_bundle_import")
        import_bundle(args.bundle, temp_import_dir)

        # Use the imported claims
        claims_files = [os.path.join(temp_import_dir, "claims_deep_research.jsonl")]
        print(f"Bundle imported. Compiling claims from {claims_files[0]}")
    else:
        claims_files = args.claims

    template = json.load(open(args.template, "r", encoding="utf-8"))
    compiled: Dict[str, Any] = dict(template)
    compiled["_schema_version"] = compiled.get("_schema_version", "0.1.0")
    compiled["claims_ledger"] = {"claims": []}

    all_claims: List[Dict[str, Any]] = []
    for cpath in claims_files:
        all_claims.extend(load_jsonl(cpath))

    # group by (path, selector_json)
    groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for c in all_claims:
        sel = c.get("selector")
        sel_key = json.dumps(sel, sort_keys=True) if sel is not None else "null"
        groups[(c.get("path"), sel_key)].append(c)

    winners: List[Dict[str, Any]] = []
    merge_notes: List[Dict[str, Any]] = []

    for (path_key, sel_key), claims in groups.items():
        # pick best score
        claims_sorted = sorted(
            claims,
            key=lambda x: (_grade_score(x.get("source_grade", "")), len(x.get("source_ids", []) or [])),
            reverse=True,
        )
        winner = claims_sorted[0]
        winners.append(winner)
        merge_notes.append({
            "path": path_key,
            "selector": None if sel_key == "null" else json.loads(sel_key),
            "winner_claim_id": winner.get("claim_id"),
            "candidates": [{"claim_id": c.get("claim_id"), "source_grade": c.get("source_grade")} for c in claims_sorted],
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
        json.dump({"merge_notes": merge_notes, "claim_count": len(all_claims)}, f, indent=2)

    qa = qa_compiled_intel(compiled)
    qa_report_path = os.path.join(args.outdir, "qa_report.json")
    with open(qa_report_path, "w", encoding="utf-8") as f:
        json.dump(qa, f, indent=2)

    if qa["status"] != "OK":
        raise SystemExit("QA failed: " + "; ".join(qa["errors"]))

    print(f"Wrote: {compiled_path}")
    print(f"Wrote: {merge_report_path}")
    print(f"Wrote: {qa_report_path}")


if __name__ == "__main__":
    main()
"""
Deterministic QA gates for compiled intel + claims ledger.
"""

from __future__ import annotations

import json
from typing import Dict, Any, List, Tuple, Set


def qa_compiled_intel(compiled: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    if "_schema_version" not in compiled:
        errors.append("Missing _schema_version")

    ledger = compiled.get("claims_ledger", {})
    claims = ledger.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("claims_ledger.claims missing or empty")

    # validate unique claim_id
    if isinstance(claims, list):
        seen: Set[str] = set()
        for c in claims:
            cid = c.get("claim_id")
            if not cid:
                errors.append("A claim is missing claim_id")
                continue
            if cid in seen:
                errors.append(f"Duplicate claim_id: {cid}")
            seen.add(cid)

    # If sources list present, ensure claim source_ids exist
    sources = compiled.get("sources")
    source_ids_set: Set[str] = set()
    if isinstance(sources, list):
        for s in sources:
            sid = s.get("id")
            if sid:
                source_ids_set.add(sid)
        # uniqueness
        if len(source_ids_set) != len(sources):
            warnings.append("sources[] contains duplicate ids or missing ids")

        if isinstance(claims, list):
            for c in claims:
                for sid in c.get("source_ids", []) or []:
                    if sid not in source_ids_set:
                        errors.append(f"Claim {c.get('claim_id')} references missing source_id: {sid}")

    # Null interpretability at ledger level
    if isinstance(claims, list):
        for c in claims:
            if c.get("value") is None:
                nr = c.get("null_reason")
                notes = c.get("notes", "")
                if not nr and not notes:
                    errors.append(f"Claim {c.get('claim_id')} has null value but missing null_reason/notes")

    return {"status": "FAIL" if errors else "OK", "errors": errors, "warnings": warnings}

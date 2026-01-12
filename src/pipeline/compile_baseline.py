"""
Compile baseline knowledge pack from curated JSONL sources.

Unlike compile_intel_v2.py which resolves conflicting claims from multiple sources,
this script validates and packages stable reference knowledge that has been
curator-authored. There is no merge logic because baseline data is authoritative.

The baseline pack contains:
- Regime structure & power centers
- Protest/crackdown history and base rates
- Ethnic composition + periphery risk
- Information control doctrine
- External actor playbooks

Usage:
    python -m src.pipeline.compile_baseline \
        --evidence knowledge/iran_baseline/evidence_docs.jsonl \
        --claims knowledge/iran_baseline/claims.jsonl \
        --outdir knowledge/iran_baseline/

Outputs:
    - compiled_baseline.json
    - baseline_qa.json
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import argparse
import json
from datetime import datetime
from typing import Any, Dict, List, Set


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load JSONL file, returning list of parsed JSON objects."""
    rows: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def validate_baseline_paths(claims: List[Dict[str, Any]], path_registry: Dict[str, Any]) -> List[str]:
    """
    Validate that all claim paths start with 'baseline.' and exist in registry.
    Returns list of validation errors.
    """
    errors: List[str] = []
    registered_paths = set(path_registry.get("paths", {}).keys())

    for claim in claims:
        path = claim.get("path", "")
        if not path.startswith("baseline."):
            errors.append(f"Claim {claim.get('claim_id')}: path '{path}' does not start with 'baseline.'")
            continue

        # Handle array notation: baseline.historical_protests.events[].year -> baseline.historical_protests.events[].year
        # The registry uses [] for array paths
        if path not in registered_paths:
            # Check if it's an array element path (contains specific index)
            # e.g., baseline.historical_protests.events.0.year should match baseline.historical_protests.events[].year
            normalized_path = path
            # This is a simplified check - in production you'd want more robust array path matching
            if normalized_path not in registered_paths:
                errors.append(f"Claim {claim.get('claim_id')}: path '{path}' not in path registry")

    return errors


def build_compiled_baseline(
    claims: List[Dict[str, Any]],
    evidence_docs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Build the compiled_baseline.json structure from claims.

    Groups claims by section (regime_structure, historical_protests, etc.)
    and builds the hierarchical structure.
    """
    compiled = {
        "_schema_version": "1.0",
        "_type": "baseline_knowledge_pack",
        "metadata": {
            "pack_id": "iran_baseline_v1",
            "created_date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "curator_notes": "",
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "coverage_assessment": {
                "regime_structure": "INCOMPLETE",
                "historical_protests": "INCOMPLETE",
                "ethnic_composition": "INCOMPLETE",
                "information_control": "INCOMPLETE",
                "external_actors": "INCOMPLETE"
            }
        },
        "regime_structure": {
            "supreme_leader": {},
            "power_centers": []
        },
        "historical_protests": {
            "base_rate_summary": {
                "major_protests_since_1979": 0,
                "outcomes": {
                    "SUPPRESSED": 0,
                    "PARTIAL_CONCESSIONS": 0,
                    "REGIME_CHANGE": 0
                },
                "defections_occurred": 0,
                "analyst_note": ""
            },
            "events": []
        },
        "ethnic_composition": {
            "summary": {
                "total_population_millions": 0,
                "persian_percent": 0,
                "minority_percent": 0,
                "periphery_risk_assessment": ""
            },
            "groups": []
        },
        "information_control": {
            "doctrine": "",
            "blackout_capability": {
                "technical_means": "",
                "implementation_speed": ""
            },
            "blackout_historical": [],
            "censorship_infrastructure": {
                "platforms_blocked": []
            }
        },
        "external_actors": {
            "playbooks": []
        },
        "evidence_sources": []
    }

    # Build evidence_sources from evidence_docs
    for doc in evidence_docs:
        compiled["evidence_sources"].append({
            "doc_id": doc.get("doc_id"),
            "title": doc.get("title"),
            "organization": doc.get("organization"),
            "access_grade": doc.get("access_grade"),
            "bias_grade": doc.get("bias_grade")
        })

    # Process claims and populate structure
    # Group claims by their top-level section
    power_centers_data: Dict[str, Dict[str, Any]] = {}
    protest_events_data: Dict[str, Dict[str, Any]] = {}
    ethnic_groups_data: Dict[str, Dict[str, Any]] = {}
    blackout_historical_data: Dict[str, Dict[str, Any]] = {}
    external_actors_data: Dict[str, Dict[str, Any]] = {}

    for claim in claims:
        path = claim.get("path", "")
        value = claim.get("value")
        sources = claim.get("source_doc_refs", [])

        parts = path.replace("baseline.", "").split(".")
        if not parts:
            continue

        section = parts[0]

        # Handle regime_structure
        if section == "regime_structure":
            if len(parts) >= 3 and parts[1] == "supreme_leader":
                field = parts[2]
                compiled["regime_structure"]["supreme_leader"][field] = value
                if sources:
                    compiled["regime_structure"]["supreme_leader"]["sources"] = [r.get("doc_id") for r in sources]
            elif len(parts) >= 3 and "power_centers" in parts[1]:
                # Handle power_centers[].field - extract index and field
                # Path like: baseline.regime_structure.power_centers[].name
                # For now, use selector to identify which power center
                selector = claim.get("selector", {})
                pc_name = selector.get("name", selector.get("power_center", "unknown"))
                if pc_name not in power_centers_data:
                    power_centers_data[pc_name] = {"name": pc_name, "sources": []}
                field = parts[-1]
                if field == "estimated_personnel":
                    # Handle nested object
                    if "estimated_personnel" not in power_centers_data[pc_name]:
                        power_centers_data[pc_name]["estimated_personnel"] = {}
                    subfield = parts[-1] if len(parts) > 4 else None
                    if subfield and subfield in ("low", "high"):
                        power_centers_data[pc_name]["estimated_personnel"][subfield] = value
                    else:
                        power_centers_data[pc_name]["estimated_personnel"] = value
                else:
                    power_centers_data[pc_name][field] = value
                if sources:
                    power_centers_data[pc_name]["sources"].extend([r.get("doc_id") for r in sources])

        # Handle historical_protests
        elif section == "historical_protests":
            if "base_rate_summary" in parts[1]:
                if len(parts) >= 4 and parts[2] == "outcomes":
                    outcome = parts[3]
                    compiled["historical_protests"]["base_rate_summary"]["outcomes"][outcome] = value
                elif len(parts) >= 3:
                    field = parts[2]
                    compiled["historical_protests"]["base_rate_summary"][field] = value
            elif "events" in parts[1]:
                selector = claim.get("selector", {})
                event_id = selector.get("id", selector.get("event_id", "unknown"))
                if event_id not in protest_events_data:
                    protest_events_data[event_id] = {"id": event_id, "sources": []}
                field = parts[-1]
                if "casualties" in path:
                    if "casualties" not in protest_events_data[event_id]:
                        protest_events_data[event_id]["casualties"] = {"killed": {}}
                    if "killed" in path:
                        subfield = parts[-1]
                        protest_events_data[event_id]["casualties"]["killed"][subfield] = value
                    elif "arrested" in path:
                        protest_events_data[event_id]["casualties"]["arrested"] = value
                else:
                    protest_events_data[event_id][field] = value
                if sources:
                    protest_events_data[event_id]["sources"].extend([r.get("doc_id") for r in sources])

        # Handle ethnic_composition
        elif section == "ethnic_composition":
            if "summary" in parts[1]:
                if len(parts) >= 3:
                    field = parts[2]
                    compiled["ethnic_composition"]["summary"][field] = value
            elif "groups" in parts[1]:
                selector = claim.get("selector", {})
                group_name = selector.get("name", selector.get("group_name", "unknown"))
                if group_name not in ethnic_groups_data:
                    ethnic_groups_data[group_name] = {"name": group_name, "sources": []}
                field = parts[-1]
                ethnic_groups_data[group_name][field] = value
                if sources:
                    ethnic_groups_data[group_name]["sources"].extend([r.get("doc_id") for r in sources])

        # Handle information_control
        elif section == "information_control":
            if parts[1] == "doctrine":
                compiled["information_control"]["doctrine"] = value
            elif "blackout_capability" in parts[1]:
                if len(parts) >= 3:
                    field = parts[2]
                    compiled["information_control"]["blackout_capability"][field] = value
            elif "blackout_historical" in parts[1]:
                selector = claim.get("selector", {})
                year = str(selector.get("year", "unknown"))
                if year not in blackout_historical_data:
                    blackout_historical_data[year] = {"year": int(year) if year.isdigit() else year}
                field = parts[-1]
                blackout_historical_data[year][field] = value
            elif "censorship_infrastructure" in parts[1]:
                if len(parts) >= 3:
                    field = parts[2]
                    compiled["information_control"]["censorship_infrastructure"][field] = value

        # Handle external_actors
        elif section == "external_actors":
            if "playbooks" in parts[1]:
                selector = claim.get("selector", {})
                actor = selector.get("actor", selector.get("name", "unknown"))
                if actor not in external_actors_data:
                    external_actors_data[actor] = {"actor": actor, "sources": []}
                field = parts[-1]
                external_actors_data[actor][field] = value
                if sources:
                    external_actors_data[actor]["sources"].extend([r.get("doc_id") for r in sources])

    # Populate arrays from collected data
    compiled["regime_structure"]["power_centers"] = list(power_centers_data.values())
    compiled["historical_protests"]["events"] = list(protest_events_data.values())
    compiled["ethnic_composition"]["groups"] = list(ethnic_groups_data.values())
    compiled["information_control"]["blackout_historical"] = list(blackout_historical_data.values())
    compiled["external_actors"]["playbooks"] = list(external_actors_data.values())

    # Update coverage assessment
    if compiled["regime_structure"]["supreme_leader"]:
        compiled["metadata"]["coverage_assessment"]["regime_structure"] = "PARTIAL"
    if compiled["regime_structure"]["power_centers"]:
        compiled["metadata"]["coverage_assessment"]["regime_structure"] = "COMPLETE"
    if compiled["historical_protests"]["events"]:
        compiled["metadata"]["coverage_assessment"]["historical_protests"] = "COMPLETE"
    if compiled["ethnic_composition"]["groups"]:
        compiled["metadata"]["coverage_assessment"]["ethnic_composition"] = "COMPLETE"
    if compiled["information_control"]["doctrine"]:
        compiled["metadata"]["coverage_assessment"]["information_control"] = "PARTIAL"
    if compiled["external_actors"]["playbooks"]:
        compiled["metadata"]["coverage_assessment"]["external_actors"] = "COMPLETE"

    return compiled


def qa_baseline(compiled: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run QA checks on compiled baseline.

    Checks:
    - Schema version present
    - All sections have at least some data
    - Evidence sources referenced
    - No empty required fields
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Schema version
    if "_schema_version" not in compiled:
        errors.append("Missing _schema_version")

    # Coverage completeness
    coverage = compiled.get("metadata", {}).get("coverage_assessment", {})
    incomplete_sections = [k for k, v in coverage.items() if v == "INCOMPLETE"]
    if incomplete_sections:
        warnings.append(f"Incomplete sections: {', '.join(incomplete_sections)}")

    # Regime structure
    sl = compiled.get("regime_structure", {}).get("supreme_leader", {})
    if not sl.get("name"):
        errors.append("regime_structure.supreme_leader.name is required")

    pc = compiled.get("regime_structure", {}).get("power_centers", [])
    if not pc:
        warnings.append("regime_structure.power_centers is empty")

    # Historical protests
    events = compiled.get("historical_protests", {}).get("events", [])
    if not events:
        warnings.append("historical_protests.events is empty")

    base_rate = compiled.get("historical_protests", {}).get("base_rate_summary", {})
    if not base_rate.get("major_protests_since_1979"):
        errors.append("historical_protests.base_rate_summary.major_protests_since_1979 is required")

    # Ethnic composition
    groups = compiled.get("ethnic_composition", {}).get("groups", [])
    if not groups:
        warnings.append("ethnic_composition.groups is empty")

    # Information control
    doctrine = compiled.get("information_control", {}).get("doctrine")
    if not doctrine:
        warnings.append("information_control.doctrine is empty")

    # External actors
    playbooks = compiled.get("external_actors", {}).get("playbooks", [])
    if not playbooks:
        warnings.append("external_actors.playbooks is empty")

    # Evidence sources
    sources = compiled.get("evidence_sources", [])
    if not sources:
        warnings.append("No evidence_sources provided - baseline lacks source citations")

    return {
        "status": "FAIL" if errors else "OK",
        "errors": errors,
        "warnings": warnings,
        "coverage": coverage,
        "stats": {
            "power_centers_count": len(pc),
            "protest_events_count": len(events),
            "ethnic_groups_count": len(groups),
            "external_actors_count": len(playbooks),
            "evidence_sources_count": len(sources)
        }
    }


def main():
    p = argparse.ArgumentParser(description="Compile baseline knowledge pack")
    p.add_argument("--evidence", required=True, help="evidence_docs.jsonl path")
    p.add_argument("--claims", required=True, help="claims.jsonl path")
    p.add_argument("--registry", default="config/path_registry_v2.json", help="Path registry for validation")
    p.add_argument("--outdir", default="knowledge/iran_baseline", help="Output directory")
    args = p.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Load inputs
    evidence_docs = load_jsonl(args.evidence)
    claims = load_jsonl(args.claims)

    print(f"Loaded {len(evidence_docs)} evidence docs, {len(claims)} claims")

    # Load path registry for validation
    registry = {}
    if os.path.exists(args.registry):
        with open(args.registry, "r", encoding="utf-8") as f:
            registry = json.load(f)

    # Validate paths (warning only, don't block)
    path_errors = validate_baseline_paths(claims, registry)
    if path_errors:
        print(f"⚠ Path validation warnings ({len(path_errors)}):")
        for err in path_errors[:5]:
            print(f"  - {err}")
        if len(path_errors) > 5:
            print(f"  ... and {len(path_errors) - 5} more")

    # Build compiled baseline
    compiled = build_compiled_baseline(claims, evidence_docs)

    # Run QA
    qa = qa_baseline(compiled)

    # Write outputs
    compiled_path = os.path.join(args.outdir, "compiled_baseline.json")
    with open(compiled_path, "w", encoding="utf-8") as f:
        json.dump(compiled, f, indent=2)

    qa_path = os.path.join(args.outdir, "baseline_qa.json")
    with open(qa_path, "w", encoding="utf-8") as f:
        json.dump(qa, f, indent=2)

    print(f"\nWrote: {compiled_path}")
    print(f"Wrote: {qa_path}")
    print(f"\nQA Status: {qa['status']}")
    if qa["errors"]:
        print(f"Errors: {'; '.join(qa['errors'])}")
    if qa["warnings"]:
        print(f"Warnings: {'; '.join(qa['warnings'])}")
    print(f"Stats: {qa['stats']}")


if __name__ == "__main__":
    main()

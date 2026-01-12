#!/usr/bin/env python3
"""
Merge ISW evidence docs with existing bundle_v3.json.
"""

import json

# Load bundle_v3.json
print("Loading bundle_v3.json...")
with open('bundle_v3.json', 'r') as f:
    bundle_v3 = json.load(f)

# Load ISW evidence docs
print("Loading ISW evidence docs...")
isw_docs = []
with open('ingest/isw_output/evidence_docs_isw.jsonl', 'r') as f:
    for line in f:
        isw_docs.append(json.loads(line))

# Load ISW source index
print("Loading ISW source index...")
with open('ingest/isw_output/source_index_isw.json', 'r') as f:
    isw_source_index = json.load(f)

# Combine evidence docs
all_evidence_docs = bundle_v3.get('evidence_docs', []) + isw_docs

# Combine source index
all_source_index = bundle_v3.get('source_index', []) + isw_source_index

# Create combined bundle
combined_bundle = {
    "run_manifest": {
        "run_id": "RUN_20260111_v3_with_isw",
        "generated_at": "2026-01-11T21:49:00Z",
        "description": "Combined bundle: original bundle_v3 + ISW evidence docs"
    },
    "data_cutoff_utc": "2026-01-10T12:00:00Z",  # Match RUN_20260111_v3
    "source_index": all_source_index,
    "evidence_docs": all_evidence_docs,
    "candidate_claims": bundle_v3.get('candidate_claims', [])
}

# Write combined bundle
output_path = 'bundle_v3_with_isw.json'
print(f"Writing combined bundle to {output_path}...")
with open(output_path, 'w') as f:
    json.dump(combined_bundle, f, indent=2)

print(f"\n✓ Combined bundle created:")
print(f"  Evidence docs: {len(combined_bundle['evidence_docs'])} ({len(bundle_v3.get('evidence_docs', []))} original + {len(isw_docs)} ISW)")
print(f"  Source index: {len(combined_bundle['source_index'])}")
print(f"  Candidate claims: {len(combined_bundle['candidate_claims'])}")
print(f"  Data cutoff: {combined_bundle['data_cutoff_utc']}")
print(f"  Output: {output_path}")

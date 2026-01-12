# Deep Research Evidence Bundle Specification

**Version:** 1.0
**Status:** MVP
**Purpose:** Define the structure for Deep Research JSON bundles that feed into the Iran Crisis Simulator evidence pipeline.

---

## Overview

A Deep Research evidence bundle is a single JSON file containing:
1. **run_manifest** - Metadata about the research run
2. **source_index** - List of sources consulted
3. **evidence_docs** - Raw evidence documents with excerpts
4. **candidate_claims** - Structured claims extracted from evidence

This bundle is imported via `import_deep_research_bundle.py`, which validates structure and outputs JSONL files for compilation.

---

## Top-Level Structure

```json
{
  "run_manifest": { ... },
  "source_index": [ ... ],
  "evidence_docs": [ ... ],
  "candidate_claims": [ ... ]
}
```

All four top-level keys are **required**.

---

## 1. run_manifest

Metadata about the Deep Research run that produced this bundle.

### Schema

```json
{
  "run_id": "string (unique identifier for this research run)",
  "query": "string (the research query/prompt used)",
  "executed_at_utc": "string (ISO 8601 timestamp)",
  "data_cutoff_utc": "string (ISO 8601 timestamp of latest data)",
  "time_horizon_days": "integer (forecast horizon, e.g., 90)",
  "researcher": "string (who/what ran the query, e.g., 'Deep Research', 'Analyst A')",
  "notes": "string (optional; any relevant context)"
}
```

### Example

```json
{
  "run_id": "DR_20260111_1430",
  "query": "Analyze Iranian protest dynamics and regime stability, 90-day horizon",
  "executed_at_utc": "2026-01-11T14:30:00Z",
  "data_cutoff_utc": "2026-01-10T23:59:59Z",
  "time_horizon_days": 90,
  "researcher": "Deep Research",
  "notes": "Focus on IRGC defection risk and ethnic coordination"
}
```

---

## 2. source_index

Array of sources consulted during research. Each source is graded for reliability.

### Schema

```json
[
  {
    "source_id": "string (unique ID for this source)",
    "organization": "string (e.g., 'Reuters', 'BBC Persian', 'OSINT Twitter')",
    "title": "string (article/report title)",
    "url": "string (URL if available)",
    "published_at_utc": "string (ISO 8601 timestamp)",
    "access_grade": "string (A|B|C|D per NATO standard)",
    "bias_grade": "string (1|2|3|4, where 1=confirmed, 4=unreliable)",
    "language": "string (ISO 639-1 code, e.g., 'en', 'fa', 'ar')",
    "notes": "string (optional; context about this source)"
  }
]
```

### Grading Standards (NATO)

**Access Grade (Source Reliability):**
- **A**: Completely reliable (e.g., Reuters, AP, government official statements)
- **B**: Usually reliable (e.g., BBC, NYT, established OSINT)
- **C**: Fairly reliable (e.g., regional media, single-source reports)
- **D**: Not usually reliable (e.g., unverified social media, propaganda outlets)

**Bias Grade (Information Credibility):**
- **1**: Confirmed by other sources (triangulated)
- **2**: Probably true (consistent with known facts)
- **3**: Possibly true (plausible but unverified)
- **4**: Doubtful (contradicts other sources or implausible)

**Combined:** A1 is the gold standard (Reuters, confirmed). D4 is rumor/propaganda.

### Example

```json
[
  {
    "source_id": "src_001",
    "organization": "Reuters",
    "title": "Iran protests enter second month as IRGC commander defects",
    "url": "https://reuters.com/world/middleeast/iran-protests-2026-01-10",
    "published_at_utc": "2026-01-10T18:45:00Z",
    "access_grade": "A",
    "bias_grade": "1",
    "language": "en",
    "notes": "Confirmed defection of Brigadier General Ahmad Rahimi"
  },
  {
    "source_id": "src_002",
    "organization": "BBC Persian",
    "title": "گزارش از تهران: تظاهرات در حال گسترش",
    "url": "https://bbc.com/persian/...",
    "published_at_utc": "2026-01-09T12:00:00Z",
    "access_grade": "B",
    "bias_grade": "2",
    "language": "fa",
    "notes": "Report from Tehran on protest expansion"
  }
]
```

---

## 3. evidence_docs

Raw evidence documents with key excerpts extracted.

### Schema

```json
[
  {
    "doc_id": "string (unique ID for this document)",
    "source_id": "string (references source_index.source_id)",
    "title": "string (document title)",
    "url": "string (URL if available)",
    "published_at_utc": "string (ISO 8601 timestamp)",
    "retrieved_at_utc": "string (ISO 8601 timestamp)",
    "language": "string (ISO 639-1 code)",
    "raw_text": "string (full text if available, or summary)",
    "translation_en": "string|null (English translation; null if language='en')",
    "translation_confidence": "string|null (MACHINE|HUMAN|MIXED|UNKNOWN; required if language != 'en')",
    "key_excerpts": [
      {
        "excerpt_id": "string (unique within this doc)",
        "text_original": "string (excerpt in original language)",
        "text_en": "string (English translation or original if already English)",
        "page_or_timestamp": "string (optional; location in document)"
      }
    ]
  }
]
```

### Validation Rules

1. **doc_id must be unique** across all evidence_docs
2. **language != "en"** → `translation_confidence` **required** (cannot be null)
3. **language == "en"** → `translation_en` **may be null** (no translation needed)
4. **key_excerpts** should contain at least one excerpt, but not required for validation

### Example

```json
[
  {
    "doc_id": "doc_reuters_20260110_001",
    "source_id": "src_001",
    "title": "Iran protests enter second month as IRGC commander defects",
    "url": "https://reuters.com/world/middleeast/iran-protests-2026-01-10",
    "published_at_utc": "2026-01-10T18:45:00Z",
    "retrieved_at_utc": "2026-01-11T09:00:00Z",
    "language": "en",
    "raw_text": "[Full article text would go here...]",
    "translation_en": null,
    "translation_confidence": null,
    "key_excerpts": [
      {
        "excerpt_id": "exc_001",
        "text_original": "Brigadier General Ahmad Rahimi, a senior IRGC commander, defected to the opposition on January 9, according to multiple sources.",
        "text_en": "Brigadier General Ahmad Rahimi, a senior IRGC commander, defected to the opposition on January 9, according to multiple sources.",
        "page_or_timestamp": "para 3"
      },
      {
        "excerpt_id": "exc_002",
        "text_original": "Protests have grown from an estimated 50,000 to over 120,000 participants in Tehran alone.",
        "text_en": "Protests have grown from an estimated 50,000 to over 120,000 participants in Tehran alone.",
        "page_or_timestamp": "para 7"
      }
    ]
  },
  {
    "doc_id": "doc_bbc_20260109_001",
    "source_id": "src_002",
    "title": "گزارش از تهران: تظاهرات در حال گسترش",
    "url": "https://bbc.com/persian/...",
    "published_at_utc": "2026-01-09T12:00:00Z",
    "retrieved_at_utc": "2026-01-11T09:15:00Z",
    "language": "fa",
    "raw_text": "[Persian text...]",
    "translation_en": "Report from Tehran: Protests expanding. Sources indicate increased participation in western districts...",
    "translation_confidence": "MACHINE",
    "key_excerpts": [
      {
        "excerpt_id": "exc_001",
        "text_original": "منابع محلی از افزایش چشمگیر شرکت‌کنندگان در مناطق غربی تهران خبر می‌دهند",
        "text_en": "Local sources report a significant increase in participants in western Tehran districts",
        "page_or_timestamp": null
      }
    ]
  }
]
```

---

## 4. candidate_claims

Structured claims extracted from evidence documents, ready for compilation.

### Schema

```json
[
  {
    "claim_id": "string (unique ID for this claim)",
    "path": "string (JSON path in compiled intel, e.g., 'current_situation.protest_status.estimated_participants')",
    "selector": "object|null (optional; for array items, e.g., {city: 'Tehran'})",
    "value": "any (the claim value; can be null)",
    "units": "string (units/data type, e.g., 'count', 'ISO8601', 'boolean')",
    "null_reason": "string (required if value=null; one of: NOT_APPLICABLE, CONFLICTING_SOURCES, INSUFFICIENT_DATA, UNKNOWN)",
    "as_of_utc": "string (ISO 8601 timestamp; when this claim is current)",
    "source_grade": "string (e.g., 'A1', 'B2'; best source grade supporting this claim)",
    "source_doc_refs": [
      {
        "doc_id": "string (references evidence_docs.doc_id)",
        "excerpt_id": "string (references key_excerpts.excerpt_id)"
      }
    ],
    "claim_class": "string (FACTUAL|ESTIMATED|INFERRED|SPECULATIVE)",
    "confidence": "string (HIGH|MEDIUM|LOW; analyst confidence in this claim)",
    "triangulated": "boolean (true if confirmed by multiple independent sources)",
    "notes": "string (optional; context or reasoning)"
  }
]
```

### Validation Rules

1. **claim_id must be unique** across all candidate_claims
2. **source_doc_refs must be non-empty** (at least one doc reference)
3. **Every doc_id in source_doc_refs must exist** in evidence_docs
4. **If value is null**, `null_reason` **must be non-empty**
5. **Required fields:** path, value, units, null_reason (if value=null), as_of_utc, source_grade, source_doc_refs, claim_class

### Claim Classes

- **FACTUAL**: Directly stated in source (e.g., "IRGC commander defected")
- **ESTIMATED**: Quantitative estimate (e.g., "120,000 protesters")
- **INFERRED**: Logical inference from facts (e.g., "Protest momentum increasing" from size growth)
- **SPECULATIVE**: Analyst judgment with weak evidence

### Null Reasons

- **NOT_APPLICABLE**: Question doesn't apply to current situation
- **CONFLICTING_SOURCES**: Sources contradict each other
- **INSUFFICIENT_DATA**: Not enough information to make a claim
- **UNKNOWN**: Data exists but we couldn't access it

### Example

```json
[
  {
    "claim_id": "claim_001",
    "path": "current_situation.regime_response.defections",
    "selector": null,
    "value": {
      "confirmed_defections": 1,
      "rank": "Brigadier General",
      "date": "2026-01-09"
    },
    "units": "object",
    "null_reason": null,
    "as_of_utc": "2026-01-10T18:45:00Z",
    "source_grade": "A1",
    "source_doc_refs": [
      {
        "doc_id": "doc_reuters_20260110_001",
        "excerpt_id": "exc_001"
      }
    ],
    "claim_class": "FACTUAL",
    "confidence": "HIGH",
    "triangulated": true,
    "notes": "First confirmed unit-level defection; unprecedented in Iranian protest history"
  },
  {
    "claim_id": "claim_002",
    "path": "current_situation.protest_status.estimated_participants",
    "selector": {"city": "Tehran"},
    "value": 120000,
    "units": "count",
    "null_reason": null,
    "as_of_utc": "2026-01-10T18:45:00Z",
    "source_grade": "A1",
    "source_doc_refs": [
      {
        "doc_id": "doc_reuters_20260110_001",
        "excerpt_id": "exc_002"
      },
      {
        "doc_id": "doc_bbc_20260109_001",
        "excerpt_id": "exc_001"
      }
    ],
    "claim_class": "ESTIMATED",
    "confidence": "MEDIUM",
    "triangulated": true,
    "notes": "Estimate based on aerial footage and local reports; ±30% uncertainty"
  },
  {
    "claim_id": "claim_003",
    "path": "regional_cascade.syria.protest_spillover",
    "selector": null,
    "value": null,
    "units": "boolean",
    "null_reason": "INSUFFICIENT_DATA",
    "as_of_utc": "2026-01-10T18:45:00Z",
    "source_grade": "C3",
    "source_doc_refs": [
      {
        "doc_id": "doc_osint_20260108_001",
        "excerpt_id": "exc_001"
      }
    ],
    "claim_class": "SPECULATIVE",
    "confidence": "LOW",
    "triangulated": false,
    "notes": "Some Twitter reports of solidarity protests in Damascus, but unverified"
  }
]
```

---

## Fail-Fast Validation Rules

The importer (`import_deep_research_bundle.py`) enforces these rules:

### Evidence Docs
- ✅ **doc_id unique** across all evidence_docs
- ✅ **translation_confidence required** if language != "en"
- ✅ **translation_en may be null** if language == "en"

### Candidate Claims
- ✅ **claim_id unique** across all candidate_claims
- ✅ **source_doc_refs non-empty** (at least one doc reference)
- ✅ **Referenced doc_ids exist** in evidence_docs
- ✅ **null_reason non-empty** if value is null
- ✅ **Required fields present**: path, value, units, as_of_utc, source_grade, source_doc_refs, claim_class

If any rule fails, the importer **exits with error** and clear message.

---

## Minimal Working Example

```json
{
  "run_manifest": {
    "run_id": "test_001",
    "query": "Test query",
    "executed_at_utc": "2026-01-11T12:00:00Z",
    "data_cutoff_utc": "2026-01-11T12:00:00Z",
    "time_horizon_days": 90,
    "researcher": "Test",
    "notes": ""
  },
  "source_index": [
    {
      "source_id": "src_test_001",
      "organization": "Test Source",
      "title": "Test Article",
      "url": "https://example.com",
      "published_at_utc": "2026-01-11T12:00:00Z",
      "access_grade": "A",
      "bias_grade": "1",
      "language": "en",
      "notes": ""
    }
  ],
  "evidence_docs": [
    {
      "doc_id": "doc_test_001",
      "source_id": "src_test_001",
      "title": "Test Article",
      "url": "https://example.com",
      "published_at_utc": "2026-01-11T12:00:00Z",
      "retrieved_at_utc": "2026-01-11T12:00:00Z",
      "language": "en",
      "raw_text": "Test content",
      "translation_en": null,
      "translation_confidence": null,
      "key_excerpts": [
        {
          "excerpt_id": "exc_001",
          "text_original": "Test excerpt",
          "text_en": "Test excerpt",
          "page_or_timestamp": null
        }
      ]
    }
  ],
  "candidate_claims": [
    {
      "claim_id": "claim_test_001",
      "path": "test.value",
      "selector": null,
      "value": 42,
      "units": "count",
      "null_reason": null,
      "as_of_utc": "2026-01-11T12:00:00Z",
      "source_grade": "A1",
      "source_doc_refs": [
        {
          "doc_id": "doc_test_001",
          "excerpt_id": "exc_001"
        }
      ],
      "claim_class": "FACTUAL",
      "confidence": "HIGH",
      "triangulated": false,
      "notes": ""
    }
  ]
}
```

---

## Usage Workflow

```bash
# 1. Deep Research outputs bundle.json
# (or you create one manually following this spec)

# 2. Import bundle
python -m src.pipeline.import_deep_research_bundle \
    --bundle runs/bundle_20260111.json \
    --out_dir runs/RUN_20260111_1430

# 3. Compile intel
python -m src.pipeline.compile_intel \
    --claims runs/RUN_20260111_1430/claims_deep_research.jsonl \
    --template data/iran_crisis_intel.json \
    --outdir runs/RUN_20260111_1430

# 4. Run simulation
python src/simulation.py \
    --intel runs/RUN_20260111_1430/compiled_intel.json \
    --priors data/analyst_priors.json \
    --runs 10000 \
    --output runs/RUN_20260111_1430/simulation_results.json
```

---

## Version History

- **v1.0 (2026-01-11)**: Initial MVP spec based on 5.2 review
- Future: May add schema for automated source grading, conflict resolution metadata

---

## Questions?

See `WORKFLOW_UPDATE.md` for end-to-end integration guide.

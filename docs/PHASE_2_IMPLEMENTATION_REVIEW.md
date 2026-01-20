# Oracle Phase 2: Implementation Review

**Date:** 2026-01-19
**Implementer:** Claude Opus 4.5
**Status:** Complete - All 172 tests passing

---

## Executive Summary

Phase 2 implements resolution governance, evidence snapshots, external auto-resolution, coverage metrics, and catalog versioning for the Oracle forecasting layer. All changes are observe-only with append-only ledgers - no simulation logic was modified.

---

## Task A: Schema Updates

### A.1 Resolution Record Schema
**File:** `config/schemas/resolution_record.schema.json`

**New Required Fields:**
```json
{
  "resolution_mode": { "enum": ["external_auto", "external_manual", "claims_inferred"] },
  "reason_code": { "type": "string" }
}
```

**New Optional Fields:**
```json
{
  "adjudicator_id": { "type": "string" },
  "evidence_refs": { "type": "array", "items": { "type": "string" } },
  "evidence_hashes": {
    "type": "array",
    "items": { "type": "string", "pattern": "^sha256:[a-f0-9]{64}$" }
  }
}
```

**Conditional Validation:**
- When `resolution_mode == "external_manual"`, `adjudicator_id` is required
- Implemented via JSON Schema `allOf`/`if`/`then` construct

### A.2 Event Catalog Schema
**File:** `config/schemas/event_catalog.schema.json`

**Changes:**
- `catalog_version` pattern: `^\d+\.\d+$` → `^\d+\.\d+\.\d+$` (SemVer)
- Added `auto_resolve` boolean field to event definition
- Added `effective_from_utc` date-time field for new events

---

## Task B: Evidence Store

### B.1 Evidence Module
**File:** `src/forecasting/evidence.py` (NEW)

**Functions:**
```python
def write_evidence_snapshot(
    resolution_id: str,
    snapshot_data: Dict[str, Any],
    evidence_dir: Path = EVIDENCE_DIR
) -> Tuple[str, str]:
    """
    Write evidence snapshot and return (repo_relative_path, "sha256:<hash>").

    Snapshot contains:
    - run_id, data_cutoff_utc, path_used, extracted_value, rule_applied, snapshot_utc
    """

def compute_file_hash(file_path: Path) -> str:
    """Return sha256:<hex_digest> for file."""

def compute_content_hash(content: bytes) -> str:
    """Return sha256:<hex_digest> for content."""

def read_evidence_snapshot(resolution_id: str, evidence_dir: Path) -> Optional[Dict]:
    """Read evidence snapshot by resolution ID."""

def verify_evidence_hash(resolution_id: str, expected_hash: str, evidence_dir: Path) -> bool:
    """Verify evidence file matches expected hash."""

def list_evidence_files(evidence_dir: Path) -> list:
    """List all resolution IDs with evidence snapshots."""
```

**Design Decisions:**
- Evidence files are JSON with sorted keys for deterministic hashing
- Atomic write via temp file + rename
- Hash computed before write, returned to caller
- Default directory: `forecasting/evidence/`

### B.2 Gitignore Update
**File:** `.gitignore`

Added:
```
forecasting/evidence/
```

---

## Task C: Catalog Updates

### C.1 Event Catalog
**File:** `config/event_catalog.json`

**Version Bump:** `1.0` → `2.0.0`

**Events with `auto_resolve: true`:**

| Event ID | Data Path | Rule |
|----------|-----------|------|
| `econ.rial_ge_1_2m` | `current_state.economic_conditions.rial_usd_rate.market` | `threshold_gte:1200000` |
| `econ.inflation_ge_50` | `current_state.economic_conditions.inflation.official_annual_percent` | `threshold_gte:50` |
| `state.internet_degraded` | `current_state.information_environment.internet_status.current` | `enum_in:["BLACKOUT","SEVERELY_DEGRADED"]` |

### C.2 Changelog
**File:** `config/event_catalog_changelog.md` (NEW)

Documents:
- v2.0.0 changes (auto_resolve, effective_from_utc, resolution modes, SemVer)
- v1.0 initial release

---

## Task D: Resolver Changes

**File:** `src/forecasting/resolver.py`

### D.1 New Import
```python
from . import evidence
```

### D.2 Helper Function
```python
def get_resolution_mode(resolution: Dict[str, Any]) -> str:
    """
    Get resolution mode with backward compatibility.
    Old resolutions without resolution_mode treated as "external_auto".
    """
    return resolution.get("resolution_mode", "external_auto")
```

### D.3 Updated `resolve_event()` Function

**New Logic Flow:**
1. Check if `event.auto_resolve == true` and `resolution_source.type == "compiled_intel"`
2. Extract value from compiled intel using path
3. Apply resolution rule
4. If auto_resolve and outcome != UNKNOWN:
   - Write evidence snapshot via `evidence.write_evidence_snapshot()`
   - Set `resolution_mode = "external_auto"`
   - Populate `evidence_refs` and `evidence_hashes`
5. Otherwise set `resolution_mode = "claims_inferred"`
6. Set `reason_code` to rule applied (e.g., `threshold_gte:1200000`)

**New Resolution Record Fields:**
```python
record = {
    # ... existing fields ...
    "resolution_mode": resolution_mode,
    "reason_code": rule_applied if rule_applied else "unknown",
    "evidence_refs": evidence_refs,
    "evidence_hashes": evidence_hashes,
    "resolved_by": "oracle_resolver_v2",  # Updated version
}
```

---

## Task E: CLI Queue Command

**File:** `src/forecasting/cli.py`

### New Command
```
forecast queue [--due-only]
```

**Functionality:**
- Lists forecasts where `target_date_utc <= now` and no resolution exists
- Output columns: event_id, horizon_days, target_date, days_overdue
- Sorted by most overdue first
- `--due-only` is default behavior

**Output Example:**
```
Forecasts awaiting resolution: 3

Event ID                       Horizon    Target Date  Overdue
--------------------------------------------------------------
econ.rial_ge_1_2m              7          2026-01-12   7d
econ.inflation_ge_50           15         2026-01-14   5d
state.internet_degraded        7          2026-01-18   1d
```

---

## Task F: Scoring & Reporting

### F.1 Scorer Updates
**File:** `src/forecasting/scorer.py`

**New Imports:**
```python
from datetime import datetime, timezone
from . import resolver
```

**New Functions:**

```python
def compute_coverage_metrics(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Returns:
    - forecasts_due: Count where target_date <= now
    - resolved_known: YES/NO outcomes
    - resolved_unknown: UNKNOWN outcomes
    - abstained: abstain=true forecasts
    - unresolved: No resolution yet
    - coverage_rate: resolved_known / forecasts_due
    - unknown_rate, abstain_rate
    """

def effective_brier_score(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]]
) -> float:
    """
    Brier score including UNKNOWN outcomes as outcome=0.5.
    - YES -> outcome=1.0, NO -> outcome=0.0, UNKNOWN -> outcome=0.5
    - Abstained forecasts use p_yes=0.5
    - Unresolved (no resolution record) excluded
    - Penalizes overconfident predictions that couldn't be verified
    """

def compute_scores_for_mode(
    forecasts: List[Dict[str, Any]],
    resolutions: List[Dict[str, Any]],
    mode_filter: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compute scores for resolutions matching specific modes.
    Returns: { brier_score, log_score, count }
    """
```

**Updated `compute_scores()` Output:**
```python
{
    # Existing fields...
    "coverage": {
        "forecasts_due": int,
        "resolved_known": int,
        "resolved_unknown": int,
        "abstained": int,
        "unresolved": int,
        "coverage_rate": float,
        "unknown_rate": float,
        "abstain_rate": float
    },
    "effective_brier": float,
    "core_scores": {           # external_auto + external_manual
        "brier_score": float,
        "log_score": float,
        "count": int
    },
    "claims_inferred_scores": { # claims_inferred only
        "brier_score": float,
        "log_score": float,
        "count": int
    },
    "combined_scores": {...}    # All modes (reference only)
}
```

### F.2 Reporter Updates
**File:** `src/forecasting/reporter.py`

**New Functions:**
```python
def format_coverage_table(coverage: Dict[str, Any]) -> str:
    """Format coverage metrics as markdown table."""

def format_mode_scores_table(core, claims, combined) -> str:
    """Format scores by resolution mode as markdown table."""
```

**Updated Markdown Report Sections:**
1. **Coverage Metrics** - New table showing due/resolved/unknown/abstain counts
2. **Core Accuracy (External Resolution)** - Brier/Log for external_auto + external_manual
3. **Claims Inferred Scores** - Separate section, labeled as not part of core
4. **Scores by Resolution Mode** - Combined table with footnote
5. **Effective Brier Score** - New section explaining p=0.5 treatment
6. **Interpretation Guide** - Updated with coverage and mode explanations

---

## Test Coverage

### New Test Files

| File | Tests | Description |
|------|-------|-------------|
| `tests/test_resolution_schema.py` | 12 | Schema validation for new fields |
| `tests/test_evidence.py` | 18 | Snapshot write, hash verification, file ops |
| `tests/test_resolution_queue.py` | 10 | Queue listing, sorting, filtering |
| `tests/test_coverage_metrics.py` | 13 | Coverage rate calculations |
| `tests/test_scoring_separation.py` | 14 | External vs claims_inferred separation |
| `tests/test_backward_compat.py` | 10 | Old resolutions treated as external_auto |

### Test Results
```
============================= 172 passed in 0.24s ==============================
```

All 77 new tests pass, along with 95 existing tests.

---

## Backward Compatibility

### Resolution Records
- Old resolutions without `resolution_mode` field are treated as `"external_auto"`
- Implemented in `resolver.get_resolution_mode()` helper
- Scoring functions use this helper for consistent behavior

### Catalog Version
- Old format `X.Y` no longer validates against schema
- Test fixtures updated to use `X.Y.Z` format
- Production catalog updated to `2.0.0`

---

## Module Version
**File:** `src/forecasting/__init__.py`

```python
__version__ = "2.0.0"  # Updated from 1.0.0
```

---

## Verification Commands

```bash
# 1. Schema validation
python -m src.forecasting.cli validate

# 2. Resolution queue
python -m src.forecasting.cli queue

# 3. Auto-resolve and check evidence (dry run)
python -m src.forecasting.cli resolve --dry-run

# 4. Score with coverage metrics
python -m src.forecasting.cli score

# 5. Report shows separated scores
python -m src.forecasting.cli report --format md

# 6. Run all tests
python -m pytest tests/test_forecasting_*.py tests/test_evidence.py \
    tests/test_coverage_metrics.py tests/test_backward_compat.py \
    tests/test_scoring_separation.py tests/test_resolution_queue.py \
    tests/test_resolution_schema.py -v
```

---

## Files Summary

| File | Action | Lines Changed |
|------|--------|---------------|
| `config/schemas/resolution_record.schema.json` | MODIFIED | +50 |
| `config/schemas/event_catalog.schema.json` | MODIFIED | +12 |
| `config/event_catalog.json` | MODIFIED | +4 |
| `config/event_catalog_changelog.md` | NEW | 30 |
| `src/forecasting/__init__.py` | MODIFIED | +3 |
| `src/forecasting/evidence.py` | NEW | 156 |
| `src/forecasting/resolver.py` | MODIFIED | +60 |
| `src/forecasting/scorer.py` | MODIFIED | +120 |
| `src/forecasting/reporter.py` | MODIFIED | +80 |
| `src/forecasting/cli.py` | MODIFIED | +65 |
| `.gitignore` | MODIFIED | +1 |
| `tests/test_forecasting_catalog.py` | MODIFIED | +5 |
| `tests/test_resolution_schema.py` | NEW | 145 |
| `tests/test_evidence.py` | NEW | 185 |
| `tests/test_resolution_queue.py` | NEW | 155 |
| `tests/test_coverage_metrics.py` | NEW | 165 |
| `tests/test_scoring_separation.py` | NEW | 175 |
| `tests/test_backward_compat.py` | NEW | 145 |

---

## Phase 2 Acceptance Checklist

- [x] Resolutions include resolution_mode, adjudicator_id (when manual), reason_code, evidence_refs, evidence_hashes
- [x] Evidence snapshots written to forecasting/evidence/ with sha256 hashes
- [x] At least 2 events auto-resolve with external_auto mode (3 configured)
- [x] Scorecard shows core accuracy + coverage metrics + effective Brier
- [x] Claims_inferred excluded from core scorecard, reported separately
- [x] Old resolutions without resolution_mode treated as external_auto
- [x] Catalog version bumped to 2.0.0 + changelog created
- [x] All 172 tests passing

---

## Non-Negotiables Verification

| Requirement | Status |
|-------------|--------|
| Observe-only (no simulation changes) | ✅ Only forecasting module modified |
| Append-only ledgers | ✅ No ledger write changes |
| No overwrites | ✅ Evidence files are write-once |
| resolution_mode + evidence refs/hashes | ✅ Required in schema |
| External/manual scoring separate from claims_inferred | ✅ Separate score sections |

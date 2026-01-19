# Claude Code Handoff: Plan A Execution

This file is the authoritative execution brief. Read these first:
- `PLAN_A.md`
- `TASKLIST_A.md`
- `QA_GATES_SPEC_A.md`

Then follow the steps below.

## Non-negotiables
- Preserve QA firewall: cutoff enforcement, path registry validation, enum normalization, conflict policy (no averaging).
- Replace any cutoff-date gates with rolling window gates.
- Use required default windows, including `internet_monitoring: 72h` (non-critical bucket).
- Automated collection is “no wires” (do not require wires for coverage in auto-ingest or daily gates).
- On coverage FAIL: skip simulation and mark the run unreliable in `run_manifest.json`.
- Do not commit or track `runs/`, bundles, or `.env`.
- Avoid network calls in tests; use fixtures.

## Implementation order (all required)
1) Rolling-window coverage gates
2) Deterministic merge policy
3) Run manifest + hashing
4) Shared run validation helpers
5) Source health + alerts
6) Automation guardrails
7) Diff report improvements

## Detailed tasks

### 1) Rolling-window coverage gates
Files: `src/ingest/coverage.py`, `src/pipeline/import_deep_research_bundle_v3.py`, tests
- Update `BUCKET_WINDOWS` in `src/ingest/coverage.py`:
  - Set `internet_monitoring` to 72h.
- Replace `check_daily_update_gates` in `src/pipeline/import_deep_research_bundle_v3.py` with a rolling-window gate:
  - Use `src/ingest/coverage.evaluate_coverage` on `kept_docs`.
  - Ensure no wires requirement.
  - Ensure `coverage_report.json` includes `counts_by_bucket`, `buckets_missing`, `bucket_details`, `status`, and `status_reason`.
- Tests:
  - Extend `tests/test_ingest.py` to assert the 72h `internet_monitoring` window.
  - Add a test for the new rolling-window gates used in bundle import (use small in-memory docs, no network).

### 2) Deterministic merge policy
Files: `scripts/daily_update.py`, `src/pipeline/compile_intel.py` OR use `src/pipeline/compile_intel_v2.py`
- Ensure deterministic merge and conflict policy:
  - Prefer switching daily_update compile stage to `compile_intel_v2.py`.
  - If porting, replicate `_merge_claims` priority order and conflict handling from `compile_intel_v2.py`.
- Record tie-break order in run metadata (see run manifest below).

### 3) Run manifest + hashing
Files: `src/run_manifest.py` (new), `scripts/daily_update.py`, tests
- Implement a helper to (re)write `run_manifest.json` after compile/sim.
- Required fields (per `QA_GATES_SPEC_A.md`):
  - `git_commit`, `data_cutoff_utc`, `ingest_since_utc`, `seed`
  - `hashes.evidence_docs.jsonl`, `hashes.claims.jsonl`, `hashes.compiled_intel.json`
  - `hashes.priors_resolved.json` if present
  - `deterministic_tiebreaks` (order: source_grade, triangulated, confidence, latest_published_at, claim_id)
  - `reliability` (status RELIABLE/UNRELIABLE + reason + coverage_status)
- Choose a stable hash (SHA256), and document which claims file is used as `claims.jsonl`.
- Tests:
  - `tests/test_run_manifest.py` using temp dirs and small files.

### 4) Shared run validation helpers
Files: `src/run_utils.py` (new), `scripts/daily_update.py`, tests
- Implement:
  - `list_runs_sorted()`
  - `required_artifacts(mode)`
  - `is_run_valid_for_observe(run_dir)`
  - `is_run_valid_for_simulate(run_dir)`
- Use helpers to gate simulation/reporting in `scripts/daily_update.py`.
- Tests:
  - `tests/test_run_utils.py` with temp run dirs.

### 5) Source health + alerts
Files: `src/ingest/health.py`, `src/ingest/alerts.py`, `src/ingest/coordinator.py`, tests
- Ensure `runs/_meta/sources_health.json` remains authoritative and is updated per auto-ingest.
- Ensure `coverage_report.json` includes `health_summary` for bundle runs (use latest tracker state if present).
- Ensure `alerts.json` is emitted on DEGRADED/DOWN transitions.
- Tests:
  - Extend `tests/test_ingest.py` (health transitions already exist; add regression for coverage_report health summary if needed).

### 6) Automation guardrails
Files: `config/ingest.yaml` (new), `src/ingest/base_fetcher.py`, `src/ingest/coordinator.py`, tests
- Add config for:
  - `max_docs_per_bucket`
  - `retry` (max_retries, backoff)
  - `cache` (enabled, path)
- Implement doc cache (e.g., `runs/_meta/doc_cache.json`) to skip reprocessing identical docs.
- Enforce per-bucket caps before coverage evaluation (keep most recent by published time).
- Tests:
  - `tests/test_guardrails.py` for bucket caps + cache behavior (no network).

### 7) Diff report improvements
Files: `src/pipeline/run_comparator.py`, `src/report/generate_diff_report.py`, tests
- Add to `diff_report.json`:
  - `coverage_deltas.buckets_missing_now`, `coverage_deltas.buckets_missing_prev`
  - `health_deltas` from `coverage_report.health_summary`
  - `contested_claims` (top conflict groups / high candidate counts)
  - ensure `claim_winner_changes` includes `path` + `selector`
- Update markdown rendering to include new sections.
- Tests:
  - `tests/test_diff_report.py` with small fixture JSON files.

## Testing (offline only)
Preferred:
- `python -m pytest tests/test_ingest.py`
- `python -m pytest tests/test_run_manifest.py`
- `python -m pytest tests/test_run_utils.py`
- `python -m pytest tests/test_guardrails.py`
- `python -m pytest tests/test_diff_report.py`

Avoid:
- `python scripts/daily_update.py --auto-ingest` (network and writes to `runs/`).

## Completion checklist
- All items in `QA_GATES_SPEC_A.md` satisfied.
- No new tracked artifacts in `runs/`, bundles, or `.env`.
- Report back with:
  - changed files
  - tests run + results
  - open questions

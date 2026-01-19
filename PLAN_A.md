# Plan A: Core Refactors / Hardening

Goal: make the daily pipeline trustworthy, self-monitoring, and stable for frontend consumption while preserving the QA firewall.

## Current state inventory (already in repo)
- Rolling window coverage gates live in `src/ingest/coverage.py` with `BUCKET_WINDOWS` and `CRITICAL_BUCKETS`; coverage reports include `counts_by_bucket`, `buckets_missing`, and `status`.
- Source health tracking is implemented in `src/ingest/health.py` and writes `runs/_meta/sources_health.json`; thresholds are 3 failures for DEGRADED and 7 for DOWN.
- Alerts for missing buckets and source transitions are generated in `src/ingest/alerts.py`; `scripts/daily_update.py` writes `alerts.json` during auto-ingest.
- Auto-ingest mode in `scripts/daily_update.py` produces `coverage_report.json` and `alerts.json` in `ingest/auto_fetched`, then copies to the run dir.
- Diffing exists in `src/pipeline/run_comparator.py` with outcome deltas, CI overlap flags, event rate deltas, changed claim winners, and coverage deltas.
- QA firewall for bundle imports exists in `src/pipeline/import_deep_research_bundle_v3.py` (cutoff enforcement, path registry, enum normalization).

## Gaps vs requirements
- Daily gates in `src/pipeline/import_deep_research_bundle_v3.py` are still cutoff-date based; they must be replaced with rolling window gates.
- `internet_monitoring` window is 168h in `src/ingest/coverage.py` but required default is 72h.
- Bundle import coverage reports lack window coverage fields (`counts_by_bucket`, `buckets_missing`) and health summary.
- `run_manifest.json` does not include git commit hash, ingest since window, seed, artifact hashes, or deterministic tie-break policy.
- Diff report lacks contested claims/conflict groups and coverage/health deltas (buckets missing now vs previous; health transitions).
- No shared run validation helpers for the frontend (run validity for observe/simulate).
- Guardrails for automation cost controls (max docs per bucket, retry/backoff config, doc cache) are not configurable.
- Daily pipeline behavior on coverage FAIL is not standardized (strict flags exist, but behavior needs a clear default).

## Plan A (minimal, testable)
1. Rolling-window coverage everywhere (replace cutoff-date gates)
   - Update `BUCKET_WINDOWS` defaults to required windows (set `internet_monitoring` to 72h).
   - Replace `check_daily_update_gates` in `src/pipeline/import_deep_research_bundle_v3.py` with window-based coverage (reuse `src/ingest/coverage.evaluate_coverage`).
   - Ensure bundle import coverage report includes window coverage fields (`counts_by_bucket`, `buckets_missing`, `bucket_details`, `status`) and no wire dependency.
   - Add/adjust unit tests to validate rolling-window behavior and 72h internet monitoring window.

2. Preserve QA firewall + deterministic merge policy
   - Keep cutoff enforcement, source refs, path registry, enum normalization unchanged in import v3.
   - Align compile stage to deterministic merge policy with conflict handling (prefer `compile_intel_v2` or port its merge policy into `compile_intel.py`), and record the tie-break order in run metadata.

3. Source health tracking + alerts hardening
   - Confirm `runs/_meta/sources_health.json` remains the authoritative store and is updated each auto-ingest run.
   - Include health summary in coverage report for bundle runs when possible (or add a `health_summary` field from latest tracker state).
   - Ensure `alerts.json` is emitted when a source transitions to DEGRADED/DOWN; surface this in the diff report.

4. Run manifest + hashing for reproducibility
   - Add a helper module (e.g., `src/run_manifest.py`) to (re)write `run_manifest.json` after compile/sim.
   - Required fields: git commit hash, `data_cutoff_utc`, `ingest_since_utc`, `seed`, run parameters, and SHA256 hashes for:
     - `evidence_docs.jsonl`
     - `claims_deep_research.jsonl` or `claims_extracted.jsonl` (mapped to `claims.jsonl` in manifest)
     - `compiled_intel.json`
     - `priors_resolved.json` (if present)
   - Record deterministic tie-break policy (claim_id ordering, etc) in manifest.

5. Diff report improvements (what changed + why)
   - Extend `src/pipeline/run_comparator.py` to include:
     - coverage deltas: buckets missing now vs previous
     - health deltas from `coverage_report.health_summary`
     - top contested claims/conflict groups from `merge_report.json`
     - changed winners with `path` + `selector`
   - Update `src/report/generate_diff_report.py` to render new sections.
   - Add tests/fixtures to validate diff output fields.

6. Automation guardrails + cost controls
   - Add `config/ingest.yaml` with `max_docs_per_bucket`, retry/backoff settings, and cache settings.
   - Update `src/ingest/base_fetcher.py` to load retry/backoff from config.
   - Implement a doc cache (e.g., `runs/_meta/doc_cache.json`) to skip reprocessing identical docs by hash (url+published_at+title or content).
   - Enforce per-bucket caps in `src/ingest/coordinator.py` (keep most recent by published time).
   - Coverage FAIL behavior: skip simulation and mark run as unreliable in manifest (justification: avoid unstable outputs reaching frontend and reduce compute cost).

7. Shared run validation helpers
   - Add `src/run_utils.py` with:
     - `list_runs_sorted()`
     - `required_artifacts(mode)`
     - `is_run_valid_for_observe(run_dir)`
     - `is_run_valid_for_simulate(run_dir)`
   - Use these helpers in `scripts/daily_update.py` (gate simulation/reporting) and later in the frontend.

## Acceptance criteria
- Daily auto-ingest run produces a run folder with `coverage_report.json`, `alerts.json` (when needed), and updates `runs/_meta/sources_health.json`.
- Coverage gates are rolling-window based (verified by unit test) with required default windows.
- Source health transitions (OK -> DEGRADED -> DOWN) are correct (unit tests).
- Diff report highlights changed claim winners (path + selector) and contested claims (unit test or fixture).
- `run_manifest.json` includes git commit hash, cutoff and since window, seed, and artifact hashes.
- No git-tracked artifacts in `runs/`, bundle files, or `.env`.

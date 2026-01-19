# Tasklist A (Claude Code execution checklist)

Use this as the step-by-step implementation checklist with commands.

## Prep and repo scan
- [ ] `rg -n "check_daily_update_gates|daily_coverage" src/pipeline/import_deep_research_bundle_v3.py`
- [ ] `rg -n "BUCKET_WINDOWS|internet_monitoring" src/ingest/coverage.py`
- [ ] `rg -n "run_manifest|merge_report|diff_report" scripts src/pipeline src/report`
- [ ] `git status --porcelain`

## Implement rolling-window gates
- [ ] Update `src/ingest/coverage.py` windows (internet_monitoring 72h).
- [ ] Replace cutoff-date gates in `src/pipeline/import_deep_research_bundle_v3.py` with rolling-window coverage.
- [ ] Ensure bundle import `coverage_report.json` includes window coverage fields (`counts_by_bucket`, `buckets_missing`, `bucket_details`, `status`).
- [ ] Add/adjust unit tests for rolling-window coverage (including internet_monitoring 72h).

## Preserve QA firewall + deterministic merge policy
- [ ] Align compile stage to deterministic conflict policy (prefer `src/pipeline/compile_intel_v2.py` or port its merge logic into `src/pipeline/compile_intel.py`).
- [ ] Record deterministic tie-break order (claim_id ordering) in run metadata.

## Source health + alerts
- [ ] Ensure `runs/_meta/sources_health.json` is updated per auto-ingest run.
- [ ] Include health summary in coverage report for bundle runs (if available).
- [ ] Emit `alerts.json` on DEGRADED/DOWN transitions.

## Run manifest + hashing
- [ ] Add helper module (e.g., `src/run_manifest.py`) to (re)write `run_manifest.json` after compile/sim.
- [ ] Include git commit hash, cutoff, since window, seed, and SHA256 hashes for evidence, claims, compiled intel, and priors (if present).
- [ ] Wire manifest helper into `scripts/daily_update.py` after compile/sim and for bundle-only runs.

## Diff report enhancements
- [ ] Extend `src/pipeline/run_comparator.py` to add contested claims/conflict groups, coverage missing deltas, and health deltas.
- [ ] Update `src/report/generate_diff_report.py` to render new sections.
- [ ] Add fixtures/tests for diff output fields.

## Automation guardrails + costs
- [ ] Add `config/ingest.yaml` with `max_docs_per_bucket`, retry/backoff config, and cache settings.
- [ ] Update `src/ingest/base_fetcher.py` to read retry/backoff config.
- [ ] Implement doc cache in `src/ingest/coordinator.py` (e.g., `runs/_meta/doc_cache.json`).
- [ ] Enforce per-bucket caps in `src/ingest/coordinator.py` (keep most recent by published time).
- [ ] Define coverage FAIL behavior (skip simulation and mark run unreliable in manifest).

## Shared run validation helpers
- [ ] Add `src/run_utils.py` with `list_runs_sorted`, `required_artifacts`, `is_run_valid_for_observe`, `is_run_valid_for_simulate`.
- [ ] Use helpers in `scripts/daily_update.py` to gate simulation/report steps.

## Verification commands
- [ ] `python -m pytest tests/test_ingest.py`
- [ ] `python -m pytest tests/test_diff_report.py`
- [ ] `python -m pytest tests/test_run_utils.py`
- [ ] `python scripts/daily_update.py --auto-ingest --no-simulate --strict-coverage`
- [ ] `rg -n "runs/|bundle_.*\\.json|\\.env" .gitignore`

## Acceptance criteria
- Daily auto-ingest run produces a run folder with `coverage_report.json`, `alerts.json` (when needed), and updates `runs/_meta/sources_health.json`.
- Coverage gates are rolling-window based (verified by unit test) with required default windows.
- Source health transitions (OK -> DEGRADED -> DOWN) are correct (unit tests).
- Diff report highlights changed claim winners (path + selector) and contested claims (unit test or fixture).
- `run_manifest.json` includes git commit hash, cutoff and since window, seed, and artifact hashes.
- No git-tracked artifacts in `runs/`, bundle files, or `.env`.

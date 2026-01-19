# QA Gates Spec A (machine-checkable)

version: 1

coverage:
  windows_hours:
    osint_thinktank: 36
    ngo_rights: 72
    regime_outlets: 72
    persian_services: 72
    internet_monitoring: 72
    econ_fx: 72
  critical_buckets:
    - osint_thinktank
    - ngo_rights
    - regime_outlets
    - persian_services
  report_required_fields:
    - counts_by_bucket
    - buckets_missing
    - status
  status_rules:
    fail_if_missing_critical_buckets_gte: 2
    warn_if_missing_any_bucket: true
    pass_if_missing_buckets: 0

source_health:
  file: runs/_meta/sources_health.json
  required_fields:
    - last_success_at
    - last_failure_at
    - consecutive_failures
    - last_error
    - docs_fetched_last_run
    - status
  thresholds:
    degraded_consecutive_failures_gte: 3
    down_consecutive_failures_gte: 7
  statuses:
    - OK
    - DEGRADED
    - DOWN

alerts:
  file: alerts.json
  emit_on_transition_status:
    - DEGRADED
    - DOWN

run_manifest:
  file: run_manifest.json
  required_fields:
    - git_commit
    - data_cutoff_utc
    - ingest_since_utc
    - seed
    - hashes.evidence_docs.jsonl
    - hashes.claims.jsonl
    - hashes.compiled_intel.json
  optional_fields:
    - hashes.priors_resolved.json
  deterministic_tiebreaks:
    - source_grade
    - triangulated
    - confidence
    - latest_published_at
    - claim_id

diff_report:
  file: diff_report.json
  required_fields:
    - outcome_changes.*.ci_overlap
    - outcome_changes.*.delta
    - event_rate_changes.*.delta
    - claim_winner_changes[].path
    - claim_winner_changes[].selector
    - contested_claims
    - coverage_deltas.buckets_missing_now
    - coverage_deltas.buckets_missing_prev
    - health_deltas.overall_status

run_validity:
  observe_required_artifacts:
    - run_manifest.json
    - compiled_intel.json
    - coverage_report.json
  simulate_required_artifacts:
    - run_manifest.json
    - compiled_intel.json
    - priors_resolved.json
    - simulation_results.json
  fail_if_any_missing: true

automation_guardrails:
  max_docs_per_bucket: 200
  retry:
    max_retries: 3
    initial_backoff_seconds: 2
    backoff_multiplier: 2
  cache:
    enabled: true
    path: runs/_meta/doc_cache.json
  on_coverage_fail: skip_simulation

repo_hygiene:
  forbidden_tracked_paths:
    - runs/
    - bundle_*.json
    - .env

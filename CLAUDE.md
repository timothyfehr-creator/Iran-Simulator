# CLAUDE.md — Project Context for Claude Code

## What This Is

Iran Crisis Simulator: a Monte Carlo + Agent-Based Model + Bayesian forecasting pipeline for the 2025-2026 Iranian crisis. Ingests OSINT, runs probabilistic simulations, and surfaces results through a Streamlit dashboard and React war-room frontend.

## How to Run Things

```bash
# Run tests (always do this before committing)
PYTHONPATH=.:src python -m pytest tests/ -x --timeout=30

# Run the simulation
PYTHONPATH=.:src python src/simulation.py --intel data/iran_crisis_intel.json --priors data/analyst_priors.json --runs 10000 --seed 42 --output outputs/simulation_results.json

# Run simulation with ABM (agent-based protest dynamics)
PYTHONPATH=.:src python src/simulation.py --intel data/iran_crisis_intel.json --priors data/analyst_priors.json --runs 10000 --seed 42 --abm --output outputs/simulation_results.json

# Run the full daily pipeline
PYTHONPATH=.:src python scripts/daily_update.py --auto-ingest

# Run the Live Wire pipeline
PYTHONPATH=.:src python -m src.ingest.live_wire.runner

# Frontend (React)
cd frontend && npm install && npm run dev
```

## Project Structure

```
src/simulation.py          — Core Monte Carlo simulation (1,400 LOC). Beta-PERT distributions, 5 terminal outcomes, regional cascades.
src/abm_engine.py          — Agent-Based Model (800 LOC). 10K heterogeneous agents, small-world network, defection cascades.
src/ingest/                — Fetchers for OSINT sources (ISW, HRANA, Bonbast, Nobitex, IODA, OONI, GDELT, etc.)
src/ingest/live_wire/      — 6-hourly real-time signal pipeline. Rule engine, signal quality, EMA smoothing, hysteresis.
src/ingest/extract_claims.py — GPT-4 claim extraction from evidence docs.
src/pipeline/compile_intel_v2.py — Deterministic merge of claims with tiebreak policy and conflict detection.
src/pipeline/path_registry.py — Schema registry for intelligence claim paths.
src/forecasting/           — Oracle system: catalog, ledger, ensembles, baselines, Brier scoring, leaderboard.
src/priors/contract.py     — Probability contract validation with time-basis semantics.
src/logging_config.py      — Centralized logging configuration.
scripts/daily_update.py    — Daily cron orchestrator. Ingest → extract → compile → simulate → forecast → publish.
scripts/generate_public_artifacts.py — Generates JSON snapshots for the static frontend.
config/sources.yaml        — Source definitions with URLs, fetcher types, access/bias grades, retry policies.
config/live_wire.json      — Live Wire pipeline configuration (signals, thresholds, hysteresis).
config/event_catalog.json  — 18 forecastable events with v3.0.0 schema and bin specifications.
data/analyst_priors.json   — Analyst probability estimates (transition probs, US intervention, regime outcomes).
data/iran_crisis_intel.json — Compiled intelligence input for the simulation.
frontend/                  — React + TypeScript war-room dashboard with Zustand state management.
tests/                     — 40+ test files. Run with pytest.
```

## Key Design Decisions

- **PYTHONPATH=.:src** is required for all Python commands. The `priors` module lives under `src/` and uses bare imports.
- **Deterministic reproducibility.** Simulation uses seeded RNG. Pipeline uses SHA256 manifests. Merge logic has explicit tiebreak policy.
- **Append-only ledger.** Forecasting writes to JSONL ledger files. Never mutate past entries.
- **No-lookahead enforcement.** Forecasting baselines exclude future resolutions from scoring.
- **Graceful degradation.** If an external source is down, the pipeline warns and continues with partial data. Never crash on missing external data.

## Development Rules

Read CONTRIBUTING.md for the full list. The critical ones:

- **Max 500 lines added per commit. Max 8 files changed per commit.** Split larger work.
- **Tests must pass before every commit.**
- **Frontend and backend types must match.** If the backend emits a field, the frontend TypeScript interface must declare it. Same commit.
- **Every external fetcher needs retry with exponential backoff.**
- **No AI scaffolding files in the repo.** No CLAUDE.md-style docs for other models, no skill files, no migration handoffs, no swarm briefings.
- **Aggregate metrics must be meaningful.** Don't combine categorically different events into one rate.
- **Label fields accurately.** Field names must describe what they actually contain.

## Common Pitfalls

- Forgetting `PYTHONPATH=.:src` — imports will fail.
- Modifying a function's return type without updating all callers and tests.
- Adding a new fetcher without wiring it into `config/sources.yaml` and the coordinator.
- Changing economic thresholds in `analyst_priors.json` without re-running the simulation to check the output distribution still makes sense.
- The `logs/` directory must exist before `daily_update.py` runs (it creates a FileHandler at import time).

## When Reviewing Code

Assume AI-generated code has subtle bugs. Actively look for:
- Math errors (especially probability conversions, time window calculations, staleness checks)
- Type mismatches between Python dicts and TypeScript interfaces
- Silent error swallowing in except blocks
- Metrics that combine things that shouldn't be combined
- Dead code, unused constants, vestigial imports
- Fields whose names don't match their actual data source

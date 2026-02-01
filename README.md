# Iran Crisis Simulator

**Monte Carlo + Agent-Based Model + Bayesian forecasting pipeline for the 2025–2026 Iranian crisis.**
Ingests multi-source OSINT, compiles structured intelligence, calibrates probability estimates, runs 10,000+ simulations, and surfaces results through a Streamlit dashboard and React war-room frontend.

![CI](https://github.com/timothyfehr-creator/Iran-Simulator/actions/workflows/ci.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)

<!-- Add a screenshot of the war-room frontend: -->
<!-- ![War Room](docs/screenshot.png) -->

---

## What It Does

- **OSINT ingestion** — fetches evidence from ISW, HRANA, Amnesty, HRW, BBC Persian, regime outlets, and economic indicators (Bonbast, Nobitex, TGJU, IODA)
- **Live Wire pipeline** — 6-hourly real-time signals (Nobitex USDT/IRR, Bonbast, IODA connectivity, GDELT news volume) with signal quality tracking, EMA smoothing, rule-based classification, and N-cycle hysteresis. State persisted in R2.
- **Claim extraction** — GPT-4 extracts discrete factual claims with source grading and conflict preservation
- **Intelligence compilation** — merges claims into a schema-validated intel package with baseline anchoring
- **Unified pre-simulation gate** — validates coverage, economic enrichment, economic priors (sub-key + ordering), QA, and claim extraction before simulation runs; any FAIL skips simulation and records `gate_decision=SKIP_SIMULATION` in the run manifest
- **Dual simulation engines** — state-machine Monte Carlo *and* a 10,000-agent ABM with small-world network dynamics, defection cascades, and economic stress modifiers
- **Oracle forecasting layer** — catalog of 18 events, Dirichlet-smoothed baselines, static ensembles, multinomial Brier scoring, and a leaderboard
- **Public artifacts** — war room summary, leaderboard, and live wire state published to R2 every daily run; consumed by the frontend via typed fetch service
- **Interactive dashboards** — Streamlit for analysts, React + TypeScript war-room for briefings

## Architecture

```
OSINT sources ──► Evidence ingestion ──► Claim extraction (GPT-4)
                                              │
                                              ▼
                               Compile intel + baseline anchoring
                                              │
                                              ▼
                            Analyst priors (calibrated probabilities)
                                              │
                                              ▼
                                    Unified gate (5 checks)
                                    coverage │ econ_enrichment │ econ_priors │ qa │ claims
                                              │
                                        PASS? ──── FAIL → skip simulation
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                         State-machine    Multi-agent     Oracle forecasting
                         Monte Carlo       ABM engine      (ensembles + baselines)
                              │               │               │
                              └───────┬───────┘               │
                                      ▼                       ▼
                              Simulation results        Forecast ledger
                                      │                       │
                              ┌───────┴───────┐               │
                              ▼               ▼               ▼
                         Streamlit        React           Scorecard /
                         dashboard       frontend         leaderboard

Live Wire (6-hourly, independent):
  R2 state.json ──► Fetch 4 signals ──► Classify + hysteresis ──► R2: latest/
                    (Nobitex, Bonbast,
                     IODA, GDELT)

Daily pipeline (after simulation):
  Simulation results + Live Wire (from R2) + Scorecard
       │
       ▼
  generate_public_artifacts.py ──► R2: latest/war_room_summary.json
                                   R2: latest/leaderboard.json
                                   R2: latest/live_wire_state.json
```

## Quick Start

```bash
git clone https://github.com/timothyfehr-creator/Iran-Simulator.git
cd iran_simulation

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add OPENAI_API_KEY, ANTHROPIC_API_KEY

# Run tests
python -m pytest tests/ -x --timeout=30

# Fully automated daily pipeline
python scripts/daily_update.py --auto-ingest

# Dashboards
streamlit run dashboard.py          # Streamlit
cd frontend && npm install && npm run dev   # React war-room
```

## Project Structure

```
iran_simulation/
├── config/                 # Event catalog, schemas, baseline & ensemble configs
│   └── live_wire.json      # Live Wire signal config, thresholds, hysteresis
├── data/                   # Analyst priors, baseline intel
├── frontend/               # React + TypeScript war-room dashboard
│   └── src/services/       # API clients + staticDataService (R2 fetch)
│   └── src/types/          # TypeScript interfaces (simulation + publicData)
├── forecasting/            # Ledger, reports (.gitkeep tracked)
├── knowledge/              # Stable baseline knowledge pack
├── prompts/                # Agent prompts (research, analyst, red-team)
├── scripts/
│   ├── daily_update.py     # Main daily pipeline orchestrator (unified gate + validate_econ_priors)
│   ├── generate_public_artifacts.py  # Produces war_room_summary, leaderboard, live_wire JSONs
│   └── pull_live_wire.py   # Local dev helper: download live wire data from R2
├── src/
│   ├── abm_engine.py       # Multi-agent ABM (Project Swarm)
│   ├── logging_config.py   # Shared structured logging setup
│   ├── simulation.py       # State-machine Monte Carlo (no silent fallbacks)
│   ├── forecasting/        # Oracle layer (catalog, ensembles, baselines, scoring)
│   ├── ingest/             # Evidence fetching (ISW, HRANA, BBC, etc.)
│   │   ├── live_wire/      # 6-hourly signal pipeline (quality, rules, EMA, runner)
│   │   ├── fetch_nobitex.py# Nobitex USDT/IRR exchange rate
│   │   └── fetch_bonbast.py# Bonbast black-market Rial rate
│   ├── mcp/                # MCP math-model server
│   ├── pipeline/           # Intel compilation, diff reports, path registry
│   ├── priors/             # Priors contract and resolution
│   └── report/             # Report generation
├── tests/                  # Pytest suite (764 tests)
├── dashboard.py            # Streamlit entry point
└── requirements.txt
```

## License

MIT — see [LICENSE](LICENSE).

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

- **OSINT ingestion** — fetches evidence from ISW, HRANA, Amnesty, HRW, BBC Persian, regime outlets, and economic indicators (Bonbast, TGJU, IODA)
- **Claim extraction** — GPT-4 extracts discrete factual claims with source grading and conflict preservation
- **Intelligence compilation** — merges claims into a schema-validated intel package with baseline anchoring
- **Dual simulation engines** — state-machine Monte Carlo *and* a 10,000-agent ABM with small-world network dynamics, defection cascades, and economic stress modifiers
- **Oracle forecasting layer** — catalog of 18 events, Dirichlet-smoothed baselines, static ensembles, multinomial Brier scoring, and a leaderboard
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
├── data/                   # Analyst priors, baseline intel
├── frontend/               # React + TypeScript war-room dashboard
├── forecasting/            # Ledger, reports (.gitkeep tracked)
├── knowledge/              # Stable baseline knowledge pack
├── prompts/                # Agent prompts (research, analyst, red-team)
├── scripts/                # Daily update, sensitivity analysis, cron wrapper
├── src/
│   ├── abm_engine.py       # Multi-agent ABM (Project Swarm)
│   ├── simulation.py       # State-machine Monte Carlo
│   ├── forecasting/        # Oracle layer (catalog, ensembles, baselines, scoring)
│   ├── ingest/             # Evidence fetching (ISW, HRANA, BBC, etc.)
│   ├── mcp/                # MCP math-model server
│   ├── pipeline/           # Intel compilation, diff reports, path registry
│   ├── priors/             # Priors contract and resolution
│   └── report/             # Report generation
├── tests/                  # Pytest suite
├── dashboard.py            # Streamlit entry point
└── requirements.txt
```

## License

MIT — see [LICENSE](LICENSE).

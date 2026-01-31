# Iran Crisis Simulation

Monte Carlo and agent-based simulation of the 2025-2026 Iranian crisis. The system ingests multi-source OSINT, compiles structured intelligence, calibrates probability estimates, runs 10,000+ simulations (state-machine MC or network-based ABM), and surfaces results through a Streamlit dashboard and React war-room frontend.

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

## Prerequisites

- Python 3.12+
- Node 18+ (for the React frontend only)

## Local Install

```bash
# Clone and enter the repo
git clone <repo-url> && cd iran_simulation

# Python dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env — add OPENAI_API_KEY, ANTHROPIC_API_KEY

# (Optional) React frontend
cd frontend && npm install && cd ..
```

## Smoke Test

```bash
python -m pytest tests/ -x --timeout=30
```

## Daily Pipeline

```bash
# Fully automated: fetch evidence, extract claims, compile, simulate, report
python scripts/daily_update.py --auto-ingest
```

## Dashboard

```bash
# Streamlit dashboard
streamlit run dashboard.py

# React war-room frontend
cd frontend && npm run dev
```

## Output Locations

| Path | Contents |
|------|----------|
| `runs/RUN_YYYYMMDD_*/` | Per-run artifacts (intel, priors, simulation results, manifests) |
| `forecasting/ledger/` | Append-only forecast ledger and resolutions |
| `forecasting/reports/` | Scorecards and leaderboard reports |

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
├── requirements.txt
└── CLAUDE.md               # Detailed instructions for Claude Code
```

## License

MIT — see [LICENSE](LICENSE).

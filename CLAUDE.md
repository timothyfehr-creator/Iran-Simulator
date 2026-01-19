# CLAUDE.md - Instructions for Claude Code

This file provides context and instructions for Claude Code when working on this project.

## Project Overview

This is a Monte Carlo simulation of the 2025-2026 Iranian protests. The goal is to:
1. Gather structured intelligence on the crisis
2. Convert intelligence into calibrated probability estimates
3. Run 10,000+ simulations to generate outcome distributions
4. Visualize results with maps and charts

## Agent Architecture

The project uses SIX specialized agents/prompts:

### 1. Research Agent (prompts/01_research_prompt.md) - LEGACY
- **Status:** Original comprehensive prompt (still valid for manual Deep Research)
- **Run via:** Deep Research (separate Claude conversation)
- **Input:** The prompt itself
- **Output:** Complete `iran_crisis_intel.json`
- **Purpose:** Comprehensive intelligence collection in single pass
- **Note:** Use **03_deep_research_source_gathering.md** for automated pipeline

### 2. Security Analyst Agent (prompts/02_security_analyst_prompt.md)
- **Run via:** Claude Code or Claude conversation
- **Input:** `compiled_intel.json` + `compiled_baseline.json`
- **Output:** `analyst_priors.json`
- **Purpose:** Convert intelligence into calibrated probability estimates with base rate anchoring

### 3. **NEW: Deep Research Source Gathering (prompts/03_deep_research_source_gathering.md)**
- **Run via:** Deep Research conversation OR automated pipeline
- **Input:** Multi-source OSINT requirements
- **Output:** Evidence bundle (evidence_docs.jsonl, candidate_claims.jsonl, source_index.json)
- **Purpose:** Gather raw evidence from 10+ sources with proper citations and source grading
- **Integration:** Feeds automated ingestion system (`src/ingest/`)

### 4. **NEW: Schema Extraction & Analysis (prompts/04_schema_extraction_and_analysis.md)**
- **Run via:** Claude Opus 5.2 (recommended) or Claude Code
- **Input:** Evidence bundles + baseline knowledge
- **Output:** `compiled_intel.json`, `analyst_priors.json`, simulation analysis
- **Purpose:** THREE functions:
  1. Schema-compliant intelligence compilation
  2. Calibrated prior generation with base rate anchoring
  3. Simulation results interpretation and sensitivity analysis
- **Why 5.2:** Superior schema adherence, probabilistic reasoning, long-context handling

### 5. Simulation Engine (src/simulation.py)
- **Run via:** Python
- **Input:** `compiled_intel.json` + `analyst_priors.json`
- **Output:** `simulation_results.json`
- **Purpose:** Run 10,000 Monte Carlo simulations

### 6. Red Team Agent (prompts/05_red_team_prompt.md) - NEW v2.1
- **Run via:** Claude conversation with analyst_priors.json
- **Input:** `analyst_priors.json` + `compiled_intel.json`
- **Output:** `red_team_critique.json`
- **Purpose:** Challenge overconfident estimates, identify weak evidence, propose revisions
- **When to use:** After generating priors, before final simulation for decision support

## Automated Pipeline Workflow (NEW)

### Full Automation: `scripts/daily_update.py --auto-ingest`

The system now supports fully automated evidence collection and intelligence compilation:

```bash
# Set OpenAI API key for claim extraction
export OPENAI_API_KEY=sk-your-key-here

# Run complete automated daily update
python scripts/daily_update.py --auto-ingest --cutoff 2026-01-11T23:59:59Z
```

**What happens:**
1. **Evidence Fetching** (src/ingest/coordinator.py)
   - Fetches from 10+ sources: ISW, HRANA, Amnesty, HRW, BBC Persian, regime outlets
   - Generates evidence_docs.jsonl with proper source grading
   - Creates source_index.json automatically

2. **Claim Extraction** (src/ingest/extract_claims.py)
   - Uses GPT-4 API to extract discrete factual claims
   - Generates candidate_claims.jsonl with schema paths
   - Preserves conflicting data from different sources

3. **Bundle Creation** (scripts/daily_update.py)
   - Packages evidence + claims into bundle_auto_ingest.json
   - Includes metadata (data_cutoff, source diversity)

4. **Standard Pipeline** (existing)
   - Import → Compile → Simulate → Report → Diff
   - Same as manual bundle workflow

### Manual Deep Research Workflow (Alternative)

For custom intelligence collection or when automation is unavailable:

1. **Use Prompt 03** (Deep Research conversation)
   - Load `prompts/03_deep_research_source_gathering.md`
   - Gather evidence from multiple sources
   - Generate evidence bundle manually

2. **Use Prompt 04** (Claude Opus 5.2)
   - Load evidence bundle + baseline knowledge
   - Function 1: Compile to schema-compliant intel
   - Function 2: Generate calibrated priors
   - Function 3: Analyze simulation results

3. **Run Simulation** (Python)
   - Use compiled outputs from step 2

## Your Tasks (Claude Code)

### If user says "run the simulation" or similar:

1. Check if `data/iran_crisis_intel.json` has real data (not placeholder)
   - If placeholder: Tell user to run research prompt through Deep Research first
   
2. Check if `data/analyst_priors.json` has real data
   - If placeholder: Offer to generate priors by acting as Security Analyst Agent
   - Load the intel file, apply analyst prompt reasoning, output calibrated priors
   
3. Run simulation:
   ```bash
   python src/simulation.py \
       --intel data/iran_crisis_intel.json \
       --priors data/analyst_priors.json \
       --runs 10000 \
       --output outputs/simulation_results.json
   ```

4. Run visualization:
   ```bash
   pip install matplotlib seaborn
   python src/visualize.py \
       --results outputs/simulation_results.json \
       --intel data/iran_crisis_intel.json \
       --output-dir outputs
   ```

5. Present results to user:
   - Show outcome distribution
   - Highlight key findings
   - Note major uncertainties

### If user provides intel JSON:

1. Save to `data/iran_crisis_intel.json`
2. Generate analyst priors (act as Security Analyst Agent)
3. Proceed with simulation

### If user asks to update priors:

1. Load current intel
2. Discuss which estimates to adjust and why
3. Update `data/analyst_priors.json`
4. Re-run simulation
5. Compare to previous results

### If user asks about methodology:

- Explain the three-agent architecture
- Explain why probabilities are analyst estimates (not measured)
- Explain Monte Carlo approach and its limitations
- Be honest about epistemic uncertainty

### If user says "red team the priors" or "challenge the estimates":

1. Load `data/analyst_priors.json` and `runs/*/compiled_intel.json`
2. Apply red team prompt methodology
3. Identify 3-5 weakest estimates
4. Propose specific numeric revisions with reasoning
5. Optionally re-run simulation with revised priors

### If user says "run sensitivity analysis":

1. Run sensitivity script:
   ```bash
   python scripts/sensitivity_analysis.py \
       --intel runs/RUN_*/compiled_intel.json \
       --priors data/analyst_priors.json \
       --runs 1000 \
       --output outputs/sensitivity_analysis.json
   ```
2. Present top 10 most sensitive parameters
3. Explain which priors most affect outcome distribution

## v2.1 Enhancements

New features in v2.1 that improve simulation quality:

### Feedback Loops (src/simulation.py)
- **Concession dampening:** When regime makes concessions, protest escalation probability drops by 50%
- **Defection dampening:** Concessions reduce security force defection probability by 30%
- **Regional cascade:** Iraq/Syria instability increases regime crackdown probability by 20%

### Evidence Quality Gate (prompts/03_deep_research_source_gathering.md)
- Claims below grade B3 are flagged for review
- Source diversity requirements: minimum 3 independent sources for high-confidence claims
- Conflicting data preserved with source attribution

### ACH Pre-Mortem (prompts/02_security_analyst_prompt.md)
- Analysis of Competing Hypotheses integration
- Structured consideration of alternative outcomes
- Pre-mortem analysis: "What would have to be true for this estimate to be wrong?"

### Tail Risk Labels (src/visualize.py)
- Visual indicators for low-probability, high-impact scenarios
- Outcomes below 5% probability marked with tail risk warnings
- Helps avoid dismissing unlikely but catastrophic outcomes

### Path Normalization (config/path_registry_v2.json)
- Standardized file path resolution across environments
- Automatic detection of run folders and output directories
- Backwards-compatible with v1 path conventions

## v2.2: Economic Integration

The simulation now uses economic indicators from compiled_intel.json to adjust event probabilities.

### Economic State Machine (src/simulation.py)
Classifies economic stress into three levels based on Rial exchange rate and inflation:
- **STABLE:** Rial < 800k IRR/USD, inflation < 30%
- **PRESSURED:** Rial 800k-1.2M IRR/USD, inflation 30-50%
- **CRITICAL:** Rial > 1.2M IRR/USD OR inflation > 50%

### Effects on Simulation
Economic stress modifies base probabilities for key events:
- **CRITICAL:** +20% protest escalation, +30% elite fracture, +15% security defection
- **PRESSURED:** +10% protest escalation, +15% elite fracture, +8% security defection
- **STABLE:** No modifiers applied

### Configuration (data/analyst_priors.json)
Thresholds and multipliers are configurable via priors:
```json
{
  "economic_thresholds": {
    "rial_critical_threshold": 1200000,
    "inflation_critical_threshold": 50
  },
  "economic_modifiers": {
    "critical_protest_escalation_multiplier": 1.20
  }
}
```

### Data Sources
- **Bonbast:** Black market Rial exchange rate (via src/ingest/fetch_web.py)
- **TGJU:** Tehran gold/currency prices (via src/ingest/fetch_web.py)
- **IODA:** Internet connectivity index (via src/ingest/fetch_ioda.py) - NEW

### Simulation Output
Results now include an `economic_analysis` section:
```json
{
  "economic_analysis": {
    "stress_level": "critical",
    "rial_rate_used": 1500000,
    "inflation_used": 42,
    "modifiers_applied": {
      "protest_escalation": 1.20,
      "elite_fracture": 1.30,
      "security_defection": 1.15
    }
  }
}
```

### Testing
Run economic integration tests:
```bash
# Unit tests
python -m pytest tests/test_economic_state.py -v

# Integration tests
python -m pytest tests/test_economic_integration.py -v

# End-to-end test
bash scripts/test_economic_e2e.sh
```

## v2.3: Multi-Agent ABM (Project Swarm)

The daily pipeline now uses a multi-agent Agent-Based Model instead of the simple state machine Monte Carlo.

### Architecture (src/abm_engine.py)
10,000 heterogeneous agents across 5 types:
- **STUDENT (15%)** - The Spark: Low activation threshold during escalation
- **MERCHANT (20%)** - The Fuel: Graduated economic sensitivity to Rial collapse
- **CONSCRIPT (10%)** - Security forces that can defect under pressure
- **HARDLINER (5%)** - Loyal security, suppresses neighboring agents
- **CIVILIAN (50%)** - Standard threshold model with exhaustion

### Network Dynamics
- Small-world network topology (8 neighbors average, 10% rewiring)
- Protest contagion spreads through social connections
- Hardliners create "cold spots" that slow cascade
- Exhaustion creates protest waves (not monotonic growth)

### Defection Cascade
Conscripts can defect when:
1. >50% of neighbors are actively protesting (overwhelmed)
2. Crackdown intensity exceeds moral injury threshold (0.6)
3. >40% of fellow conscripts have defected (contagion)
4. **30% total conscript defection → macro regime crisis**

### Key Differences from State Machine
| Metric | State Machine | ABM |
|--------|--------------|-----|
| Regime Survives | ~83% | ~73% |
| Security Defection | ~3% | ~8% |
| Ethnic Uprising | ~9% | ~22% |
| Collapse Risk | ~4% | ~7% |

The ABM produces more volatile, realistic outcomes by capturing network effects.

### Running Without ABM
To run the old state machine (for comparison):
```bash
python3 src/simulation.py --intel ... --priors ... --runs 10000 --output ...
# (omit --abm flag)
```

## v2.4: Plan A - Pipeline Hardening

This version implements comprehensive pipeline hardening for production reliability and reproducibility.

### Rolling-Window Coverage Gates (src/ingest/coverage.py)

Coverage gates are now rolling-window based rather than simple existence checks:

| Bucket | Window (hours) | Category |
|--------|----------------|----------|
| osint_thinktank | 36 | Critical |
| ngo_rights | 72 | Critical |
| regime_outlets | 72 | Critical |
| persian_services | 72 | Critical |
| internet_monitoring | 72 | Non-critical |
| econ_fx | 72 | Non-critical |

Coverage report structure:
```json
{
  "status": "PASS",
  "buckets_ok": ["osint_thinktank", "ngo_rights", ...],
  "buckets_missing": [],
  "quality_gates": {
    "min_docs_passed": true,
    "farsi_source_present": true,
    "buckets_ok": 6
  },
  "health_summary": {
    "sources_ok": 8,
    "sources_degraded": 1,
    "sources_down": 0,
    "overall_status": "DEGRADED"
  }
}
```

### Run Manifest with Hashing (src/run_manifest.py)

Every run now generates `run_manifest.json` for reproducibility:
```json
{
  "git_commit": "abc123...",
  "data_cutoff_utc": "2025-01-19T00:00:00Z",
  "ingest_since_utc": "2025-01-16T00:00:00Z",
  "seed": 42,
  "deterministic_tiebreaks": ["source_grade", "triangulated", "confidence", "latest_published_at", "claim_id"],
  "hashes": {
    "evidence_docs.jsonl": "sha256:...",
    "claims.jsonl": "sha256:...",
    "compiled_intel.json": "sha256:...",
    "priors_resolved.json": "sha256:..."
  },
  "coverage_status": "PASS",
  "run_reliable": true
}
```

The manifest enables:
- **Reproducibility:** Re-run with same seed produces identical results
- **Audit trail:** Track exact git commit and data inputs
- **Reliability flag:** `run_reliable: false` if coverage failed

### Coverage & Health Deltas (src/pipeline/run_comparator.py)

Diff reports now include detailed deltas:
```json
{
  "coverage_deltas": {
    "buckets_missing_now": ["internet_monitoring"],
    "buckets_missing_prev": []
  },
  "health_deltas": {
    "overall_status": "DEGRADED",
    "transitions": [{"source": "bonbast", "from": "OK", "to": "DEGRADED"}]
  },
  "contested_claims": [
    {"path": "economic.inflation_rate", "conflict_group": ["claim_123", "claim_456"], "winner": "claim_123"}
  ]
}
```

### Automation Guardrails (config/ingest.yaml)

Configurable guardrails prevent runaway costs and handle failures gracefully:
```yaml
max_docs_per_bucket: 200
retry:
  max_retries: 3
  initial_backoff_seconds: 2
  backoff_multiplier: 2
cache:
  enabled: true
  path: runs/_meta/doc_cache.json
on_coverage_fail: skip_simulation
```

When `on_coverage_fail: skip_simulation` is set, coverage failures will:
1. Skip the simulation stage
2. Set `run_reliable: false` in the manifest
3. Still generate the diff report for review

### ABM Reproducibility

The ABM engine now accepts a seed parameter for deterministic runs:
```bash
# Deterministic (reproducible)
python3 src/simulation.py --intel ... --priors ... --abm --seed 42

# Non-deterministic (production default)
python3 src/simulation.py --intel ... --priors ... --abm
```

Seeding affects:
- Agent activation order
- Network topology generation
- All random choices in agent behavior

### Portable Cron Wrapper (scripts/run_daily_cron.sh)

Production-ready cron wrapper with:
- **Dynamic paths:** Computes PROJECT_DIR from script location
- **Lock file:** Prevents concurrent runs
- **Graceful alerting:** Sends email on failure (if `mail` command exists)
- **Exit code propagation:** Correct exit status for monitoring

```bash
# Set alert email (optional)
export DAILY_UPDATE_EMAIL=ops@example.com

# Add to crontab (runs at 6 AM UTC daily)
0 6 * * * /path/to/iran_simulation/scripts/run_daily_cron.sh
```

### Run Validation Helpers (src/run_utils.py)

Helper functions for validating run folders:
```python
from src.run_utils import (
    list_runs_sorted,
    is_run_valid_for_observe,
    is_run_valid_for_simulate,
    get_run_reliability
)

# List runs by date (excludes _meta, TEST_*)
runs = list_runs_sorted()

# Check if run can be observed
if is_run_valid_for_observe(run_dir):
    # Has: run_manifest.json, compiled_intel.json, coverage_report.json

# Check if run can be simulated
if is_run_valid_for_simulate(run_dir):
    # Has: run_manifest.json, compiled_intel.json, priors_resolved.json, simulation_results.json

# Get reliability status
is_reliable, reason = get_run_reliability(run_dir)
```

### Testing Plan A Features

```bash
# Run all Plan A tests
python -m pytest tests/test_run_manifest.py tests/test_run_utils.py \
    tests/test_guardrails.py tests/test_coverage_windows.py -v

# Verify ABM seeding reproducibility
python3 src/simulation.py --intel data/intel.json --priors data/priors.json \
    --abm --seed 42 --runs 100 --output /tmp/run1.json
python3 src/simulation.py --intel data/intel.json --priors data/priors.json \
    --abm --seed 42 --runs 100 --output /tmp/run2.json
diff /tmp/run1.json /tmp/run2.json  # Should be identical
```

## Important Principles

1. **Never fabricate data.** If intel is missing, say so.
2. **Probabilities are subjective.** They represent analyst judgment, not ground truth.
3. **Uncertainty is a feature.** Wide confidence intervals are honest.
4. **Base rates matter.** Always anchor to historical frequencies before adjusting.
5. **Regime survival is the base case.** Authoritarian regimes usually survive protests.

## File Locations

```
# Core data files
data/iran_crisis_intel.json    # Intel from Research Agent
data/analyst_priors.json       # Priors from Security Analyst Agent

# Baseline knowledge (stable reference data)
knowledge/iran_baseline/
  evidence_docs.jsonl          # Source citations
  claims.jsonl                 # Structured baseline claims
  compiled_baseline.json       # Packaged baseline knowledge

# Simulation outputs
outputs/simulation_results.json
outputs/outcome_distribution.png
outputs/iran_protest_map.svg
outputs/event_rates.png
outputs/scenario_narratives.md
```

## Baseline Knowledge Workflow

The baseline pack contains stable reference knowledge (regime structure, protest history, ethnic composition) that the Security Analyst uses to anchor base rate estimates.

### If user says "compile baseline" or "update baseline":

1. Compile the baseline knowledge:
   ```bash
   python -m src.pipeline.compile_baseline \
       --evidence knowledge/iran_baseline/evidence_docs.jsonl \
       --claims knowledge/iran_baseline/claims.jsonl \
       --outdir knowledge/iran_baseline/
   ```

2. Check the QA report for completeness:
   ```bash
   cat knowledge/iran_baseline/baseline_qa.json
   ```

### If user provides baseline research:

1. Save evidence docs to `knowledge/iran_baseline/evidence_docs.jsonl`
2. Save claims to `knowledge/iran_baseline/claims.jsonl`
3. Run compile_baseline.py
4. Verify coverage in baseline_qa.json

### How baseline integrates with priors:

When generating analyst priors, the Security Analyst Prompt now requires:
- Reading BOTH `compiled_intel.json` AND `compiled_baseline.json`
- Citing baseline data in `base_rate_anchor` fields
- Documenting how current intel differs from historical patterns

## Dependencies

```bash
pip install -r requirements.txt
# Optional: geopandas for better maps
```

## API Keys Setup

For scripts that call OpenAI or Anthropic APIs:

1. Copy `.env.example` to `.env` in repo root
2. Add your API keys
3. Verify with: `python -m src.config.secrets --check`

Usage in code:
```python
from src.config.secrets import get_openai_key, get_anthropic_key

# Raises MissingAPIKeyError if not configured
key = get_openai_key()
```

## Mission Control Dashboard

Interactive Streamlit dashboard for viewing past runs and running ad-hoc simulations.

### Running the Dashboard

```bash
# Using Make
make dashboard

# Or directly
streamlit run dashboard.py
```

### Dashboard Modes

**Observe Mode:**
- Select a run folder from the dropdown (defaults to latest)
- View pipeline status badges (QA, Coverage)
- See outcome distribution chart
- View key event rates and regional cascade rates
- Check diff reports if available
- TEST_* folders hidden by default (toggle to show)

**Simulate Mode:**
- Requires `compiled_intel.json` in the source run
- Run status indicators:
  - ✅ Ready: Has both intel and priors
  - ⚠️ No priors: Has intel but missing priors (uses fallback)
  - 🔧 Needs compile: Has claims but no intel (compile button available)
  - ❌ Import only: No claims or intel
- If intel is missing but claims exist, click "Compile Intel" to generate it
- Adjust parameters:
  - Max runs (100-2000)
  - Security force defection probability (0.0-0.30)
  - Protest growth factor (1.0-2.0)
- Click "Run Simulation" to execute
- Results saved to `runs/ADHOC_YYYYMMDD_HHMM/`

## Common Issues

1. **"Prior not found" error:** Check analyst_priors.json schema matches what simulation expects
2. **Visualization fails:** Install matplotlib/seaborn
3. **Results seem wrong:** Check that regime outcomes sum to 1.0 in priors
4. **Dashboard won't start:** Install dependencies with `pip install streamlit plotly pandas`

# CLAUDE.md - Instructions for Claude Code

This file provides context and instructions for Claude Code when working on this project.

## Project Overview

This is a Monte Carlo simulation of the 2025-2026 Iranian protests. The goal is to:
1. Gather structured intelligence on the crisis
2. Convert intelligence into calibrated probability estimates
3. Run 10,000+ simulations to generate outcome distributions
4. Visualize results with maps and charts

## Agent Architecture

The project uses FIVE specialized agents/prompts:

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

## Common Issues

1. **"Prior not found" error:** Check analyst_priors.json schema matches what simulation expects
2. **Visualization fails:** Install matplotlib/seaborn
3. **Results seem wrong:** Check that regime outcomes sum to 1.0 in priors

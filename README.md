# Iran Crisis Simulation

Monte Carlo simulation of the 2025-2026 Iranian protests and potential outcomes over a 90-day horizon.

## Project Structure

```
iran_simulation/
├── README.md                          # This file
├── prompts/
│   ├── 01_research_prompt.md          # Deep Research query for intel gathering
│   └── 02_security_analyst_prompt.md  # Analyst agent for probability estimation
├── schemas/
│   └── (JSON schemas extracted from prompts)
├── data/
│   ├── iran_crisis_intel.json         # Output from Research Agent (you provide)
│   └── analyst_priors.json            # Output from Security Analyst Agent
├── src/
│   ├── simulation.py                  # Monte Carlo simulation engine
│   └── visualize.py                   # Maps and charts
└── outputs/
    ├── simulation_results.json        # Raw simulation output
    ├── outcome_distribution.png       # Outcome probability chart
    ├── iran_protest_map.svg           # Geographic visualization
    ├── event_rates.png                # Key event frequency chart
    └── scenario_narratives.md         # Written scenario descriptions
```

## Workflow

### Phase 0: Intelligence Gathering

1. Run the research prompt (`prompts/01_research_prompt.md`) through Deep Research
2. Save the output as `data/iran_crisis_intel.json`

### Phase 1: Prior Calibration

1. Feed `iran_crisis_intel.json` to Claude with the security analyst prompt (`prompts/02_security_analyst_prompt.md`)
2. Save the output as `data/analyst_priors.json`

**Note on probability semantics:** in `analyst_priors.json`, most parameters are interpreted as
"probability this event happens at least once within a window". The simulator converts these
to constant daily hazards using: `1 - (1 - p_window)^(1/window_days)`. The `probability` objects
support optional fields:
- `window_days` (int) — window length used by the simulator (defaults are documented in `src/simulation.py`)
- `dist`: `beta_pert|triangular|fixed` (default: `triangular`)
- `mode` (float) — optional mode for `beta_pert` (defaults to `point`)

### Phase 2: Simulation

```bash
cd iran_simulation
python src/simulation.py \
    --intel data/iran_crisis_intel.json \
    --priors data/analyst_priors.json \
    --runs 10000 \
    --output outputs/simulation_results.json
```

### Phase 3: Visualization

```bash
python src/visualize.py \
    --results outputs/simulation_results.json \
    --intel data/iran_crisis_intel.json \
    --output-dir outputs
```

## Requirements

```bash
pip install -r requirements.txt

# Or manually:
pip install matplotlib seaborn python-dotenv
# Optional for enhanced maps:
pip install geopandas
```

## Secrets Setup

API keys are loaded from a `.env` file in the repo root (never committed to git).

### Quick Start

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Edit .env and add your keys
#    OPENAI_API_KEY=sk-...
#    ANTHROPIC_API_KEY=sk-ant-...

# 3. Verify keys are detected
python -m src.config.secrets --check
```

### Expected Output

```
OPENAI_API_KEY: OK
ANTHROPIC_API_KEY: OK

All keys configured.
```

### Usage in Code

```python
from src.config.secrets import get_openai_key, get_anthropic_key

# These will raise MissingAPIKeyError if not configured
openai_key = get_openai_key()
anthropic_key = get_anthropic_key()
```

## Claude Code Instructions

When running this project, Claude Code should:

1. **If `data/iran_crisis_intel.json` is missing:**
   - Inform user they need to run the research prompt through Deep Research first
   - Offer to help interpret the research prompt

2. **If `data/analyst_priors.json` is missing:**
   - Load `iran_crisis_intel.json`
   - Use the security analyst prompt to generate probability estimates
   - Save as `data/analyst_priors.json`

3. **Run simulation:**
   - Execute `simulation.py` with the data files
   - Default to 10,000 runs
   - Use random seed for reproducibility if requested

4. **Generate visualizations:**
   - Run `visualize.py`
   - Present outputs to user

5. **Interpret results:**
   - Summarize outcome distribution
   - Highlight key findings
   - Note major uncertainties

## Key Outputs

### Outcome Distribution
The simulation produces probabilities for five mutually exclusive outcomes:
- REGIME_SURVIVES_STATUS_QUO
- REGIME_SURVIVES_WITH_CONCESSIONS
- MANAGED_TRANSITION
- REGIME_COLLAPSE_CHAOTIC
- ETHNIC_FRAGMENTATION

### Key Event Rates
Frequency of critical events across all simulations:
- US intervention (any non-rhetorical US posture: information/economic/covert/cyber/kinetic/ground)
- Security force defection
- Khamenei death
- Ethnic uprising

### Economic Analysis (v2.2)
The simulation output includes economic stress assessment:
- `stress_level`: STABLE, PRESSURED, or CRITICAL
- `rial_rate_used`: Exchange rate from intel (IRR/USD)
- `inflation_used`: Inflation rate from intel (%)
- `modifiers_applied`: Probability adjustments by event type

Economic stress affects event probabilities:
- **CRITICAL** (Rial > 1.2M or inflation > 50%): +20% protest escalation, +15% defection
- **PRESSURED** (Rial 800k-1.2M or inflation 30-50%): +10% protest escalation, +8% defection
- **STABLE**: No modifiers

Data sources: Bonbast (Rial rates), TGJU (currency), IODA (internet connectivity).

### Scenario Narratives
Human-readable descriptions of each outcome with:
- Probability and confidence interval
- Typical timing
- Sample event trajectories

## Sensitivity Analysis

Run automated sensitivity analysis to understand which inputs most affect outcomes:

```bash
python scripts/sensitivity_analysis.py \
    --intel runs/RUN_YYYYMMDD/compiled_intel.json \
    --priors data/analyst_priors.json \
    --runs 1000 \
    --output outputs/sensitivity_analysis.json
```

**Interpreting Results:**
- **Tornado chart:** Shows parameters ranked by impact on outcome variance
- **Top parameters:** Usually defection probability, protest sustainability, and crackdown effectiveness
- **Sensitivity index:** Higher values mean small prior changes cause large outcome shifts

**Key parameters to test:**
- `security_force_defection_given_protests_30d` - Usually highest sensitivity
- `protests_sustain_30d` - Critical for regime survival scenarios
- `kinetic_strike_given_crackdown` - High variance due to external dependencies
- `protests_collapse_given_crackdown_30d` - Affects regime control margin
- `meaningful_concessions_given_protests_30d` - Triggers feedback loops

## Red Team Review

The Red Team Agent (`prompts/05_red_team_prompt.md`) provides structured critique of analyst priors.

**When to use:**
- After generating analyst_priors.json
- When confidence intervals seem too narrow
- Before finalizing simulation for decision support

**What it provides:**
- Identification of 3-5 weakest estimates
- Historical base rate challenges
- Alternative scenarios analysis
- Specific revision suggestions

**Usage:** Run the prompt manually with `analyst_priors.json` and `compiled_intel.json` as context.

## Regional Cascade Modeling

v2.1 adds bidirectional regional effects:

- **Iran → Iraq/Syria:** Crisis in Iran destabilizes neighbors
- **Iraq/Syria → Iran:** Regional instability increases regime anxiety (crackdown probability +20%)
- **Feedback loops:**
  - Concessions dampen protest escalation (-50%)
  - Concessions reduce defection probability (-30%)

Check `regional_cascade_rates` in simulation output for spillover probabilities

## Pipeline Hardening (v2.4)

Production-ready features for reliability and reproducibility:

### Rolling-Window Coverage Gates
Coverage checks now use time-based windows (36-72 hours per bucket type) rather than simple existence checks. Critical buckets (osint_thinktank, ngo_rights, regime_outlets, persian_services) must have recent data for the run to be considered reliable.

### Run Manifest
Every run produces `run_manifest.json` with:
- Git commit hash
- Data cutoff and ingestion window
- SHA256 hashes of input files
- Seed for ABM reproducibility
- Reliability flag (`run_reliable: true/false`)

### ABM Seeding
For reproducible simulations, pass `--seed` to the simulator:
```bash
python src/simulation.py --intel ... --priors ... --abm --seed 42
```
Two runs with the same seed produce identical results.

### Coverage & Health Deltas
Diff reports now include:
- `coverage_deltas`: Which buckets went missing/recovered between runs
- `health_deltas`: Source health transitions (OK → DEGRADED → DOWN)
- `contested_claims`: Conflicting claims and their resolution

### Automation Guardrails
Configure `config/ingest.yaml` to:
- Set `on_coverage_fail: skip_simulation` to mark unreliable runs
- Cap documents per bucket to control costs
- Enable document caching

### Cron Automation
Use the hardened cron wrapper for daily updates:
```bash
# Add to crontab (runs at 6 AM UTC)
0 6 * * * /path/to/iran_simulation/scripts/run_daily_cron.sh
```
Features: portable paths, lock file, graceful alerting.

See `CLAUDE.md` for detailed documentation.

## Limitations

- **Epistemic uncertainty:** Probabilities are analyst estimates, not measured frequencies
- **Model simplification:** Real-world dynamics are more complex than state transitions
- **Data gaps:** Intel may be incomplete, especially on regime internals
- **Black swans:** Model cannot capture truly unforeseen events
- **Reflexivity:** Publishing predictions can influence outcomes

## Updating the Simulation

As the crisis evolves:

1. Re-run research prompt with updated date
2. Re-calibrate analyst priors with new evidence
3. Re-run simulation
4. Compare to previous run to see how probabilities shifted

## License

For personal intellectual use. Not for policy decisions.


## New: Priors contract QA + resolved priors output

When you run the simulator, it will now:
- Resolve priors semantics (time_basis / anchor / window enforcement)
- Emit:
  - `priors_resolved.json`
  - `priors_qa.json`
next to your simulation output file (by default in `outputs/`).

If priors contract validation fails, the run will fail fast with a clear error message.

## Optional: Evidence → Claims → Compiler (MVP)

To reduce hallucination pressure and make every number traceable, you can compile your intel from a claims ledger.

MVP flow:
1) Collect evidence documents externally (Deep Research or manual) and store as `evidence_docs.jsonl` (not automated yet).
2) Run collector(s) to produce one or more `claims_*.jsonl` files (one JSON per line).
3) Compile claims into `compiled_intel.json`:

```bash
python src/pipeline/compile_intel.py \
  --claims path/to/claims_1.jsonl path/to/claims_2.jsonl \
  --template data/iran_crisis_intel.json \
  --outdir runs/compiled
```

This produces:
- `runs/compiled/compiled_intel.json`
- `runs/compiled/merge_report.json`
- `runs/compiled/qa_report.json`

Then run the simulator using `compiled_intel.json` as the `--intel` input.

## Evidence Ingestion: ISW Daily Updates

Fetch Institute for the Study of War (ISW) Iran updates to populate the evidence pipeline with high-quality OSINT think tank analysis:

### Initial Backfill

```bash
# Install dependencies
pip install -r requirements.txt

# Fetch initial 15 seed URLs
python -m src.ingest.fetch_isw_updates --seed
```

This creates:
- `ingest/isw_output/evidence_docs_isw.jsonl` - Evidence documents
- `ingest/isw_output/source_index_isw.json` - Source metadata
- `ingest/isw_output/ingest_report.json` - Fetch summary

### Daily Updates (Future)

```bash
# Fetch latest N updates
python -m src.ingest.fetch_isw_updates --latest 1 --output ingest/daily_$(date +%Y%m%d)
```

### Configuration

Edit `config/sources_isw.yaml` to:
- Add new seed URLs
- Adjust scraping selectors if ISW changes their HTML
- Modify NATO grading (default: B/2)

### Integration with Pipeline

ISW evidence docs use the same JSONL format as Deep Research outputs. To combine them:

1. Fetch ISW updates (generates `evidence_docs_isw.jsonl`)
2. Manually merge with other evidence sources or use standalone
3. Import via `import_deep_research_bundle_v3.py` for cutoff enforcement and validation

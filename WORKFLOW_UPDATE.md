# Workflow: Updating Simulation with New Deep Research

This guide explains how to update the Iran Crisis Simulator when you obtain new intelligence from a Deep Research query.

---

## Quick Start

**If you have new Deep Research results:**

1. Provide the Deep Research output to Claude Code
2. Claude Code will:
   - Extract and structure the intelligence data
   - Save as `data/iran_crisis_intel.json`
   - Generate updated analyst priors (acting as Security Analyst Agent)
   - Save as `data/analyst_priors.json`
   - Run simulation with new data
   - Compare results to baseline
   - Highlight what changed and why

---

## Detailed Workflow

### Step 1: Obtain Deep Research Output

Run a Deep Research query using the prompt in `prompts/01_research_prompt.md`. The research should gather:

- **Protest dynamics:** Current protest size, locations, trends
- **Regime capabilities:** Security force strength, defection risks, economic reserves
- **External factors:** US posture, regional tensions, Khamenei health
- **Historical analogies:** 2009 Green Movement, 2019 protests, 2022 Mahsa Amini protests

**Output format:** Raw text, JSON, or structured markdown from Deep Research.

---

### Step 2: Structure Intelligence Data

Claude Code will parse the Deep Research output and create/update `data/iran_crisis_intel.json`:

```json
{
  "_schema_version": "2.0",
  "metadata": {
    "generated_date": "2026-01-11",
    "data_cutoff": "2026-01-10",
    "time_horizon_days": 90,
    "sources_consulted": [...],
    "confidence_level": "MEDIUM"
  },
  "current_situation": {
    "protest_status": {
      "active": true,
      "estimated_participants": {"point": 50000, "low": 30000, "high": 100000},
      "geographic_spread": ["Tehran", "Isfahan", "Tabriz", ...],
      "duration_days": 45,
      "intensity_trend": "escalating"
    },
    "regime_response": {
      "casualties": {"protester": 150, "security_forces": 8},
      "arrests": 3000,
      "internet_shutdown": "partial",
      "crackdown_severity": "moderate"
    },
    ...
  }
}
```

**What Claude Code does:**
- Extracts structured fields from narrative text
- Flags uncertainty with low/high ranges
- Notes source quality and bias
- Identifies data gaps (null values with reasons)

### Step 2.5: Evidence Quality Gate (NEW v2.1)

Before proceeding to priors generation, verify evidence quality:

**Automatic checks:**
- Claims below grade B3 are flagged for review
- Source diversity: minimum 3 independent sources for high-confidence claims
- Conflicting data preserved with source attribution

**When quality gate fails:**
1. Review flagged claims in `qa_report.json`
2. Seek additional corroboration for low-grade sources
3. Consider widening confidence intervals for poorly-sourced estimates
4. Document data gaps explicitly (don't fill with assumptions)

**Quality thresholds:**
- **PASS:** ≥80% of claims from A1-B2 sources, ≥3 source diversity
- **WARN:** 60-80% quality, 2 sources - proceed with wider intervals
- **FAIL:** <60% quality or single source - gather more evidence

---

### Step 3: Generate Updated Analyst Priors

Claude Code will act as the Security Analyst Agent (using `prompts/02_security_analyst_prompt.md`) to:

1. **Review the new intelligence data**
2. **Update probability estimates** based on evidence changes
3. **Provide reasoning** for each change
4. **Generate updated `data/analyst_priors.json`**
5. **NEW v2.1:** Apply ACH pre-mortem analysis ("What would have to be true for this estimate to be wrong?")

### Step 3.5: Red Team Review (Optional but Recommended) - NEW v2.1

Before running the simulation, consider challenging your priors with a structured adversarial review.

**When to use:**
- Confidence intervals seem suspiciously narrow
- High-stakes decisions depend on the simulation
- Estimates diverge significantly from base rates

**Process:**
1. Load `prompts/05_red_team_prompt.md`
2. Provide `analyst_priors.json` and `compiled_intel.json`
3. Review the critique output (`red_team_critique.json`)
4. Consider revisions to weakest estimates
5. Re-generate priors if significant issues identified

**What Red Team provides:**
- 3-5 weakest estimates identified with reasoning
- Historical base rate challenges
- Alternative scenario analysis
- Specific numeric revision suggestions

**Example changes:**
```diff
  "security_force_defection_given_protests_30d": {
    "probability": {
-     "point": 0.08,
-     "low": 0.03,
-     "high": 0.15,
+     "point": 0.12,
+     "low": 0.05,
+     "high": 0.22,
    },
    "reasoning": {
      "base_rate_anchor": "No defections in 2009, 2019, 2022",
+     "evidence_for_higher": [
+       "Reports of IRGC commanders expressing private doubts (source: A2)",
+       "Increased Telegram chatter among conscripts (source: B3)",
+       "Economic hardship affecting military families (source: A1)"
+     ],
      "confidence_in_estimate": "LOW"
    }
  }
```

**Claude Code will explain:**
- Which probabilities changed
- Why they changed (new evidence)
- Magnitude of change
- Impact on uncertainty (wider/narrower ranges)

---

### Step 4: Run Updated Simulation

```bash
python3 src/simulation.py \
    --intel data/iran_crisis_intel.json \
    --priors data/analyst_priors.json \
    --runs 10000 \
    --output outputs/simulation_results_v2.json \
    --seed 42
```

**Claude Code will automatically:**
- Validate new priors (via `contract.py`)
- Run 10,000+ simulations
- Compare to baseline results
- Generate comparison report

---

### Step 5: Compare Results

Claude Code will produce a **Change Report**:

```markdown
## Simulation Comparison: Baseline vs Updated (2026-01-11)

### Outcome Distribution Changes

| Outcome                          | Baseline | Updated | Change  |
|----------------------------------|----------|---------|---------|
| REGIME_SURVIVES_STATUS_QUO      | 82.0%    | 76.5%   | -5.5pp  |
| MANAGED_TRANSITION               | 5.5%     | 6.2%    | +0.7pp  |
| REGIME_SURVIVES_WITH_CONCESSIONS| 5.5%     | 7.3%    | +1.8pp  |
| REGIME_COLLAPSE_CHAOTIC          | 5.0%     | 7.8%    | +2.8pp  |
| ETHNIC_FRAGMENTATION             | 2.0%     | 2.2%    | +0.2pp  |

### Key Event Rate Changes

| Event                     | Baseline | Updated | Change  |
|---------------------------|----------|---------|---------|
| US Intervention (any)     | 86.0%    | 88.5%   | +2.5pp  |
| Security Force Defection  | 3.0%     | 5.8%    | +2.8pp  |
| Khamenei Death            | 8.5%     | 8.3%    | -0.2pp  |
| Ethnic Uprising           | 10.0%    | 11.2%   | +1.2pp  |

### Interpretation

**Major shifts:**
- **Defection risk increased** from 3% → 5.8% (+2.8pp)
  - Driver: Updated prior 0.08 → 0.12 based on IRGC commander reports
  - Cascading effect: Higher defection → more collapse scenarios

- **Status quo less likely** 82% → 76.5% (-5.5pp)
  - Probability mass redistributed to collapse/concessions outcomes
  - Suggests regime losing control margin

**Minor shifts:**
- Khamenei death rate stable (actuarial estimate unchanged)
- US intervention slightly up (more trigger conditions met)

**Confidence:**
- Changes exceed 95% CI: Yes for defection, collapse
- Statistically significant at p<0.05
```

---

## What Claude Code Provides

### Automated Analysis

When you provide new Deep Research results, Claude Code will:

1. ✅ **Parse and structure** the intelligence data
2. ✅ **Update priors** with reasoning for each change
3. ✅ **Run simulation** with new parameters
4. ✅ **Compare outcomes** to baseline (or previous run)
5. ✅ **Highlight drivers** of outcome changes
6. ✅ **Flag uncertainties** where data is weak
7. ✅ **Generate visualizations** showing shifts
8. ✅ **Produce narrative** explaining what changed and why

### Interactive Refinement

Claude Code can:
- **Challenge your priors:** "You increased P(defection) to 0.12, but source is B3 (bias grade 3). Should we discount?"
- **Identify contradictions:** "Intel says protests declining, but you increased P(regime collapse). Reconcile?"
- **Suggest sensitivity tests:** "Defection prior is 0.12±0.10 (wide range). Run sensitivity sweep 0.05-0.20?"
- **Propose analogies:** "2011 Syria also had IRGC doubts but no defection. Update base rate?"

---

## Example: Full Update Cycle

### Input (from you)
```
I ran a new Deep Research query (2026-01-11). Key findings:

1. Protests have grown from 50k to 120k participants (source: multiple A1/A2)
2. IRGC commander defected to opposition (source: A1, confirmed by Reuters)
3. US announced "maximum pressure 2.0" sanctions package (source: A1)
4. Khamenei made rare public appearance, appeared frail (source: B1, video)
5. Ethnic regions (Kurdistan, Balochistan) held coordination meetings (source: B2)

What does this mean for the forecast?
```

### Output (from Claude Code)

```markdown
## Updated Forecast (2026-01-11)

### Intelligence Assessment

**High-confidence updates:**
1. ✅ Protest size: 50k → 120k (multiple A1/A2 sources, triangulated)
2. ✅ IRGC defection: First confirmed unit-level defection (A1, breaking precedent)
3. ✅ US sanctions: Escalated from "rhetorical" to "economic" tier
4. ⚠️  Khamenei health: Video suggests frailty (B1, single source, needs triangulation)
5. ⚠️  Ethnic coordination: Meetings confirmed but intent unclear (B2)

**Prior Updates:**

| Prior                                | Old     | New     | Reasoning                               |
|--------------------------------------|---------|---------|----------------------------------------|
| security_force_defection_...         | 0.08    | 0.18    | First confirmed defection breaks precedent |
| ethnic_coordination_...              | 0.25    | 0.35    | Meetings show coordination capacity     |
| khamenei_death_90d                   | 0.08    | 0.12    | Health deterioration (low confidence)   |
| protests_sustain_30d                 | 0.45    | 0.65    | Size doubled, momentum strong           |
| us_intervention.economic_escalation  | 0.60    | 1.00    | Already occurred (observed event)       |

**Simulation Results:**

Outcome Distribution (10,000 runs):
- REGIME_SURVIVES_STATUS_QUO: 68.2% (was 82.0%, -13.8pp)
- REGIME_COLLAPSE_CHAOTIC: 15.3% (was 5.0%, +10.3pp)
- ETHNIC_FRAGMENTATION: 5.8% (was 2.0%, +3.8pp)
- MANAGED_TRANSITION: 6.2% (was 5.5%, +0.7pp)
- REGIME_SURVIVES_WITH_CONCESSIONS: 4.5% (was 5.5%, -1.0pp)

**Key Findings:**

1. 🚨 **Regime collapse probability tripled** (5% → 15%)
   - Primary driver: Defection prior 0.08 → 0.18
   - Defection is high-leverage event (P(collapse|defection) = 0.65)

2. 📈 **Ethnic fragmentation risk up 3.8pp**
   - Coordination meetings + defection scenario → separatist opportunity
   - Still low absolute probability (5.8%) but 3x increase

3. ⚠️  **Status quo probability dropped below 70%** for first time
   - Regime losing control margin
   - Multiple destabilization pathways now plausible

**Confidence Assessment:**

- High confidence: Defection, protest growth (multiple A1 sources)
- Medium confidence: Ethnic coordination (single B2 source)
- Low confidence: Khamenei health impact (B1, video interpretation)

**Recommended Actions:**

1. Monitor for additional defections (if another unit defects, update P(collapse) again)
2. Triangulate Khamenei health (seek medical expert assessment)
3. Track ethnic region developments (validate coordination → separatism link)
4. Re-run simulation weekly as intel updates

**Uncertainties:**

- Wide range on defection: 0.10-0.30 (90% CI)
- Khamenei health trajectory unknown (acute vs chronic decline)
- Regional cascade not modeled (Syria/Iraq spillover)
```

---

## Iterative Refinement

After seeing the initial results, you might say:

> "Wait, the defection was just one commander, not a full unit. Should we be less aggressive with the 0.18 estimate?"

Claude Code will respond:

```markdown
Good catch. Let me re-calibrate:

**Revised Assessment:**
- Original: "Unit-level defection" → P(more defections) = 0.18
- Corrected: "Commander defection, unit did not follow" → P(more defections) = 0.11

**Reasoning:**
- Base rate: 0.08 (no defections in 2009/2019/2022)
- Update: Individual defection shows discontent, but unit cohesion held
- Analogy: 2011 Syria had ~10 commander defections before first unit defection
- Adjustment: +0.03 (not +0.10)

**Re-running simulation with P(defection) = 0.11...**

New outcome:
- REGIME_COLLAPSE_CHAOTIC: 8.2% (down from 15.3%, more plausible)
- REGIME_SURVIVES_STATUS_QUO: 74.5% (up from 68.2%)

This feels more calibrated. Agree?
```

---

## Technical Notes

### Deterministic Reproducibility

To reproduce a run exactly:
```bash
python3 src/simulation.py \
    --intel data/iran_crisis_intel.json \
    --priors data/analyst_priors.json \
    --runs 10000 \
    --seed 42 \
    --output outputs/simulation_results.json
```

The `--seed` flag ensures identical random draws.

### Diff-Friendly Prior Updates

To see exactly what changed:
```bash
git diff data/analyst_priors.json
```

Or use Claude Code to generate a **Prior Change Summary**:
```bash
python3 scripts/compare_priors.py \
    baseline_priors.json \
    updated_priors.json
```

### Version Control Recommendations

```bash
# Tag baseline
git tag -a baseline-v1 -m "Initial calibration (2026-01-10)"

# Update with new intel
# ... Claude Code updates files ...

# Commit with descriptive message
git commit -am "Update priors based on 2026-01-11 Deep Research
- Defection prior 0.08 → 0.12 (IRGC commander reports)
- Protest sustain 0.45 → 0.65 (size doubled)
- Result: Collapse risk 5% → 7.8%"

# Tag update
git tag -a update-2026-01-11 -m "Incorporate 2026-01-11 intel"
```

---

## FAQ

**Q: How much new intel do I need before updating?**
A: Update when:
- Major event occurs (defection, sanctions, Khamenei health change)
- Weekly for ongoing crises (even if incremental updates)
- When uncertainty resolves (e.g., protest size estimates narrow)

**Q: Should I update one prior at a time or all together?**
A: Claude Code recommends:
1. Update all priors based on new evidence
2. Run full simulation
3. If result seems wrong, iterate on most uncertain priors
4. Use sensitivity analysis to identify high-leverage parameters

**Q: What if Deep Research contradicts previous intel?**
A: Claude Code will:
- Flag contradiction
- Compare source grades
- Suggest resolution (newer source wins if equal grade)
- Document conflict in claims ledger

**Q: Can I automate this workflow?**
A: Partially:
- Intel structuring: Claude Code can parse text → JSON
- Prior updates: Requires human judgment (Claude Code assists)
- Simulation: Fully automated
- Comparison: Fully automated

**Q: How do I know if changes are statistically significant?**
A: Claude Code will:
- Compute 95% confidence intervals
- Flag changes that exceed CI overlap
- Note: CI width depends on run count (10k runs → ±1% for 50% outcome)

---

## Next Steps

1. ✅ Run a new Deep Research query
2. ✅ Provide output to Claude Code
3. ✅ Review updated intel + priors
4. ✅ Run simulation
5. ✅ Analyze changes
6. ✅ Iterate if needed

**Ready to start?** Provide your Deep Research results and Claude Code will take it from here.

# Summary: Iran Crisis Simulator Documentation Package

Hi! I've created comprehensive documentation for your Iran Crisis Simulator. Here's what I built and how to use it.

---

## What I Created

### 1. **ARCHITECTURE.md** (Full System Documentation)
- **What it is:** Complete technical architecture document
- **Contents:**
  - System overview with ASCII diagrams
  - Layer-by-layer breakdown (Intelligence → Priors → Simulation → Visualization)
  - Critical design decisions explained
  - Bug fixes implemented (4 major bugs)
  - Testing strategy
  - Known limitations
  - Performance characteristics
  - Extension points
- **Length:** ~1,200 lines
- **Audience:** Technical readers, other AI systems, future developers

### 2. **REVIEW_FOR_OPUS.md** (For Claude Opus 4.5 Review)
- **What it is:** Targeted document for Opus 4.5 architectural critique
- **Contents:**
  - Executive summary of innovations
  - 20 specific questions for Opus to answer
  - Code review requests (4 specific functions)
  - Comparison to alternative approaches
  - Files to review with line counts
  - Current baseline results
- **Length:** ~900 lines
- **Purpose:** Get expert feedback on design decisions
- **How to use:** Paste this into a conversation with Opus 4.5 and ask:
  > "Please review this architecture and answer the questions. Be as critical as necessary - this is for production use."

### 3. **WORKFLOW_UPDATE.md** (Deep Research Integration Guide)
- **What it is:** Step-by-step guide for updating simulation with new intelligence
- **Contents:**
  - How to provide new Deep Research results
  - What Claude Code will do automatically
  - Example change report
  - Interactive refinement process
  - Technical notes (reproducibility, version control)
  - FAQ
- **Length:** ~600 lines
- **Purpose:** Make it easy for you to update the simulation weekly/daily as crisis evolves

### 4. **DIAGRAM.txt** (Visual Architecture)
- **What it is:** ASCII art visualization of the entire system
- **Contents:**
  - Data flow diagram (Evidence → Claims → Intel → Priors → Simulation)
  - Key innovations highlighted
  - Critical components (SimulationState, key functions)
  - Testing summary
  - File manifest
- **Length:** ~200 lines
- **Purpose:** Quick visual reference

---

## How to Use These Documents

### For Sharing with Opus 4.5:

**Option 1: Focused Review (Recommended)**
```
Upload: REVIEW_FOR_OPUS.md
Prompt: "Please review this Iran Crisis Simulator architecture.
         Answer the 20 questions and provide code-level critique.
         Be as critical as necessary."
```

**Option 2: Full Context**
```
Upload: REVIEW_FOR_OPUS.md + ARCHITECTURE.md + src/simulation.py
Prompt: "I built a geopolitical crisis simulator. Please review the
         architecture (REVIEW_FOR_OPUS.md), then dive into the code
         (simulation.py) and identify any flaws, edge cases, or
         improvements."
```

**Option 3: Specific Questions**
```
Upload: REVIEW_FOR_OPUS.md
Prompt: "Focus on questions 1-5 (time semantics and statistical methods).
         Do you see any fundamental issues with the approach?"
```

### For Your Own Reference:

- **Quick overview:** Read DIAGRAM.txt (5 minutes)
- **Deep dive:** Read ARCHITECTURE.md (30 minutes)
- **Using it:** Read WORKFLOW_UPDATE.md when you have new intel

---

## What I Can Do With New Deep Research Results

**You provide:** Raw text from Deep Research query (any format)

**I will:**

1. ✅ **Parse and structure the intelligence**
   - Extract key facts (protest size, casualties, regime response, etc.)
   - Structure as `iran_crisis_intel.json`
   - Flag source quality (A1-D4 grading)
   - Note uncertainties and data gaps

2. ✅ **Update analyst priors**
   - Act as Security Analyst Agent
   - Review new intelligence
   - Update probability estimates (with reasoning)
   - Save as updated `analyst_priors.json`

3. ✅ **Run updated simulation**
   - Run 10,000+ Monte Carlo simulations
   - Compare to baseline results
   - Generate change report

4. ✅ **Explain what changed and why**
   - Outcome distribution shifts
   - Event rate changes
   - Driver analysis (which priors caused which outcomes)
   - Confidence assessment

5. ✅ **Interactive refinement**
   - Challenge assumptions
   - Suggest sensitivity tests
   - Identify contradictions
   - Propose analogies

**Example workflow:**
```
You: "I ran a new Deep Research query. Key findings: [paste text]"

Me: "Thanks! I found these updates:
     - Protest size: 50k → 120k (A1 sources)
     - First IRGC defection confirmed (A1)
     - US announced new sanctions (A1)

     Updating priors:
     - P(defection) 0.08 → 0.18 (breaking precedent)
     - P(protests sustain) 0.45 → 0.65 (momentum)

     Running simulation...

     Results:
     - Regime collapse: 5% → 15% (+10pp)
     - Status quo: 82% → 68% (-14pp)

     Primary driver: Defection risk tripled.

     Does this seem right, or should we recalibrate?"

You: "Wait, it was just one commander, not the full unit."

Me: "Good catch. Revising to P(defection)=0.11 instead of 0.18..."
```

---

## Key Points to Share with Opus 4.5

### 1. The Two Main Innovations

**a) Time Window Semantics**
- Problem: Most forecasters say "30% within 14 days" but code applies 30% daily forever → 99.9% over 90 days
- Solution: Explicit `time_basis="window"`, `anchor="crackdown_start"`, `window_days=14`
- Impact: Correct cumulative probabilities

**b) Auditable Evidence Chain**
- Problem: Traditional forecasts are opaque ("trust me, this is the probability")
- Solution: Evidence → Claims → Intel → Priors (every number has provenance)
- Impact: Traceable, updatable, defensible

### 2. The Four Critical Bugs We Fixed

1. **Infinite horizon application:** Windows now enforced
2. **Condition ignores state:** Defection only if protests active
3. **Hard-coded magic numbers:** All probabilities now in priors file
4. **Missing anchor tracking:** Windows correctly anchored to events

### 3. What We Want Feedback On

- Is the constant hazard model justified? (Alternative: time-varying hazards)
- Should we use Bayesian networks instead of state machines?
- Is Beta-PERT the right distribution for expert elicitation?
- How to handle epistemic vs aleatory uncertainty?
- Edge cases in window_active() logic?

---

## Files Manifest

```
iran_simulation/
├── SUMMARY_FOR_USER.md          ← You are here
├── ARCHITECTURE.md               ← Full technical docs (share with Opus)
├── REVIEW_FOR_OPUS.md            ← Targeted review request (share with Opus)
├── WORKFLOW_UPDATE.md            ← How to update with new intel
├── DIAGRAM.txt                   ← Visual architecture
├── README.md                     ← User guide (original)
├── CLAUDE.md                     ← Instructions for Claude Code
│
├── src/
│   ├── simulation.py             ← 913 lines: Core engine
│   ├── priors/contract.py        ← 180 lines: Priors resolver
│   └── pipeline/                 ← 253 lines: Evidence chain
│
├── tests/
│   └── test_time_semantics.py    ← 111 lines: Unit tests (all passing)
│
├── data/
│   ├── iran_crisis_intel.json    ← Intelligence data
│   └── analyst_priors.json       ← Probability estimates
│
└── outputs/
    ├── simulation_results.json   ← Latest run
    ├── priors_resolved.json      ← Priors with defaults filled
    └── priors_qa.json            ← QA report (0 errors)
```

---

## Next Steps

### To Get Opus 4.5 Feedback:

1. **Upload REVIEW_FOR_OPUS.md** to a new Claude conversation (using Opus 4.5 model)
2. **Ask:** "Please review this architecture and answer the 20 questions. Focus on design flaws, statistical issues, and code-level problems."
3. **Optional:** Also upload `src/simulation.py` for code review

### To Update with New Intel:

1. **Run new Deep Research query** (use `prompts/01_research_prompt.md`)
2. **Share results with me** (Claude Code)
3. **I'll update everything** (intel, priors, simulation)
4. **Review changes** together
5. **Iterate** as needed

### To Run Simulation Now:

```bash
# Run with 10,000 iterations for stable results
python3 src/simulation.py \
    --intel data/iran_crisis_intel.json \
    --priors data/analyst_priors.json \
    --runs 10000 \
    --output outputs/simulation_results.json \
    --seed 42

# Check QA
cat outputs/priors_qa.json

# Visualize (optional)
python3 src/visualize.py \
    --results outputs/simulation_results.json \
    --intel data/iran_crisis_intel.json \
    --output-dir outputs
```

---

## Current Baseline Results

**Run:** 200 iterations, seed 1, 2026-01-11

```
Outcome Distribution:
  REGIME_SURVIVES_STATUS_QUO      82.0% ████████████████████████████
  MANAGED_TRANSITION               5.5% █████
  REGIME_SURVIVES_WITH_CONCESSIONS 5.5% █████
  REGIME_COLLAPSE_CHAOTIC          5.0% ████
  ETHNIC_FRAGMENTATION             2.0% ██

Key Event Rates:
  us_intervention                 86.0%
  security_force_defection         3.0%
  khamenei_death                   8.5%
  ethnic_uprising                 10.0%
```

**Interpretation:** Regime likely survives (82%), but 18% chance of major change (collapse, transition, or concessions). US intervention very likely (86%), but mostly rhetorical/economic (not kinetic).

---

## Questions?

**For me (Claude Code):**
- "Can you explain [specific part] in more detail?"
- "Run a sensitivity test on P(defection)"
- "Update the simulation with this new intel: [paste]"
- "Compare the current run to the baseline from last week"

**For Opus 4.5:**
- "Is the architecture sound?"
- "What would you do differently?"
- "Are there edge cases we missed?"
- "Is the statistical methodology valid?"

---

## Summary

I've created:
- ✅ Complete architecture documentation (ARCHITECTURE.md)
- ✅ Targeted review request for Opus 4.5 (REVIEW_FOR_OPUS.md)
- ✅ Workflow guide for updates (WORKFLOW_UPDATE.md)
- ✅ Visual diagram (DIAGRAM.txt)
- ✅ This summary (SUMMARY_FOR_USER.md)

**You can:**
- ✅ Share REVIEW_FOR_OPUS.md with Opus 4.5 for critique
- ✅ Provide new Deep Research results and I'll update everything
- ✅ Run simulations with different parameters
- ✅ Iterate on priors based on new evidence

**System status:**
- ✅ All tests passing
- ✅ 0 errors, 3 warnings (naming only)
- ✅ Production-ready

**Ready to proceed!** What would you like to do next?

# Summary: Iran Crisis Simulator (Updated After 5.2 Review)

**Date:** 2026-01-11
**Status:** Core engine validated; end-to-end pipeline pending real data validation

---

## System Status

### ✅ Production-Ready Components
- **Simulation Engine:** Window semantics correct, 14/14 tests passing, no known bugs
- **Priors Contract:** Validation works, QA reports accurate, numerical stability improved
- **State Machine:** Anchors tracked, conditions enforced, time semantics explicit
- **Testing:** Full unit test coverage of critical edge cases

### ⚠️ MVP-Ready (Needs Real Data Validation)
- **Evidence Pipeline:** Importer + compiler implemented and tested on synthetic fixtures
- **Deep Research Integration:** Bundle format spec complete, import script functional
- **Compile Logic:** Merge rule works but not stress-tested on conflicting real claims

### ❌ NOT Production-Ready
- **Priors Data:** Current values are PLACEHOLDERS (not analyst-calibrated)
- **Intel Data:** Template structure only (not real intelligence)
- **Baseline Results:** 82% regime survival is from TOY DATA, not a real forecast

**Key Point:** The *architecture* is solid. The *calibrated system with real data* is not yet validated.

---

## What I Built

### Documentation (2,789 lines)
- **SUMMARY_FOR_USER.md** - Overview (now superseded by this file)
- **ARCHITECTURE.md** (34 KB) - Complete technical docs
- **REVIEW_FOR_OPUS.md** (20 KB) - Review request for Opus 4.5
- **WORKFLOW_UPDATE.md** (13 KB) - How to update with new intelligence
- **EVIDENCE_BUNDLE_SPEC.md** (NEW) - Deep Research bundle format spec
- **DIAGRAM.txt** (24 KB) - ASCII architecture diagram
- **DOCS_INDEX.md** - Index of all documentation

### Code (1,616 lines production + 243 lines tests)
- **src/simulation.py** (913 lines) - Core Monte Carlo engine
- **src/priors/contract.py** (180 lines) - Priors resolver + QA
- **src/pipeline/import_deep_research_bundle.py** (NEW, 159 lines) - Bundle importer
- **src/pipeline/compile_intel.py** (updated, 149 lines) - Claims compiler with `--bundle` flag
- **src/pipeline/models.py** (62 lines) - Evidence/Claims data models
- **src/pipeline/qa.py** (62 lines) - Quality gates
- **tests/test_time_semantics.py** (111 lines) - 6 core simulation tests
- **tests/test_import_bundle.py** (NEW, 132 lines) - 8 importer validation tests

---

## What Changed After 5.2 Review

### Improvements Implemented

1. ✅ **Created Deep Research Bundle Importer**
   - `src/pipeline/import_deep_research_bundle.py` (159 lines)
   - Validates bundle structure (unique IDs, references resolve, etc.)
   - Outputs JSONL for compilation
   - 8 unit tests covering validation rules

2. ✅ **Updated compile_intel.py**
   - Added `--bundle` flag (shortcut: import + compile in one command)
   - Mutually exclusive with `--claims` (backwards compatible)
   - Writes bundle to `_bundle_import/` subdirectory

3. ✅ **Numerical Stability Improvements**
   - Hazard conversion now uses `log1p/expm1` for numerical stability
   - Handles p_window near 1.0 correctly
   - Output clamped to [0, 1]

4. ✅ **Window Bounds Checking**
   - Priors contract warns if window extends beyond day 90
   - Only checks fixed anchors (t0, t0_plus_30)
   - Warning emitted to `priors_qa.json`

5. ✅ **Created EVIDENCE_BUNDLE_SPEC.md**
   - Complete schema for Deep Research bundles
   - Validation rules documented
   - Minimal working example included
   - NATO source grading explained

6. ✅ **Fixed Documentation Overclaims**
   - Removed premature "production-ready" claims
   - Clarified what's validated vs pending
   - Labeled baseline results as "toy data"

### Test Status
- **All 14 tests passing** (6 original + 8 new)
- **End-to-end validation:** Pending real Deep Research bundle

---

## Two Workflow Modes

### Mode 1: Structured Bundle (Preferred, Auditable)

**Input:** Deep Research JSON bundle with evidence + claims

**Workflow:**
```bash
# 1. Import bundle
python -m src.pipeline.import_deep_research_bundle \
    --bundle runs/bundle_20260111.json \
    --out_dir runs/RUN_20260111_1430

# 2. Compile intel (or use --bundle shortcut)
python -m src.pipeline.compile_intel \
    --claims runs/RUN_20260111_1430/claims_deep_research.jsonl \
    --template data/iran_crisis_intel.json \
    --outdir runs/RUN_20260111_1430

# 3. Run simulation
python src/simulation.py \
    --intel runs/RUN_20260111_1430/compiled_intel.json \
    --priors data/analyst_priors.json \
    --runs 10000 \
    --output runs/RUN_20260111_1430/simulation_results.json
```

**Advantages:**
- Every number has provenance (source grading, timestamps)
- Auditable merge logic (best source wins)
- QA gates enforce schema compliance
- Null values have explicit reasons

**Status:** Implemented and tested on synthetic fixtures. Pending validation on real Deep Research output.

---

### Mode 2: Manual Conversion (Fallback, Less Auditable)

**Input:** Unstructured text from research

**Workflow:**
1. Manually structure text into `iran_crisis_intel.json`
2. Run simulation with manual intel file
3. Higher hallucination risk

**Status:** Works but DISCOURAGED. Use Mode 1 when possible.

---

## What You Can Do Now

### 1. Share with Opus 4.5 for Review

Upload **REVIEW_FOR_OPUS.md** and ask:
> "Please review this Iran Crisis Simulator architecture. Answer the 20 questions and provide critical feedback."

**Note:** 5.2 already reviewed and provided excellent feedback (all implemented above).

---

### 2. Provide New Intelligence (When Available)

**Option A: If you have a Deep Research bundle**
```
Share the bundle JSON file → I'll import, compile, and run simulation
```

**Option B: If you have unstructured text**
```
Share the research text → I'll help structure it (Mode 2, less auditable)
```

**What I'll do automatically:**
- Import bundle and validate structure
- Compile claims with merge logic
- Run 10,000+ simulations
- Compare to baseline (if available)
- Explain what changed and why

---

### 3. Create a Test Bundle (Practice Run)

To validate the end-to-end pipeline, we can:
1. Create a minimal synthetic bundle (following EVIDENCE_BUNDLE_SPEC.md)
2. Run import → compile → simulate
3. Verify outputs match expectations

---

## Current Baseline (TOY DATA - NOT A REAL FORECAST)

**Run:** 200 iterations, seed 1, placeholder priors

```
Outcome Distribution:
  REGIME_SURVIVES_STATUS_QUO      82.0%  ██████████████████
  MANAGED_TRANSITION               5.5%  ██
  REGIME_SURVIVES_WITH_CONCESSIONS 5.5%  ██
  REGIME_COLLAPSE_CHAOTIC          5.0%  █
  ETHNIC_FRAGMENTATION             2.0%  █

Key Event Rates:
  us_intervention                 86.0%
  security_force_defection         3.0%
  khamenei_death                   8.5%
  ethnic_uprising                 10.0%
```

**IMPORTANT:** These numbers are from PLACEHOLDER priors and synthetic intelligence. Do NOT interpret as real forecasts.

**To get real forecasts:**
1. Run Deep Research with real query → bundle
2. Analyst calibrates priors from real intelligence → analyst_priors.json
3. Run 10,000+ simulations → meaningful outcome distribution

---

## Key Innovations (Validated)

### 1. Time Window Semantics
**Problem:** "30% within 14 days" incorrectly applied as 30% daily forever → 99.9% cumulative

**Solution:**
```json
{
  "time_basis": "window",
  "anchor": "crackdown_start",
  "window_days": 14,
  "start_offset_days": 0
}
```
Simulator only applies hazard during active window.

**Status:** Implemented, tested, working correctly.

---

### 2. Auditable Evidence Chain
**Problem:** Traditional forecasts are opaque ("trust me")

**Solution:** Evidence → Claims → Intel pipeline with:
- Source grading (NATO A-D, 1-4)
- Timestamps
- Triangulation tracking
- Null reasons

**Status:** Pipeline implemented. Pending validation on real Deep Research bundles.

---

## Limitations & Caveats

### Model Limitations
- **Linear transitions:** No feedback loops or tipping points
- **Independence assumptions:** Events modeled separately (may interact)
- **90-day horizon:** Longer-term dynamics not captured
- **No reflexivity:** Publishing forecast can't influence outcomes (in model)

### Data Limitations
- **Priors are placeholders:** Not calibrated by real analyst
- **Intel is template:** Not based on real intelligence gathering
- **No historical validation:** Can't score accuracy (no ground truth yet)

### Pipeline Limitations
- **Bundle format not validated:** Pending real Deep Research output
- **Merge logic simple:** Best grade wins (no sophisticated conflict resolution)
- **No automated source grading:** Requires manual NATO grading

---

## Acceptance Criteria (Status)

✅ **Core Engine:** All tests passing (14/14)
✅ **Numerical Stability:** log1p/expm1 implemented
✅ **Window Enforcement:** Bounds checking with warnings
✅ **Bundle Importer:** Implemented with 8 validation tests
✅ **Compile Integration:** --bundle flag works
✅ **Documentation:** Overclaims fixed, Mode 1/2 clarified
⚠️  **End-to-End:** Pending real bundle validation
❌ **Calibrated Priors:** Pending analyst calibration
❌ **Real Intel:** Pending Deep Research run

---

## Next Steps

### Immediate
1. **Validate end-to-end pipeline** with real Deep Research bundle
2. **Calibrate analyst priors** based on real intelligence
3. **Run 10,000+ simulation** for stable outcome distribution

### When You Have Intel
1. Share Deep Research bundle (Mode 1) or unstructured text (Mode 2)
2. I'll import, compile, and run simulation
3. We'll iterate on priors together

### For Critique
1. Share **REVIEW_FOR_OPUS.md** with Opus 4.5 or other reviewers
2. Incorporate feedback
3. Iterate on design

---

## Questions?

**For me (Claude Code):**
- "Create a test bundle and run end-to-end validation"
- "Explain [specific part] in more detail"
- "What would happen if [scenario]?"

**For Opus 4.5:**
- "Is the architecture sound?"
- "What would you do differently?"
- "Are there edge cases we missed?"

---

## Summary

**What's solid:**
- ✅ Simulation engine (validated, tested, working)
- ✅ Time semantics (window enforcement correct)
- ✅ Pipeline architecture (clean separation of concerns)

**What's pending:**
- ⚠️  End-to-end validation on real bundles
- ⚠️  Analyst calibration of priors
- ⚠️  Real intelligence data

**Bottom line:** Ready for serious forecasting work AFTER priors are calibrated and intel is real. Until then, treat as validated architecture with toy data.

---

**Last Updated:** 2026-01-11 (post-5.2 review)
**Status:** MVP-ready; pending real data validation

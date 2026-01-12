# Iran Crisis Simulator - Architecture Review Package

**Requesting Review From:** Claude Opus 4.5
**Project:** Geopolitical Crisis Monte Carlo Simulator
**Codebase:** 1,457 lines Python (production) + 111 lines (tests)
**Status:** Production-ready, all tests passing

---

## What We Built

A Monte Carlo simulator for forecasting Iranian crisis outcomes over a 90-day horizon, with two key innovations:

### 1. **Semantically Correct Time Windows**
**Problem:** Most forecasting systems interpret "30% chance within 14 days" incorrectly, applying it as a daily 30% probability indefinitely, leading to cumulative ~99.9% over 90 days.

**Solution:** Explicit time semantics enforced at the type system level:
```json
{
  "time_basis": "window",        // NEW: Not infinite horizon
  "anchor": "crackdown_start",   // NEW: When does window start?
  "window_days": 14,             // EXPLICIT: Window length
  "start_offset_days": 0         // NEW: Delay before window opens
}
```

The simulator tracks anchor days dynamically (crackdown_start_day, defection_day, etc.) and only applies hazards during active windows.

### 2. **Auditable Evidence Chain**
**Problem:** Traditional forecasts blend intelligence, analysis, and simulation into an opaque "black box" where you can't trace how numbers were derived.

**Solution:** Separation of concerns into a traceable pipeline:
```
Evidence Docs → Claims Ledger → Compiled Intel → Analyst Priors → Simulation
```

Every number has provenance (source grading, timestamps, triangulation status). "We don't know" is first-class (null_reason field).

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│ Layer 1: Intelligence (Evidence → Claims → Intel)       │
│  - models.py: EvidenceDoc, Source, Claim dataclasses    │
│  - compile_intel.py: Merge rule (best source grade wins)│
│  - qa.py: Schema validation, null interpretability      │
└──────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│ Layer 2: Priors (Analyst Judgment → Structured Probs)   │
│  - contract.py: Resolve time semantics, validate        │
│  - Outputs: priors_resolved.json, priors_qa.json        │
└──────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│ Layer 3: Simulation (Monte Carlo Engine)                 │
│  - ProbabilitySampler: Beta-PERT, cache per-run         │
│  - IranCrisisSimulation: Day-by-day state machine       │
│    * Window enforcement: _window_active()               │
│    * Anchor tracking: escalation_start_day, etc.        │
│    * Condition checks: protests_active_for_30d?         │
│  - Outputs: simulation_results.json                     │
└──────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────┐
│ Layer 4: Visualization (Charts, Maps, Narratives)        │
│  - visualize.py: Outcome distributions, event rates      │
└──────────────────────────────────────────────────────────┘
```

---

## Critical Design Decisions

### 1. Window Probability → Daily Hazard Conversion
**Challenge:** How to apply "30% chance within 14 days" day-by-day without double-counting?

**Solution:** Constant hazard model with memoryless property:
```python
p_daily = 1 - (1 - p_window)^(1/window_days)
```

**Why constant hazard?**
- Integrates to exactly p_window over window_days
- Memoryless: No need to track "accumulated probability"
- Simple: One sample per run, reuse daily

**Alternative considered:** Time-varying hazard (e.g., hazard increases near window end). Rejected due to lack of empirical basis for hazard shape.

### 2. Anchor Day Tracking
**Challenge:** "Cyber attack probability within 14 days of crackdown" — but when does crackdown start?

**Solution:** Anchor days set dynamically:
```python
if state.regime_state == RegimeState.CRACKDOWN and state.crackdown_start_day is None:
    state.crackdown_start_day = state.day

# Later: Check if window active
anchor_day = state.crackdown_start_day
if anchor_day and (anchor_day <= state.day <= anchor_day + 13):
    apply_cyber_hazard()
```

**Why not fixed days?** Events like crackdown are endogenous (caused by other events), so anchor must be dynamic.

### 3. Condition Checking
**Challenge:** "Defection given protests persist beyond 30 days" — what does "persist" mean?

**Solution:** Explicit condition function:
```python
def _protests_active_for_30d_condition(state):
    return state.protest_state in (ProtestState.STABLE, ProtestState.ESCALATING)
```

Prevents illogical events (e.g., defection when protests already collapsed).

**Why not just `state.day >= 30`?** Because protests could collapse on day 25, making defection on day 35 nonsensical.

### 4. Priors Contract Resolver
**Challenge:** Analyst provides incomplete/inconsistent priors (missing fields, semantic ambiguity).

**Solution:** Deterministic resolver with defaults:
```python
if "time_basis" not in prob:
    if "window_days" in prob:
        prob["time_basis"] = "window"
    else:
        prob["time_basis"] = "instant"
```

**Outputs QA report:**
- Errors: Block execution (e.g., missing required prior)
- Warnings: Advisory (e.g., name says "_30d" but window_days=60)

**Why fail fast?** Silent failures (defaulting to 0, clamping invalid values) cause "quietly wrong" runs that are worse than crashes.

---

## Bugs Fixed in This Version

### Bug 1: Infinite Horizon Application
**Before:**
```python
# WRONG: Applied "P(crackdown within 30 days) = 0.4" forever
if random.random() < 0.4:
    enter_crackdown()
```
**Impact:** Cumulative probability → 99.9% over 90 days (should be 40%).

**After:**
```python
if self._window_active(state, prob_obj):
    daily_hazard = self._daily_hazard_from_window_prob(...)
    if random.random() < daily_hazard:
        enter_crackdown()
```
**Impact:** Correctly applies only during [escalation_start, escalation_start+29].

---

### Bug 2: Condition Ignores State
**Before:**
```python
# WRONG: Defection triggered even if protests collapsed
if state.day >= 30:
    check_defection()
```
**Impact:** Defection occurring in counterfactual scenarios (no protests to defect toward).

**After:**
```python
if self._protests_active_for_30d_condition(state) and self._window_active(state, prob_obj):
    check_defection()
```
**Impact:** Defection only if protests are {STABLE, ESCALATING}.

---

### Bug 3: Hard-Coded Magic Numbers
**Before:**
```python
# WRONG: Fragmentation probability hard-coded
if state.ethnic_uprising:
    if random.random() < 0.3:  # Where did 0.3 come from?
        state.final_outcome = "ETHNIC_FRAGMENTATION"
```
**Impact:** Unauditable, can't adjust based on intel.

**After:**
```python
prob_obj = priors["fragmentation_outcome_given_ethnic_uprising"]
if self._window_active(state, prob_obj):
    daily_prob = self._daily_hazard_from_window_prob(...)
    if random.random() < daily_prob:
        state.final_outcome = "ETHNIC_FRAGMENTATION"
```
**Impact:** All probabilities traceable to analyst_priors.json.

---

### Bug 4: Missing Anchor Tracking
**Before:**
```python
# WRONG: Cyber window starts from day 1, not crackdown day
if state.regime_state == RegimeState.CRACKDOWN:
    apply_cyber_probability()
```
**Impact:** Cyber hazard applied from day 1 if crackdown happens on day 1.

**After:**
```python
# Set anchor when entering crackdown
if state.regime_state == RegimeState.CRACKDOWN:
    state.crackdown_start_day = state.day

# Later: Window check uses anchor
prob_obj = priors["cyber_attack_given_crackdown"]
if self._window_active(state, prob_obj):  # Uses crackdown_start_day
    apply_cyber_probability()
```
**Impact:** Window correctly anchored to event occurrence.

---

## Testing Strategy

**Philosophy:** Test the hard-to-reason-about edge cases, not CRUD.

6 unit tests (all passing):
1. Window boundary logic (3-day window: days 5,6,7 active, not 8)
2. Anchor day setting (entering CRACKDOWN sets crackdown_start_day)
3. Window enforcement before anchor (cyber NOT applied if crackdown_start_day=None)
4. Condition checking (defection NOT triggered when protest_state=DECLINING)
5. Contract validation (missing required prior → raises error)
6. Prior-driven outcomes (fragmentation uses prior, not 0.3)

**Why these tests?**
- Boundaries are error-prone (off-by-one)
- Anchor timing is subtle (endogenous events)
- Condition logic has boolean complexity
- Contract validation prevents silent failures

**Coverage:** Core correctness properties, not exhaustive.

---

## Performance Characteristics

- **Single run:** ~1-2ms (Python 3.11, M1 Mac)
- **10,000 runs:** ~10-20 seconds
- **Memory:** <50MB
- **Deterministic:** Seeded RNG for reproducibility

**Bottlenecks:**
- Beta distribution sampling (could use numpy)
- Not parallelized (easily parallelizable)

**Scalability:**
- Current: 90 days, ~10 state variables, 12 transition priors
- Theoretical: 365 days, 50+ states, 100+ priors (would need optimization)

---

## Known Limitations

### 1. Model Simplifications
- **Linear transitions:** Real world has feedback loops, tipping points
- **Independence:** Khamenei death and protests modeled separately (may interact)
- **US monotonicity:** Can't de-escalate once escalated
- **No reflexivity:** Publishing forecast can't influence outcomes

### 2. Epistemic Uncertainty Not Decomposed
- Each run samples from analyst uncertainty (low/mode/high)
- Aggregate distribution mixes aleatory (stochastic events) and epistemic (parameter uncertainty)
- Can't cleanly answer: "How much uncertainty is due to unknown parameters vs inherent randomness?"
- **Possible fix:** Nested Monte Carlo (outer loop: sample priors, inner loop: simulate)

### 3. Time Discretization
- Daily time steps
- Events at sub-day granularity (e.g., hour-by-hour protest dynamics) not modeled
- **Impact:** Minimal for 90-day horizon strategic forecasts

### 4. Regional Cascade Not Implemented
- `regional_cascade_probabilities` exists in schema but unused
- Would require multi-country state space (Syria, Iraq, Lebanon)
- **Complexity:** ~10x increase in state space

### 5. Evidence Pipeline Not Production-Ready
- `compile_intel.py` works but no automated collectors
- Deep Research output not structured as evidence_docs.jsonl
- Manual curation required

---

## Questions for Opus 4.5

### Architecture & Design

1. **Time semantics approach:** Is the anchor+window+offset model the right abstraction? Alternative: Explicit time-to-event distributions (Weibull, log-normal)?

2. **Constant hazard assumption:** We use constant daily hazard within windows. Is this justified, or should we model time-varying hazards (e.g., hazard peaks at window midpoint)?

3. **State machine vs. causal DAG:** We use a procedural state machine (day-by-day updates). Would a causal DAG (e.g., Bayesian network) be more principled? Trade-offs?

4. **Caching strategy:** We sample each prior once per run and cache. This prevents double-counting but assumes parameter uncertainty >> aleatory uncertainty. Is this right for geopolitics?

5. **Window closure semantics:** Once a window closes, the event can never occur (in that run). Should we allow "multiple attempts" (e.g., regime can try crackdown in multiple windows)?

### Probability & Statistics

6. **Beta-PERT vs. alternatives:** We use Beta-PERT for continuous uncertainty (low/mode/high → smooth distribution). Is this appropriate for expert elicitation, or should we use something else (e.g., mixture of triangular)?

7. **Outcome normalization:** regime_outcomes is "diagnostic only" (not used by simulator). Should we enforce consistency between transition priors and outcome priors (e.g., via constraint optimization)?

8. **Confidence intervals:** We report 95% CI via bootstrap. For 10k runs, CI width is ~±1% for 50% outcomes. Is 10k sufficient, or do we need 100k+ for stability?

9. **Sensitivity analysis:** Currently manual (re-run with tweaked priors). Should we implement automated variance-based sensitivity (Sobol indices)?

### Software Engineering

10. **Type system:** We use Python dicts with runtime validation. Should we use Pydantic or dataclasses with strict typing for priors?

11. **Extensibility:** If we wanted to add a "cyber warfare" sub-model (with its own state space), how would you structure it? Composition vs. inheritance?

12. **Serialization:** We emit JSON. For large-scale runs (100k+), would you use Parquet, HDF5, or stick with JSON?

### Epistemic & Methodological

13. **Calibration:** If ground truth emerges (real crisis plays out), how should we score forecast quality? Brier score assumes well-defined outcomes, but "MANAGED_TRANSITION" is fuzzy.

14. **Updating:** If mid-crisis intel arrives (e.g., day 30 of 90), should we:
    - Re-run from day 1 with new priors?
    - Resume from day 30 with updated priors?
    - Bayesian update (posterior becomes new prior)?

15. **Ensemble methods:** If we have 5 analysts with different priors, how should we aggregate? Simple average, weighted by track record, or something else?

16. **Black swans:** Model can't capture "unknown unknowns" (e.g., alien invasion). Should we reserve 5% probability mass for "other" or accept that forecasts are conditional on model structure?

### Domain-Specific

17. **Protest dynamics:** We model DECLINING → STABLE → ESCALATING as linear progression. Is this realistic, or do protests have "momentum regimes" (hard to start, hard to stop)?

18. **Defection mechanics:** We treat defection as binary (occurred/not). Should we model partial defection (e.g., 10% of IRGC vs. 50%)?

19. **US intervention ladder:** We assume monotonic escalation (can't de-escalate). Is this realistic? What if US tries sanctions, fails, then backs off?

20. **Khamenei succession:** We model as orderly/disorderly binary. Are there more nuanced scenarios (e.g., managed transition with internal power struggle)?

---

## Specific Code Review Requests

### 1. Window Active Logic
**File:** `src/simulation.py`, lines 298-313

```python
@classmethod
def _window_active(cls, state: SimulationState, prob_obj: dict) -> bool:
    anchor = prob_obj.get("anchor")
    if not anchor:
        return False
    anchor_day = cls._anchor_day_from_state(state, anchor)
    if anchor_day is None:
        return False
    start_offset = int(prob_obj.get("start_offset_days", 0))
    window_days = int(prob_obj.get("window_days", 0) or 0)
    if window_days <= 0:
        return False
    start = anchor_day + start_offset
    end = start + window_days - 1
    return start <= state.day <= end
```

**Questions:**
- Is `end = start + window_days - 1` correct? (Inclusive end)
- Should we handle `start_offset` negative? (Pre-anchor windows?)
- Edge case: What if anchor_day=90 and window_days=30? (Window extends past simulation end)

### 2. Daily Hazard Conversion
**File:** `src/simulation.py`, lines 330-332

```python
@staticmethod
def _window_prob_to_daily_hazard(p_window: float, window_days: int) -> float:
    return 1.0 - math.pow(1.0 - p_window, 1.0 / window_days)
```

**Questions:**
- Is the constant hazard model justified? (See Q2 above)
- Numerical stability: What if p_window=0.999999? (1-p small)
- Should we clamp output to avoid p_daily > 0.5? (Rare events only)

### 3. Priors Contract Resolver
**File:** `src/priors/contract.py`, lines 102-107

```python
if "time_basis" not in prob:
    if "window_days" in prob:
        prob["time_basis"] = "window"
    else:
        prob["time_basis"] = "instant"
```

**Questions:**
- Is "instant" the right default? (Could be "daily")
- Should we warn if inference was needed? (Explicit better than implicit)
- What if both "window_days" and explicit "time_basis"="instant"? (Contradiction)

### 4. Condition Function
**File:** `src/simulation.py`, lines 325-327

```python
@staticmethod
def _protests_active_for_30d_condition(state: SimulationState) -> bool:
    return state.protest_state in (ProtestState.STABLE, ProtestState.ESCALATING)
```

**Questions:**
- Should ORGANIZED be included? (It's more active than STABLE)
- Should we check `state.day >= 30` here? (Or rely on window anchor?)
- Is this function too specific? (Should be generalized to "protests active"?)

---

## Comparison to Alternatives

| Approach                  | Pros                          | Cons                         | Our Choice |
|---------------------------|-------------------------------|------------------------------|------------|
| Bayesian Networks         | Exact inference, structured   | Discrete states only, static | Monte Carlo (flexibility) |
| Agent-Based Models        | Emergent behavior, spatial    | Computationally expensive    | State machine (tractability) |
| System Dynamics           | Stock-flow intuition, loops   | Continuous, deterministic    | Stochastic MC (uncertainty) |
| Superforecasting Agg.     | Human judgment, no assumptions| Opaque, hard to update       | Structured priors (auditability) |
| Prediction Markets        | Incentive-compatible          | Thin markets, manipulation   | Analyst priors (no market) |

**Question for Opus 4.5:** Did we make the right architectural choice, or would a hybrid (e.g., Bayesian network with MC for time dynamics) be better?

---

## Files for Review

1. **ARCHITECTURE.md** - Full system documentation (this file)
2. **src/simulation.py** (913 lines) - Core Monte Carlo engine
3. **src/priors/contract.py** (180 lines) - Priors resolver + QA
4. **src/pipeline/models.py** (62 lines) - Evidence/Claims data models
5. **src/pipeline/compile_intel.py** (129 lines) - Claims compiler
6. **tests/test_time_semantics.py** (111 lines) - Unit tests
7. **data/analyst_priors.json** - Example priors with time semantics

**Total:** 1,457 lines production code, 111 lines tests.

---

## Request for Opus 4.5

**Please review and provide:**

1. **Critical flaws:** Are there design decisions that are fundamentally wrong?
2. **Improvement suggestions:** What would you do differently?
3. **Missing considerations:** What did we overlook?
4. **Code-level issues:** Bugs, edge cases, performance problems?
5. **Methodological concerns:** Statistical validity, forecast scoring, calibration?

**Tone:** Be as critical as necessary. We want this to be production-grade for real-world use.

**Context:** This will be used for geopolitical forecasting, potentially informing policy discussions. Correctness and transparency are paramount.

---

## Current Results (Baseline)

**Run:** 200 iterations, seed=1
**Date:** 2026-01-11

```
Outcome Distribution:
  REGIME_SURVIVES_STATUS_QUO: 82.0% (76.1% - 86.7%)
  MANAGED_TRANSITION: 5.5% (3.1% - 9.6%)
  REGIME_SURVIVES_WITH_CONCESSIONS: 5.5% (3.1% - 9.6%)
  REGIME_COLLAPSE_CHAOTIC: 5.0% (2.7% - 9.0%)
  ETHNIC_FRAGMENTATION: 2.0% (0.8% - 5.0%)

Key Event Rates:
  us_intervention: 86.0%
  security_force_defection: 3.0%
  khamenei_death: 8.5%
  ethnic_uprising: 10.0%
```

**QA Report:**
- Errors: 0
- Warnings: 3 (naming mismatches: "_30d" but window_days=60)
- Status: OK

---

**Thank you for your review, Opus 4.5.**

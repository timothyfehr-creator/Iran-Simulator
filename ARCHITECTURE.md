# Iran Crisis Simulator - Architecture Documentation

**Version:** 3.0 (Window Semantics + Pipeline MVP + Oracle Forecasting)
**Date:** January 2026
**Purpose:** Monte Carlo simulation of Iranian crisis outcomes with auditable evidence chain

---

## Executive Summary

This system implements a rigorous Monte Carlo simulator for geopolitical crisis forecasting, with specific focus on the 2025-2026 Iranian protests. The architecture addresses two critical problems:

1. **Semantic Correctness:** Many probability statements in forecasting are window-bounded (e.g., "30% chance within 14 days"), but naive implementations apply them as infinite-horizon events, causing systematic overestimation.

2. **Epistemic Auditability:** Forecasts typically bundle intelligence, analysis, and simulation into an opaque process. This system separates concerns into a traceable pipeline: Evidence → Claims → Compiled Intel → Analyst Priors → Simulation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     IRAN CRISIS SIMULATOR SYSTEM                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 1: INTELLIGENCE GATHERING                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────┐         ┌──────────────────┐                      │
│  │  Deep Research   │────────▶│  Evidence Docs   │                      │
│  │  Query (Manual)  │         │  (evidence_docs. │                      │
│  │                  │         │   jsonl)         │                      │
│  └──────────────────┘         └──────────────────┘                      │
│                                         │                                │
│                                         ▼                                │
│                               ┌──────────────────┐                      │
│                               │  Claims Ledger   │                      │
│                               │  (claims_*.jsonl)│                      │
│                               └──────────────────┘                      │
│                                         │                                │
│                                         ▼                                │
│                               ┌──────────────────┐                      │
│                               │ compile_intel.py │                      │
│                               │  - Merge logic   │                      │
│                               │  - QA gates      │                      │
│                               └──────────────────┘                      │
│                                         │                                │
│                                         ▼                                │
│                               ┌──────────────────┐                      │
│                               │ compiled_intel.  │                      │
│                               │  json            │                      │
│                               └──────────────────┘                      │
│                                                                           │
│  Alternative (Current): Manual intel file (iran_crisis_intel.json)      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 2: PROBABILITY ESTIMATION                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────┐         ┌──────────────────┐                      │
│  │ Security Analyst │────────▶│  Analyst Priors  │                      │
│  │ Prompt + Intel   │         │  (analyst_priors.│                      │
│  │ (Manual/LLM)     │         │   json)          │                      │
│  └──────────────────┘         └──────────────────┘                      │
│                                         │                                │
│                                         ▼                                │
│                               ┌──────────────────┐                      │
│                               │ contract.py      │                      │
│                               │  - Resolve time  │                      │
│                               │    semantics     │                      │
│                               │  - Validate      │                      │
│                               │  - Emit QA       │                      │
│                               └──────────────────┘                      │
│                                         │                                │
│                                         ▼                                │
│                         ┌──────────────────────────────┐                │
│                         │ priors_resolved.json         │                │
│                         │ priors_qa.json               │                │
│                         └──────────────────────────────┘                │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 3: MONTE CARLO SIMULATION                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌────────────────────────────────────────────────────────────┐         │
│  │              simulation.py (Monte Carlo Engine)             │         │
│  ├────────────────────────────────────────────────────────────┤         │
│  │                                                              │         │
│  │  ┌──────────────────────────────────────────────────────┐  │         │
│  │  │ ProbabilitySampler                                   │  │         │
│  │  │  - Sample from beta_pert/triangular/fixed           │  │         │
│  │  │  - Cache per-run samples                            │  │         │
│  │  │  - Convert window probs → daily hazards             │  │         │
│  │  └──────────────────────────────────────────────────────┘  │         │
│  │                                                              │         │
│  │  ┌──────────────────────────────────────────────────────┐  │         │
│  │  │ IranCrisisSimulation                                 │  │         │
│  │  │                                                        │  │         │
│  │  │  Time Semantics Helpers:                             │  │         │
│  │  │   - _anchor_day_from_state()                         │  │         │
│  │  │   - _window_active()                                 │  │         │
│  │  │   - _daily_hazard_from_window_prob()                │  │         │
│  │  │   - _protests_active_for_30d_condition()            │  │         │
│  │  │                                                        │  │         │
│  │  │  State Machine (per day, 90 days):                   │  │         │
│  │  │   1. Khamenei death check                            │  │         │
│  │  │   2. Protest trajectory                              │  │         │
│  │  │   3. Regime transitions                              │  │         │
│  │  │   4. Security force defection                        │  │         │
│  │  │   5. Ethnic fragmentation                            │  │         │
│  │  │   6. US posture escalation                           │  │         │
│  │  │   7. Terminal outcome detection                      │  │         │
│  │  │                                                        │  │         │
│  │  └──────────────────────────────────────────────────────┘  │         │
│  │                                                              │         │
│  │  SimulationState:                                            │         │
│  │   - regime_state, protest_state, us_posture                │         │
│  │   - Anchor days: escalation_start_day,                     │         │
│  │     crackdown_start_day, defection_day, etc.               │         │
│  │   - Event trackers: khamenei_dead, defection_occurred, ... │         │
│  │   - final_outcome, outcome_day                             │         │
│  │                                                              │         │
│  └──────────────────────────────────────────────────────────────┘         │
│                                    │                                      │
│                                    ▼                                      │
│                      ┌──────────────────────────────┐                    │
│                      │ simulation_results.json      │                    │
│                      │  - Outcome distribution      │                    │
│                      │  - Event rates               │                    │
│                      │  - Sample trajectories       │                    │
│                      └──────────────────────────────┘                    │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 4: VISUALIZATION & ANALYSIS                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────┐         ┌──────────────────┐                      │
│  │  visualize.py    │────────▶│  Charts & Maps   │                      │
│  │                  │         │   - outcome_dist. │                      │
│  │                  │         │     png           │                      │
│  │                  │         │   - iran_map.svg  │                      │
│  │                  │         │   - narratives.md │                      │
│  └──────────────────┘         └──────────────────┘                      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Intelligence Layer (`src/pipeline/`)

**Purpose:** Establish a traceable chain from raw evidence to structured intelligence.

#### `models.py` - Data Models
```python
@dataclass
class EvidenceDoc:
    doc_id, source_name, url, published_at_utc,
    retrieved_at_utc, language, raw_text,
    translation_en?, translation_confidence?

@dataclass
class Source:
    id, organization, title, date, url,
    access_grade (A-D), bias_grade (1-4)

@dataclass
class Claim:
    claim_id, path, value, units, as_of,
    source_ids[], source_grade, confidence,
    triangulated, null_reason?, notes, conflicts[]
```

**Design Rationale:**
- **Source grading:** Uses NATO source reliability grading (A=reliable, 1=confirmed)
- **Claims ledger:** Every number has provenance, not just "analyst judgment"
- **Null semantics:** Explicit null_reason prevents silent data gaps

#### `compile_intel.py` - Merge & Compile
```python
# Merge rule: Best source_grade wins per (path, selector)
# Grade score = access_level*10 + (5-bias)
# Example: A1 = 4*10 + 4 = 44 (best)
#          B3 = 3*10 + 2 = 32
```

**Outputs:**
- `compiled_intel.json` - Final intelligence artifact
- `merge_report.json` - Which claims won, which were rejected
- `qa_report.json` - Validation errors/warnings

#### `qa.py` - Quality Gates
- Schema validation (_schema_version required)
- Unique claim_id enforcement
- Source reference integrity (source_ids exist in sources[])
- Null interpretability (value=null requires null_reason OR notes)

**Current Status:** MVP implemented, not yet used in production (direct intel file used instead).

---

### 1b. Baseline Knowledge Layer (`knowledge/iran_baseline/`)

**Purpose:** Provide stable, slowly-changing reference knowledge to anchor analyst estimates with historical base rates.

#### Design Rationale

The baseline pack addresses a critical calibration problem: analysts consistently overestimate regime fragility and underestimate historical suppression rates. By separating **current crisis intel** from **historical reference data**, we ensure:

1. **Base rate anchoring:** Every probability estimate must cite baseline historical data
2. **Auditability:** Clear separation between "what's happening now" and "what usually happens"
3. **Update frequency:** Baseline updates quarterly, not with every intel cycle

#### Directory Structure
```
knowledge/iran_baseline/
├── evidence_docs.jsonl      # Source citations for baseline facts
├── claims.jsonl             # Structured claims with baseline.* paths
└── compiled_baseline.json   # Packaged reference knowledge
```

#### `compiled_baseline.json` Schema
```json
{
  "_schema_version": "1.0",
  "_type": "baseline_knowledge_pack",
  "metadata": { "pack_id", "created_date", "coverage_assessment" },

  "regime_structure": {
    "supreme_leader": { "name", "tenure_years", "age", "health_baseline" },
    "power_centers": [{ "name", "role", "estimated_personnel", "loyalty_assessment" }]
  },

  "historical_protests": {
    "base_rate_summary": {
      "major_protests_since_1979": 6,
      "outcomes": { "SUPPRESSED": 5, "PARTIAL_CONCESSIONS": 0, "REGIME_CHANGE": 0 },
      "defections_occurred": 0
    },
    "events": [{ "id", "year", "trigger", "duration_days", "outcome", "defections_occurred" }]
  },

  "ethnic_composition": {
    "groups": [{ "name", "population_percent", "historical_grievance_level", "armed_groups" }]
  },

  "information_control": {
    "doctrine": "...",
    "blackout_capability": { "technical_means", "implementation_speed" }
  },

  "external_actors": {
    "playbooks": [{ "actor", "historical_posture", "intervention_precedents" }]
  }
}
```

#### Integration with Analyst Workflow

```
┌─────────────────────┐     ┌─────────────────────┐
│ compiled_intel.json │     │compiled_baseline.json│
│  (current crisis)   │     │ (historical anchor) │
└─────────┬───────────┘     └──────────┬──────────┘
          │                            │
          └──────────┬─────────────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ Security Analyst     │
          │ Prompt               │
          │                      │
          │ For each estimate:   │
          │ 1. Check baseline    │
          │ 2. Start from base   │
          │ 3. Adjust with intel │
          │ 4. Document reasoning│
          └──────────┬───────────┘
                     │
                     ▼
          ┌──────────────────────┐
          │ analyst_priors.json  │
          │ (base_rate_anchor    │
          │  cites baseline)     │
          └──────────────────────┘
```

#### `compile_baseline.py` - Baseline Compilation

Unlike `compile_intel_v2.py` which resolves conflicting claims, baseline compilation:
- Validates claims against `baseline.*` paths in path registry
- Groups data by section (regime_structure, historical_protests, etc.)
- Runs completeness checks (all sections populated)
- Does NOT perform merge logic (baseline is curator-authored, not merged)

**Outputs:**
- `compiled_baseline.json` - Packaged baseline knowledge
- `baseline_qa.json` - Completeness and validation report

**Current Status:** Infrastructure implemented, placeholder data populated. Requires Deep Research run to populate with actual historical analysis.

---

### 2. Priors Layer (`src/priors/`)

**Purpose:** Make probability semantics machine-checkable and prevent "quietly wrong" runs.

#### `contract.py` - Priors Contract Resolver

**The Problem:**
```
❌ BAD: "P(crackdown within 30 days of escalation) = 0.4"
         Simulator applies 0.4 daily forever → cumulative 99.9% after 90 days

✅ GOOD: time_basis="window", anchor="escalation_start", window_days=30
         Simulator applies daily_hazard only during days [escalation_start, escalation_start+29]
```

**Schema Extensions:**
```json
{
  "probability": {
    "low": 0.25, "mode": 0.4, "high": 0.6,
    "dist": "beta_pert",
    "time_basis": "window",        // NEW: window | instant | daily
    "anchor": "escalation_start",  // NEW: when does window start?
    "start_offset_days": 0,        // NEW: delay before window opens
    "window_days": 30              // CLARIFIED: explicit window length
  }
}
```

**Anchor Points Supported:**
- `t0` - Simulation day 1
- `t0_plus_30` - Day 31
- `escalation_start` - When protests escalate
- `crackdown_start` - When mass-casualty crackdown begins
- `concessions_start` - When regime offers concessions
- `defection_day` - When security forces defect
- `ethnic_uprising_day` - When ethnic regions declare autonomy
- `khamenei_death_day` - When Khamenei dies
- `collapse_day` - When regime collapses

**Resolution Algorithm:**
1. Fill defaults:
   - `dist` defaults to `"beta_pert"`
   - `mode` defaults to `point` if missing
   - `time_basis` inferred from `window_days` presence
   - `start_offset_days` defaults to 0

2. Validate:
   - `low ≤ mode ≤ high` and all in [0,1]
   - `window_days > 0` if `time_basis="window"`
   - `anchor` present if `time_basis="window"`
   - Required keys exist (based on simulator dependencies)

3. Warn:
   - Name contains "_30d" but `window_days != 30`
   - Keys present but unused by current simulator
   - `regime_outcomes` not marked as `"role": "diagnostic_only"`

**Outputs:**
- `priors_resolved.json` - Priors with all defaults filled
- `priors_qa.json` - Errors (blocking) and warnings (advisory)

---

### 3. Simulation Layer (`src/simulation.py`)

**Purpose:** Run Monte Carlo trajectories with semantically correct probability application.

#### Key Design Decisions

**1. Window Semantics Enforcement**

```python
@classmethod
def _window_active(cls, state: SimulationState, prob_obj: dict) -> bool:
    anchor_day = cls._anchor_day_from_state(state, prob_obj["anchor"])
    if anchor_day is None:
        return False  # Anchor not yet set, window not open

    start = anchor_day + prob_obj["start_offset_days"]
    end = start + prob_obj["window_days"] - 1
    return start <= state.day <= end
```

**Example:** Cyber attack probability
- Prior: `P(cyber | crackdown) = 0.3 within 14 days`
- Semantics: `time_basis="window"`, `anchor="crackdown_start"`, `window_days=14`
- Behavior:
  - Before crackdown: `_window_active() = False` → skip check
  - Days [crackdown_start, crackdown_start+13]: Apply daily hazard
  - After day crackdown_start+14: `_window_active() = False` → window closed

**2. Window Probability → Daily Hazard Conversion**

```python
def _window_prob_to_daily(p_window: float, window_days: int) -> float:
    """
    Convert P(event occurs within N days) to constant daily hazard.

    Derivation:
        P(event within N days) = 1 - (1 - p_daily)^N
        p_daily = 1 - (1 - p_window)^(1/N)
    """
    if p_window >= 1.0:
        return 1.0
    return 1.0 - math.pow(1.0 - p_window, 1.0 / window_days)
```

**Why constant hazard?**
- Memoryless: Day-by-day simulation doesn't need to track "accumulated probability"
- Correct: Integrates to exactly `p_window` over `window_days`
- Simple: No partial credit or complex conditional logic

**3. Condition Semantics Clarification**

**Problem:** "Defection given protests persist beyond 30 days"
- Naive: Any day ≥ 30 with any protest_state
- Correct: Days 30-90 AND protest_state ∈ {STABLE, ESCALATING}

```python
@staticmethod
def _protests_active_for_30d_condition(state: SimulationState) -> bool:
    """
    'Protests persist' means NOT collapsed AND NOT declining.
    This prevents events from triggering during protest death spiral.
    """
    return state.protest_state in (ProtestState.STABLE, ProtestState.ESCALATING)
```

**Applied to:**
- `security_force_defection_given_protests_30d`
- `ethnic_coordination_given_protests_30d`
- `meaningful_concessions_given_protests_30d`
- `covert_support_given_protests_30d`

**4. State Machine Architecture**

```python
class SimulationState:
    # Current state
    day: int
    regime_state: RegimeState  # STATUS_QUO, ESCALATING, CRACKDOWN, ...
    protest_state: ProtestState  # DECLINING, STABLE, ESCALATING, ...
    us_posture: USPosture  # RHETORICAL → ... → KINETIC → GROUND

    # Anchor days (None until event occurs)
    escalation_start_day: Optional[int]
    crackdown_start_day: Optional[int]
    defection_day: Optional[int]
    ethnic_uprising_day: Optional[int]
    khamenei_death_day: Optional[int]
    collapse_day: Optional[int]

    # Terminal outcome
    final_outcome: Optional[str]  # "REGIME_SURVIVES_STATUS_QUO", ...
    outcome_day: Optional[int]
```

**Daily Update Sequence:**
1. **Khamenei death check** (independent event, daily hazard from 90-day window prob)
2. **Protest trajectory** (escalation/sustain/collapse dynamics)
3. **Regime transitions** (crackdown, concessions)
4. **Security defection** (windowed conditional)
5. **Ethnic fragmentation** (coordination event, then terminalization window)
6. **US posture escalation** (monotonic ladder, multiple trigger conditions)
7. **Terminal state detection** (collapse, transition, suppression)

**5. Sampling Strategy**

```python
class ProbabilitySampler:
    def __init__(self, priors):
        self.priors = priors
        self._cache = {}  # Sample once per run, reuse per day

    def sample(self, category, key):
        cache_key = f"{category}.{key}"
        if cache_key not in self._cache:
            prob_obj = self._get_probability(category, key)
            dist = prob_obj.get("dist", "beta_pert")

            if dist == "beta_pert":
                # PERT distribution: expert mode with uncertainty
                self._cache[cache_key] = self._sample_beta_pert(prob_obj)
            elif dist == "triangular":
                self._cache[cache_key] = random.triangular(low, mode, high)
            elif dist == "fixed":
                self._cache[cache_key] = prob_obj["point"]

        return self._cache[cache_key]
```

**Why cache per run?**
- Consistency: "P(defection) = 0.08" means 8% of runs have defection, not 8% per day
- Epistemic uncertainty: Each run samples from analyst uncertainty, then commits
- Prevents double-counting: Don't re-roll probability every day for same event

---

## Critical Bug Fixes Implemented

### Bug 1: Infinite-Horizon Application of Window Probabilities
**Before:**
```python
# WRONG: Applied "P(crackdown within 30 days) = 0.4" as daily 0.4 forever
if random.random() < 0.4:
    enter_crackdown()
```

**After:**
```python
# CORRECT: Only apply during [escalation_start, escalation_start+29]
prob_obj = priors["mass_casualty_crackdown_given_escalation"]["probability"]
if self._window_active(state, prob_obj):
    daily_hazard = self._daily_hazard_from_window_prob(...)
    if random.random() < daily_hazard:
        enter_crackdown()
```

**Impact:** Prevented systematic overestimation of rare events over 90-day horizon.

---

### Bug 2: Condition Check Ignores Protest State
**Before:**
```python
# WRONG: Defection could trigger even if protests collapsed
if state.day >= 30:
    check_defection()
```

**After:**
```python
# CORRECT: Only if protests are active (STABLE or ESCALATING)
if self._protests_active_for_30d_condition(state) and self._window_active(state, prob_obj):
    check_defection()
```

**Impact:** Prevents illogical events (e.g., security defecting to support non-existent protests).

---

### Bug 3: Hard-Coded Magic Numbers
**Before:**
```python
# WRONG: Fragmentation outcome hard-coded
if state.ethnic_uprising:
    if random.random() < 0.3:  # Magic number!
        state.final_outcome = "ETHNIC_FRAGMENTATION"
```

**After:**
```python
# CORRECT: Uses prior "fragmentation_outcome_given_ethnic_uprising"
prob_obj = priors["transition"]["fragmentation_outcome_given_ethnic_uprising"]
if self._window_active(state, prob_obj):
    daily_prob = self._daily_hazard_from_window_prob(...)
    if random.random() < daily_prob:
        state.final_outcome = "ETHNIC_FRAGMENTATION"
```

**Impact:** All probabilities now traceable to analyst priors file, auditable.

---

### Bug 4: Missing Anchor Day Tracking
**Before:**
```python
# WRONG: Cyber attack window starts from day 1, not crackdown day
if state.regime_state == RegimeState.CRACKDOWN:
    apply_cyber_probability()
```

**After:**
```python
# CORRECT: Anchor days set when event occurs
if state.regime_state == RegimeState.CRACKDOWN and state.crackdown_start_day is None:
    state.crackdown_start_day = state.day

# Later: Window check uses anchor
prob_obj = priors["cyber_attack_given_crackdown"]
if self._window_active(state, prob_obj):  # Checks crackdown_start_day
    apply_cyber_probability()
```

**Impact:** Windows now correctly anchored to triggering events, not arbitrary days.

---

## Testing Strategy

### Unit Tests (`tests/test_time_semantics.py`)

**Philosophy:** Test the hard-to-reason-about edge cases, not obvious CRUD.

1. **Window boundary logic**
   - 3-day window starting day 5 → active days 5,6,7 only (not 8)

2. **Anchor day setting**
   - Entering CRACKDOWN state sets `crackdown_start_day`

3. **Window enforcement before anchor**
   - Cyber probability NOT applied when `crackdown_start_day=None`

4. **Condition checking**
   - Defection NOT triggered when `protest_state=DECLINING` (even if day ≥ 30)

5. **Contract validation**
   - Missing `protests_collapse_given_concessions_30d` → raises error

6. **Prior-driven outcomes**
   - Fragmentation outcome uses prior, not hard-coded 0.3

**Result:** All 6 tests passing.

---

## Data Flow Example

### Scenario: US Cyber Attack Following Crackdown

1. **Day 1-10:** Protests in STABLE state
2. **Day 11:** Protests escalate
   - `state.protest_state = ProtestState.ESCALATING`
   - `state.escalation_start_day = 11`
3. **Day 15:** Crackdown begins (within 30-day escalation window)
   - `state.regime_state = RegimeState.CRACKDOWN`
   - `state.crackdown_start_day = 15`
4. **Day 16-28:** Cyber attack window active
   - Prior: `time_basis="window"`, `anchor="crackdown_start"`, `window_days=14`
   - Window: days [15, 28]
   - Each day: Sample `P(cyber within 14d) = 0.15` → daily hazard ≈ 0.0114
   - Random draw each day, may trigger cyber attack
5. **Day 29+:** Cyber window closed
   - `_window_active() = False`
   - No more cyber checks (unless prior has multiple attempts semantics, not implemented)

---

## Performance Characteristics

- **Single run:** ~1-2ms (Python 3.11, M1 Mac)
- **10,000 runs:** ~10-20 seconds
- **Memory:** <50MB for full 10k run batch
- **Deterministic:** Seeded RNG for reproducibility

**Bottlenecks:**
- Beta distribution sampling (can be optimized with numpy if needed)
- Not parallelized (easily parallelizable via multiprocessing)

---

## Regional Cascade System

The simulation now models spillover effects from Iran to neighboring countries and external actor responses.

### Multi-Country State Model

```
                    ┌─────────────┐
                    │    IRAN     │
                    │  (Primary)  │
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
         ▼                 ▼                 ▼
   ┌───────────┐    ┌───────────┐    ┌───────────────┐
   │   IRAQ    │    │   SYRIA   │    │ EXTERNAL ACTORS│
   │           │    │           │    │                │
   │ STABLE    │    │ STABLE    │    │ Israel: MON→STR│
   │ STRESSED  │    │ STRESSED  │    │ Russia: OBS→SUP│
   │ CRISIS    │    │ CRISIS    │    │ Gulf realign   │
   │ COLLAPSE  │    │ COLLAPSE  │    │                │
   └───────────┘    └───────────┘    └────────────────┘
```

### Coupling Probabilities

| Coupling | Anchor | Window | Mode |
|----------|--------|--------|------|
| Iraq stressed ← Iran escalation | escalation_start | 30d | 25% |
| Iraq crisis ← Iran collapse | collapse_day | 30d | 45% |
| Syria crisis ← Iran collapse | collapse_day | 30d | 50% |
| Iraq proxy activation ← US kinetic | us_kinetic_day | 14d | 65% |
| Syria proxy activation ← US kinetic | us_kinetic_day | 14d | 55% |
| Israel strikes ← Iran defection | defection_day | 30d | 45% |
| Russia support ← Iran threatened | escalation_start | 60d | 25% |
| Gulf realignment ← Iran collapse | collapse_day | 30d | 70% |

### Implementation Details

1. **RegionalState dataclass**: Tracks each secondary country's stability, proxy activation status, and event log

2. **New state enums**:
   - `CountryStability`: STABLE → STRESSED → CRISIS → COLLAPSE
   - `IsraelPosture`: MONITORING → STRIKES → MAJOR_OPERATION
   - `RussiaPosture`: OBSERVING → SUPPORTING → INTERVENING

3. **Update sequence**: Regional cascade runs after Iran state updates (step 8 in daily loop)

4. **Output**: `regional_cascade_rates` in simulation results shows empirical frequencies

### Example Output

```json
{
  "regional_cascade_rates": {
    "iraq_crisis": 0.02,
    "syria_crisis": 0.025,
    "israel_strikes": 0.008,
    "iraq_proxy_activation": 0.011,
    "syria_proxy_activation": 0.006,
    "gulf_realignment": 0.018,
    "russia_support": 0.07
  }
}
```

### Design Notes

- **One-way coupling**: Iran → neighbors (bidirectional effects are future work)
- **Window semantics**: All couplings use the same anchor/window_days pattern as Iran events
- **Conditional probabilities**: Couplings only fire when the triggering Iran event occurs

---

## Oracle Layer: Forecasting & Scoring System (v3.0)

The Oracle Layer provides observe-only forecasting, resolution, and scoring capabilities that never modify simulation logic.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 5: ORACLE (OBSERVE-ONLY)                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────┐         ┌──────────────────┐                      │
│  │  Event Catalog   │         │  Forecast Gen    │                      │
│  │  (v3.0.0)        │────────▶│  (forecast.py)   │                      │
│  │  18 events       │         │                  │                      │
│  │  - 5 forecastable│         │  Outputs:        │                      │
│  │  - 5 diagnostic  │         │  - forecasts.jsonl│                      │
│  │  - 8 disabled    │         │                  │                      │
│  └──────────────────┘         └────────┬─────────┘                      │
│                                        │                                │
│  ┌──────────────────┐                  ▼                                │
│  │  Bins Module     │         ┌──────────────────┐                      │
│  │  (bins.py)       │────────▶│  Resolution      │                      │
│  │                  │         │  (resolver.py)   │                      │
│  │  - validate_spec │         │                  │                      │
│  │  - value_to_bin  │         │  Outputs:        │                      │
│  └──────────────────┘         │  - resolutions.jsonl│                   │
│                               │  - evidence/     │                      │
│                               └────────┬─────────┘                      │
│                                        │                                │
│                                        ▼                                │
│                               ┌──────────────────┐                      │
│                               │  Scorer          │                      │
│                               │  (scorer.py)     │                      │
│                               │                  │                      │
│                               │  - Brier scores  │                      │
│                               │  - Calibration   │                      │
│                               └──────────────────┘                      │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Event Catalog Schema (v3.0.0)

The catalog defines 18 events across multiple types:

```json
{
  "catalog_version": "3.0.0",
  "events": [
    {
      "event_id": "econ.fx_band",
      "name": "FX black-market band",
      "event_type": "binned_continuous",
      "category": "econ",
      "enabled": true,
      "horizons_days": [1, 7, 15, 30],
      "allowed_outcomes": ["FX_LT_800K", "FX_800K_1M", "FX_1M_1_2M", "FX_GE_1_2M", "UNKNOWN"],
      "auto_resolve": true,
      "requires_manual_resolution": false,
      "forecast_source": {
        "type": "baseline_climatology"
      },
      "resolution_source": {
        "type": "compiled_intel",
        "path": "current_state.economic_conditions.rial_usd_rate.market",
        "rule": "bin_map"
      },
      "bin_spec": {
        "bins": [
          { "bin_id": "FX_LT_800K", "min": null, "max": 800000, "include_min": false, "include_max": false },
          { "bin_id": "FX_800K_1M", "min": 800000, "max": 1000000, "include_min": true, "include_max": false },
          { "bin_id": "FX_1M_1_2M", "min": 1000000, "max": 1200000, "include_min": true, "include_max": false },
          { "bin_id": "FX_GE_1_2M", "min": 1200000, "max": null, "include_min": true, "include_max": true }
        ]
      }
    }
  ]
}
```

### Event Types

| Type | Description | Resolution |
|------|-------------|------------|
| `binary` | YES/NO outcomes | threshold rules |
| `categorical` | Multiple discrete outcomes | enum_match rule |
| `binned_continuous` | Numeric values mapped to bins | bin_map rule |

### Bin Validation Rules

The `bins.py` module enforces:

1. **No overlaps:** Bins must not share any values
2. **No gaps:** Bins must cover entire domain (or have explicit UNDERFLOW/OVERFLOW)
3. **Boundary determinism:** `include_min`/`include_max` flags resolve ties
4. **ID matching:** `bin_ids == (allowed_outcomes - {"UNKNOWN"})`

```python
# Validation
errors = bins.validate_bin_spec(bin_spec)

# Value mapping
bin_id, reason = bins.value_to_bin(value, bin_spec)
# Returns: ("FX_1M_1_2M", None) or ("UNKNOWN", "missing_value")
```

### Resolution Rules

| Rule | Input | Output |
|------|-------|--------|
| `threshold_gte` | numeric | YES if value >= threshold |
| `threshold_gt` | numeric | YES if value > threshold |
| `bin_map` | numeric | bin_id from bin_spec |
| `enum_match` | string | outcome if in allowed_outcomes |
| `enum_in` | string | YES if value in values list |

### Forecast Source Types

| Type | Description | Phase |
|------|-------------|-------|
| `simulation_output` | Direct field from simulation | 2.x |
| `simulation_derived` | Derived with conditional logic | 2.x |
| `baseline_climatology` | Uniform distribution (fallback) | 3A |
| `baseline_persistence` | Last resolved outcome | 3C |
| `diagnostic_only` | No forecast, tracking only | 3A |

### Event Filtering

Events are filtered before forecast generation:

```python
def get_forecastable_events(catalog):
    """
    Returns events where:
    - enabled == true (default: true)
    - forecast_source.type != "diagnostic_only"
    """
```

This ensures disabled events and diagnostic-only events don't generate forecasts.

### Probability Distribution Validation

All forecast distributions are validated before ledger append:

```python
def validate_distribution(probs, event):
    """
    Checks:
    1. No NaN values
    2. No negative values
    3. All values in [0, 1]
    4. Sum to 1.0 (tolerance: 1e-6)
    5. All required outcomes present
    6. No unexpected outcomes (UNKNOWN always allowed)
    """
```

### Manual Resolution Workflow

Events with `requires_manual_resolution: true` are:
- Skipped by `resolve_pending()` automatic resolution
- Left in the pending queue for manual adjudication
- Resolved via `forecast resolve --manual` CLI command

### Module Structure

```
src/forecasting/
├── __init__.py          # Package exports (v3.0.0)
├── catalog.py           # Event catalog loading, validation, filtering
├── bins.py              # Bin validation and value-to-bin mapping
├── ledger.py            # Append-only JSONL storage
├── forecast.py          # Forecast generation, distribution validation
├── resolver.py          # Resolution logic with bin_map/enum_match
├── evidence.py          # Evidence snapshot storage with hashing
├── scorer.py            # Brier/log scoring (Phase 3B)
├── reporter.py          # Report generation
└── cli.py               # Command-line interface
```

### Test Coverage

```
tests/
├── test_bins.py                 # 24 tests - bin validation, value mapping
├── test_catalog_v3.py           # 26 tests - schema, filtering, validation
├── test_resolver_bins.py        # 18 tests - bin_map, enum_match rules
├── test_forecast_validation.py  # 18 tests - distribution validation
├── test_forecasting_catalog.py  # Updated for v3.0.0
├── test_forecasting_forecast.py # Updated for baseline forecasters
└── test_forecasting_resolver.py # Updated for event parameter
```

---

## Known Limitations

### 1. Model Simplifications
- **Linear state transitions:** Real world has feedback loops, tipping points
- **Independent events:** Khamenei death and protests modeled separately (may interact)
- **US posture monotonicity:** Can't de-escalate once escalated
- **No reflexivity:** Publishing this forecast can't influence outcomes (in model)

### 2. Epistemic Uncertainty Not Propagated
- Priors are point estimates with uncertainty (low/mode/high)
- Each run samples from uncertainty, but aggregate doesn't decompose aleatory vs epistemic
- Future: Nested Monte Carlo or variance decomposition

### 3. Evidence Pipeline Not Production-Ready
- `compile_intel.py` works but no automated evidence collectors
- Deep Research output not yet structured as `evidence_docs.jsonl`
- Manual curation still required

---

## Design Principles

### 1. Epistemic Humility
- Wide confidence intervals are honest, not weak
- "We don't know" (via null_reason) is valid data
- Probabilistic forecasts acknowledge irreducible uncertainty

### 2. Auditability Over Automation
- Every number has provenance (claims ledger)
- Merge logic is deterministic and transparent
- QA gates fail fast rather than silently degrade

### 3. Semantic Precision
- "Probability" is ambiguous; `time_basis` + `anchor` + `window_days` is precise
- Code enforces what prompts can't
- Fail fast if semantics unclear (required fields)

### 4. Separation of Concerns
- Intelligence ≠ Analysis ≠ Simulation
- Each layer can be tested, updated, or swapped independently
- Prompts for humans (Research, Analyst), code for correctness

### 5. No Silent Failures
- Missing priors → error, not default to 0
- Invalid probability triplet → error, not clamp
- Semantic mismatch → warning, logged to QA report

---

## Extension Points

### Easy Additions
1. **Parallel execution:** Wrap `run_single()` in multiprocessing pool
2. **Outcome narratives:** Generate natural language descriptions of trajectories
3. **Sensitivity analysis:** Automated parameter sweep + tornado charts
4. **Calibration metrics:** If ground truth emerges, compute Brier scores

### Medium Effort
1. **Regional cascade:** Multi-country state space
2. **Dynamic priors:** Update probabilities mid-run based on realized events
3. **Epistemic uncertainty decomposition:** Nested sampling or variance attribution
4. **Real-time updates:** Streaming intel → recompile → re-simulate

### Research Directions
1. **Causal DAG extraction:** Infer causal model from priors structure
2. **Counterfactual queries:** "What if US didn't intervene?"
3. **Active learning:** Which intel gaps reduce uncertainty most?
4. **Ensemble methods:** Multiple analyst priors → probability of probabilities

---

## File Manifest

```
iran_simulation/
├── README.md                        # User guide
├── ARCHITECTURE.md                  # This file
├── CLAUDE.md                        # Claude Code instructions
│
├── data/
│   ├── iran_crisis_intel.json      # Intelligence data (manual or compiled)
│   └── analyst_priors.json         # Probability estimates with time semantics
│
├── src/
│   ├── simulation.py               # Monte Carlo engine (913 lines)
│   ├── visualize.py                # Charts and maps
│   ├── priors/
│   │   ├── __init__.py
│   │   └── contract.py             # Priors resolver + QA (180 lines)
│   └── pipeline/
│       ├── __init__.py
│       ├── models.py               # Evidence/Claim data models (62 lines)
│       ├── compile_intel.py        # Claims → compiled intel (129 lines)
│       └── qa.py                   # Quality gates (62 lines)
│
├── tests/
│   ├── __init__.py
│   └── test_time_semantics.py      # Unit tests (111 lines, 6 tests)
│
├── outputs/
│   ├── simulation_results.json     # Run outcomes
│   ├── priors_resolved.json        # Priors with defaults filled
│   └── priors_qa.json              # QA warnings/errors
│
└── prompts/
    ├── 01_research_prompt.md       # Deep Research query
    └── 02_security_analyst_prompt.md  # Analyst agent prompt
```

**Total:** 1,457 lines of production code, 111 lines of tests.

---

## Acceptance Criteria (Met)

✅ **P0:** Baseline runs successfully (200 iterations, seed 1)
✅ **P3:** Time semantics explicit in all window priors
✅ **P2:** Window enforcement in simulator (8+ priors corrected)
✅ **P1:** Evidence pipeline MVP (models, compiler, QA)
✅ **Tests:** 6 unit tests passing
✅ **Documentation:** README updated with new features
✅ **No TODOs:** Zero placeholders in core logic
✅ **Auditability:** priors_qa.json, priors_resolved.json emitted

---

## Comparison to Alternatives

### vs. Bayesian Networks (e.g., GeNIe)
**Pros:** More structured, can do exact inference
**Cons:** Discrete states only, hard to express time-varying hazards
**Our choice:** Monte Carlo for flexibility with continuous time

### vs. Agent-Based Models (e.g., NetLogo)
**Pros:** Emergent behavior, spatial dynamics
**Cons:** Computationally expensive, hard to calibrate
**Our choice:** State machine for tractability

### vs. System Dynamics (e.g., Vensim)
**Pros:** Stock-flow intuition, feedback loops
**Cons:** Continuous approximation, deterministic
**Our choice:** Stochastic for irreducible uncertainty

### vs. Superforecasting Aggregation
**Pros:** Human judgment, no model assumptions
**Cons:** Opaque process, hard to update mid-crisis
**Our choice:** Structured priors + transparent simulation

---

## Conclusion

This architecture implements a production-grade geopolitical crisis simulator with two key innovations:

1. **Semantic Correctness:** Window-bounded probabilities are enforced at the type system level (via priors contract), preventing a class of systematic errors.

2. **Epistemic Auditability:** A clean separation between evidence, claims, intelligence, analysis, and simulation makes every number traceable and every assumption explicit.

The system is **ready for production use** with real intelligence data and calibrated analyst priors.

---

**For questions or critique, contact the development team or submit to Opus 4.5 for architectural review.**

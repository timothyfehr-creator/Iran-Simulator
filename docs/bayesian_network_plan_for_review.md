# Bayesian Network Implementation Plan - For Review

**Request:** Please review this implementation plan for upgrading the Iran crisis simulation from if-statement logic to a pgmpy Bayesian Network. Offer suggestions, identify gaps, and flag any potential issues.

---

## Table of Contents
1. [Background Context](#background-context)
2. [Current Simulation Architecture](#current-simulation-architecture)
3. [Analyst Priors Structure](#analyst-priors-structure)
4. [Time-Window Semantics](#time-window-semantics)
5. [Proposed Implementation Plan](#proposed-implementation-plan)
6. [Review Questions](#review-questions)

---

# Background Context

## Project Overview

This is a Monte Carlo simulation modeling the 2025-2026 Iranian crisis over a 90-day horizon. The simulation:
- Runs 10,000+ trajectories with daily state updates
- Uses calibrated probability estimates from `analyst_priors.json`
- Converts window probabilities (e.g., "35% within 14 days") to daily hazard rates
- Has both Monte Carlo state machine and Agent-Based Model (ABM) modes
- Outputs terminal regime outcomes: STATUS_QUO, CONCESSIONS, TRANSITION, COLLAPSE, FRAGMENTATION

## Goal of This Upgrade

Replace the rigid if-statement causal logic in `simulation.py` with a probabilistic Bayesian Network using `pgmpy` to enable:
1. Explicit causal reasoning with uncertainty quantification
2. "What-if" queries (e.g., "P(Collapse | Security forces defect)")
3. Sensitivity analysis on causal pathways
4. Foundation for future causal inference

## Constraints

1. **Safety First:** All work in a sandboxed environment (git branch, standalone script)
2. **Do NOT modify** `src/simulation.py` until the BN is validated
3. **Delegate complex math:** CPT derivation for complex tables should be sent to a reasoning model (GPT-5.2 or Claude 3.7 Thinking)

---

# Current Simulation Architecture

## Source File: `src/simulation.py` (1,412 lines)

### State Definitions

```python
class RegimeState(Enum):
    STATUS_QUO = "status_quo"           # Protests ongoing, regime holding
    ESCALATING = "escalating"            # Protests intensifying
    CRACKDOWN = "crackdown"              # Mass violence by regime
    CONCESSIONS = "concessions"          # Regime offers meaningful concessions
    DEFECTION = "defection"              # Security force defection occurring
    FRAGMENTATION = "fragmentation"      # Ethnic regions breaking away
    COLLAPSE = "collapse"                # Regime collapse
    TRANSITION = "transition"            # Managed succession
    SUPPRESSED = "suppressed"            # Protests crushed, regime stable

class EconomicStress(Enum):
    STABLE = "stable"           # Rial < 800k, inflation < 30%
    PRESSURED = "pressured"     # Rial 800k-1.2M, inflation 30-50%
    CRITICAL = "critical"       # Rial > 1.2M OR inflation > 50%

class ProtestState(Enum):
    DECLINING = "declining"
    STABLE = "stable"
    ESCALATING = "escalating"
    ORGANIZED = "organized"     # Developed leadership/coordination
    COLLAPSED = "collapsed"

class USPosture(Enum):
    RHETORICAL = "rhetorical"           # Statements only
    INFORMATION_OPS = "information_ops" # Starlink, cyber support
    ECONOMIC = "economic"               # Sanctions escalation
    COVERT = "covert"                   # Material support to opposition
    CYBER_OFFENSIVE = "cyber_offensive" # Offensive cyber ops
    KINETIC = "kinetic"                 # Military strikes
    GROUND = "ground"                   # Ground intervention
```

### Daily Simulation Step (lines 685-722)

```python
def _simulate_day(self, state: SimulationState):
    # 1. Check for Khamenei death (exogenous shock)
    self._check_khamenei_death(state)
    if state.final_outcome:
        return

    # 2. Update protest dynamics
    self._update_protest_state(state)

    # 3. Update economic stress (from real-time data)
    self._update_economic_stress(state)

    # 4. Regime transitions (crackdown, concessions)
    self._check_regime_transitions(state)

    # 4b. Security force defection
    self._check_defection(state)
    self._check_regime_collapse_after_defection(state)
    if state.final_outcome:
        return

    # 5. Ethnic fragmentation
    self._check_ethnic_fragmentation(state)
    self._check_fragmentation_outcome(state)
    if state.final_outcome:
        return

    # 6. US intervention escalation
    self._update_us_posture(state)

    # 7. Terminal outcomes
    self._check_terminal_states(state)

    # 8. Regional cascade (Iraq/Syria spillover)
    self._update_regional_cascade(state)
```

### Key Causal Logic (If-Statements)

#### Protest Escalation (lines 730-748)
```python
if state.day <= 14 and state.protest_state == ProtestState.STABLE:
    p_escalate_14d = self.sampler.sample("transition", "protests_escalate_14d")
    daily_escalate = self._window_prob_to_daily_hazard(p_escalate_14d, 14)

    # FEEDBACK: Economic stress increases escalation
    daily_escalate = self._apply_economic_modifiers(daily_escalate, "protest_escalation")

    # FEEDBACK: Concessions dampen escalation by 50%
    if state.regime_state == RegimeState.CONCESSIONS:
        daily_escalate *= 0.5

    if random.random() < daily_escalate:
        state.protest_state = ProtestState.ESCALATING
```

#### Security Force Defection (lines 828-858)
```python
if self._protests_active_for_30d_condition(state) and self._window_active(state, prob_obj):
    daily_prob = self._daily_hazard_from_window_prob("transition", "security_force_defection_given_protests_30d")

    # FEEDBACK: Economic stress increases defection (CRITICAL: ×1.15, PRESSURED: ×1.08)
    daily_prob = self._apply_economic_modifiers(daily_prob, "security_defection")

    # FEEDBACK: Concessions reduce defection by 30%
    if state.regime_state == RegimeState.CONCESSIONS:
        daily_prob *= 0.7

    if random.random() < daily_prob:
        state.defection_occurred = True
        state.regime_state = RegimeState.DEFECTION
```

#### Regime Crackdown (lines 787-808)
```python
if state.protest_state == ProtestState.ESCALATING and state.regime_state == RegimeState.STATUS_QUO:
    daily_crackdown = self._daily_hazard_from_window_prob("transition", "mass_casualty_crackdown_given_escalation")

    # FEEDBACK: Regional instability increases crackdown probability by 20%
    regional_crisis = (
        state.iraq.stability in [CountryStability.CRISIS, CountryStability.COLLAPSE] or
        state.syria.stability in [CountryStability.CRISIS, CountryStability.COLLAPSE]
    )
    if regional_crisis:
        daily_crackdown *= 1.2

    if random.random() < daily_crackdown:
        state.regime_state = RegimeState.CRACKDOWN
```

### Feedback Loops Identified

| Source → Target | Effect | Magnitude | Line |
|-----------------|--------|-----------|------|
| Economic_CRITICAL → Protest_Escalation | Increase | ×1.20 | 737 |
| Economic_CRITICAL → Security_Defection | Increase | ×1.15 | 847 |
| Economic_CRITICAL → Elite_Fracture | Increase | ×1.30 | (priors) |
| Regime_CONCESSIONS → Protest_Escalation | Decrease | ×0.50 | 742 |
| Regime_CONCESSIONS → Security_Defection | Decrease | ×0.70 | 852 |
| Regional_CRISIS → Regime_Crackdown | Increase | ×1.20 | 800 |
| Defection → Regime_Collapse | Cascade | 65% in 14d | 868 |

---

# Analyst Priors Structure

## Source File: `data/analyst_priors.json` (669 lines)

### Regime Outcomes (Target Marginals)

```json
{
  "regime_outcomes": {
    "REGIME_SURVIVES_STATUS_QUO": { "mode": 0.55, "low": 0.40, "high": 0.70 },
    "REGIME_SURVIVES_WITH_CONCESSIONS": { "mode": 0.15, "low": 0.08, "high": 0.25 },
    "MANAGED_TRANSITION": { "mode": 0.10, "low": 0.05, "high": 0.18 },
    "REGIME_COLLAPSE_CHAOTIC": { "mode": 0.12, "low": 0.05, "high": 0.22 },
    "ETHNIC_FRAGMENTATION": { "mode": 0.08, "low": 0.03, "high": 0.15 },
    "sum_check": 1.0
  }
}
```

### Transition Probabilities (12 Required)

| Probability | Mode | Low | High | Window | Anchor |
|-------------|------|-----|------|--------|--------|
| khamenei_death_90d | 0.08 | 0.03 | 0.15 | 90d | t0 |
| orderly_succession_given_khamenei_death | 0.70 | 0.50 | 0.85 | 1d (instant) | khamenei_death_day |
| protests_escalate_14d | 0.35 | 0.20 | 0.50 | 14d | t0 |
| protests_sustain_30d | 0.45 | 0.30 | 0.60 | 30d | t0 |
| mass_casualty_crackdown_given_escalation | 0.40 | 0.25 | 0.60 | 30d | escalation_start |
| protests_collapse_given_crackdown_30d | 0.55 | 0.35 | 0.75 | 30d | crackdown_start |
| protests_collapse_given_concessions_30d | 0.65 | 0.45 | 0.82 | 30d | concessions_start |
| meaningful_concessions_given_protests_30d | 0.15 | 0.07 | 0.30 | 30d | t0+30d |
| security_force_defection_given_protests_30d | 0.08 | 0.03 | 0.15 | 60d | t0+30d |
| regime_collapse_given_defection | 0.65 | 0.45 | 0.80 | 14d | defection_day |
| ethnic_coordination_given_protests_30d | 0.25 | 0.12 | 0.40 | 60d | t0+30d |
| fragmentation_outcome_given_ethnic_uprising | 0.30 | 0.15 | 0.45 | 30d | ethnic_uprising_day |

### US Intervention Probabilities (6 Required)

| Probability | Mode | Window | Anchor |
|-------------|------|--------|--------|
| information_ops | 0.70 | 30d | t0 |
| economic_escalation | 0.50 | 30d | t0 |
| covert_support_given_protests_30d | 0.35 | 60d | t0+30d |
| cyber_attack_given_crackdown | 0.40 | 14d | crackdown_start |
| kinetic_strike_given_crackdown | 0.25 | 14d | crackdown_start |
| ground_intervention_given_collapse | 0.15 | 14d | collapse_day |

### Regional Cascade Probabilities (8 Required)

| Probability | Mode | Window | Anchor |
|-------------|------|--------|--------|
| iraq_stressed_given_iran_crisis | 0.25 | 30d | escalation_start |
| iraq_crisis_given_iran_collapse | 0.45 | 30d | collapse_day |
| syria_crisis_given_iran_collapse | 0.50 | 30d | collapse_day |
| iraq_proxy_activation_given_us_kinetic | 0.65 | 14d | us_kinetic_day |
| syria_proxy_activation_given_us_kinetic | 0.55 | 14d | us_kinetic_day |
| israel_strikes_given_defection | 0.45 | 30d | defection_day |
| russia_support_given_iran_threatened | 0.25 | 60d | escalation_start |
| gulf_realignment_given_collapse | 0.70 | 30d | collapse_day |

### Economic Modifiers

```json
{
  "economic_thresholds": {
    "rial_critical_threshold": 1200000,
    "rial_pressured_threshold": 800000,
    "inflation_critical_threshold": 50,
    "inflation_pressured_threshold": 30
  },
  "economic_modifiers": {
    "critical_protest_escalation_multiplier": 1.20,
    "critical_elite_fracture_multiplier": 1.30,
    "critical_security_defection_multiplier": 1.15,
    "critical_regime_concession_multiplier": 1.10,
    "pressured_protest_escalation_multiplier": 1.10,
    "pressured_elite_fracture_multiplier": 1.15,
    "pressured_security_defection_multiplier": 1.08,
    "pressured_regime_concession_multiplier": 1.05
  }
}
```

---

# Time-Window Semantics

## Source File: `src/priors/contract.py`

### Allowed Time Bases
```python
TIME_BASIS_ALLOWED = {"window", "instant", "daily"}
```

### Allowed Anchors
```python
ANCHOR_ALLOWED = {
    "t0",                    # Day 1
    "t0_plus_30",            # Day 31
    "escalation_start",      # Day protests escalate
    "crackdown_start",       # Day crackdown begins
    "concessions_start",     # Day concessions offered
    "defection_day",         # Day defection occurs
    "ethnic_uprising_day",   # Day ethnic uprising declared
    "khamenei_death_day",    # Day Khamenei dies
    "collapse_day",          # Day regime collapses
    "us_kinetic_day",        # Day US goes kinetic
    "israel_strike_day",     # Day Israel strikes
}
```

### Window-to-Daily Hazard Conversion

```python
def _window_prob_to_daily_hazard(p_window: float, window_days: int) -> float:
    """
    Convert P(event at least once within window) to constant daily hazard.

    Uses numerically stable formula:
    p_daily = -expm1(log1p(-p_window) / window_days)

    Example: protests_escalate_14d = 0.35
    daily_hazard = -expm1(log1p(-0.35) / 14) ≈ 0.030
    """
    return -math.expm1(math.log1p(-p_window) / window_days)
```

---

# Proposed Implementation Plan

## Executive Summary

Create a **Hybrid CausalEngine** that:
1. Encapsulates a pgmpy Bayesian Network for causal structure
2. Provides query interface for "what-if" analysis
3. Can optionally integrate with MC simulation as probability oracle
4. Preserves existing simulation for trajectory generation

**Key Insight:** A static BN cannot replace the temporal simulation (90-day trajectories with daily updates), but it can complement it by enabling causal queries.

## Proposed DAG Architecture

### Nodes (17 total)

**Root Nodes (Observable/Exogenous):**
| Node | Cardinality | States |
|------|-------------|--------|
| Rial_Rate | 3 | LOW, MODERATE, HIGH |
| Inflation | 3 | LOW, MODERATE, HIGH |
| Khamenei_Health | 2 | ALIVE, DEAD |
| US_Policy_Disposition | 4 | RHETORICAL, ECONOMIC, COVERT, KINETIC |

**Intermediate Nodes:**
| Node | Cardinality | States | Parents |
|------|-------------|--------|---------|
| Economic_Stress | 3 | STABLE, PRESSURED, CRITICAL | Rial_Rate, Inflation |
| Protest_Escalation | 2 | NO, YES | Economic_Stress |
| Protest_Sustained | 2 | NO, YES | Protest_Escalation, Regime_Response |
| Protest_State | 5 | DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED | Protest_Escalation, Protest_Sustained, Regime_Response |
| Regime_Response | 4 | STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED | Protest_State, Regional_Instability |
| Security_Loyalty | 3 | LOYAL, WAVERING, DEFECTED | Economic_Stress, Protest_State, Regime_Response |
| Elite_Cohesion | 3 | COHESIVE, FRACTURED, COLLAPSED | Economic_Stress, Security_Loyalty |
| Ethnic_Uprising | 2 | NO, YES | Protest_Sustained, Economic_Stress |
| Fragmentation_Outcome | 2 | NO, YES | Ethnic_Uprising |
| Succession_Type | 2 | ORDERLY, CHAOTIC | Khamenei_Health, Elite_Cohesion |
| Regional_Instability | 3 | NONE, MODERATE, SEVERE | US_Policy_Disposition, Regime_Outcome |
| Israel_Posture | 2 | RESTRAINED, STRIKING | Security_Loyalty, US_Policy_Disposition |
| Russia_Posture | 2 | NEUTRAL, SUPPORTING | Regional_Instability |
| Gulf_Realignment | 2 | NO, YES | Regime_Outcome |

**Terminal Node:**
| Node | Cardinality | States | Parents |
|------|-------------|--------|---------|
| Regime_Outcome | 5 | STATUS_QUO, CONCESSIONS, TRANSITION, COLLAPSE, FRAGMENTATION | Security_Loyalty, Succession_Type, Fragmentation_Outcome, Elite_Cohesion |

### Edges (23 total)

```python
EDGES = [
    # Economic
    ("Rial_Rate", "Economic_Stress"),
    ("Inflation", "Economic_Stress"),

    # Protest dynamics
    ("Economic_Stress", "Protest_Escalation"),
    ("Protest_Escalation", "Protest_State"),
    ("Regime_Response", "Protest_State"),
    ("Protest_Escalation", "Protest_Sustained"),
    ("Regime_Response", "Protest_Sustained"),
    ("Protest_Sustained", "Protest_State"),

    # Regime response
    ("Protest_State", "Regime_Response"),
    ("Regional_Instability", "Regime_Response"),

    # Security dynamics
    ("Economic_Stress", "Security_Loyalty"),
    ("Protest_State", "Security_Loyalty"),
    ("Regime_Response", "Security_Loyalty"),

    # Elite cohesion
    ("Economic_Stress", "Elite_Cohesion"),
    ("Security_Loyalty", "Elite_Cohesion"),

    # Ethnic
    ("Protest_Sustained", "Ethnic_Uprising"),
    ("Economic_Stress", "Ethnic_Uprising"),
    ("Ethnic_Uprising", "Fragmentation_Outcome"),

    # Succession
    ("Khamenei_Health", "Succession_Type"),
    ("Elite_Cohesion", "Succession_Type"),

    # Terminal outcome
    ("Security_Loyalty", "Regime_Outcome"),
    ("Succession_Type", "Regime_Outcome"),
    ("Fragmentation_Outcome", "Regime_Outcome"),
    ("Elite_Cohesion", "Regime_Outcome"),

    # Regional cascade
    ("US_Policy_Disposition", "Regional_Instability"),
    ("Regime_Outcome", "Regional_Instability"),
    ("Regional_Instability", "Iraq_Stability"),
    ("Regional_Instability", "Syria_Stability"),

    # External actors
    ("Security_Loyalty", "Israel_Posture"),
    ("US_Policy_Disposition", "Israel_Posture"),
    ("Regional_Instability", "Russia_Posture"),
    ("Regime_Outcome", "Gulf_Realignment"),
]
```

## CPT Classification

### Simple CPTs (Direct Derivation from Priors)

| CPT | Size | Derivation Method |
|-----|------|-------------------|
| P(Economic_Stress \| Rial, Inflation) | 27 | Deterministic threshold rules |
| P(Khamenei_Health) | 2 | Direct: 0.92 alive, 0.08 dead |
| P(Rial_Rate), P(Inflation) | 6 | Observable from intel |
| P(Succession_Type \| Khamenei, Elite) | 12 | Direct: orderly=0.70 |

### Complex CPTs (Require Reasoning Model Delegation)

| CPT | Size | Complexity Reason |
|-----|------|-------------------|
| P(Protest_State \| Escalation, Sustained, Response) | 80 | Multi-way interaction |
| P(Security_Loyalty \| Economic, Protest, Response) | 108 | Modifier stacking (×1.15, ×0.7) |
| P(Regime_Response \| Protest, Regional) | 60 | Window-to-marginal conversion |
| P(Regime_Outcome \| Security, Succession, Frag, Elite) | 270 | Causal priority rules |
| P(Ethnic_Uprising \| Sustained, Economic) | 12 | Window semantics |

## Window-to-Marginal Conversion Formula

For static BN, convert window probability to marginal state probability:

```python
def window_to_marginal(p_window: float, window_days: int, total_days: int = 90) -> float:
    """
    Approximation: If event occurs with p_window within window_days,
    and once it occurs it persists, the marginal probability is roughly:

    p_marginal ≈ p_window * (total_days - window_days/2) / total_days
    """
    expected_onset = window_days / 2
    duration_if_occurs = total_days - expected_onset
    return p_window * (duration_if_occurs / total_days)
```

## Handling Feedback Loops

BNs are acyclic, but simulation has feedback loops (e.g., `Regime_Response → Protest_State → Regime_Response`).

**Solution: Equilibrium Modeling**
- Model the "settled" state after feedback resolves
- `Protest_State` represents steady-state given regime response
- `Regime_Response` represents settled response given protest level
- No cycles in BN; captures equilibrium distribution

## CausalEngine Class API

```python
class CausalEngine:
    def __init__(self, priors_path: str, intel_path: str):
        self.priors = load_json(priors_path)
        self.intel = load_json(intel_path)
        self.model = self._build_dag()
        self._add_simple_cpds()

    def load_complex_cpds(self, cpt_dir: Path):
        """Load CPT JSON files generated by reasoning model."""

    def infer(self, evidence: Dict[str, str]) -> Dict[str, np.ndarray]:
        """Query posterior distribution given evidence."""

    def what_if(self, intervention: Dict[str, str], query: str) -> Dict[str, float]:
        """Causal intervention query (do-calculus)."""

    def sensitivity(self, target: str = "Regime_Outcome") -> Dict[str, float]:
        """Compute mutual information I(Parent; Target) for each parent."""
```

## Example What-If Queries

```python
# What's the collapse probability if security forces defect?
engine.infer({"Security_Loyalty": "DEFECTED"})
# Expected: P(COLLAPSE) ≈ 0.65

# What if economic crisis AND protests organized?
engine.infer({"Economic_Stress": "CRITICAL", "Protest_State": "ORGANIZED"})

# Which factors most affect collapse probability?
engine.sensitivity("Regime_Outcome")
# Expected ranking: Security_Loyalty > Elite_Cohesion > Succession_Type

# Causal intervention: What if US went kinetic?
engine.what_if({"US_Policy_Disposition": "KINETIC"}, "Regime_Outcome")
```

## Validation Strategy

### Acceptance Criteria

1. **DAG validates:** `model.check_model()` returns True
2. **Marginals match:** KL divergence < 0.10 vs Monte Carlo
3. **Per-outcome diff:** Maximum absolute difference < 8%
4. **Inference works:** Conditional queries return sensible results
5. **Tests pass:** `pytest tests/test_pgmpy_prototype.py -v` all green

### Validation Against Both MC and ABM

The project has two simulation modes - validate against both:
```bash
python scripts/prototype_causal_graph.py --compare-mc runs/RUN_*/simulation_results.json
python scripts/prototype_causal_graph.py --compare-mc runs/RUN_*/abm_results.json
```

## Implementation Sequence

1. **Day 1:** Create git branch, add pgmpy dependency, build DAG skeleton, implement simple CPTs
2. **Day 2:** Export prompts for complex CPTs, send to reasoning model, parse responses
3. **Day 3:** Assemble full model, implement CausalEngine.infer(), test queries
4. **Day 4:** Validate against MC, iterate on CPTs if needed, document

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/prototype_causal_graph.py` | Main prototype with CausalEngine |
| `tests/test_pgmpy_prototype.py` | Unit and integration tests |
| `prompts/cpt_derivation/*.md` | Prompts for reasoning model |
| `prompts/cpt_derivation/responses/*.json` | CPT values from reasoning model |

## Files NOT to Modify

| File | Reason |
|------|--------|
| `src/simulation.py` | Protected until BN validated |
| `data/analyst_priors.json` | Read-only source |

---

# Review Questions

Please evaluate the following aspects of this plan:

1. **DAG Architecture:**
   - Are there missing nodes that should be included?
   - Are the parent-child relationships correct?
   - How should the feedback loops (concessions dampening, regional cascade) be handled?

2. **CPT Complexity:**
   - Is the classification of simple vs complex CPTs correct?
   - Are there CPTs I've underestimated that need more careful derivation?

3. **Window-to-Marginal Conversion:**
   - Is the approximation formula reasonable?
   - Are there better approaches for converting temporal window probabilities to static BN marginals?

4. **Hybrid vs Pure Replacement:**
   - Is the "CausalEngine as complementary tool" approach correct?
   - Should we consider a Dynamic Bayesian Network instead?

5. **Validation Criteria:**
   - Is KL divergence < 0.10 a reasonable acceptance threshold?
   - What other validation metrics should be included?

6. **Missing Elements:**
   - What have I overlooked in the simulation logic?
   - Are there edge cases that need special handling?

7. **Implementation Risks:**
   - What are the most likely failure modes?
   - How should we handle CPT derivation errors?

---

*Generated by Claude Code for Gemini review.*

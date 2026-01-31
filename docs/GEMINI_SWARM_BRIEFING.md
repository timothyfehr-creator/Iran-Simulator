# Project Swarm: ABM Migration Briefing for Review

**To:** Gemini (Reviewer/Advisor)
**From:** Claude (Implementer)
**Date:** January 17, 2026
**Status:** Plan complete, awaiting review before implementation

---

## Executive Summary

We are upgrading an Iran Crisis Monte Carlo simulation from a **State Machine** model to a **Hybrid Agent-Based Model (ABM)** with 10,000 heterogeneous agents. This document provides full context for your review.

**Your role:** Review the architecture, identify logical flaws, suggest improvements, and flag any risks before we implement.

---

## Table of Contents

1. [Project Background](#1-project-background)
2. [Current Architecture](#2-current-architecture)
3. [Feasibility Analysis (Completed)](#3-feasibility-analysis-completed)
4. [Prototype Benchmark Results](#4-prototype-benchmark-results)
5. [Project Swarm Specification](#5-project-swarm-specification)
6. [Implementation Plan](#6-implementation-plan)
7. [Questions for Reviewer](#7-questions-for-reviewer)
8. [Code Appendix](#8-code-appendix)

---

## 1. Project Background

### What This Simulation Does

This is a Monte Carlo simulation modeling the 2025-2026 Iranian protest crisis over a 90-day horizon. It:

1. Ingests intelligence data (protest metrics, economic indicators, casualty counts)
2. Applies analyst probability estimates (e.g., "30% chance of crackdown within 14 days")
3. Runs 10,000 simulation trajectories
4. Produces outcome probability distributions (regime survives, collapses, transitions, etc.)

### Why We're Upgrading

**Current Problem:** The state machine uses rigid rules like:
```python
if protest_state == ESCALATING and regime_state == STATUS_QUO:
    if random() < crackdown_probability:
        regime_state = CRACKDOWN
```

This fails to capture:
- **Heterogeneous incentives** (students vs merchants vs security forces)
- **Local cascade effects** (protests spread neighbor-to-neighbor)
- **Emergent tipping points** (small sparks → large fires)

**Target:** An ABM where 10,000 agents with different types and incentives interact, and macro outcomes *emerge* from micro behaviors.

---

## 2. Current Architecture

### Key Files

```
iran_simulation/
├── src/
│   ├── simulation.py      # Main engine - STATE MACHINE (1,350 lines)
│   ├── visualize.py       # Charts and maps (344 lines)
│   ├── abm_engine.py      # NEW PROTOTYPE (created in this session)
│   └── priors/
│       └── contract.py    # Probability validation (216 lines)
├── data/
│   ├── iran_crisis_intel.json    # Intelligence data
│   └── analyst_priors.json       # Probability estimates
```

### Current State Enums

```python
class RegimeState(Enum):
    STATUS_QUO = "status_quo"       # Protests ongoing, regime holding
    ESCALATING = "escalating"       # Protests intensifying
    CRACKDOWN = "crackdown"         # Mass violence by regime
    CONCESSIONS = "concessions"     # Regime offers meaningful concessions
    DEFECTION = "defection"         # Security force defection occurring
    FRAGMENTATION = "fragmentation" # Ethnic regions breaking away
    COLLAPSE = "collapse"           # Regime collapse
    TRANSITION = "transition"       # Managed succession
    SUPPRESSED = "suppressed"       # Protests crushed

class ProtestState(Enum):
    DECLINING = "declining"
    STABLE = "stable"
    ESCALATING = "escalating"
    ORGANIZED = "organized"
    COLLAPSED = "collapsed"
```

### Current Simulation Flow

```
Day 1-90 Loop:
  1. Check Khamenei death (independent hazard)
  2. Update protest state (escalate/decline/collapse)
  3. Check regime transitions (crackdown vs concessions)
  4. Check security force defection
  5. Check ethnic fragmentation
  6. Update US posture
  7. Update regional cascade (Iraq/Syria spillover)
  8. Check terminal states
```

---

## 3. Feasibility Analysis (Completed)

We evaluated four key questions before proceeding:

### Q1: State Decoupling (RegimeState → Visualization)

**Finding:** LOW coupling - safe to modify.

`visualize.py` uses string keys from JSON results, not enum imports:
```python
colors = {
    "REGIME_SURVIVES_STATUS_QUO": "#2ecc71",
    "REGIME_COLLAPSE_CHAOTIC": "#e74c3c",
}
```

### Q2: Performance Budget

**Finding:** Mesa library is TOO SLOW. NumPy vectorization REQUIRED.

| Approach | 10K agents × 90 days | 1000 MC runs |
|----------|---------------------|--------------|
| Mesa (Python objects) | ~1-5 sec/run | 15-90 minutes |
| **NumPy vectorized** | **0.06 sec/run** | **~60 seconds** |

### Q3: Data Granularity for Agent Types

**Finding:** Province-level data available, but no demographic breakdown.

Current intel has:
- Province population
- Primary ethnicity per province
- Protest status (HIGH/MED/LOW)

Missing:
- Occupation distribution (student/merchant/worker)
- Income by demographic
- Age distribution

**Workaround:** Use synthetic distributions calibrated to literature (Beta distributions by agent type).

### Q4: Hybrid Architecture Viability

**Finding:** VIABLE - clean interface possible.

```
simulation.py (Macro Controller)
    │
    ├── Regime decisions (crackdown/concessions)
    ├── US intervention ladder
    ├── Regional cascade (Iraq/Syria)
    │
    └── calls → abm_engine.py (Micro Dynamics)
                    │
                    ├── 10,000 agent states
                    ├── Network influence
                    └── returns aggregates
```

---

## 4. Prototype Benchmark Results

We built and benchmarked a minimal NumPy-vectorized prototype:

```
============================================================
ABM Engine Benchmark
============================================================
Agents: 10,000
Days per run: 90
Total runs: 1,000
Total agent-steps: 900,000,000
============================================================

Initialization time: 0.019s
Total time: 59.10s
Mean run time: 0.0591s (±0.0030s)
Agent-steps/sec: 15,229,701

✅ EXCELLENT: Sub-second per run
============================================================
```

**Performance confirmed:** 10K agents × 90 days × 500 runs = ~30 seconds (meets target).

---

## 5. Project Swarm Specification

### The Core 4 Agent Types (+ Mass)

| Type | % | Role | Key Behavior |
|------|---|------|--------------|
| **Student** | 15% | The Spark | Lower activation threshold when protests escalating (-0.2) |
| **Merchant** | 20% | The Fuel | Economic sensitivity (+0.3 grievance when Rial > 1.5M), exit on concessions |
| **Conscript** | 10% | The Weak Link | Security force, can DEFECT (not protest) when overwhelmed + moral injury |
| **Hardliner** | 5% | The Firebreak | Security force, NEVER defects until regime collapse |
| **Civilian** | 50% | The Mass | Standard Granovetter threshold model |

### Agent State Arrays

```python
# Core state (NumPy arrays, length 10,000)
self.agent_type: np.int8        # 0=Student, 1=Merchant, 2=Conscript, 3=Hardliner, 4=Civilian
self.grievance: np.float32      # [0, 1] - How upset the agent is
self.threshold: np.float32      # [0, 1] - Activation threshold
self.active: np.bool_           # Currently protesting?
self.defected: np.bool_         # (Security only) Has defected?

# Network
self.neighbors: scipy.sparse.csr_matrix  # Adjacency matrix
```

### Logic Rules

**Student Logic:**
```python
if protest_state == "ESCALATING":
    effective_threshold[student_mask] = base_threshold[student_mask] - 0.2
```

**Merchant Logic:**
```python
if rial_rate > 1_500_000:
    grievance[merchant_mask] += 0.3
if concessions_offered:
    grievance[merchant_mask] *= 0.5  # 50% reduction, exit early
```

**Conscript Defection Logic:**
```python
# Conditions: overwhelmed locally AND moral injury from shooting
overwhelmed = neighbor_active_pct > 0.5
moral_injury = crackdown_intensity > 0.6
eligible = conscript_mask & overwhelmed & moral_injury & ~defected

# Stochastic: 30% daily probability when eligible
defected[eligible & (random() < 0.3)] = True
```

**Hardliner Logic:**
```python
grievance[hardliner_mask] = 0.0  # Locked at zero
# Defect only when >50% conscripts defected OR explicit COLLAPSE
if defection_rate > 0.5 or regime_state == "COLLAPSE":
    defected[hardliner_mask] = True
```

### Output Interface

```python
def step(self, global_context) -> dict:
    return {
        "total_protesting": float,       # % of non-security agents active
        "student_participation": float,  # % of students active
        "merchant_participation": float, # % of merchants active
        "defection_rate": float,         # % of conscripts defected
        "coordination_score": float,     # Graph clustering metric
    }
```

### ABM → Macro Controller Feedback

| ABM Output | Macro Effect |
|------------|--------------|
| `total_protesting > 0.10` | `protest_state = ESCALATING` |
| `total_protesting < 0.02` | `protest_state = COLLAPSED` |
| `defection_rate > 0.30` | `defection_occurred = True`, triggers regime crisis |

---

## 6. Implementation Plan

### Design Decisions (Confirmed with User)

| Decision | Resolution |
|----------|------------|
| Defection macro threshold | 30% conscript defection triggers `state.defection_occurred` |
| Defection mechanics | Stochastic: 30%/day probability when conditions met |
| Post-defection behavior | Stay neutral (stop suppressing, don't join protests) |
| Student threshold modifier | Temporary -0.2 each step, reset from base when not escalating |
| Hardliner defection | When >50% conscripts defected OR explicit COLLAPSE |

### Initial Grievance Distributions

| Type | Distribution | Mean |
|------|-------------|------|
| Student | Beta(4, 2) | ~0.67 |
| Merchant | Beta(3, 3) | ~0.50 |
| Civilian | Beta(2, 3) | ~0.40 |
| Conscript | Beta(1, 4) | ~0.20 |
| Hardliner | Fixed 0.0 | 0.00 |

### Files to Modify

| File | Changes |
|------|---------|
| `src/abm_engine.py` | Complete rewrite with agent types, defection logic, new output interface |
| `src/simulation.py` | Add ABM integration (~50 lines), `--abm` CLI flag |

### Integration Code

```python
# In simulation.py._simulate_day()

if self.use_abm:
    abm_context = {
        "protest_state": state.protest_state.value.upper(),
        "regime_state": state.regime_state.value.upper(),
        "rial_rate": self._economic_data.get("rial_rate", 1_000_000),
        "crackdown_intensity": 0.8 if state.regime_state == RegimeState.CRACKDOWN else 0.2,
        "concessions_offered": state.regime_state == RegimeState.CONCESSIONS,
        "internet_blackout": state.regime_state == RegimeState.CRACKDOWN,
    }

    abm_result = self.abm.step(abm_context)

    # Map to macro state
    if abm_result["total_protesting"] > 0.10:
        state.protest_state = ProtestState.ESCALATING
    elif abm_result["total_protesting"] < 0.02:
        state.protest_state = ProtestState.COLLAPSED

    # Defection trigger
    if abm_result["defection_rate"] > 0.30 and not state.defection_occurred:
        state.defection_occurred = True
        state.regime_state = RegimeState.DEFECTION
```

### Emergent Cascade Path (Expected)

```
1. Economic crisis (Rial > 1.5M)
       ↓
2. Merchant grievance spikes (+0.3)
       ↓
3. Students activate early (threshold -0.2)
       ↓
4. Network effect → Merchants + Civilians join
       ↓
5. High density + crackdown → Conscripts overwhelmed
       ↓
6. Stochastic defection begins (30%/day)
       ↓
7. 30% defection → Macro DEFECTION event
       ↓
8. Regime crisis pathway activated
```

---

## 7. Questions for Reviewer

### Architecture Questions

1. **Network topology for security forces:** Should Conscripts/Hardliners share the same social network as civilians, or have a separate command structure network? Current plan: single network for simplicity.

2. **Defection contagion:** Should defected conscripts influence other conscripts to defect (spreading through security network)? Current plan: No, only civilian protest density triggers defection.

3. **Hardliner suppression effect:** Should active Hardliners *reduce* protest activity in their neighborhood (representing local suppression)? Not currently modeled.

### Parameter Calibration Questions

4. **Student threshold modifier (-0.2):** Is this too aggressive? With base threshold ~0.5, this gives effective threshold ~0.3, meaning students activate when grievance alone exceeds 0.3.

5. **Merchant economic sensitivity (+0.3):** Combined with Rial > 1.5M being common, this could cause merchants to hit grievance ceiling (1.0) quickly. Should this be lower?

6. **Defection probability (30%/day):** Given conditions are met, is 30% daily defection rate realistic? This means ~90% of eligible conscripts defect within a week of conditions being met.

### Validation Questions

7. **How do we validate emergent behavior?** The whole point is outcomes emerge rather than being coded. What does "correct" look like?

8. **Comparison with state machine:** Should ABM and state machine produce similar outcome distributions, or is divergence expected/desired?

### Risk Questions

9. **Runaway dynamics:** What prevents the simulation from always ending in collapse (students → merchants → civilians → defection → collapse)?

10. **Parameter sensitivity:** Which parameters are most likely to cause wildly different outcomes? Should we run sensitivity analysis before deployment?

---

## 8. Code Appendix

### A. Current Prototype (abm_engine.py) - To Be Replaced

```python
"""
Agent-Based Model Engine for Iran Crisis Simulation
====================================================

Minimal NumPy-vectorized ABM prototype for benchmarking.
Implements Granovetter threshold model with social network influence.
"""

import numpy as np
from scipy import sparse
from dataclasses import dataclass
from typing import Dict, Optional, Any
import time


@dataclass
class ABMConfig:
    """Configuration for ABM engine."""
    n_agents: int = 10_000
    seed: Optional[int] = None
    network_type: str = "small_world"
    avg_neighbors: int = 8
    rewire_prob: float = 0.1
    grievance_mean: float = 0.5
    grievance_std: float = 0.2
    threshold_low: float = 0.3
    threshold_high: float = 0.8
    neighbor_influence: float = 0.4
    economic_sensitivity: float = 0.02
    fear_effect_range: tuple = (-0.1, 0.05)
    concession_dampening: float = 0.95


class ABMEngine:
    """NumPy-vectorized Agent-Based Model for protest dynamics."""

    def __init__(self, config: Dict[str, Any] = None, intel: Dict[str, Any] = None):
        config = config or {}
        self.config = ABMConfig(**{k: v for k, v in config.items() if hasattr(ABMConfig, k)})
        self.rng = np.random.default_rng(self.config.seed)

        n = self.config.n_agents

        # Agent state arrays (CURRENT: homogeneous agents)
        self.grievance = self._init_grievance(intel)
        self.threshold = self.rng.uniform(
            self.config.threshold_low,
            self.config.threshold_high,
            n
        )
        self.active = np.zeros(n, dtype=bool)
        self.days_active = np.zeros(n, dtype=np.int32)
        self.province_id = self._assign_provinces(intel)

        # Social network
        self.neighbors = self._build_network()
        self.neighbor_counts = np.array(self.neighbors.sum(axis=1)).flatten()
        self.history = []

    def _build_small_world_network(self, n: int, k: int, p: float) -> sparse.csr_matrix:
        """Build Watts-Strogatz small-world network."""
        # Start with ring lattice
        adj = self._build_lattice_network(n, k)
        rows, cols = adj.nonzero()
        mask = self.rng.random(len(rows)) < p
        new_cols = cols.copy()
        for i in np.where(mask)[0]:
            new_target = self.rng.integers(0, n)
            while new_target == rows[i]:
                new_target = self.rng.integers(0, n)
            new_cols[i] = new_target
        data = np.ones(len(rows), dtype=np.float32)
        adj_rewired = sparse.csr_matrix((data, (rows, new_cols)), shape=(n, n))
        return (adj_rewired + adj_rewired.T).tocsr()

    def step(self, global_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute one time step (day) of agent dynamics."""
        cfg = self.config
        was_active = self.active.copy()

        # Update grievance
        self._update_grievance(global_context)

        # Neighbor influence
        neighbor_active_pct = self._compute_neighbor_influence(global_context)

        # Activation decision (Granovetter threshold)
        activation_signal = self.grievance + cfg.neighbor_influence * neighbor_active_pct
        self.active = activation_signal > self.threshold

        # Update counters
        self.days_active[self.active] += 1
        self.days_active[~self.active] = 0

        result = {
            "pct_protesting": float(self.active.mean()),
            "n_active": int(self.active.sum()),
            "coordination_score": self._compute_coordination(),
            "new_activations": int((self.active & ~was_active).sum()),
            "avg_grievance": float(self.grievance.mean()),
        }
        self.history.append(result)
        return result

    def _compute_neighbor_influence(self, ctx: Dict[str, Any]) -> np.ndarray:
        """Compute fraction of each agent's neighbors who are active."""
        active_float = self.active.astype(np.float32)
        neighbor_active_sum = np.array(self.neighbors @ active_float).flatten()
        neighbor_counts_safe = np.maximum(self.neighbor_counts, 1)
        neighbor_pct = neighbor_active_sum / neighbor_counts_safe

        # Internet blackout
        if ctx.get("internet_blackout", False):
            neighbor_pct *= 0.3

        return neighbor_pct

    def reset(self) -> None:
        """Reset agent state for new simulation run."""
        n = self.config.n_agents
        self.grievance = self.rng.beta(
            self.config.grievance_mean * 4,
            (1 - self.config.grievance_mean) * 4,
            n
        )
        self.threshold = self.rng.uniform(
            self.config.threshold_low,
            self.config.threshold_high,
            n
        )
        self.active = np.zeros(n, dtype=bool)
        self.days_active = np.zeros(n, dtype=np.int32)
        self.history = []
```

### B. Key simulation.py Excerpts (Integration Points)

```python
# simulation.py - SimulationState dataclass (lines 147-176)

@dataclass
class SimulationState:
    """Current state of a single simulation run"""
    day: int = 0
    regime_state: RegimeState = RegimeState.STATUS_QUO
    us_posture: USPosture = USPosture.RHETORICAL
    protest_state: ProtestState = ProtestState.STABLE

    escalation_start_day: Optional[int] = None
    crackdown_start_day: Optional[int] = None
    defection_day: Optional[int] = None
    collapse_day: Optional[int] = None

    defection_occurred: bool = False
    khamenei_dead: bool = False
    us_intervened: bool = False

    final_outcome: Optional[str] = None
    outcome_day: Optional[int] = None
    events: List[str] = field(default_factory=list)


# simulation.py - Main loop (lines 576-601)

def run_single(self) -> SimulationState:
    """Run a single simulation trajectory"""
    state = SimulationState()
    self.sampler.reset_cache()
    state.protester_casualties = self._get_initial_casualties()

    for day in range(1, 91):
        state.day = day
        if state.final_outcome:
            break
        self._simulate_day(state)

    if not state.final_outcome:
        state.final_outcome = self._determine_final_outcome(state)
        state.outcome_day = 90

    return state
```

---

## Summary

**What we're building:**
- Hybrid ABM with 10,000 heterogeneous agents (5 types)
- NumPy-vectorized for performance (60ms/run)
- Emergent cascade dynamics (students → merchants → civilians → defection)
- Clean integration with existing macro controller

**What we need from you:**
- Architecture review
- Parameter sanity check
- Risk identification
- Validation strategy suggestions

---

*End of briefing document*

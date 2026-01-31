# ABM Migration Feasibility Study & Prototype

**Project:** Iran Crisis Simulation
**Date:** January 17, 2026
**Prepared by:** Claude (Anthropic)
**Purpose:** Handoff document for continuing ABM architecture work

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current Architecture](#current-architecture)
3. [Migration Goal](#migration-goal)
4. [Feasibility Analysis](#feasibility-analysis)
5. [Prototype Implementation](#prototype-implementation)
6. [Benchmark Results](#benchmark-results)
7. [Recommended Architecture](#recommended-architecture)
8. [Code Appendix](#code-appendix)

---

## Executive Summary

We evaluated migrating an Iran crisis simulation from a **State Machine model** to an **Agent-Based Model (ABM)** with 5,000-10,000 agents. Key findings:

| Question | Answer |
|----------|--------|
| Can we decouple RegimeState from visualization? | ✅ Yes - loosely coupled via string keys |
| Can we hit <30s for 10K agents? | ✅ Yes - 60ms/run with NumPy (500 runs in 30s) |
| Do we have enough data for agent initialization? | ⚠️ Partial - province-level only, no demographic segments |
| Can we keep simulation.py as macro controller? | ✅ Yes - clean hybrid architecture possible |

**Recommendation:** Proceed with NumPy-vectorized ABM. Do NOT use Mesa Agent objects.

---

## Current Architecture

### Overview

The simulation models the 2025-2026 Iranian protest crisis over a 90-day horizon using Monte Carlo methods. It runs 10,000+ trajectories to produce outcome probability distributions.

### Key Files

```
iran_simulation/
├── src/
│   ├── simulation.py      # Main engine (1,350 lines) - STATE MACHINE
│   ├── visualize.py       # Charts and maps (344 lines)
│   ├── abm_engine.py      # NEW PROTOTYPE (created in this session)
│   └── priors/
│       └── contract.py    # Probability validation (216 lines)
├── data/
│   ├── iran_crisis_intel.json    # Intelligence data
│   └── analyst_priors.json       # Probability estimates
└── outputs/
    └── simulation_results.json   # Monte Carlo results
```

### Current State Machine (simulation.py)

The simulation uses discrete state enums:

```python
class RegimeState(Enum):
    STATUS_QUO = "status_quo"
    ESCALATING = "escalating"
    CRACKDOWN = "crackdown"
    CONCESSIONS = "concessions"
    DEFECTION = "defection"
    FRAGMENTATION = "fragmentation"
    COLLAPSE = "collapse"
    TRANSITION = "transition"
    SUPPRESSED = "suppressed"

class ProtestState(Enum):
    DECLINING = "declining"
    STABLE = "stable"
    ESCALATING = "escalating"
    ORGANIZED = "organized"
    COLLAPSED = "collapsed"
```

State transitions are governed by probability priors sampled from Beta-PERT distributions, with window probabilities converted to daily hazards.

### Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Research Agent  │────▶│ iran_crisis_     │────▶│                 │
│ (Deep Research) │     │ intel.json       │     │                 │
└─────────────────┘     └──────────────────┘     │   simulation.py │
                                                  │   (Monte Carlo) │
┌─────────────────┐     ┌──────────────────┐     │                 │
│ Security Analyst│────▶│ analyst_         │────▶│                 │
│ Agent           │     │ priors.json      │     └────────┬────────┘
└─────────────────┘     └──────────────────┘              │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │ simulation_     │
                                                 │ results.json    │
                                                 └────────┬────────┘
                                                          │
                                                          ▼
                                                 ┌─────────────────┐
                                                 │ visualize.py    │
                                                 │ (charts, maps)  │
                                                 └─────────────────┘
```

---

## Migration Goal

Replace the discrete `ProtestState` enum with emergent behavior from 10,000 individual agents, where:

- Each agent has: grievance level, activation threshold, social network connections
- Agents decide to protest based on: personal grievance + neighbor influence
- Macro outcomes emerge from micro-level agent interactions
- Global factors (economy, crackdown, internet) affect all agents

### Why ABM?

1. **Richer dynamics** - Protest intensity becomes continuous, not categorical
2. **Network effects** - Information cascades and coordination emerge naturally
3. **Heterogeneity** - Different demographic groups respond differently
4. **Geographic granularity** - Province-level variation in protest intensity

---

## Feasibility Analysis

### Question 1: State Decoupling (RegimeState → Visualization)

**Finding: LOW coupling - visualization uses string keys, not enum imports**

`visualize.py` receives simulation results as JSON with string keys:

```python
# visualize.py:49-54
colors = {
    "REGIME_SURVIVES_STATUS_QUO": "#2ecc71",
    "REGIME_COLLAPSE_CHAOTIC": "#e74c3c",
    ...
}
```

**Impact of replacing RegimeState with aggregate scores:**

| Component | Change Required | Effort |
|-----------|-----------------|--------|
| `create_outcome_chart()` | New chart type (histogram vs bars) | Medium |
| `create_iran_map()` | None (uses geographic data) | None |
| `create_sensitivity_chart()` | Update key names | Low |
| `create_scenario_narratives()` | Rewrite descriptions | Medium |

### Question 2: Performance Budget

**Finding: Mesa is TOO SLOW. NumPy vectorization REQUIRED.**

Performance comparison (theoretical + measured):

| Approach | 10K agents × 90 days | Time for 1000 MC runs |
|----------|---------------------|----------------------|
| Mesa (Python objects) | ~1-5 sec/run | 15-90 minutes |
| **NumPy vectorized** | **0.06 sec/run** | **~60 seconds** |

Mesa's bottleneck is Python method dispatch overhead:
```python
# Mesa - O(n) Python calls per step
for agent in self.schedule.agents:  # 10,000 iterations
    agent.step()  # Python method call overhead
```

NumPy eliminates this:
```python
# NumPy - single vectorized operation
self.active = (grievance + 0.4 * neighbor_pct) > threshold  # All 10K agents at once
```

### Question 3: Data Granularity for Agent Initialization

**Finding: INSUFFICIENT for demographic heterogeneity**

Current intel schema provides:

| Available | Missing |
|-----------|---------|
| Province population | Occupation distribution |
| Primary ethnicity | Income by demographic |
| Protest status (HIGH/MED/LOW) | Age distribution |
| Casualty counts | Urban/rural split |
| Rial exchange rate | Education levels |

**Workaround implemented:** Initialize agents from province-level data with added noise:
```python
def _init_grievance_from_provinces(self, provinces):
    status_map = {"HIGH": 0.7, "MEDIUM": 0.5, "LOW": 0.3}
    for prov in provinces:
        base = status_map[prov["current_protest_status"]]
        grievance[idx:idx+n] = np.random.normal(base, 0.15, n)
```

### Question 4: Hybrid Architecture Viability

**Finding: VIABLE and RECOMMENDED**

Keep `simulation.py` as macro controller for:
- Regime decision logic (crackdown vs concessions)
- US intervention escalation ladder
- Regional cascade (Iraq/Syria spillover)
- Khamenei succession scenarios

Add `abm_engine.py` for:
- Micro-level protest dynamics
- Agent activation/deactivation
- Network-based coordination

Interface between them:
```python
# simulation.py calls abm_engine.py
global_context = {"rial_rate": 1.5M, "crackdown_intensity": 0.6}
abm_result = self.abm.step(global_context)
# Returns: {"pct_protesting": 0.12, "coordination_score": 0.34}
```

---

## Prototype Implementation

### Design Decisions

1. **NumPy arrays for agent state** - Not Python objects
2. **SciPy sparse matrices for network** - CSR format for fast row slicing
3. **Granovetter threshold model** - Classic collective action framework
4. **Small-world network** - Watts-Strogatz topology for realistic clustering

### Core Data Structures

```python
# Agent state (all NumPy arrays of length n_agents)
self.grievance: np.ndarray[float]    # Personal grievance level [0,1]
self.threshold: np.ndarray[float]    # Activation threshold [0,1]
self.active: np.ndarray[bool]        # Currently protesting?
self.days_active: np.ndarray[int]    # Consecutive days active
self.province_id: np.ndarray[int]    # Province assignment

# Social network (sparse CSR matrix)
self.neighbors: scipy.sparse.csr_matrix  # Adjacency matrix (n × n)
```

### Activation Rule

Agent `i` becomes active if:

```
grievance[i] + λ × (fraction of active neighbors) > threshold[i]
```

Where `λ = 0.4` is the neighbor influence weight.

Vectorized implementation:
```python
neighbor_active_pct = (self.neighbors @ self.active.astype(float)) / neighbor_counts
activation_signal = self.grievance + 0.4 * neighbor_active_pct
self.active = activation_signal > self.threshold
```

### Global Context Effects

```python
def _update_grievance(self, ctx):
    # Economic effect
    if ctx["rial_rate"] > 1_200_000:
        self.grievance += 0.02 * (rial_rate - 1.2M) / 300K

    # Crackdown: fear vs radicalization
    if ctx["crackdown_intensity"] > 0.3:
        fear_effect = np.random.uniform(-0.1, 0.05, n_agents)
        self.grievance += fear_effect * crackdown

    # Concessions reduce grievance
    if ctx["concessions_offered"]:
        self.grievance *= 0.95
```

---

## Benchmark Results

### Test Configuration

- **Hardware:** MacBook (Apple Silicon assumed based on performance)
- **Python:** 3.x with NumPy + SciPy
- **Network:** Small-world (k=8 neighbors, p=0.1 rewire)

### Results

```
============================================================
ABM Engine Benchmark
============================================================
Agents: 10,000
Days per run: 90
Total runs: 1000
Total agent-steps: 900,000,000
============================================================

Initialization time: 0.019s
Total time: 59.10s
Mean run time: 0.0591s (±0.0030s)
Min/Max run time: 0.0542s / 0.0718s
Agent-steps/sec: 15,229,701
Mean final protest rate: 95.3%
============================================================

✅ EXCELLENT: Sub-second per run
```

### Scaling Analysis

| Agents | Time/Run | 100 runs | 500 runs | 1000 runs |
|--------|----------|----------|----------|-----------|
| 5,000 | 29.5ms | 3.0s | 14.8s | 29.5s |
| 10,000 | 59.1ms | 5.9s | 29.6s | 59.1s |

**Scaling factor:** 2.04x when doubling agents (near-linear, good)

### Performance vs Target

User's target: **<30 seconds per simulation batch**

| Configuration | Meets Target? |
|---------------|---------------|
| 10K agents × 500 runs | ✅ ~30s |
| 10K agents × 1000 runs | ⚠️ ~60s |
| 5K agents × 1000 runs | ✅ ~30s |

---

## Recommended Architecture

### Hybrid Design

```
┌─────────────────────────────────────────────────────────────┐
│                     simulation.py                            │
│                   (MACRO CONTROLLER)                         │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Regime      │  │ US Posture  │  │ Regional Cascade    │  │
│  │ Decisions   │  │ Ladder      │  │ (Iraq/Syria)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│         │                │                    │              │
│         └────────────────┼────────────────────┘              │
│                          │                                   │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │    Global Context     │                       │
│              │  - rial_rate          │                       │
│              │  - crackdown_intensity│                       │
│              │  - internet_blackout  │                       │
│              └───────────┬───────────┘                       │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     abm_engine.py                            │
│                   (MICRO DYNAMICS)                           │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  10,000 Agents (NumPy Arrays)                       │    │
│  │  - grievance[10000]                                 │    │
│  │  - threshold[10000]                                 │    │
│  │  - active[10000]                                    │    │
│  │  - province_id[10000]                               │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Social Network (Sparse Matrix)                     │    │
│  │  - Small-world topology                             │    │
│  │  - ~80,000 edges                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                          ▼                                   │
│              ┌───────────────────────┐                       │
│              │   Aggregate Results   │                       │
│              │  - pct_protesting     │                       │
│              │  - coordination_score │                       │
│              │  - regional_breakdown │                       │
│              └───────────────────────┘                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Integration Code (Pseudocode)

```python
# simulation.py modifications

class IranCrisisSimulation:
    def __init__(self, intel, priors, abm_config=None):
        self.intel = intel
        self.priors = priors

        # NEW: Initialize ABM if configured
        if abm_config:
            from abm_engine import ABMEngine
            self.abm = ABMEngine(abm_config, intel)
        else:
            self.abm = None

    def _simulate_day(self, state):
        # Build global context
        global_context = {
            "day": state.day,
            "rial_rate": self._get_rial_rate(),
            "crackdown_intensity": 0.8 if state.regime_state == RegimeState.CRACKDOWN else 0.0,
            "concessions_offered": state.regime_state == RegimeState.CONCESSIONS,
            "internet_blackout": state.day in range(30, 41),
        }

        # Use ABM for protest dynamics
        if self.abm:
            result = self.abm.step(global_context)

            # Map ABM output to macro state
            if result["pct_protesting"] > 0.10:
                state.protest_state = ProtestState.ESCALATING
            elif result["pct_protesting"] < 0.02:
                state.protest_state = ProtestState.COLLAPSED

            # Store for analysis
            state.protest_intensity = result["pct_protesting"]
        else:
            # Fallback to original state machine
            self._update_protest_state(state)

        # Continue with regime response logic (unchanged)
        self._check_regime_transitions(state)
        self._check_defection(state)
        self._update_us_posture(state)
```

---

## Code Appendix

### A. Complete abm_engine.py

```python
"""
Agent-Based Model Engine for Iran Crisis Simulation
====================================================

Minimal NumPy-vectorized ABM prototype for benchmarking.
Implements Granovetter threshold model with social network influence.

Usage:
    from abm_engine import ABMEngine

    engine = ABMEngine({"n_agents": 10000})
    for day in range(90):
        result = engine.step({"rial_rate": 1500000, "crackdown_intensity": 0.0})
        print(f"Day {day}: {result['pct_protesting']:.1%} protesting")

Benchmark:
    python -m src.abm_engine --benchmark
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

    # Network parameters
    network_type: str = "small_world"  # "small_world", "random", "lattice"
    avg_neighbors: int = 8
    rewire_prob: float = 0.1  # For small-world networks

    # Agent behavior parameters
    grievance_mean: float = 0.5
    grievance_std: float = 0.2
    threshold_low: float = 0.3
    threshold_high: float = 0.8

    # Influence weights
    neighbor_influence: float = 0.4
    economic_sensitivity: float = 0.02
    fear_effect_range: tuple = (-0.1, 0.05)
    concession_dampening: float = 0.95


class ABMEngine:
    """
    NumPy-vectorized Agent-Based Model for protest dynamics.

    Agent state is stored in NumPy arrays for O(1) batch operations.
    Social network is stored as sparse matrix for efficient neighbor queries.
    """

    def __init__(self, config: Dict[str, Any] = None, intel: Dict[str, Any] = None):
        """
        Initialize ABM engine.

        Args:
            config: Configuration dict (converted to ABMConfig)
            intel: Intel data for province-based initialization (optional)
        """
        config = config or {}
        self.config = ABMConfig(**{k: v for k, v in config.items() if hasattr(ABMConfig, k)})
        self.rng = np.random.default_rng(self.config.seed)

        n = self.config.n_agents

        # Agent state arrays (core state - vectorized)
        self.grievance = self._init_grievance(intel)
        self.threshold = self.rng.uniform(
            self.config.threshold_low,
            self.config.threshold_high,
            n
        )
        self.active = np.zeros(n, dtype=bool)
        self.days_active = np.zeros(n, dtype=np.int32)

        # Province assignment (for regional breakdown)
        self.province_id = self._assign_provinces(intel)

        # Social network (sparse CSR matrix for fast row slicing)
        self.neighbors = self._build_network()
        self.neighbor_counts = np.array(self.neighbors.sum(axis=1)).flatten()

        # Track history for analysis
        self.history = []

    def _init_grievance(self, intel: Optional[Dict]) -> np.ndarray:
        """Initialize grievance from intel or use default distribution."""
        n = self.config.n_agents

        if intel and "geographic_data" in intel:
            provinces = intel["geographic_data"].get("provinces", [])
            if provinces:
                return self._init_grievance_from_provinces(provinces)

        # Default: Beta distribution centered around mean
        alpha = self.config.grievance_mean * 4
        beta = (1 - self.config.grievance_mean) * 4
        return self.rng.beta(alpha, beta, n)

    def _init_grievance_from_provinces(self, provinces: list) -> np.ndarray:
        """Initialize grievance based on province-level protest status."""
        n = self.config.n_agents
        grievance = np.zeros(n)

        # Map protest status to base grievance
        status_map = {"HIGH": 0.7, "MEDIUM": 0.5, "LOW": 0.3, None: 0.4}

        # Calculate total population for proportional assignment
        total_pop = sum(p.get("population_millions", 1.0) for p in provinces)

        idx = 0
        for prov in provinces:
            pop_share = prov.get("population_millions", 1.0) / total_pop
            n_prov = max(1, int(pop_share * n))

            # Don't exceed array bounds
            n_prov = min(n_prov, n - idx)
            if n_prov <= 0:
                break

            status = prov.get("current_protest_status")
            base = status_map.get(status, 0.4)

            grievance[idx:idx+n_prov] = self.rng.normal(base, 0.15, n_prov)
            idx += n_prov

        # Fill any remaining with default
        if idx < n:
            grievance[idx:] = self.rng.normal(0.4, 0.15, n - idx)

        return np.clip(grievance, 0, 1)

    def _assign_provinces(self, intel: Optional[Dict]) -> np.ndarray:
        """Assign agents to provinces based on population."""
        n = self.config.n_agents

        if not intel or "geographic_data" not in intel:
            # Default: single province
            return np.zeros(n, dtype=np.int32)

        provinces = intel["geographic_data"].get("provinces", [])
        if not provinces:
            return np.zeros(n, dtype=np.int32)

        total_pop = sum(p.get("population_millions", 1.0) for p in provinces)
        province_ids = np.zeros(n, dtype=np.int32)

        idx = 0
        for i, prov in enumerate(provinces):
            pop_share = prov.get("population_millions", 1.0) / total_pop
            n_prov = max(1, int(pop_share * n))
            n_prov = min(n_prov, n - idx)
            if n_prov <= 0:
                break
            province_ids[idx:idx+n_prov] = i
            idx += n_prov

        return province_ids

    def _build_network(self) -> sparse.csr_matrix:
        """Build social network as sparse adjacency matrix."""
        n = self.config.n_agents
        k = self.config.avg_neighbors

        if self.config.network_type == "random":
            return self._build_random_network(n, k)
        elif self.config.network_type == "lattice":
            return self._build_lattice_network(n, k)
        else:  # small_world (default)
            return self._build_small_world_network(n, k, self.config.rewire_prob)

    def _build_random_network(self, n: int, k: int) -> sparse.csr_matrix:
        """Build Erdos-Renyi random network."""
        p = k / n
        # Generate random edges
        rows = []
        cols = []
        for i in range(n):
            # Sample ~k neighbors
            neighbors = self.rng.choice(n, size=k, replace=False)
            neighbors = neighbors[neighbors != i]  # No self-loops
            rows.extend([i] * len(neighbors))
            cols.extend(neighbors)

        data = np.ones(len(rows), dtype=np.float32)
        adj = sparse.csr_matrix((data, (rows, cols)), shape=(n, n))
        # Make symmetric
        return (adj + adj.T).tocsr()

    def _build_lattice_network(self, n: int, k: int) -> sparse.csr_matrix:
        """Build 1D ring lattice with k nearest neighbors."""
        rows = []
        cols = []
        half_k = k // 2

        for i in range(n):
            for j in range(1, half_k + 1):
                # Connect to neighbors on each side
                rows.extend([i, i])
                cols.extend([(i + j) % n, (i - j) % n])

        data = np.ones(len(rows), dtype=np.float32)
        return sparse.csr_matrix((data, (rows, cols)), shape=(n, n))

    def _build_small_world_network(self, n: int, k: int, p: float) -> sparse.csr_matrix:
        """Build Watts-Strogatz small-world network."""
        # Start with ring lattice
        adj = self._build_lattice_network(n, k)

        # Rewire edges with probability p
        rows, cols = adj.nonzero()
        mask = self.rng.random(len(rows)) < p

        # For edges to rewire, pick new random targets
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
        """
        Execute one time step (day) of agent dynamics.

        Args:
            global_context: Dict with global state variables:
                - rial_rate: Currency exchange rate (higher = worse economy)
                - crackdown_intensity: 0-1 scale of regime violence
                - concessions_offered: bool, whether regime made concessions
                - internet_blackout: bool, reduces coordination

        Returns:
            Dict with aggregate metrics:
                - pct_protesting: Fraction of agents currently active
                - coordination_score: Measure of spatial clustering
                - regional_breakdown: Activity by province
                - new_activations: Agents who just joined
                - deactivations: Agents who stopped
        """
        n = self.config.n_agents
        cfg = self.config

        # Store previous state for delta computation
        was_active = self.active.copy()

        # 1. Update grievance based on global factors
        self._update_grievance(global_context)

        # 2. Compute neighbor influence (vectorized sparse matrix operation)
        neighbor_active_pct = self._compute_neighbor_influence(global_context)

        # 3. Activation decision (Granovetter threshold model)
        activation_signal = self.grievance + cfg.neighbor_influence * neighbor_active_pct
        self.active = activation_signal > self.threshold

        # 4. Update days active counter
        self.days_active[self.active] += 1
        self.days_active[~self.active] = 0

        # 5. Compute aggregates
        result = {
            "pct_protesting": float(self.active.mean()),
            "n_active": int(self.active.sum()),
            "coordination_score": self._compute_coordination(),
            "regional_breakdown": self._compute_regional_activity(),
            "new_activations": int((self.active & ~was_active).sum()),
            "deactivations": int((~self.active & was_active).sum()),
            "avg_grievance": float(self.grievance.mean()),
        }

        self.history.append(result)
        return result

    def _update_grievance(self, ctx: Dict[str, Any]) -> None:
        """Update agent grievance based on global context."""
        cfg = self.config

        # Economic effect: high Rial rate increases grievance
        rial_rate = ctx.get("rial_rate", 1_000_000)
        if rial_rate > 1_200_000:
            economic_anger = cfg.economic_sensitivity * (rial_rate - 1_200_000) / 300_000
            self.grievance += economic_anger

        # Crackdown effect: fear vs radicalization
        crackdown = ctx.get("crackdown_intensity", 0.0)
        if crackdown > 0.3:
            # Some agents scared, some radicalized
            fear_effect = self.rng.uniform(
                cfg.fear_effect_range[0],
                cfg.fear_effect_range[1],
                self.config.n_agents
            )
            self.grievance += fear_effect * crackdown

        # Concessions reduce grievance
        if ctx.get("concessions_offered", False):
            self.grievance *= cfg.concession_dampening

        # Clamp to [0, 1]
        np.clip(self.grievance, 0, 1, out=self.grievance)

    def _compute_neighbor_influence(self, ctx: Dict[str, Any]) -> np.ndarray:
        """Compute fraction of each agent's neighbors who are active."""
        # Sparse matrix-vector multiply: adj @ active_vec
        active_float = self.active.astype(np.float32)
        neighbor_active_sum = np.array(self.neighbors @ active_float).flatten()

        # Normalize by number of neighbors (avoid div by zero)
        neighbor_counts_safe = np.maximum(self.neighbor_counts, 1)
        neighbor_pct = neighbor_active_sum / neighbor_counts_safe

        # Internet blackout reduces coordination (information flow)
        if ctx.get("internet_blackout", False):
            neighbor_pct *= 0.3  # 70% reduction in influence

        return neighbor_pct

    def _compute_coordination(self) -> float:
        """Measure coordination as clustering of active agents."""
        n_active = self.active.sum()
        if n_active < 2:
            return 0.0

        # Count edges between active agents
        active_mask = self.active
        active_subgraph = self.neighbors[active_mask][:, active_mask]
        n_edges = active_subgraph.sum() / 2  # Undirected

        # Normalize by maximum possible edges
        max_edges = n_active * (n_active - 1) / 2
        if max_edges == 0:
            return 0.0

        return float(n_edges / max_edges)

    def _compute_regional_activity(self) -> Dict[int, float]:
        """Compute protest activity rate by province."""
        unique_provinces = np.unique(self.province_id)
        return {
            int(p): float(self.active[self.province_id == p].mean())
            for p in unique_provinces
        }

    def reset(self) -> None:
        """Reset agent state for new simulation run."""
        n = self.config.n_agents

        # Re-randomize grievance and thresholds
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


def benchmark(n_agents: int = 10_000, n_days: int = 90, n_runs: int = 100) -> Dict[str, float]:
    """
    Benchmark ABM engine performance.

    Args:
        n_agents: Number of agents
        n_days: Days per simulation
        n_runs: Number of simulation runs

    Returns:
        Dict with timing statistics
    """
    print(f"\n{'='*60}")
    print(f"ABM Engine Benchmark")
    print(f"{'='*60}")
    print(f"Agents: {n_agents:,}")
    print(f"Days per run: {n_days}")
    print(f"Total runs: {n_runs}")
    print(f"Total agent-steps: {n_agents * n_days * n_runs:,}")
    print(f"{'='*60}\n")

    # Initialize engine once (measure init time separately)
    init_start = time.perf_counter()
    engine = ABMEngine({"n_agents": n_agents, "seed": 42})
    init_time = time.perf_counter() - init_start
    print(f"Initialization time: {init_time:.3f}s")

    # Sample global context progression
    contexts = []
    for day in range(n_days):
        ctx = {
            "rial_rate": 1_000_000 + day * 10_000,
            "crackdown_intensity": 0.2 if day < 30 else 0.6,
            "concessions_offered": day > 60,
            "internet_blackout": 30 <= day <= 40,
        }
        contexts.append(ctx)

    # Run benchmark
    run_times = []
    final_pcts = []

    for run in range(n_runs):
        engine.reset()

        run_start = time.perf_counter()
        for day in range(n_days):
            result = engine.step(contexts[day])
        run_time = time.perf_counter() - run_start

        run_times.append(run_time)
        final_pcts.append(result["pct_protesting"])

        if (run + 1) % 20 == 0:
            print(f"  Completed {run + 1}/{n_runs} runs...")

    # Compute statistics
    run_times = np.array(run_times)
    total_time = run_times.sum()
    mean_time = run_times.mean()
    std_time = run_times.std()

    agent_steps_per_sec = (n_agents * n_days) / mean_time

    results = {
        "n_agents": n_agents,
        "n_days": n_days,
        "n_runs": n_runs,
        "init_time_sec": init_time,
        "total_time_sec": total_time,
        "mean_run_time_sec": mean_time,
        "std_run_time_sec": std_time,
        "min_run_time_sec": run_times.min(),
        "max_run_time_sec": run_times.max(),
        "agent_steps_per_sec": agent_steps_per_sec,
        "mean_final_pct_protesting": np.mean(final_pcts),
    }

    print(f"\n{'='*60}")
    print("Results:")
    print(f"{'='*60}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Mean run time: {mean_time:.4f}s (±{std_time:.4f}s)")
    print(f"Min/Max run time: {run_times.min():.4f}s / {run_times.max():.4f}s")
    print(f"Agent-steps/sec: {agent_steps_per_sec:,.0f}")
    print(f"Mean final protest rate: {np.mean(final_pcts):.1%}")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ABM Engine Benchmark")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark")
    parser.add_argument("--agents", type=int, default=10_000, help="Number of agents")
    parser.add_argument("--days", type=int, default=90, help="Days per simulation")
    parser.add_argument("--runs", type=int, default=100, help="Number of runs")
    parser.add_argument("--compare", action="store_true", help="Compare 5K vs 10K agents")

    args = parser.parse_args()

    if args.compare:
        print("\n" + "="*60)
        print("COMPARISON: 5,000 vs 10,000 agents")
        print("="*60)

        results_5k = benchmark(n_agents=5_000, n_days=90, n_runs=50)
        results_10k = benchmark(n_agents=10_000, n_days=90, n_runs=50)

        print("\n" + "="*60)
        print("SUMMARY")
        print("="*60)
        print(f"5K agents: {results_5k['mean_run_time_sec']:.4f}s/run")
        print(f"10K agents: {results_10k['mean_run_time_sec']:.4f}s/run")
        print(f"Scaling factor: {results_10k['mean_run_time_sec']/results_5k['mean_run_time_sec']:.2f}x")

    elif args.benchmark:
        benchmark(n_agents=args.agents, n_days=args.days, n_runs=args.runs)

    else:
        # Demo run
        print("Running demo simulation...")
        engine = ABMEngine({"n_agents": 1000, "seed": 42})

        for day in range(10):
            ctx = {
                "rial_rate": 1_200_000 + day * 50_000,
                "crackdown_intensity": 0.1 * day,
            }
            result = engine.step(ctx)
            print(f"Day {day+1}: {result['pct_protesting']:.1%} protesting, "
                  f"coordination={result['coordination_score']:.3f}")
```

### B. Key Excerpts from simulation.py (Current State Machine)

```python
# simulation.py - State definitions (lines 38-91)

class RegimeState(Enum):
    STATUS_QUO = "status_quo"
    ESCALATING = "escalating"
    CRACKDOWN = "crackdown"
    CONCESSIONS = "concessions"
    DEFECTION = "defection"
    FRAGMENTATION = "fragmentation"
    COLLAPSE = "collapse"
    TRANSITION = "transition"
    SUPPRESSED = "suppressed"

class ProtestState(Enum):
    DECLINING = "declining"
    STABLE = "stable"
    ESCALATING = "escalating"
    ORGANIZED = "organized"
    COLLAPSED = "collapsed"

# simulation.py - Main simulation loop (lines 576-601)

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

### C. visualize.py Outcome Mapping (Current)

```python
# visualize.py - Color mapping for outcomes (lines 49-55)

colors = {
    "REGIME_SURVIVES_STATUS_QUO": "#2ecc71",
    "REGIME_SURVIVES_WITH_CONCESSIONS": "#27ae60",
    "MANAGED_TRANSITION": "#3498db",
    "REGIME_COLLAPSE_CHAOTIC": "#e74c3c",
    "ETHNIC_FRAGMENTATION": "#9b59b6"
}
```

---

## Next Steps for Gemini

1. **Review the hybrid architecture** - Is the macro/micro split clean enough?

2. **Consider network topology** - Small-world is a good default, but scale-free (Barabási-Albert) might better model social media influence

3. **Add demographic heterogeneity** - The prototype treats all agents identically except for province. Consider adding:
   - Occupation-based grievance modifiers
   - Age-based threshold distributions
   - Urban/rural network density differences

4. **Calibrate parameters** - The current values (λ=0.4, threshold=[0.3, 0.8]) are placeholders. Need empirical calibration from protest literature.

5. **Integrate with simulation.py** - The pseudocode in section 7 shows the interface, but actual integration requires:
   - Adding `abm_config` parameter to CLI
   - Modifying `_simulate_day()` to call ABM
   - Updating output schema to include ABM metrics

6. **Extend visualization** - Create new charts for:
   - Time series of `pct_protesting` (continuous curve)
   - Network visualization of coordination clusters
   - Provincial heatmaps from `regional_breakdown`

---

## Questions for Continuation

1. Should the ABM also model security forces as agents, or keep them as aggregate probability?

2. How should the network evolve over time? (e.g., new connections during protests, broken connections during blackouts)

3. What validation data exists for calibrating agent parameters?

4. Should we implement multiple agent "types" (student, merchant, worker) with different parameters?

---

*End of handoff document*

"""
Agent-Based Model Engine for Iran Crisis Simulation
====================================================

Project Swarm: Hybrid ABM with 10,000 heterogeneous agents ("The Core 4" + Civilians).

Agent Types:
    - STUDENT (15%): The Spark - low threshold when escalating
    - MERCHANT (20%): The Fuel - graduated economic sensitivity
    - CONSCRIPT (10%): Security - can defect via contagion
    - HARDLINER (5%): Security - loyal firebreak, suppresses neighbors
    - CIVILIAN (50%): The Mass - standard threshold + exhaustion

Emergent Cascade Path:
    1. Economic crisis -> Merchant grievance ramps gradually
    2. Students activate early (threshold -0.2)
    3. Network effect spreads to Merchants -> Civilians
    4. Hardliner suppression creates "cold spots"
    5. Exhaustion creates waves (not monotonic explosion)
    6. High density + crackdown OR 4/8 neighbor defection -> Conscripts defect
    7. 30% defection -> Macro defection event triggers regime crisis

Design Philosophy (V1):
    - Regime survival is the BASE CASE (authoritarian robustness)
    - Collapse requires a PERFECT STORM
    - Start "hard" and loosen later based on calibration

Usage:
    from abm_engine import ABMEngine

    engine = ABMEngine({"n_agents": 10000})
    for day in range(90):
        result = engine.step({
            "protest_state": "ESCALATING",
            "rial_rate": 1500000,
            "crackdown_intensity": 0.6,
        })
        print(f"Day {day}: {result['total_protesting']:.1%} protesting")

Benchmark:
    python -m src.abm_engine --benchmark
"""

import numpy as np
from scipy import sparse
from dataclasses import dataclass
from typing import Dict, Optional, Any, List
import time


# ============================================================================
# AGENT TYPE CONSTANTS
# ============================================================================

STUDENT = 0      # 15% - The Spark
MERCHANT = 1     # 20% - The Fuel
CONSCRIPT = 2    # 10% - Security (can defect)
HARDLINER = 3    # 5%  - Security (loyal)
CIVILIAN = 4     # 50% - The Mass

AGENT_TYPE_NAMES = {
    STUDENT: "student",
    MERCHANT: "merchant",
    CONSCRIPT: "conscript",
    HARDLINER: "hardliner",
    CIVILIAN: "civilian",
}

# Agent type distribution (must sum to 1.0)
AGENT_TYPE_DISTRIBUTION = {
    STUDENT: 0.15,
    MERCHANT: 0.20,
    CONSCRIPT: 0.10,
    HARDLINER: 0.05,
    CIVILIAN: 0.50,
}


# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class ABMConfig:
    """Configuration for ABM engine."""
    n_agents: int = 10_000
    seed: Optional[int] = None

    # Network parameters
    network_type: str = "small_world"  # "small_world", "random", "lattice"
    avg_neighbors: int = 8
    rewire_prob: float = 0.1  # For small-world networks

    # Threshold parameters
    threshold_low: float = 0.3
    threshold_high: float = 0.8

    # Influence weights
    neighbor_influence: float = 0.4

    # Student behavior
    student_threshold_reduction: float = 0.2  # When escalating

    # Merchant behavior
    merchant_economic_scale: float = 0.3  # Max grievance increase at 2M Rial
    merchant_concession_reduction: float = 0.5  # Grievance multiplier on concessions

    # Conscript defection parameters
    defection_base_prob: float = 0.3  # 30% daily when eligible
    defection_overwhelmed_threshold: float = 0.5  # >50% neighbors active
    defection_moral_injury_threshold: float = 0.6  # crackdown intensity
    defection_contagion_threshold: float = 0.4  # >40% neighbor conscripts defected (Gemini V2: raised from 0.3)

    # Hardliner effects (Gemini additions)
    hardliner_fear_bonus: float = 0.2  # Defection resistance for conscripts near hardliners
    hardliner_suppression_effect: float = 0.1  # Threshold increase for neighbors of hardliners
    hardliner_mass_defection_threshold: float = 0.5  # 50% conscript defection triggers hardliner defection

    # Exhaustion (Gemini addition)
    exhaustion_threshold_days: int = 7  # Days active before exhaustion kicks in
    exhaustion_grievance_decay: float = 0.05  # Daily grievance reduction when exhausted

    # Macro defection threshold
    macro_defection_threshold: float = 0.30  # 30% conscript defection = macro event


# ============================================================================
# ABM ENGINE
# ============================================================================

class ABMEngine:
    """
    NumPy-vectorized Agent-Based Model for protest dynamics.

    Agent state is stored in NumPy arrays for O(1) batch operations.
    Social network is stored as sparse matrix for efficient neighbor queries.

    Implements "The Core 4" agent types with heterogeneous behavior:
    - Students: Low threshold during escalation
    - Merchants: Economic sensitivity with graduated scale
    - Conscripts: Can defect under pressure or contagion
    - Hardliners: Suppress neighbors, resist defection
    - Civilians: Standard threshold model with exhaustion
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

        # Initialize agent types first (needed for grievance initialization)
        self.agent_type = self._init_agent_types()

        # Agent state arrays
        self.grievance = self._init_grievance_by_type()
        self.base_threshold = self.rng.uniform(
            self.config.threshold_low,
            self.config.threshold_high,
            n
        )
        self.threshold = self.base_threshold.copy()  # Effective threshold (modified each step)
        self.active = np.zeros(n, dtype=bool)
        self.defected = np.zeros(n, dtype=bool)
        self.days_active = np.zeros(n, dtype=np.int32)

        # Province assignment (for regional breakdown)
        self.province_id = self._assign_provinces(intel)

        # Social network (sparse CSR matrix for fast row slicing)
        self.neighbors = self._build_network()
        self.neighbor_counts = np.array(self.neighbors.sum(axis=1)).flatten()

        # Track history for analysis
        self.history: List[Dict[str, Any]] = []

    def _init_agent_types(self) -> np.ndarray:
        """Initialize agent type distribution.

        Distribution:
        - Students: 15%
        - Merchants: 20%
        - Conscripts: 10%
        - Hardliners: 5%
        - Civilians: 50%

        Returns:
            Array of agent type IDs, shuffled for uniform distribution in network.
        """
        n = self.config.n_agents
        types = np.empty(n, dtype=np.int8)
        idx = 0

        for type_id, pct in AGENT_TYPE_DISTRIBUTION.items():
            count = int(n * pct)
            # Handle rounding for last type
            if type_id == CIVILIAN:
                count = n - idx
            types[idx:idx + count] = type_id
            idx += count

        # Uniform distribution: "Dispersed wet blanket" abstraction (Gemini V2)
        self.rng.shuffle(types)
        return types

    def _init_grievance_by_type(self) -> np.ndarray:
        """Initialize grievance using type-specific Beta distributions.

        Initial Grievance by Agent Type:
        - Students: Beta(4, 2) -> mean ~0.67 (idealistic, frustrated)
        - Merchants: Beta(3, 3) -> mean ~0.50 (variable, depends on business)
        - Civilians: Beta(2, 3) -> mean ~0.40 (cautious majority)
        - Conscripts: Beta(1, 4) -> mean ~0.20 (institutional loyalty)
        - Hardliners: Fixed 0.0 (true believers)
        """
        n = self.config.n_agents
        grievance = np.zeros(n, dtype=np.float32)

        # Beta distribution parameters for each type
        beta_params = {
            STUDENT: (4.0, 2.0),    # mean ~0.67
            MERCHANT: (3.0, 3.0),   # mean ~0.50
            CIVILIAN: (2.0, 3.0),   # mean ~0.40
            CONSCRIPT: (1.0, 4.0),  # mean ~0.20
            HARDLINER: None,        # Fixed 0.0
        }

        for type_id, params in beta_params.items():
            mask = self.agent_type == type_id
            if params is None:
                # Hardliners: fixed 0.0
                grievance[mask] = 0.0
            else:
                alpha, beta = params
                grievance[mask] = self.rng.beta(alpha, beta, mask.sum())

        return grievance

    def _assign_provinces(self, intel: Optional[Dict]) -> np.ndarray:
        """Assign agents to provinces based on population."""
        n = self.config.n_agents

        if not intel or "geographic_data" not in intel:
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
            province_ids[idx:idx + n_prov] = i
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
        rows = []
        cols = []
        for i in range(n):
            neighbors = self.rng.choice(n, size=k, replace=False)
            neighbors = neighbors[neighbors != i]
            rows.extend([i] * len(neighbors))
            cols.extend(neighbors)

        data = np.ones(len(rows), dtype=np.float32)
        adj = sparse.csr_matrix((data, (rows, cols)), shape=(n, n))
        return (adj + adj.T).tocsr()

    def _build_lattice_network(self, n: int, k: int) -> sparse.csr_matrix:
        """Build 1D ring lattice with k nearest neighbors."""
        rows = []
        cols = []
        half_k = k // 2

        for i in range(n):
            for j in range(1, half_k + 1):
                rows.extend([i, i])
                cols.extend([(i + j) % n, (i - j) % n])

        data = np.ones(len(rows), dtype=np.float32)
        return sparse.csr_matrix((data, (rows, cols)), shape=(n, n))

    def _build_small_world_network(self, n: int, k: int, p: float) -> sparse.csr_matrix:
        """Build Watts-Strogatz small-world network."""
        if k % 2 != 0:
            k += 1
        half_k = k // 2

        rows = []
        cols = []

        for i in range(n):
            for j in range(1, half_k + 1):
                target = (i + j) % n
                if self.rng.random() < p:
                    new_target = self.rng.integers(0, n)
                    while new_target == i or new_target == target:
                        new_target = self.rng.integers(0, n)
                    target = new_target
                rows.append(i)
                cols.append(target)

        data = np.ones(len(rows), dtype=np.float32)
        adj = sparse.csr_matrix((data, (rows, cols)), shape=(n, n))
        return (adj + adj.T).tocsr()

    def step(self, global_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute one time step (day) of agent dynamics.

        Gemini V2 Ruling: Exhaustion applies BEFORE activation decision.

        Args:
            global_context: Dict with global state variables:
                - protest_state: "STABLE", "ESCALATING", "COLLAPSED"
                - regime_state: "STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "COLLAPSE"
                - rial_rate: Currency exchange rate (higher = worse economy)
                - crackdown_intensity: 0-1 scale of regime violence
                - concessions_offered: bool, whether regime made concessions
                - internet_blackout: bool, reduces coordination

        Returns:
            Dict with aggregate metrics for simulation.py integration
        """
        n = self.config.n_agents
        cfg = self.config
        ctx = global_context

        # Store previous state for delta computation
        was_active = self.active.copy()

        # =====================================================================
        # PHASE 1: EXHAUSTION (Gemini V2: Apply BEFORE activation)
        # =====================================================================
        # Real people can't protest forever - creates realistic "waves"
        exhausted_mask = self.days_active > cfg.exhaustion_threshold_days
        self.grievance[exhausted_mask] -= cfg.exhaustion_grievance_decay
        np.clip(self.grievance, 0, 1, out=self.grievance)

        # =====================================================================
        # PHASE 2: UPDATE GRIEVANCE (Type-specific effects)
        # =====================================================================

        # --- Merchant Economic Sensitivity (Non-accumulating) ---
        merchant_mask = self.agent_type == MERCHANT
        rial_rate = ctx.get("rial_rate", 1_000_000)
        # Economic boost applied to activation_signal in Phase 5, not here

        # Merchant exit on concessions (50% reduction, not cliff)
        if ctx.get("concessions_offered", False):
            self.grievance[merchant_mask] *= cfg.merchant_concession_reduction

        # --- Hardliner grievance lock ---
        hardliner_mask = self.agent_type == HARDLINER
        self.grievance[hardliner_mask] = 0.0

        # Clamp grievance
        np.clip(self.grievance, 0, 1, out=self.grievance)

        # =====================================================================
        # PHASE 3: COMPUTE EFFECTIVE THRESHOLDS
        # =====================================================================

        # Start from base threshold
        effective_threshold = self.base_threshold.copy()

        # --- Student threshold reduction when escalating ---
        student_mask = self.agent_type == STUDENT
        if ctx.get("protest_state", "").upper() == "ESCALATING":
            effective_threshold[student_mask] -= cfg.student_threshold_reduction

        # --- Hardliner Suppression Effect (Gemini Addition) ---
        # Agents connected to Hardliner get +0.1 threshold (scared to protest)
        # Gemini V2: Suppression affects THRESHOLD, not signal
        hardliner_float = hardliner_mask.astype(np.float32)
        has_hardliner_neighbor = np.array(self.neighbors @ hardliner_float).flatten() > 0
        effective_threshold[has_hardliner_neighbor] += cfg.hardliner_suppression_effect

        # =====================================================================
        # PHASE 4: COMPUTE NEIGHBOR INFLUENCE
        # =====================================================================

        active_float = self.active.astype(np.float32)
        neighbor_active_sum = np.array(self.neighbors @ active_float).flatten()
        neighbor_counts_safe = np.maximum(self.neighbor_counts, 1)
        neighbor_active_pct = neighbor_active_sum / neighbor_counts_safe

        # Internet blackout reduces coordination
        if ctx.get("internet_blackout", False):
            neighbor_active_pct *= 0.3

        # =====================================================================
        # PHASE 5: ACTIVATION DECISION (Granovetter threshold model)
        # =====================================================================

        # Economic pressure for merchants (non-accumulating)
        economic_boost = np.zeros(n, dtype=np.float32)
        if rial_rate > 1_000_000:
            economic_boost[merchant_mask] = cfg.merchant_economic_scale * (rial_rate - 1_000_000) / 1_000_000

        activation_signal = self.grievance + cfg.neighbor_influence * neighbor_active_pct + economic_boost
        self.active = activation_signal > effective_threshold

        # Security forces NEVER protest
        security_mask = (self.agent_type == CONSCRIPT) | (self.agent_type == HARDLINER)
        self.active[security_mask] = False

        # =====================================================================
        # PHASE 6: CONSCRIPT DEFECTION LOGIC (+ Gemini: Contagion & Fear Bonus)
        # =====================================================================

        conscript_mask = (self.agent_type == CONSCRIPT) & ~self.defected
        crackdown = ctx.get("crackdown_intensity", 0)

        # Compute neighbor defection rate for each conscript
        defected_float = self.defected.astype(np.float32)
        neighbor_defected_sum = np.array(self.neighbors @ defected_float).flatten()
        neighbor_defection_pct = neighbor_defected_sum / neighbor_counts_safe

        # Hardliner "Fear Bonus" - conscripts near hardliners resist defection
        fear_bonus = np.where(has_hardliner_neighbor, cfg.hardliner_fear_bonus, 0.0)

        # Defection conditions (either triggers eligibility):
        # 1. Overwhelmed by crowd + moral injury from crackdown
        overwhelmed = neighbor_active_pct > cfg.defection_overwhelmed_threshold
        moral_injury = crackdown > cfg.defection_moral_injury_threshold
        condition_1 = overwhelmed & moral_injury

        # 2. Defection contagion - "safety in mutiny" (Gemini V2: raised to 0.4)
        # Requires 4/8 neighbors, not 3/8
        condition_2 = neighbor_defection_pct > cfg.defection_contagion_threshold

        defection_eligible = conscript_mask & (condition_1 | condition_2)

        # Stochastic defection (30% daily, reduced by fear_bonus)
        effective_defection_prob = np.maximum(0, cfg.defection_base_prob - fear_bonus)
        defection_roll = self.rng.random(n) < effective_defection_prob
        self.defected[defection_eligible & defection_roll] = True

        # =====================================================================
        # PHASE 7: HARDLINER DEFECTION (Only on mass conscript defection or collapse)
        # =====================================================================

        total_conscripts = (self.agent_type == CONSCRIPT).sum()
        defected_conscripts = self.defected[self.agent_type == CONSCRIPT].sum()
        conscript_defection_rate = defected_conscripts / max(total_conscripts, 1)

        if (ctx.get("regime_state", "").upper() == "COLLAPSE" or
                conscript_defection_rate > cfg.hardliner_mass_defection_threshold):
            self.defected[hardliner_mask] = True

        # =====================================================================
        # PHASE 8: UPDATE COUNTERS
        # =====================================================================

        self.days_active[self.active] += 1
        self.days_active[~self.active] = 0

        # =====================================================================
        # PHASE 9: COMPUTE METRICS
        # =====================================================================

        # Civilian protesters (exclude security forces)
        civilian_protesters_mask = ~security_mask

        result = {
            # Primary metrics for simulation.py integration
            "total_protesting": float(self.active[civilian_protesters_mask].mean()),
            "defection_rate": float(self.defected[self.agent_type == CONSCRIPT].mean()),
            "coordination_score": self._compute_coordination(),

            # Type-specific breakdown
            "student_participation": float(self.active[self.agent_type == STUDENT].mean()),
            "merchant_participation": float(self.active[self.agent_type == MERCHANT].mean()),
            "civilian_participation": float(self.active[self.agent_type == CIVILIAN].mean()),
            "hardliner_defection": float(self.defected[self.agent_type == HARDLINER].mean()),

            # Extended metrics for debugging
            "avg_grievance": float(self.grievance.mean()),
            "avg_threshold": float(effective_threshold.mean()),
            "n_active": int(self.active.sum()),
            "n_defected": int(self.defected.sum()),
            "new_activations": int((self.active & ~was_active).sum()),
            "deactivations": int((~self.active & was_active).sum()),
            "churn_rate": float((self.active & ~was_active).sum() + (~self.active & was_active).sum()) / n,

            # Regional breakdown
            "regional_breakdown": self._compute_regional_activity(),
        }

        self.history.append(result)
        return result

    def _compute_coordination(self) -> float:
        """Measure coordination as clustering of active agents."""
        n_active = self.active.sum()
        if n_active < 2:
            return 0.0

        active_mask = self.active
        active_subgraph = self.neighbors[active_mask][:, active_mask]
        n_edges = active_subgraph.sum() / 2

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
        """Reset agent state for new simulation run (Monte Carlo support)."""
        n = self.config.n_agents

        # Re-initialize grievance by type (preserves type distribution)
        self.grievance = self._init_grievance_by_type()

        # Re-randomize thresholds
        self.base_threshold = self.rng.uniform(
            self.config.threshold_low,
            self.config.threshold_high,
            n
        )
        self.threshold = self.base_threshold.copy()

        # Reset state
        self.active = np.zeros(n, dtype=bool)
        self.defected = np.zeros(n, dtype=bool)
        self.days_active = np.zeros(n, dtype=np.int32)
        self.history = []

    def get_snapshot(self) -> Dict[str, Any]:
        """
        Return full state arrays for debugging (Gemini V2 Requirement).

        Use this when aggregate metrics don't explain behavior.
        Example: "Why did everyone go home on Day 12?"
        - If grievance histogram shows low values -> Exhaustion
        - If threshold histogram shows high values -> Suppression

        Returns:
            Dict containing:
            - Full arrays (grievance, threshold, active, defected, etc.)
            - Histograms for quick analysis
            - Per-type breakdown
        """
        # Commissar metric
        hardliner_vec = (self.agent_type == HARDLINER).astype(np.float32)
        has_commissar = np.array(self.neighbors @ hardliner_vec).flatten() > 0

        return {
            "grievance": self.grievance.copy(),
            "threshold": self.base_threshold.copy(),
            "active": self.active.copy(),
            "defected": self.defected.copy(),
            "days_active": self.days_active.copy(),
            "agent_type": self.agent_type.copy(),
            "grievance_histogram": {
                "bins": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
                "counts": [
                    int(((self.grievance >= lo) & (self.grievance < hi)).sum())
                    for lo, hi in [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
                ]
            },
            "by_type": {
                "student": {
                    "count": int((self.agent_type == STUDENT).sum()),
                    "active_pct": float(self.active[self.agent_type == STUDENT].mean()) if (self.agent_type == STUDENT).any() else 0.0,
                    "avg_grievance": float(self.grievance[self.agent_type == STUDENT].mean()) if (self.agent_type == STUDENT).any() else 0.0,
                },
                "merchant": {
                    "count": int((self.agent_type == MERCHANT).sum()),
                    "active_pct": float(self.active[self.agent_type == MERCHANT].mean()) if (self.agent_type == MERCHANT).any() else 0.0,
                    "avg_grievance": float(self.grievance[self.agent_type == MERCHANT].mean()) if (self.agent_type == MERCHANT).any() else 0.0,
                },
                "civilian": {
                    "count": int((self.agent_type == CIVILIAN).sum()),
                    "active_pct": float(self.active[self.agent_type == CIVILIAN].mean()) if (self.agent_type == CIVILIAN).any() else 0.0,
                    "avg_grievance": float(self.grievance[self.agent_type == CIVILIAN].mean()) if (self.agent_type == CIVILIAN).any() else 0.0,
                },
                "conscript": {
                    "count": int((self.agent_type == CONSCRIPT).sum()),
                    "defected_pct": float(self.defected[self.agent_type == CONSCRIPT].mean()) if (self.agent_type == CONSCRIPT).any() else 0.0,
                },
                "hardliner": {
                    "count": int((self.agent_type == HARDLINER).sum()),
                    "defected_pct": float(self.defected[self.agent_type == HARDLINER].mean()) if (self.agent_type == HARDLINER).any() else 0.0,
                },
            },
            "debug_metrics": {
                "conscripts_under_surveillance": int((has_commissar & (self.agent_type == CONSCRIPT)).sum())
            }
        }


# ============================================================================
# BENCHMARK
# ============================================================================

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
    print(f"ABM Engine Benchmark (Project Swarm V1)")
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

    # Verify agent type distribution
    type_counts = {AGENT_TYPE_NAMES[t]: int((engine.agent_type == t).sum())
                   for t in AGENT_TYPE_NAMES}
    print(f"Agent types: {type_counts}")

    # Sample global context progression
    contexts = []
    for day in range(n_days):
        ctx = {
            "protest_state": "ESCALATING" if day > 5 else "STABLE",
            "regime_state": "CRACKDOWN" if day > 30 else "STATUS_QUO",
            "rial_rate": 1_000_000 + day * 15_000,  # Gradual economic decline
            "crackdown_intensity": 0.2 if day < 30 else 0.7,
            "concessions_offered": day > 60,
            "internet_blackout": 30 <= day <= 40,
        }
        contexts.append(ctx)

    # Run benchmark
    run_times = []
    final_metrics = []

    for run in range(n_runs):
        engine.reset()

        run_start = time.perf_counter()
        for day in range(n_days):
            result = engine.step(contexts[day])
        run_time = time.perf_counter() - run_start

        run_times.append(run_time)
        final_metrics.append({
            "total_protesting": result["total_protesting"],
            "defection_rate": result["defection_rate"],
        })

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
        "min_run_time_sec": float(run_times.min()),
        "max_run_time_sec": float(run_times.max()),
        "agent_steps_per_sec": agent_steps_per_sec,
        "mean_final_protesting": float(np.mean([m["total_protesting"] for m in final_metrics])),
        "mean_final_defection": float(np.mean([m["defection_rate"] for m in final_metrics])),
    }

    print(f"\n{'='*60}")
    print("Results:")
    print(f"{'='*60}")
    print(f"Total time: {total_time:.2f}s")
    print(f"Mean run time: {mean_time:.4f}s (+/-{std_time:.4f}s)")
    print(f"Min/Max run time: {run_times.min():.4f}s / {run_times.max():.4f}s")
    print(f"Agent-steps/sec: {agent_steps_per_sec:,.0f}")
    print(f"Mean final protest rate: {results['mean_final_protesting']:.1%}")
    print(f"Mean final defection rate: {results['mean_final_defection']:.1%}")
    print(f"{'='*60}\n")

    # Performance assessment
    if mean_time < 1.0:
        print("EXCELLENT: Sub-second per run - can do 1000+ Monte Carlo runs in <30s")
    elif mean_time < 5.0:
        print("GOOD: Can do ~100 Monte Carlo runs in <30s")
    elif mean_time < 30.0:
        print("ACCEPTABLE: Under target but consider optimization for large MC runs")
    else:
        print("TOO SLOW: Exceeds 30s target - need further optimization")

    return results


def verify_agent_types():
    """Quick verification of agent type distribution."""
    print("\n" + "="*60)
    print("Agent Type Distribution Verification")
    print("="*60)

    engine = ABMEngine({"n_agents": 10_000, "seed": 42})

    expected = {
        STUDENT: 1500,
        MERCHANT: 2000,
        CONSCRIPT: 1000,
        HARDLINER: 500,
        CIVILIAN: 5000,
    }

    for type_id, expected_count in expected.items():
        actual = (engine.agent_type == type_id).sum()
        name = AGENT_TYPE_NAMES[type_id]
        status = "OK" if actual == expected_count else "MISMATCH"
        print(f"  {name:12s}: {actual:5d} (expected {expected_count:5d}) [{status}]")

    print("\nInitial Grievance by Type:")
    for type_id in AGENT_TYPE_NAMES:
        mask = engine.agent_type == type_id
        if mask.any():
            mean_g = engine.grievance[mask].mean()
            name = AGENT_TYPE_NAMES[type_id]
            print(f"  {name:12s}: mean={mean_g:.3f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ABM Engine Benchmark (Project Swarm)")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark")
    parser.add_argument("--verify", action="store_true", help="Verify agent type distribution")
    parser.add_argument("--agents", type=int, default=10_000, help="Number of agents")
    parser.add_argument("--days", type=int, default=90, help="Days per simulation")
    parser.add_argument("--runs", type=int, default=100, help="Number of runs")

    args = parser.parse_args()

    if args.verify:
        verify_agent_types()
    elif args.benchmark:
        benchmark(n_agents=args.agents, n_days=args.days, n_runs=args.runs)
    else:
        # Demo run
        print("Running demo simulation...")
        engine = ABMEngine({"n_agents": 1000, "seed": 42})

        verify_agent_types()

        print("\nDemo Simulation (10 days):")
        for day in range(10):
            ctx = {
                "protest_state": "ESCALATING" if day > 2 else "STABLE",
                "rial_rate": 1_200_000 + day * 50_000,
                "crackdown_intensity": 0.1 * day,
            }
            result = engine.step(ctx)
            print(f"Day {day+1}: {result['total_protesting']:.1%} protesting, "
                  f"defection={result['defection_rate']:.1%}, "
                  f"coord={result['coordination_score']:.3f}")

        # Show snapshot
        print("\nSnapshot:")
        snap = engine.get_snapshot()
        print(f"  Grievance histogram: {snap['grievance_histogram']['counts']}")
        for t, data in snap['by_type'].items():
            print(f"  {t}: {data}")

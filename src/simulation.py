"""
Iran Crisis Monte Carlo Simulation Engine
==========================================

This simulation models the evolution of the Iran crisis over a 90-day horizon,
using probability estimates from the Security Analyst Agent and structural data
from the Research Agent.

Usage:
    python simulation.py --intel data/iran_crisis_intel.json --priors data/analyst_priors.json --runs 10000

Outputs:
    - outputs/outcome_distribution.json
    - outputs/outcome_distribution.png
    - outputs/sensitivity_analysis.json
    - outputs/scenario_narratives.md
"""

import json
import math
import random
import argparse
import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from enum import Enum
from collections import Counter
import statistics

# Local priors contract resolver (time-basis semantics + QA)
from priors.contract import resolve_priors


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

class RegimeState(Enum):
    STATUS_QUO = "status_quo"                    # Protests ongoing, regime holding
    ESCALATING = "escalating"                     # Protests intensifying
    CRACKDOWN = "crackdown"                       # Mass violence by regime
    CONCESSIONS = "concessions"                   # Regime offers meaningful concessions
    DEFECTION = "defection"                       # Security force defection occurring
    FRAGMENTATION = "fragmentation"               # Ethnic regions breaking away
    COLLAPSE = "collapse"                         # Regime collapse
    TRANSITION = "transition"                     # Managed succession
    SUPPRESSED = "suppressed"                     # Protests crushed, regime stable


class EconomicStress(Enum):
    """Economic stress levels based on Rial exchange rate and inflation.

    Thresholds (configurable via analyst_priors.json):
    - STABLE: Rial < 800k IRR/USD, inflation < 30%
    - PRESSURED: Rial 800k-1.2M IRR/USD, inflation 30-50%
    - CRITICAL: Rial > 1.2M IRR/USD OR inflation > 50%
    """
    STABLE = "stable"           # Normal economic stress
    PRESSURED = "pressured"     # Elevated economic stress
    CRITICAL = "critical"       # Severe economic stress


class USPosture(Enum):
    RHETORICAL = "rhetorical"                     # Statements only
    INFORMATION_OPS = "information_ops"           # Starlink, cyber support
    ECONOMIC = "economic"                         # Sanctions escalation
    COVERT = "covert"                             # Material support to opposition
    CYBER_OFFENSIVE = "cyber_offensive"           # Offensive cyber ops
    KINETIC = "kinetic"                           # Military strikes
    GROUND = "ground"                             # Ground intervention


# Explicit ordering for escalation-ladder logic.
# NOTE: Do NOT compare Enum.value strings lexicographically.
US_POSTURE_LEVEL = {
    USPosture.RHETORICAL: 0,
    USPosture.INFORMATION_OPS: 1,
    USPosture.ECONOMIC: 2,
    USPosture.COVERT: 3,
    USPosture.CYBER_OFFENSIVE: 4,
    USPosture.KINETIC: 5,
    USPosture.GROUND: 6,
}

# Intervention tiers for downstream weighting.
# NOTE: CYBER_OFFENSIVE is classified as *soft* (deniable, no physical footprint)
# even though it sits at level 4 on the escalation ladder — above COVERT (level 3).
# The tier split is about diplomatic visibility, not escalation rank.
US_SOFT_POSTURES = {USPosture.INFORMATION_OPS, USPosture.ECONOMIC, USPosture.CYBER_OFFENSIVE}
US_HARD_POSTURES = {USPosture.COVERT, USPosture.KINETIC, USPosture.GROUND}

# Modest impact for soft measures; stronger impact for hard measures
US_SOFT_INTERVENTION_MODIFIERS = {
    "protest_escalation": 1.07,
    "security_defection": 1.05,
    "regime_collapse": 1.05,
}
US_HARD_INTERVENTION_MODIFIERS = {
    "protest_escalation": 1.20,
    "security_defection": 1.15,
    "regime_collapse": 1.20,
}

class ProtestState(Enum):
    DECLINING = "declining"
    STABLE = "stable"
    ESCALATING = "escalating"
    ORGANIZED = "organized"                       # Developed leadership/coordination
    COLLAPSED = "collapsed"


# ============================================================================
# REGIONAL CASCADE STATE DEFINITIONS
# ============================================================================

class CountryStability(Enum):
    """Stability state for secondary countries (Iraq, Syria)"""
    STABLE = "stable"           # Business as usual
    STRESSED = "stressed"       # Elevated tensions, minor unrest
    CRISIS = "crisis"           # Active instability, conflict
    COLLAPSE = "collapse"       # State failure, power vacuum


class IsraelPosture(Enum):
    """Israel's posture toward Iran during crisis"""
    MONITORING = "monitoring"           # Watching developments
    STRIKES = "strikes"                 # Conducting targeted strikes
    MAJOR_OPERATION = "major_operation" # Major military campaign


class RussiaPosture(Enum):
    """Russia's posture toward Iran during crisis"""
    OBSERVING = "observing"       # Diplomatic support only
    SUPPORTING = "supporting"     # Material aid, advisors
    INTERVENING = "intervening"   # Direct military involvement


# Ordering for external actor escalation
ISRAEL_POSTURE_LEVEL = {
    IsraelPosture.MONITORING: 0,
    IsraelPosture.STRIKES: 1,
    IsraelPosture.MAJOR_OPERATION: 2,
}

RUSSIA_POSTURE_LEVEL = {
    RussiaPosture.OBSERVING: 0,
    RussiaPosture.SUPPORTING: 1,
    RussiaPosture.INTERVENING: 2,
}


# ============================================================================
# SIMULATION STATE
# ============================================================================

@dataclass
class RegionalState:
    """State of a secondary country in the regional system (Iraq or Syria)"""
    country: str = ""
    stability: CountryStability = CountryStability.STABLE
    proxy_activated: bool = False       # Iranian proxies attacking US/Israel
    crisis_start_day: Optional[int] = None
    events: List[str] = field(default_factory=list)

@dataclass
class SimulationState:
    """Current state of a single simulation run - includes regional cascade"""
    day: int = 0
    regime_state: RegimeState = RegimeState.STATUS_QUO
    us_posture: USPosture = USPosture.RHETORICAL
    protest_state: ProtestState = ProtestState.STABLE

    # When did special phases start? (None if not started)
    escalation_start_day: Optional[int] = None
    crackdown_start_day: Optional[int] = None
    concessions_start_day: Optional[int] = None
    defection_day: Optional[int] = None
    ethnic_uprising_day: Optional[int] = None
    khamenei_death_day: Optional[int] = None
    collapse_day: Optional[int] = None

    # Cumulative trackers
    protester_casualties: int = 0
    security_force_casualties: int = 0
    defection_occurred: bool = False
    khamenei_dead: bool = False
    ethnic_uprising: bool = False
    us_soft_intervened: bool = False
    us_hard_intervened: bool = False

    # Outcome
    final_outcome: Optional[str] = None
    outcome_day: Optional[int] = None

    # Event log
    events: List[str] = field(default_factory=list)

    # -------------------------------------------------------------------------
    # REGIONAL CASCADE STATE
    # -------------------------------------------------------------------------

    # Secondary country states
    iraq: RegionalState = field(default_factory=lambda: RegionalState(country="Iraq"))
    syria: RegionalState = field(default_factory=lambda: RegionalState(country="Syria"))

    # External actor postures
    israel_posture: IsraelPosture = IsraelPosture.MONITORING
    russia_posture: RussiaPosture = RussiaPosture.OBSERVING
    gulf_realignment: bool = False

    # Regional anchor days
    us_kinetic_day: Optional[int] = None      # When US goes kinetic (for proxy activation)
    israel_strike_day: Optional[int] = None   # When Israel begins strikes


# ============================================================================
# PROBABILITY SAMPLER
# ============================================================================

class ProbabilitySampler:
    """
    Samples from probability distributions defined in analyst priors.
    Supports:
      - beta_pert (preferred for probabilities)
      - triangular (legacy)
      - fixed (degenerate)

    Also supports converting window probabilities ("p within T days") into a
    per-day hazard that yields the same window probability under a constant-hazard
    assumption.
    """
    
    def __init__(self, priors: dict):
        self.priors = priors
        # Cache sampled parameters per simulation run so we don't re-sample a "probability of a probability"
        self._cache: Dict[str, float] = {}

    def reset_cache(self) -> None:
        """Reset parameter cache at the start of each simulation run."""
        self._cache.clear()

    def sample(self, category: str, key: str) -> float:
        """Sample a window probability from the specified prior.

        Values are cached per run so repeated calls during a single trajectory are stable.
        """
        cache_key = f"{category}.{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        prob_data = self._get_probability(category, key)

        # Back-compat: older priors use {low, point, high}
        low = prob_data.get("low")
        mode = prob_data.get("mode", prob_data.get("point"))
        high = prob_data.get("high")

        if low is None or mode is None or high is None:
            raise ValueError(f"Malformed probability prior for {category}.{key}: {prob_data}")

        dist = (prob_data.get("dist") or prob_data.get("distribution") or "triangular").lower()
        if dist == "beta_pert":
            lam = float(prob_data.get("lambda", 4.0))
            sampled = self._sample_beta_pert(low=low, mode=mode, high=high, lam=lam)
        elif dist == "fixed":
            sampled = float(mode)
        else:
            # Legacy/default
            sampled = random.triangular(low, high, mode)

        sampled = max(0.0, min(1.0, float(sampled)))
        self._cache[cache_key] = sampled
        return sampled

    def sample_daily(self, category: str, key: str, default_window_days: int) -> float:
        """Sample per-day probability implied by a window probability."""
        prob_data = self._get_probability(category, key)
        window_days = int(prob_data.get("window_days", default_window_days))
        p_window = self.sample(category, key)
        return self._window_prob_to_daily(p_window=p_window, window_days=window_days)

    @staticmethod
    def _window_prob_to_daily(p_window: float, window_days: int) -> float:
        """
        Convert P(event within T days) into constant-hazard daily probability.

        Uses numerically stable computation via log1p/expm1 for p_window near 1.

        Formula:
            p_daily = 1 - (1 - p_window)^(1/window_days)
                    = -expm1(log1p(-p_window) / window_days)
        """
        if window_days <= 0:
            raise ValueError("window_days must be positive")

        # Clamp to [0, 1]
        p_window = min(max(p_window, 0.0), 1.0)

        if p_window >= 1.0:
            return 1.0
        if p_window <= 0.0:
            return 0.0

        # Numerically stable computation
        # p_daily = 1 - exp(log(1 - p_window) / window_days)
        #         = -expm1(log1p(-p_window) / window_days)
        p_daily = -math.expm1(math.log1p(-p_window) / window_days)

        # Clamp output to [0, 1] for safety
        return min(max(p_daily, 0.0), 1.0)

    @staticmethod
    def _sample_beta_pert(low: float, mode: float, high: float, lam: float = 4.0) -> float:
        """Sample from a Beta-PERT distribution on [low, high] with mode."""
        if high <= low:
            return float(low)
        mode = min(max(mode, low), high)
        # Standard PERT uses lambda=4.
        alpha = 1.0 + lam * (mode - low) / (high - low)
        beta = 1.0 + lam * (high - mode) / (high - low)
        x = random.betavariate(alpha, beta)
        return low + x * (high - low)

    def sample_dirichlet_regime_outcomes(self) -> Dict[str, float]:
        """Sample a coherent regime outcome simplex using a Dirichlet draw.

        This is optional: the current simulation transitions are still the primary
        outcome generator. This method exists for calibration experiments and
        consistency checks.
        """
        outcomes = [
            "REGIME_SURVIVES_STATUS_QUO",
            "REGIME_SURVIVES_WITH_CONCESSIONS",
            "MANAGED_TRANSITION",
            "REGIME_COLLAPSE_CHAOTIC",
            "ETHNIC_FRAGMENTATION",
        ]
        ro = self.priors.get("regime_outcomes", {})
        sampling_cfg = ro.get("sampling", {}) if isinstance(ro, dict) else {}
        alpha_map = sampling_cfg.get("alpha")
        if isinstance(alpha_map, dict) and all(k in alpha_map for k in outcomes):
            alphas = [max(float(alpha_map[k]), 1e-6) for k in outcomes]
        else:
            # Derive alphas from point estimates and a concentration scalar.
            concentration = float(sampling_cfg.get("concentration", 30.0))
            points = []
            for k in outcomes:
                p = self._get_probability("regime_outcomes", k).get("point")
                if p is None:
                    p = self._get_probability("regime_outcomes", k).get("mode")
                points.append(float(p))
            s = sum(points) or 1.0
            points = [p / s for p in points]
            alphas = [max(p * concentration, 1e-6) for p in points]

        draws = [random.gammavariate(a, 1.0) for a in alphas]
        total = sum(draws) or 1.0
        return {k: d / total for k, d in zip(outcomes, draws)}
    
    def _get_probability(self, category: str, key: str) -> dict:
        """Navigate the priors structure to get probability dict"""
        if category == "regime_outcomes":
            return self.priors["regime_outcomes"][key]["probability"]
        elif category == "transition":
            return self.priors["transition_probabilities"][key]["probability"]
        elif category == "us_intervention":
            return self.priors["us_intervention_probabilities"][key]["probability"]
        elif category == "regional":
            return self.priors["regional_cascade_probabilities"][key]["probability"]
        else:
            raise ValueError(f"Unknown category: {category}")


# ============================================================================
# SIMULATION ENGINE
# ============================================================================


def _first_not_none(*vals):
    """Return the first non-None value, or None if all are None."""
    for v in vals:
        if v is not None:
            return v
    return None


class IranCrisisSimulation:
    """
    Monte Carlo simulation of Iran crisis scenarios.

    The simulation runs day-by-day for 90 days, with state transitions
    governed by the probability priors from the Security Analyst Agent.

    When use_abm=True, protest dynamics are driven by the Agent-Based Model
    (Project Swarm) instead of the state machine.
    """

    def __init__(self, intel: dict, priors: dict, use_abm: bool = False, seed: Optional[int] = None):
        self.intel = intel
        self.sampler = ProbabilitySampler(priors)
        self.priors = priors
        # Cache economic stress level (computed once from intel)
        self._economic_stress: Optional[EconomicStress] = None
        self._economic_data: Dict[str, float] = {}

        # ABM integration (Project Swarm)
        self.use_abm = use_abm
        self.abm = None
        if use_abm:
            # Handle both running as module (python -m src.simulation) and script (python src/simulation.py)
            try:
                from src.abm_engine import ABMEngine
            except ImportError:
                import sys
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from abm_engine import ABMEngine
            # Pass CLI seed for reproducibility; None means non-deterministic
            self.abm = ABMEngine({"n_agents": 10_000, "seed": seed}, intel)

    # ----------------------------------------------------------------------
    # Economic State Machine
    # ----------------------------------------------------------------------

    def _get_economic_stress(self) -> EconomicStress:
        """Determine economic stress level from intel data.

        Uses thresholds from priors if available, otherwise defaults:
        - STABLE: Rial < 800k, inflation < 30%
        - PRESSURED: Rial 800k-1.2M, inflation 30-50%
        - CRITICAL: Rial > 1.2M OR inflation > 50%

        Returns:
            EconomicStress enum value
        """
        if self._economic_stress is not None:
            return self._economic_stress

        # Get thresholds from priors — gate validates these exist before simulation
        thresholds = self.priors.get("economic_thresholds")
        if not isinstance(thresholds, dict):
            raise ValueError("analyst_priors.json missing 'economic_thresholds'")
        try:
            rial_critical = int(thresholds["rial_critical_threshold"])
            rial_pressured = int(thresholds["rial_pressured_threshold"])
            inflation_critical = float(thresholds["inflation_critical_threshold"])
            inflation_pressured = float(thresholds["inflation_pressured_threshold"])
        except KeyError as e:
            raise ValueError(f"analyst_priors.json economic_thresholds missing {e.args[0]}") from e

        # Extract economic data from intel — no fabrication, raise on missing
        econ = self.intel.get("current_state", {}).get("economic_conditions")
        if not isinstance(econ, dict):
            raise ValueError("missing economic_conditions in intel current_state")

        rial_data = econ.get("rial_usd_rate")
        if not isinstance(rial_data, dict):
            raise ValueError("missing rial_usd_rate in intel economic_conditions")
        rial_rate = _first_not_none(rial_data.get("market"), rial_data.get("mid"), rial_data.get("value"))
        if rial_rate is None:
            raise ValueError("missing rial_usd_rate value — market/mid/value all None")

        inflation_data = econ.get("inflation")
        if not isinstance(inflation_data, dict):
            raise ValueError("missing inflation in intel economic_conditions")
        inflation = _first_not_none(
            inflation_data.get("official_annual_percent"),
            inflation_data.get("mid"),
            inflation_data.get("value"),
        )
        if inflation is None:
            raise ValueError("missing inflation value — official_annual_percent/mid/value all None")

        rial_rate_f = float(rial_rate)
        inflation_f = float(inflation)
        self._economic_data = {"rial_rate": rial_rate_f, "inflation": inflation_f}

        # Classify stress level
        if rial_rate_f > rial_critical or inflation_f > inflation_critical:
            self._economic_stress = EconomicStress.CRITICAL
        elif rial_rate_f > rial_pressured or inflation_f > inflation_pressured:
            self._economic_stress = EconomicStress.PRESSURED
        else:
            self._economic_stress = EconomicStress.STABLE

        return self._economic_stress

    def _get_economic_modifier(self, event_type: str) -> float:
        """Get the probability multiplier for an event type based on economic stress.

        Reads multipliers from priors if available, otherwise uses defaults:
        - CRITICAL: +20% protest escalation, +30% elite fracture, +15% defection
        - PRESSURED: +10% protest escalation, +15% elite fracture, +8% defection

        Args:
            event_type: One of "protest_escalation", "elite_fracture", "security_defection"

        Returns:
            Probability multiplier (1.0 = no change)
        """
        stress = self._get_economic_stress()

        # Get multipliers from priors — pre-simulation validation should ensure these exist
        multipliers = self.priors.get("economic_modifiers")
        if not multipliers:
            raise ValueError(
                "analyst_priors.json missing 'economic_modifiers'. "
                "Run the pre-simulation economic validator first."
            )

        if stress == EconomicStress.STABLE:
            return 1.0

        prefix = "critical" if stress == EconomicStress.CRITICAL else "pressured"
        key = f"{prefix}_{event_type}_multiplier"
        value = multipliers.get(key)
        if value is None:
            raise ValueError(
                f"analyst_priors.json economic_modifiers missing '{key}'. "
                "All required multiplier keys must be present."
            )
        return float(value)

    def _apply_economic_modifiers(self, base_prob: float, event_type: str) -> float:
        """Adjust probability based on economic stress level.

        Args:
            base_prob: Base probability to adjust
            event_type: Type of event for modifier lookup

        Returns:
            Adjusted probability (capped at 0.95)
        """
        modifier = self._get_economic_modifier(event_type)
        return min(0.95, base_prob * modifier)

    def _apply_us_intervention_modifiers(
        self,
        base_prob: float,
        state: SimulationState,
        event_type: str
    ) -> float:
        """Adjust probability based on US intervention tier.

        Soft interventions (info ops, economic escalation, cyber) apply a modest lift.
        Hard interventions (covert, kinetic, ground) apply a stronger lift.
        """
        modifier = 1.0
        # Hard intentionally supersedes soft (elif, not additive). A state that
        # has escalated to kinetic/ground already subsumes softer measures.
        if state.us_hard_intervened:
            modifier = US_HARD_INTERVENTION_MODIFIERS.get(event_type, 1.0)
        elif state.us_soft_intervened:
            modifier = US_SOFT_INTERVENTION_MODIFIERS.get(event_type, 1.0)

        return min(0.95, base_prob * modifier)

    # ----------------------------------------------------------------------
    # Time-basis helpers (P3 semantics)
    # ----------------------------------------------------------------------

    @staticmethod
    def _anchor_day_from_state(state: SimulationState, anchor: str) -> Optional[int]:
        """Resolve an anchor label to a concrete simulation day."""
        if anchor == "t0":
            return 1
        if anchor == "t0_plus_30":
            return 31
        if anchor == "escalation_start":
            return state.escalation_start_day
        if anchor == "crackdown_start":
            return state.crackdown_start_day
        if anchor == "concessions_start":
            return state.concessions_start_day
        if anchor == "defection_day":
            return state.defection_day
        if anchor == "ethnic_uprising_day":
            return state.ethnic_uprising_day
        if anchor == "khamenei_death_day":
            return state.khamenei_death_day
        if anchor == "collapse_day":
            return state.collapse_day
        # Regional cascade anchors
        if anchor == "us_kinetic_day":
            return state.us_kinetic_day
        if anchor == "israel_strike_day":
            return state.israel_strike_day
        return None

    @classmethod
    def _window_active(cls, state: SimulationState, prob_obj: dict) -> bool:
        """Return True if current day is inside the (anchor + offset ... + window) interval."""
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

    def _daily_hazard_from_window_prob(self, category: str, key: str) -> float:
        """Sample P(event within window_days) once per run and convert to a constant daily hazard."""
        prob_obj = self.sampler._get_probability(category, key)
        wd = int(prob_obj.get("window_days", 0) or 0)
        if wd <= 0:
            raise ValueError(f"window_days missing/invalid for {category}.{key}")
        p_window = self.sampler.sample(category, key)
        return self._window_prob_to_daily_hazard(p_window, wd)

    @staticmethod
    def _protests_active_for_30d_condition(state: SimulationState) -> bool:
        """Interpret 'protests persist' as not collapsed AND not declining."""
        return state.protest_state in (ProtestState.STABLE, ProtestState.ESCALATING)

    @staticmethod
    def _window_prob_to_daily_hazard(p_window: float, window_days: int) -> float:
        """Backward-compatible wrapper for window->daily conversion."""
        return ProbabilitySampler._window_prob_to_daily(p_window=p_window, window_days=window_days)

    @staticmethod
    def _posture_lt(a: USPosture, b: USPosture) -> bool:
        """Return True if posture a is less escalatory than posture b."""
        return US_POSTURE_LEVEL[a] < US_POSTURE_LEVEL[b]

    @staticmethod
    def _posture_gt(a: USPosture, b: USPosture) -> bool:
        """Return True if posture a is more escalatory than posture b."""
        return US_POSTURE_LEVEL[a] > US_POSTURE_LEVEL[b]

    def run_single(self) -> SimulationState:
        """Run a single simulation trajectory"""
        state = SimulationState()

        # Sample each parameter once per trajectory (prevents re-drawing priors every day)
        self.sampler.reset_cache()

        # Reset ABM for new trajectory (Monte Carlo support)
        if self.use_abm and self.abm is not None:
            self.abm.reset()

        # Initialize economic data for ABM context
        self._get_economic_stress()

        # Initialize from current intel
        state.protester_casualties = self._get_initial_casualties()

        for day in range(1, 91):
            state.day = day
            
            # Check for terminal states
            if state.final_outcome:
                break
            
            # Daily state transitions
            self._simulate_day(state)
        
        # If no terminal state reached, determine outcome
        if not state.final_outcome:
            state.final_outcome = self._determine_final_outcome(state)
            state.outcome_day = 90
            
        return state
    
    def _simulate_day(self, state: SimulationState):
        """Simulate a single day's state transitions."""

        # 1. Khamenei death (independent event; daily hazard implied by window probability)
        if not state.khamenei_dead:
            daily_death_prob = self.sampler.sample_daily("transition", "khamenei_death_90d", default_window_days=90)
            if random.random() < daily_death_prob:
                state.khamenei_dead = True
                state.events.append(f"Day {state.day}: Khamenei dies")
                state.khamenei_death_day = state.day

                # Succession: modeled as orderly vs disorderly
                orderly_prob = self.sampler.sample("transition", "orderly_succession_given_khamenei_death")
                if random.random() < orderly_prob:
                    state.regime_state = RegimeState.TRANSITION
                    state.final_outcome = "MANAGED_TRANSITION"
                    state.outcome_day = state.day
                    return

                # Disorderly succession crisis: treat as chaotic collapse (simple placeholder)
                state.regime_state = RegimeState.COLLAPSE
                state.final_outcome = "REGIME_COLLAPSE_CHAOTIC"
                state.outcome_day = state.day
                state.collapse_day = state.day
                state.events.append(f"Day {state.day}: Succession crisis triggers regime collapse")
                return

        # 2. Protest trajectory - ABM or state machine
        if self.use_abm and self.abm is not None:
            # Build global context for ABM
            abm_context = {
                "protest_state": state.protest_state.value.upper(),
                "regime_state": state.regime_state.value.upper(),
                "rial_rate": self._economic_data["rial_rate"],
                "crackdown_intensity": 0.8 if state.regime_state == RegimeState.CRACKDOWN else 0.2,
                "concessions_offered": state.regime_state == RegimeState.CONCESSIONS,
                "internet_blackout": state.regime_state == RegimeState.CRACKDOWN,
            }

            # Run ABM step
            abm_result = self.abm.step(abm_context)

            # Map ABM outputs to macro state
            if abm_result["total_protesting"] > 0.10:
                if state.protest_state != ProtestState.ESCALATING:
                    state.protest_state = ProtestState.ESCALATING
                    if state.escalation_start_day is None:
                        state.escalation_start_day = state.day
                        state.events.append(f"Day {state.day}: Protests escalate (ABM: {abm_result['total_protesting']:.1%})")
            elif abm_result["total_protesting"] < 0.02:
                if state.protest_state != ProtestState.COLLAPSED:
                    state.protest_state = ProtestState.COLLAPSED
                    state.events.append(f"Day {state.day}: Protests collapse (ABM: {abm_result['total_protesting']:.1%})")

            # ABM-driven defection (30% threshold)
            if abm_result["defection_rate"] > 0.30 and not state.defection_occurred:
                state.defection_occurred = True
                state.defection_day = state.day
                state.regime_state = RegimeState.DEFECTION
                state.events.append(f"Day {state.day}: Security force defection (ABM: {abm_result['defection_rate']:.1%})")
        else:
            # Fallback to state machine logic
            if state.protest_state != ProtestState.COLLAPSED:
                self._update_protest_state(state)
        if state.final_outcome:
            return

        # 3. Regime response
        if state.regime_state == RegimeState.STATUS_QUO:
            self._check_regime_transitions(state)
        if state.final_outcome:
            return

        # 4. Security force loyalty
        if state.regime_state in [RegimeState.STATUS_QUO, RegimeState.CRACKDOWN, RegimeState.CONCESSIONS]:
            self._check_defection(state)
        # Defection may lead to collapse within a window after it occurs
        self._check_regime_collapse_after_defection(state)
        if state.final_outcome:
            return

        # 5. Ethnic fragmentation
        if not state.ethnic_uprising:
            self._check_ethnic_fragmentation(state)
        # Ethnic uprising may later result in terminal fragmentation within a window
        self._check_fragmentation_outcome(state)
        if state.final_outcome:
            return

        # 6. US intervention escalation
        self._update_us_posture(state)

        # 7. Terminal outcomes
        self._check_terminal_states(state)

        # 8. Regional cascade updates (Iraq/Syria spillover, external actor responses)
        self._update_regional_cascade(state)

    def _update_protest_state(self, state: SimulationState):
        """Update protest intensity.

        Interpret priors as window probabilities and convert them into constant daily hazards.
        """

        # Escalation: probability that protests escalate at least once within the next 14 days
        if state.day <= 14 and state.protest_state == ProtestState.STABLE:
            p_escalate_14d = self.sampler.sample("transition", "protests_escalate_14d")
            daily_escalate = self._window_prob_to_daily_hazard(p_escalate_14d, 14)

            # FEEDBACK LOOP: Economic stress increases protest escalation probability
            # Rationale: Economic hardship fuels grievances and mobilization
            daily_escalate = self._apply_economic_modifiers(daily_escalate, "protest_escalation")

            # FEEDBACK LOOP: Concessions dampen protest escalation probability
            # Rationale: Regime flexibility reduces grievance intensity
            if state.regime_state == RegimeState.CONCESSIONS:
                daily_escalate *= 0.5

            # FEEDBACK LOOP: US intervention increases protest escalation (tier-weighted)
            daily_escalate = self._apply_us_intervention_modifiers(
                daily_escalate, state, "protest_escalation"
            )

            if random.random() < daily_escalate:
                state.protest_state = ProtestState.ESCALATING
                state.events.append(f"Day {state.day}: Protests escalate")
                if state.escalation_start_day is None:
                    state.escalation_start_day = state.day

        # Decline: interpret protests_sustain_30d as the probability of NOT declining within 30 days
        if state.day <= 30 and state.protest_state in [ProtestState.STABLE, ProtestState.ESCALATING]:
            p_sustain_30d = self.sampler.sample("transition", "protests_sustain_30d")
            p_decline_30d = 1.0 - p_sustain_30d
            daily_decline = self._window_prob_to_daily_hazard(p_decline_30d, 30)
            if random.random() < daily_decline:
                state.protest_state = ProtestState.DECLINING
                state.events.append(f"Day {state.day}: Protest momentum begins declining")

        # Collapse after crackdown: probability protests collapse within 30 days of a mass-casualty crackdown
        if state.regime_state == RegimeState.CRACKDOWN and state.protest_state != ProtestState.COLLAPSED:
            prob_obj = self.sampler._get_probability("transition", "protests_collapse_given_crackdown_30d")
            if self._window_active(state, prob_obj):
                daily_collapse = self._daily_hazard_from_window_prob("transition", "protests_collapse_given_crackdown_30d")
                if random.random() < daily_collapse:
                    state.protest_state = ProtestState.COLLAPSED
                    state.events.append(f"Day {state.day}: Protests collapse after crackdown")

        # Collapse after concessions: probability protests collapse within 30 days of meaningful concessions
        if state.regime_state == RegimeState.CONCESSIONS and state.protest_state != ProtestState.COLLAPSED:
            prob_obj = self.sampler._get_probability("transition", "protests_collapse_given_concessions_30d")
            if self._window_active(state, prob_obj):
                daily_collapse = self._daily_hazard_from_window_prob("transition", "protests_collapse_given_concessions_30d")
                if random.random() < daily_collapse:
                    state.protest_state = ProtestState.COLLAPSED
                    state.events.append(f"Day {state.day}: Protests collapse after concessions")
    
    def _check_regime_transitions(self, state: SimulationState):
        """Check for regime response transitions.

        Interpretation conventions:
        - mass_casualty_crackdown_given_escalation: probability of at least one mass-casualty crackdown
          occurring within 30 days after protests enter an ESCALATING state.
        - meaningful_concessions_given_protests_30d: probability of meaningful concessions occurring within
          30 days, conditional on protests persisting past day ~30.
        """

        # Crackdown hazard once protests are escalating (windowed from escalation onset)
        if state.protest_state == ProtestState.ESCALATING and state.regime_state == RegimeState.STATUS_QUO:
            prob_obj = self.sampler._get_probability("transition", "mass_casualty_crackdown_given_escalation")
            if self._window_active(state, prob_obj):
                daily_crackdown = self._daily_hazard_from_window_prob("transition", "mass_casualty_crackdown_given_escalation")

                # FEEDBACK LOOP: Regional instability increases regime anxiety → higher crackdown probability
                # Rationale: Iraq/Syria crisis signals regime vulnerability, triggering preemptive repression
                regional_crisis = (
                    state.iraq.stability in [CountryStability.CRISIS, CountryStability.COLLAPSE] or
                    state.syria.stability in [CountryStability.CRISIS, CountryStability.COLLAPSE]
                )
                if regional_crisis:
                    daily_crackdown *= 1.2

                if random.random() < daily_crackdown:
                    state.regime_state = RegimeState.CRACKDOWN
                    state.crackdown_start_day = state.day
                    state.protester_casualties += random.randint(50, 200)
                    state.events.append(
                        f"Day {state.day}: Mass casualty crackdown - {state.protester_casualties} total dead"
                    )

        # Meaningful concessions: windowed conditional on protests persisting beyond ~30 days
        prob_obj = self.sampler._get_probability("transition", "meaningful_concessions_given_protests_30d")
        if (
            state.regime_state == RegimeState.STATUS_QUO
            and self._protests_active_for_30d_condition(state)
            and self._window_active(state, prob_obj)
        ):
            daily_concessions = self._daily_hazard_from_window_prob("transition", "meaningful_concessions_given_protests_30d")
            if random.random() < daily_concessions:
                state.regime_state = RegimeState.CONCESSIONS
                state.concessions_start_day = state.day
                # Concessions usually aim to deflate protests; model immediate momentum loss.
                if state.protest_state == ProtestState.ESCALATING:
                    state.protest_state = ProtestState.STABLE
                else:
                    state.protest_state = ProtestState.DECLINING
                state.events.append(f"Day {state.day}: Regime offers meaningful concessions")
    
    def _check_defection(self, state: SimulationState):
        """Check for security force defection.

        Semantics:
        - security_force_defection_given_protests_30d is a window probability that a significant
          unit-level defection occurs during a specific window anchored at t0+30.
        - The condition "protests persist" is interpreted as protest_state in {STABLE, ESCALATING}.
        """

        if state.defection_occurred:
            return

        prob_obj = self.sampler._get_probability("transition", "security_force_defection_given_protests_30d")

        if self._protests_active_for_30d_condition(state) and self._window_active(state, prob_obj):
            daily_prob = self._daily_hazard_from_window_prob("transition", "security_force_defection_given_protests_30d")

            # FEEDBACK LOOP: Economic stress increases defection probability
            # Rationale: Economic hardship affects military pay, morale, and family welfare
            daily_prob = self._apply_economic_modifiers(daily_prob, "security_defection")

            # FEEDBACK LOOP: Concessions reduce defection probability
            # Rationale: Security forces see regime flexibility as sign of adaptability, not weakness
            if state.regime_state == RegimeState.CONCESSIONS:
                daily_prob *= 0.7

            # FEEDBACK LOOP: US intervention increases defection probability (tier-weighted)
            daily_prob = self._apply_us_intervention_modifiers(
                daily_prob, state, "security_defection"
            )

            if random.random() < daily_prob:
                state.defection_occurred = True
                state.defection_day = state.day
                state.regime_state = RegimeState.DEFECTION
                state.events.append(f"Day {state.day}: Security force defection")

    def _check_regime_collapse_after_defection(self, state: SimulationState) -> None:
        """Check if an earlier defection leads to regime collapse within a window."""
        if not state.defection_occurred or state.final_outcome:
            return

        prob_obj = self.sampler._get_probability("transition", "regime_collapse_given_defection")
        # Only evaluate collapse hazard inside the window anchored at defection_day.
        if self._window_active(state, prob_obj):
            daily_prob = self._daily_hazard_from_window_prob("transition", "regime_collapse_given_defection")
            # FEEDBACK LOOP: US intervention increases collapse likelihood (tier-weighted)
            daily_prob = self._apply_us_intervention_modifiers(
                daily_prob, state, "regime_collapse"
            )
            if random.random() < daily_prob:
                state.regime_state = RegimeState.COLLAPSE
                state.collapse_day = state.day
                state.final_outcome = "REGIME_COLLAPSE_CHAOTIC"
                state.outcome_day = state.day
                state.events.append(f"Day {state.day}: Regime collapses after defection")

    def _check_ethnic_fragmentation(self, state: SimulationState):
        """Check for ethnic regional breakaway.

        Semantics:
        - ethnic_coordination_given_protests_30d is a window probability that an autonomy/coordination
          event occurs during a window anchored at t0+30.
        - The condition "protests persist" is interpreted as protest_state in {STABLE, ESCALATING}.
        """
        if state.ethnic_uprising:
            return

        prob_obj = self.sampler._get_probability("transition", "ethnic_coordination_given_protests_30d")
        if self._protests_active_for_30d_condition(state) and self._window_active(state, prob_obj):
            daily_prob = self._daily_hazard_from_window_prob("transition", "ethnic_coordination_given_protests_30d")
            if random.random() < daily_prob:
                state.ethnic_uprising = True
                state.ethnic_uprising_day = state.day
                state.events.append(f"Day {state.day}: Ethnic region declares autonomy")

    def _check_fragmentation_outcome(self, state: SimulationState) -> None:
        """After an ethnic uprising, fragmentation may become a terminal outcome within a window."""
        if not state.ethnic_uprising or state.final_outcome:
            return
        prob_obj = self.sampler._get_probability("transition", "fragmentation_outcome_given_ethnic_uprising")
        if self._window_active(state, prob_obj):
            daily_prob = self._daily_hazard_from_window_prob("transition", "fragmentation_outcome_given_ethnic_uprising")
            if random.random() < daily_prob:
                state.regime_state = RegimeState.FRAGMENTATION
                state.final_outcome = "ETHNIC_FRAGMENTATION"
                state.outcome_day = state.day
                state.events.append(f"Day {state.day}: Fragmentation becomes terminal outcome")

    def _update_us_posture(self, state: SimulationState):
        """Update US intervention level.

        Interpret intervention priors as window probabilities and convert to daily hazards.
        US posture is treated as a monotonic escalation ladder.
        """

        def escalate(new_posture: USPosture, event: str) -> None:
            if self._posture_gt(new_posture, state.us_posture):
                state.us_posture = new_posture
                if new_posture in US_SOFT_POSTURES:
                    state.us_soft_intervened = True
                if new_posture in US_HARD_POSTURES:
                    state.us_hard_intervened = True
                state.events.append(f"Day {state.day}: {event}")

        # Information operations: probability of occurring within the next 30 days
        if state.day <= 30 and self._posture_lt(state.us_posture, USPosture.INFORMATION_OPS):
            p_info_30d = self.sampler.sample("us_intervention", "information_ops")
            daily_info = self._window_prob_to_daily_hazard(p_info_30d, 30)
            if random.random() < daily_info:
                escalate(USPosture.INFORMATION_OPS, "US begins information operations support")

        # Economic escalation: probability of occurring within the next 30 days
        if state.day <= 30 and self._posture_lt(state.us_posture, USPosture.ECONOMIC):
            p_econ_30d = self.sampler.sample("us_intervention", "economic_escalation")
            daily_econ = self._window_prob_to_daily_hazard(p_econ_30d, 30)
            if random.random() < daily_econ:
                escalate(USPosture.ECONOMIC, "US escalates economic pressure")

        # Covert support if protests persist beyond 30 days: probability within remaining 60 days
        if state.day >= 30 and state.protest_state != ProtestState.COLLAPSED and self._posture_lt(state.us_posture, USPosture.COVERT):
            p_covert_60d = self.sampler.sample("us_intervention", "covert_support_given_protests_30d")
            daily_covert = self._window_prob_to_daily_hazard(p_covert_60d, 60)
            if random.random() < daily_covert:
                escalate(USPosture.COVERT, "US begins covert support to opposition")

        # Offensive cyber response to mass-casualty crackdown: windowed from crackdown onset
        if state.regime_state == RegimeState.CRACKDOWN and self._posture_lt(state.us_posture, USPosture.CYBER_OFFENSIVE):
            prob_obj = self.sampler._get_probability("us_intervention", "cyber_attack_given_crackdown")
            if self._window_active(state, prob_obj):
                daily_cyber = self._daily_hazard_from_window_prob("us_intervention", "cyber_attack_given_crackdown")
                if random.random() < daily_cyber:
                    escalate(USPosture.CYBER_OFFENSIVE, "US conducts offensive cyber operations")

        # Kinetic response to crackdown: windowed from crackdown onset
        if state.regime_state == RegimeState.CRACKDOWN and self._posture_lt(state.us_posture, USPosture.KINETIC):
            prob_obj = self.sampler._get_probability("us_intervention", "kinetic_strike_given_crackdown")
            if self._window_active(state, prob_obj):
                daily_kinetic = self._daily_hazard_from_window_prob("us_intervention", "kinetic_strike_given_crackdown")
                if random.random() < daily_kinetic:
                    escalate(USPosture.KINETIC, "US conducts military strikes")
                    # Track kinetic day for regional cascade proxy activation
                    if state.us_kinetic_day is None:
                        state.us_kinetic_day = state.day

        # Ground intervention in a collapse scenario: windowed from collapse onset
        if state.regime_state == RegimeState.COLLAPSE and self._posture_lt(state.us_posture, USPosture.GROUND):
            prob_obj = self.sampler._get_probability("us_intervention", "ground_intervention_given_collapse")
            if self._window_active(state, prob_obj):
                daily_ground = self._daily_hazard_from_window_prob("us_intervention", "ground_intervention_given_collapse")
                if random.random() < daily_ground:
                    escalate(USPosture.GROUND, "US deploys ground forces")
    
    def _check_terminal_states(self, state: SimulationState):
        """Check if simulation has reached a terminal state"""

        # Protests collapsed + no defection = regime survives
        if state.protest_state == ProtestState.COLLAPSED and not state.defection_occurred:
            if state.regime_state == RegimeState.CONCESSIONS:
                state.final_outcome = "REGIME_SURVIVES_WITH_CONCESSIONS"
            else:
                state.final_outcome = "REGIME_SURVIVES_STATUS_QUO"
            state.outcome_day = state.day
            state.events.append(f"Day {state.day}: Regime successfully suppresses protests")

    # -------------------------------------------------------------------------
    # REGIONAL CASCADE METHODS
    # -------------------------------------------------------------------------

    def _update_regional_cascade(self, state: SimulationState):
        """Update regional cascade: Iraq/Syria stability and external actor responses."""
        self._update_iraq_stability(state)
        self._update_syria_stability(state)
        self._update_proxy_activations(state)
        self._update_israel_posture(state)
        self._update_russia_posture(state)
        self._update_gulf_realignment(state)

    def _update_iraq_stability(self, state: SimulationState):
        """Update Iraq stability based on Iran crisis spillover."""
        iraq = state.iraq

        # Already in terminal state
        if iraq.stability == CountryStability.COLLAPSE:
            return

        # Iran collapse → Iraq crisis (most severe coupling)
        if state.regime_state == RegimeState.COLLAPSE and iraq.stability != CountryStability.CRISIS:
            prob_obj = self.sampler._get_probability("regional", "iraq_crisis_given_iran_collapse")
            if self._window_active(state, prob_obj):
                daily_prob = self._daily_hazard_from_window_prob("regional", "iraq_crisis_given_iran_collapse")
                if random.random() < daily_prob:
                    iraq.stability = CountryStability.CRISIS
                    iraq.crisis_start_day = state.day
                    iraq.events.append(f"Day {state.day}: Iraq enters crisis (Iran collapse spillover)")
                    state.events.append(f"Day {state.day}: REGIONAL: Iraq destabilized by Iran collapse")

        # Iran escalation → Iraq stressed (milder coupling)
        if (state.escalation_start_day is not None and
            iraq.stability == CountryStability.STABLE):
            prob_obj = self.sampler._get_probability("regional", "iraq_stressed_given_iran_crisis")
            if self._window_active(state, prob_obj):
                daily_prob = self._daily_hazard_from_window_prob("regional", "iraq_stressed_given_iran_crisis")
                if random.random() < daily_prob:
                    iraq.stability = CountryStability.STRESSED
                    iraq.events.append(f"Day {state.day}: Iraq enters stressed state (Iran crisis spillover)")

    def _update_syria_stability(self, state: SimulationState):
        """Update Syria stability based on Iran crisis spillover."""
        syria = state.syria

        # Already in terminal state
        if syria.stability == CountryStability.COLLAPSE:
            return

        # Iran collapse → Syria crisis
        if state.regime_state == RegimeState.COLLAPSE and syria.stability != CountryStability.CRISIS:
            prob_obj = self.sampler._get_probability("regional", "syria_crisis_given_iran_collapse")
            if self._window_active(state, prob_obj):
                daily_prob = self._daily_hazard_from_window_prob("regional", "syria_crisis_given_iran_collapse")
                if random.random() < daily_prob:
                    syria.stability = CountryStability.CRISIS
                    syria.crisis_start_day = state.day
                    syria.events.append(f"Day {state.day}: Syria enters crisis (Iran collapse spillover)")
                    state.events.append(f"Day {state.day}: REGIONAL: Syria destabilized by Iran collapse")

    def _update_proxy_activations(self, state: SimulationState):
        """Check for proxy activation in Iraq/Syria given US kinetic action."""
        # Only trigger if US has gone kinetic
        if state.us_kinetic_day is None:
            return

        # Iraq proxy activation
        if not state.iraq.proxy_activated:
            prob_obj = self.sampler._get_probability("regional", "iraq_proxy_activation_given_us_kinetic")
            if self._window_active(state, prob_obj):
                daily_prob = self._daily_hazard_from_window_prob("regional", "iraq_proxy_activation_given_us_kinetic")
                if random.random() < daily_prob:
                    state.iraq.proxy_activated = True
                    state.iraq.events.append(f"Day {state.day}: Iraqi proxies activate against US forces")
                    state.events.append(f"Day {state.day}: REGIONAL: Iraqi militias attack US targets")

        # Syria proxy activation
        if not state.syria.proxy_activated:
            prob_obj = self.sampler._get_probability("regional", "syria_proxy_activation_given_us_kinetic")
            if self._window_active(state, prob_obj):
                daily_prob = self._daily_hazard_from_window_prob("regional", "syria_proxy_activation_given_us_kinetic")
                if random.random() < daily_prob:
                    state.syria.proxy_activated = True
                    state.syria.events.append(f"Day {state.day}: Syrian proxies activate against US forces")
                    state.events.append(f"Day {state.day}: REGIONAL: Syrian militias attack US targets")

    def _update_israel_posture(self, state: SimulationState):
        """Update Israel posture based on Iran regime weakening."""
        # Already escalated
        if state.israel_posture != IsraelPosture.MONITORING:
            return

        # Israel strikes given defection (signal of regime weakness)
        if state.defection_occurred:
            prob_obj = self.sampler._get_probability("regional", "israel_strikes_given_defection")
            if self._window_active(state, prob_obj):
                daily_prob = self._daily_hazard_from_window_prob("regional", "israel_strikes_given_defection")
                if random.random() < daily_prob:
                    state.israel_posture = IsraelPosture.STRIKES
                    state.israel_strike_day = state.day
                    state.events.append(f"Day {state.day}: REGIONAL: Israel conducts strikes on Iranian assets")

    def _update_russia_posture(self, state: SimulationState):
        """Update Russia posture based on Iran being threatened."""
        # Already escalated
        if state.russia_posture != RussiaPosture.OBSERVING:
            return

        # Russia support given Iran escalation/threat
        if state.escalation_start_day is not None:
            prob_obj = self.sampler._get_probability("regional", "russia_support_given_iran_threatened")
            if self._window_active(state, prob_obj):
                daily_prob = self._daily_hazard_from_window_prob("regional", "russia_support_given_iran_threatened")
                if random.random() < daily_prob:
                    state.russia_posture = RussiaPosture.SUPPORTING
                    state.events.append(f"Day {state.day}: REGIONAL: Russia begins material support to Tehran")

    def _update_gulf_realignment(self, state: SimulationState):
        """Update Gulf realignment status given Iran collapse."""
        # Already realigned
        if state.gulf_realignment:
            return

        # Gulf realignment given Iran collapse
        if state.regime_state == RegimeState.COLLAPSE:
            prob_obj = self.sampler._get_probability("regional", "gulf_realignment_given_collapse")
            if self._window_active(state, prob_obj):
                daily_prob = self._daily_hazard_from_window_prob("regional", "gulf_realignment_given_collapse")
                if random.random() < daily_prob:
                    state.gulf_realignment = True
                    state.events.append(f"Day {state.day}: REGIONAL: Gulf states begin strategic realignment")

    def _determine_final_outcome(self, state: SimulationState) -> str:
        """Determine outcome if no terminal state reached by day 90"""
        
        if state.regime_state == RegimeState.TRANSITION:
            return "MANAGED_TRANSITION"
        elif state.regime_state == RegimeState.COLLAPSE:
            return "REGIME_COLLAPSE_CHAOTIC"
        elif state.regime_state == RegimeState.FRAGMENTATION:
            return "ETHNIC_FRAGMENTATION"
        elif state.protest_state == ProtestState.COLLAPSED:
            return "REGIME_SURVIVES_STATUS_QUO"
        elif state.regime_state == RegimeState.CONCESSIONS:
            return "REGIME_SURVIVES_WITH_CONCESSIONS"
        else:
            # Stalemate at 90 days - categorize as status quo with ongoing tension
            return "REGIME_SURVIVES_STATUS_QUO"
    
    def _get_initial_casualties(self) -> int:
        """Get initial casualty count from intel"""
        try:
            casualties = self.intel["current_state"]["casualties"]["protesters"]["killed"]
            return casualties.get("mid") or casualties.get("low") or 36
        except (KeyError, TypeError):
            return 36  # Default from current reporting
    
    def run_monte_carlo(self, n_runs: int = 10000) -> dict:
        """Run full Monte Carlo simulation"""
        results = []
        
        for i in range(n_runs):
            result = self.run_single()
            results.append(result)
            
            if (i + 1) % 1000 == 0:
                print(f"Completed {i + 1} / {n_runs} runs")
        
        return self._aggregate_results(results)
    
    def _aggregate_results(self, results: List[SimulationState]) -> dict:
        """Aggregate Monte Carlo results"""
        
        outcomes = Counter(r.final_outcome for r in results)
        n = len(results)
        
        # Outcome distribution
        outcome_dist = {
            outcome: {
                "count": count,
                "probability": count / n,
                "ci_low": self._wilson_ci(count, n)[0],
                "ci_high": self._wilson_ci(count, n)[1]
            }
            for outcome, count in outcomes.items()
        }
        
        # Timing statistics
        outcome_days = {}
        for outcome in outcomes.keys():
            days = [r.outcome_day for r in results if r.final_outcome == outcome and r.outcome_day]
            if days:
                outcome_days[outcome] = {
                    "mean_day": statistics.mean(days),
                    "median_day": statistics.median(days),
                    "min_day": min(days),
                    "max_day": max(days)
                }
        
        # US intervention frequency by tier
        us_soft_intervention_rate = sum(1 for r in results if r.us_soft_intervened) / n
        us_hard_intervention_rate = sum(1 for r in results if r.us_hard_intervened) / n
        
        # Defection frequency
        defection_rate = sum(1 for r in results if r.defection_occurred) / n
        
        # Khamenei death frequency
        khamenei_death_rate = sum(1 for r in results if r.khamenei_dead) / n
        
        # Ethnic fragmentation frequency
        ethnic_rate = sum(1 for r in results if r.ethnic_uprising) / n

        # Regional cascade rates
        iraq_crisis_rate = sum(1 for r in results
            if r.iraq.stability in [CountryStability.CRISIS, CountryStability.COLLAPSE]) / n
        syria_crisis_rate = sum(1 for r in results
            if r.syria.stability in [CountryStability.CRISIS, CountryStability.COLLAPSE]) / n
        israel_strikes_rate = sum(1 for r in results
            if r.israel_posture != IsraelPosture.MONITORING) / n
        iraq_proxy_rate = sum(1 for r in results if r.iraq.proxy_activated) / n
        syria_proxy_rate = sum(1 for r in results if r.syria.proxy_activated) / n
        gulf_realignment_rate = sum(1 for r in results if r.gulf_realignment) / n
        russia_support_rate = sum(1 for r in results
            if r.russia_posture != RussiaPosture.OBSERVING) / n

        # Build economic analysis section
        stress = self._get_economic_stress()
        economic_analysis = {
            "stress_level": stress.value,
            "rial_rate_used": self._economic_data.get("rial_rate"),
            "inflation_used": self._economic_data.get("inflation"),
            "modifiers_applied": {
                "protest_escalation": self._get_economic_modifier("protest_escalation"),
                "elite_fracture": self._get_economic_modifier("elite_fracture"),
                "security_defection": self._get_economic_modifier("security_defection"),
            }
        }

        return {
            "n_runs": n,
            "outcome_distribution": outcome_dist,
            "outcome_timing": outcome_days,
            "key_event_rates": {
                "us_soft_intervention": us_soft_intervention_rate,
                "us_hard_intervention": us_hard_intervention_rate,
                "security_force_defection": defection_rate,
                "khamenei_death": khamenei_death_rate,
                "ethnic_uprising": ethnic_rate
            },
            "regional_cascade_rates": {
                "iraq_crisis": iraq_crisis_rate,
                "syria_crisis": syria_crisis_rate,
                "israel_strikes": israel_strikes_rate,
                "iraq_proxy_activation": iraq_proxy_rate,
                "syria_proxy_activation": syria_proxy_rate,
                "gulf_realignment": gulf_realignment_rate,
                "russia_support": russia_support_rate
            },
            "economic_analysis": economic_analysis,
            "sample_trajectories": [
                {
                    "outcome": r.final_outcome,
                    "outcome_day": r.outcome_day,
                    "events": r.events[:10]  # First 10 events
                }
                for r in random.sample(results, min(10, len(results)))
            ]
        }
    
    @staticmethod
    def _wilson_ci(successes: int, n: int, z: float = 1.96) -> Tuple[float, float]:
        """Wilson score confidence interval for proportion"""
        if n == 0:
            return (0.0, 0.0)
        
        p = successes / n
        denominator = 1 + z**2 / n
        center = (p + z**2 / (2*n)) / denominator
        spread = z * (p * (1 - p) / n + z**2 / (4 * n**2))**0.5 / denominator
        
        return (max(0, center - spread), min(1, center + spread))


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Iran Crisis Monte Carlo Simulation")
    parser.add_argument("--intel", required=True, help="Path to intel JSON file")
    parser.add_argument("--priors", required=True, help="Path to analyst priors JSON file")
    parser.add_argument("--runs", type=int, default=10000, help="Number of simulation runs")
    parser.add_argument("--output", default="outputs/simulation_results.json", help="Output file path")
    parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    parser.add_argument("--abm", action="store_true", help="Use Agent-Based Model (Project Swarm) for protest dynamics")

    args = parser.parse_args()
    
    if args.seed:
        random.seed(args.seed)
    
    # Load inputs
    with open(args.intel, 'r') as f:
        intel = json.load(f)
    
    with open(args.priors, 'r') as f:
        priors = json.load(f)


    # Resolve priors semantics (time_basis/anchor/window enforcement) and emit QA
    priors_resolved, priors_qa = resolve_priors(priors)
    if priors_qa.get("status") == "FAIL":
        raise ValueError("Priors contract failed:\n" + "\n".join(priors_qa.get("errors", [])))

    # Write resolved priors + QA next to output
    out_dir = os.path.dirname(args.output) or "."
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "priors_resolved.json"), "w", encoding="utf-8") as f:
        json.dump(priors_resolved, f, indent=2)
    with open(os.path.join(out_dir, "priors_qa.json"), "w", encoding="utf-8") as f:
        json.dump(priors_qa, f, indent=2)

    validate_priors(priors_resolved)

    
    # Run simulation
    if args.abm:
        print(f"Running {args.runs} simulations with ABM (Project Swarm)...")
    else:
        print(f"Running {args.runs} simulations...")
    sim = IranCrisisSimulation(intel, priors_resolved, use_abm=args.abm, seed=args.seed)
    results = sim.run_monte_carlo(args.runs)
    
    # Save results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {args.output}")
    print("\nOutcome Distribution:")
    for outcome, data in sorted(results["outcome_distribution"].items(), 
                                key=lambda x: -x[1]["probability"]):
        print(f"  {outcome}: {data['probability']:.1%} ({data['ci_low']:.1%} - {data['ci_high']:.1%})")
    
    print("\nKey Event Rates:")
    for event, rate in results["key_event_rates"].items():
        print(f"  {event}: {rate:.1%}")


def validate_priors(priors: dict) -> None:
    """Validate `analyst_priors.json` enough to fail fast with a clear error message."""
    required_transition_keys = [
        "khamenei_death_90d",
        "orderly_succession_given_khamenei_death",
        "protests_escalate_14d",
        "protests_sustain_30d",
        "mass_casualty_crackdown_given_escalation",
        "protests_collapse_given_crackdown_30d",
        "protests_collapse_given_concessions_30d",
        "meaningful_concessions_given_protests_30d",
        "security_force_defection_given_protests_30d",
        "regime_collapse_given_defection",
        "ethnic_coordination_given_protests_30d",
        "fragmentation_outcome_given_ethnic_uprising",
    ]
    required_us_keys = [
        "information_ops",
        "economic_escalation",
        "covert_support_given_protests_30d",
        "cyber_attack_given_crackdown",
        "kinetic_strike_given_crackdown",
        "ground_intervention_given_collapse",
    ]

    def _prob_triplet(prob: dict) -> Tuple[float, float, float]:
        low = float(prob.get("low"))
        mode = float(prob.get("mode", prob.get("point")))
        high = float(prob.get("high"))
        return low, mode, high

    def _check_prob(path: str, prob: dict) -> None:
        low, mode, high = _prob_triplet(prob)
        for v in (low, mode, high):
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"Probability out of [0,1] at {path}: {v}")
        if not (low <= mode <= high):
            raise ValueError(f"Expected low<=mode<=high at {path}: {low}, {mode}, {high}")
        if "window_days" in prob:
            wd = int(prob["window_days"])
            if wd <= 0:
                raise ValueError(f"window_days must be positive at {path}: {wd}")

    # Transition probabilities
    tp = priors.get("transition_probabilities")
    if not isinstance(tp, dict):
        raise ValueError("Missing transition_probabilities")
    for k in required_transition_keys:
        if k not in tp:
            raise ValueError(f"Missing transition probability: {k}")
        _check_prob(f"transition_probabilities.{k}.probability", tp[k]["probability"])

    # US intervention probabilities
    up = priors.get("us_intervention_probabilities")
    if not isinstance(up, dict):
        raise ValueError("Missing us_intervention_probabilities")
    for k in required_us_keys:
        if k not in up:
            raise ValueError(f"Missing US intervention probability: {k}")
        _check_prob(f"us_intervention_probabilities.{k}.probability", up[k]["probability"])

    # Regime outcomes (soft check)
    ro = priors.get("regime_outcomes")
    if isinstance(ro, dict):
        keys = [
            "REGIME_SURVIVES_STATUS_QUO",
            "REGIME_SURVIVES_WITH_CONCESSIONS",
            "MANAGED_TRANSITION",
            "REGIME_COLLAPSE_CHAOTIC",
            "ETHNIC_FRAGMENTATION",
        ]
        pts = []
        for k in keys:
            if k in ro and isinstance(ro[k], dict) and "probability" in ro[k]:
                _check_prob(f"regime_outcomes.{k}.probability", ro[k]["probability"])
                pts.append(float(ro[k]["probability"].get("point", ro[k]["probability"].get("mode"))))
        if pts:
            s = sum(pts)
            if not (0.95 <= s <= 1.05):
                raise ValueError(f"Regime outcome point/mode estimates should sum to ~1.0 (got {s:.3f})")


if __name__ == "__main__":
    main()

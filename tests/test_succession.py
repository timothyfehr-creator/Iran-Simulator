"""
Post-succession simulation phase: state machine invariant tests.

These tests verify that the succession phase produces emergent outcomes
from interacting subsystems rather than hardcoded coin flips.
"""

import os
import sys
import json
import random
import unittest

HERE = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from simulation import (
    IranCrisisSimulation,
    SimulationState,
    RegimeState,
    ProtestState,
    validate_priors,
)
from priors.contract import resolve_priors


def load_priors():
    priors_path = os.path.join(REPO_ROOT, "data", "analyst_priors.json")
    with open(priors_path, "r", encoding="utf-8") as f:
        priors = json.load(f)
    resolved, qa = resolve_priors(priors)
    if qa["status"] == "FAIL":
        raise ValueError("Priors contract failed: " + "\n".join(qa["errors"]))
    return resolved


def load_intel():
    """Load the latest intel file for test runs."""
    intel_path = os.path.join(REPO_ROOT, "runs", "RUN_20260309_daily", "compiled_intel.json")
    if not os.path.exists(intel_path):
        # Fallback: find any run with compiled_intel
        runs_dir = os.path.join(REPO_ROOT, "runs")
        for d in sorted(os.listdir(runs_dir), reverse=True):
            candidate = os.path.join(runs_dir, d, "compiled_intel.json")
            if os.path.exists(candidate):
                intel_path = candidate
                break
    with open(intel_path, "r", encoding="utf-8") as f:
        return json.load(f)


def make_sim(priors=None, intel=None, seed=42, use_abm=False):
    priors = priors or load_priors()
    intel = intel or load_intel()
    random.seed(seed)
    return IranCrisisSimulation(intel, priors, use_abm=use_abm, seed=seed)


class TestSuccessionNonTerminal(unittest.TestCase):
    """SUCCESSION_CONTESTED and SUCCESSION_CONSOLIDATING never appear as final_outcome."""

    def test_non_terminal_invariant(self):
        sim = make_sim()
        terminal_succession_states = set()
        for _ in range(500):
            result = sim.run_single()
            sim.sampler.reset_cache()
            if result.final_outcome in ("SUCCESSION_CONTESTED", "SUCCESSION_CONSOLIDATING"):
                terminal_succession_states.add(result.final_outcome)
        self.assertEqual(
            terminal_succession_states, set(),
            "Succession states must resolve to MANAGED_TRANSITION or REGIME_COLLAPSE_CHAOTIC, "
            f"but found as final outcome: {terminal_succession_states}"
        )


class TestMonotonicLoyalty(unittest.TestCase):
    """security_loyalty_modifier never increases during SUCCESSION_CONTESTED."""

    def test_loyalty_never_increases_during_contested(self):
        priors = load_priors()
        # Force contested succession
        tp = priors["transition_probabilities"]["quick_succession_given_death"]["probability"]
        tp["low"] = tp["mode"] = tp["high"] = 0.0  # Always contested
        sim = make_sim(priors=priors)

        for _ in range(100):
            state = SimulationState()
            sim.sampler.reset_cache()
            state.khamenei_dead = True
            state.khamenei_death_day = 0
            sim._get_economic_stress()
            sim._init_succession_phase(state)

            prev_loyalty = state.security_loyalty_modifier
            for day in range(1, 91):
                state.day = day
                if state.final_outcome:
                    break
                was_contested = state.regime_state == RegimeState.SUCCESSION_CONTESTED
                if was_contested:
                    sim._update_succession_state(state)
                    # Only assert monotonic decrease if still contested after update
                    if state.regime_state == RegimeState.SUCCESSION_CONTESTED:
                        self.assertLessEqual(
                            state.security_loyalty_modifier, prev_loyalty + 1e-9,
                            f"Loyalty increased during CONTESTED on day {day}: "
                            f"{prev_loyalty:.4f} -> {state.security_loyalty_modifier:.4f}"
                        )
                    prev_loyalty = state.security_loyalty_modifier
                else:
                    break  # Transitioned out of contested


class TestCohesionBounds(unittest.TestCase):
    """elite_cohesion stays in [0.0, 1.0]."""

    def test_cohesion_bounded(self):
        sim = make_sim()
        for _ in range(500):
            result = sim.run_single()
            sim.sampler.reset_cache()
            self.assertGreaterEqual(result.elite_cohesion, 0.0)
            self.assertLessEqual(result.elite_cohesion, 1.0)


class TestMourningExpiry(unittest.TestCase):
    """Mourning always clears within max mourning duration (10 days)."""

    def test_mourning_clears(self):
        sim = make_sim()
        for _ in range(200):
            result = sim.run_single()
            sim.sampler.reset_cache()
            if result.khamenei_dead and result.outcome_day and result.outcome_day > 10:
                self.assertEqual(
                    result.mourning_days_remaining, 0,
                    f"Mourning should have cleared by day {result.outcome_day} "
                    f"but has {result.mourning_days_remaining} days remaining"
                )


class TestEconomicShockOnce(unittest.TestCase):
    """economic_shock_applied transitions False→True exactly once per contested run."""

    def test_shock_fires_once(self):
        priors = load_priors()
        tp = priors["transition_probabilities"]["quick_succession_given_death"]["probability"]
        tp["low"] = tp["mode"] = tp["high"] = 0.0  # Always contested
        sim = make_sim(priors=priors)

        contested_count = 0
        shocked_count = 0
        for _ in range(200):
            result = sim.run_single()
            sim.sampler.reset_cache()
            if result.succession_type == "contested":
                contested_count += 1
                if result.economic_shock_applied:
                    shocked_count += 1

        self.assertGreater(contested_count, 0, "Should have contested runs")
        self.assertEqual(
            shocked_count, contested_count,
            f"Economic shock should fire in every contested run: "
            f"{shocked_count}/{contested_count}"
        )


class TestConsolidationGate(unittest.TestCase):
    """Consolidation cannot fire while defection_occurred is True."""

    def test_no_consolidation_after_defection(self):
        sim = make_sim()
        for _ in range(500):
            result = sim.run_single()
            sim.sampler.reset_cache()
            if result.defection_occurred and result.final_outcome == "MANAGED_TRANSITION":
                # Check events — consolidation should not appear after defection
                defection_day = result.defection_day or 999
                for event in result.events:
                    if "consolidates power" in event:
                        # Extract day from event string
                        day_str = event.split(":")[0].replace("Day ", "")
                        consol_day = int(day_str)
                        self.assertLess(
                            consol_day, defection_day,
                            "Consolidation fired after defection"
                        )


class TestRegimeStateAwareDeath(unittest.TestCase):
    """Khamenei death during CRACKDOWN produces lower orderly probability than STATUS_QUO."""

    def test_crackdown_reduces_orderly(self):
        priors = load_priors()
        intel = load_intel()

        # Disable observed khamenei death so we can test mid-sim death
        priors["observed_events"]["khamenei_death"]["occurred"] = False
        # Make khamenei die every day
        tp = priors["transition_probabilities"]["khamenei_death_90d"]["probability"]
        tp["low"] = tp["mode"] = tp["high"] = 1.0
        tp["dist"] = "fixed"

        # Run with STATUS_QUO initial state
        n_runs = 500
        smooth_sq = 0
        random.seed(100)
        sim_sq = IranCrisisSimulation(intel, priors, seed=100)
        for _ in range(n_runs):
            result = sim_sq.run_single()
            sim_sq.sampler.reset_cache()
            if result.succession_type == "smooth":
                smooth_sq += 1

        # Now force CRACKDOWN before death
        # We'll manually set regime state
        smooth_ck = 0
        random.seed(200)
        for _ in range(n_runs):
            state = SimulationState()
            state.regime_state = RegimeState.CRACKDOWN
            state.crackdown_start_day = 1
            state.khamenei_dead = True
            state.khamenei_death_day = 5
            state.day = 5
            sim_sq.sampler.reset_cache()
            sim_sq._get_economic_stress()
            sim_sq._init_succession_phase(state)
            if state.succession_type == "smooth":
                smooth_ck += 1

        rate_sq = smooth_sq / n_runs
        rate_ck = smooth_ck / n_runs
        self.assertGreater(
            rate_sq, rate_ck,
            f"STATUS_QUO orderly rate ({rate_sq:.2%}) should exceed "
            f"CRACKDOWN orderly rate ({rate_ck:.2%})"
        )


class TestNoDay0Terminal(unittest.TestCase):
    """With observed Khamenei death, no run should have outcome_day == 0."""

    def test_no_instant_terminal(self):
        sim = make_sim()
        for _ in range(500):
            result = sim.run_single()
            sim.sampler.reset_cache()
            self.assertNotEqual(
                result.outcome_day, 0,
                f"Run terminated on day 0 with outcome {result.final_outcome}. "
                f"Post-succession phase should prevent instant terminal outcomes."
            )


class TestRegionalCascadeFires(unittest.TestCase):
    """With us_kinetic_day=0, proxy activation rates should be non-zero across 1000 runs."""

    def test_proxy_activation_nonzero(self):
        sim = make_sim()
        n_runs = 1000
        iraq_proxy = 0
        syria_proxy = 0
        for _ in range(n_runs):
            result = sim.run_single()
            sim.sampler.reset_cache()
            if result.iraq.proxy_activated:
                iraq_proxy += 1
            if result.syria.proxy_activated:
                syria_proxy += 1

        self.assertGreater(
            iraq_proxy, 0,
            f"Iraq proxy activation should be non-zero across {n_runs} runs "
            f"(got {iraq_proxy})"
        )
        self.assertGreater(
            syria_proxy, 0,
            f"Syria proxy activation should be non-zero across {n_runs} runs "
            f"(got {syria_proxy})"
        )


if __name__ == "__main__":
    unittest.main()

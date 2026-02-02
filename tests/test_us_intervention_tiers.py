"""Tests for US intervention tier split logic."""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation import (
    IranCrisisSimulation,
    SimulationState,
    USPosture,
    US_SOFT_POSTURES,
    US_HARD_POSTURES,
    US_SOFT_INTERVENTION_MODIFIERS,
    US_HARD_INTERVENTION_MODIFIERS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_intel():
    return {
        "current_state": {
            "casualties": {"protesters": {"killed": {"mid": 50}}},
            "economic_conditions": {
                "rial_usd_rate": {"market": 600000},
                "inflation": {"official_annual_percent": 20}
            }
        }
    }


@pytest.fixture
def base_priors():
    return {
        "regime_outcomes": {
            "REGIME_SURVIVES_STATUS_QUO": {"probability": {"low": 0.4, "mode": 0.55, "high": 0.7}},
            "REGIME_SURVIVES_WITH_CONCESSIONS": {"probability": {"low": 0.08, "mode": 0.15, "high": 0.25}},
            "MANAGED_TRANSITION": {"probability": {"low": 0.05, "mode": 0.1, "high": 0.18}},
            "REGIME_COLLAPSE_CHAOTIC": {"probability": {"low": 0.05, "mode": 0.12, "high": 0.22}},
            "ETHNIC_FRAGMENTATION": {"probability": {"low": 0.03, "mode": 0.08, "high": 0.15}},
        },
        "transition_probabilities": {
            "khamenei_death_90d": {"probability": {"low": 0.03, "mode": 0.08, "high": 0.15, "window_days": 90}},
            "orderly_succession_given_khamenei_death": {"probability": {"low": 0.5, "mode": 0.7, "high": 0.85, "window_days": 1}},
            "protests_escalate_14d": {"probability": {"low": 0.2, "mode": 0.35, "high": 0.5, "window_days": 14}},
            "protests_sustain_30d": {"probability": {"low": 0.3, "mode": 0.45, "high": 0.6, "window_days": 30}},
            "mass_casualty_crackdown_given_escalation": {"probability": {"low": 0.25, "mode": 0.4, "high": 0.6, "window_days": 30, "anchor": "escalation_start"}},
            "protests_collapse_given_crackdown_30d": {"probability": {"low": 0.35, "mode": 0.55, "high": 0.75, "window_days": 30, "anchor": "crackdown_start"}},
            "protests_collapse_given_concessions_30d": {"probability": {"low": 0.45, "mode": 0.65, "high": 0.82, "window_days": 30, "anchor": "concessions_start"}},
            "meaningful_concessions_given_protests_30d": {"probability": {"low": 0.07, "mode": 0.15, "high": 0.3, "window_days": 30, "anchor": "t0", "start_offset_days": 30}},
            "security_force_defection_given_protests_30d": {"probability": {"low": 0.03, "mode": 0.08, "high": 0.15, "window_days": 60, "anchor": "t0", "start_offset_days": 30}},
            "regime_collapse_given_defection": {"probability": {"low": 0.45, "mode": 0.65, "high": 0.8, "window_days": 14, "anchor": "defection_day"}},
            "ethnic_coordination_given_protests_30d": {"probability": {"low": 0.12, "mode": 0.25, "high": 0.4, "window_days": 60, "anchor": "t0", "start_offset_days": 30}},
            "fragmentation_outcome_given_ethnic_uprising": {"probability": {"low": 0.15, "mode": 0.3, "high": 0.45, "window_days": 30, "anchor": "ethnic_uprising_day"}},
        },
        "us_intervention_probabilities": {
            "information_ops": {"probability": {"low": 0.5, "mode": 0.7, "high": 0.85, "window_days": 30}},
            "economic_escalation": {"probability": {"low": 0.3, "mode": 0.5, "high": 0.7, "window_days": 30}},
            "covert_support_given_protests_30d": {"probability": {"low": 0.15, "mode": 0.35, "high": 0.55, "window_days": 60}},
            "cyber_attack_given_crackdown": {"probability": {"low": 0.2, "mode": 0.4, "high": 0.6, "window_days": 14, "anchor": "crackdown_start"}},
            "kinetic_strike_given_crackdown": {"probability": {"low": 0.1, "mode": 0.25, "high": 0.45, "window_days": 14, "anchor": "crackdown_start"}},
            "ground_intervention_given_collapse": {"probability": {"low": 0.05, "mode": 0.15, "high": 0.3, "window_days": 14, "anchor": "collapse_day"}},
        },
        "regional_cascade_probabilities": {
            "iraq_stressed_given_iran_crisis": {"probability": {"low": 0.15, "mode": 0.25, "high": 0.4, "window_days": 30, "anchor": "escalation_start"}},
            "iraq_crisis_given_iran_collapse": {"probability": {"low": 0.3, "mode": 0.45, "high": 0.6, "window_days": 30, "anchor": "collapse_day"}},
            "syria_crisis_given_iran_collapse": {"probability": {"low": 0.35, "mode": 0.5, "high": 0.65, "window_days": 30, "anchor": "collapse_day"}},
            "iraq_proxy_activation_given_us_kinetic": {"probability": {"low": 0.5, "mode": 0.65, "high": 0.8, "window_days": 14, "anchor": "us_kinetic_day"}},
            "syria_proxy_activation_given_us_kinetic": {"probability": {"low": 0.4, "mode": 0.55, "high": 0.7, "window_days": 14, "anchor": "us_kinetic_day"}},
            "israel_strikes_given_defection": {"probability": {"low": 0.3, "mode": 0.45, "high": 0.6, "window_days": 30, "anchor": "defection_day"}},
            "russia_support_given_iran_threatened": {"probability": {"low": 0.15, "mode": 0.25, "high": 0.4, "window_days": 60, "anchor": "escalation_start"}},
            "gulf_realignment_given_collapse": {"probability": {"low": 0.5, "mode": 0.7, "high": 0.85, "window_days": 30, "anchor": "collapse_day"}},
        },
        "economic_thresholds": {
            "rial_critical_threshold": 1200000,
            "rial_pressured_threshold": 800000,
            "inflation_critical_threshold": 50,
            "inflation_pressured_threshold": 30,
        },
        "economic_modifiers": {
            "critical_protest_escalation_multiplier": 1.20,
            "critical_elite_fracture_multiplier": 1.30,
            "critical_security_defection_multiplier": 1.15,
            "pressured_protest_escalation_multiplier": 1.10,
            "pressured_elite_fracture_multiplier": 1.15,
            "pressured_security_defection_multiplier": 1.08,
        }
    }


@pytest.fixture
def sim(base_intel, base_priors):
    return IranCrisisSimulation(base_intel, base_priors)


# ---------------------------------------------------------------------------
# 4a. Test _apply_us_intervention_modifiers
# ---------------------------------------------------------------------------

class TestApplyUSInterventionModifiers:

    def test_soft_only(self, sim):
        state = SimulationState()
        state.us_soft_intervened = True
        result = sim._apply_us_intervention_modifiers(0.5, state, "protest_escalation")
        expected = 0.5 * US_SOFT_INTERVENTION_MODIFIERS["protest_escalation"]
        assert result == pytest.approx(expected)

    def test_hard_only(self, sim):
        state = SimulationState()
        state.us_hard_intervened = True
        result = sim._apply_us_intervention_modifiers(0.5, state, "protest_escalation")
        expected = 0.5 * US_HARD_INTERVENTION_MODIFIERS["protest_escalation"]
        assert result == pytest.approx(expected)

    def test_both_flags_hard_wins(self, sim):
        state = SimulationState()
        state.us_soft_intervened = True
        state.us_hard_intervened = True
        result = sim._apply_us_intervention_modifiers(0.5, state, "protest_escalation")
        expected = 0.5 * US_HARD_INTERVENTION_MODIFIERS["protest_escalation"]
        assert result == pytest.approx(expected)

    def test_neither_flag(self, sim):
        state = SimulationState()
        result = sim._apply_us_intervention_modifiers(0.5, state, "protest_escalation")
        assert result == pytest.approx(0.5)

    def test_unknown_event_type(self, sim):
        state = SimulationState()
        state.us_soft_intervened = True
        result = sim._apply_us_intervention_modifiers(0.5, state, "nonexistent_event")
        # Falls back to modifier 1.0
        assert result == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 4b. Tier set invariants
# ---------------------------------------------------------------------------

class TestTierSetInvariants:

    def test_soft_hard_disjoint(self):
        assert US_SOFT_POSTURES & US_HARD_POSTURES == set()

    def test_soft_hard_plus_rhetorical_covers_all(self):
        assert US_SOFT_POSTURES | US_HARD_POSTURES | {USPosture.RHETORICAL} == set(USPosture)


# ---------------------------------------------------------------------------
# 4c. Test aggregate output keys
# ---------------------------------------------------------------------------

class TestAggregateOutputKeys:

    def test_key_event_rates_keys_and_values(self, sim):
        """Build deterministic states and verify aggregate rates."""
        states = []
        for i in range(10):
            s = SimulationState()
            s.final_outcome = "REGIME_SURVIVES_STATUS_QUO"
            s.outcome_day = 90
            # First 3: soft only, next 2: hard only, rest: neither
            if i < 3:
                s.us_soft_intervened = True
            elif i < 5:
                s.us_hard_intervened = True
            states.append(s)

        result = sim._aggregate_results(states)
        rates = result["key_event_rates"]

        assert "us_soft_intervention" in rates
        assert "us_hard_intervention" in rates
        assert "us_intervention" not in rates

        assert rates["us_soft_intervention"] == pytest.approx(3 / 10)
        assert rates["us_hard_intervention"] == pytest.approx(2 / 10)

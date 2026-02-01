"""Tests for economic state machine in simulation."""
import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.simulation import IranCrisisSimulation, EconomicStress


class TestEconomicStress:
    """Test suite for economic stress classification."""

    @pytest.fixture
    def base_intel(self):
        """Base intel fixture with minimal required structure."""
        return {
            "current_state": {
                "casualties": {"protesters": {"killed": {"mid": 50}}},
                "economic_conditions": {}
            }
        }

    @pytest.fixture
    def base_priors(self):
        """Base priors fixture with minimal required structure."""
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

    def test_critical_high_rial(self, base_intel, base_priors):
        """Test CRITICAL classification with high Rial rate."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 1500000},
            "inflation": {"official_annual_percent": 25}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)
        assert sim._get_economic_stress() == EconomicStress.CRITICAL

    def test_critical_high_inflation(self, base_intel, base_priors):
        """Test CRITICAL classification with high inflation."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 700000},
            "inflation": {"official_annual_percent": 55}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)
        assert sim._get_economic_stress() == EconomicStress.CRITICAL

    def test_pressured_moderate_rial(self, base_intel, base_priors):
        """Test PRESSURED classification with moderate Rial rate."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 900000},
            "inflation": {"official_annual_percent": 35}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)
        assert sim._get_economic_stress() == EconomicStress.PRESSURED

    def test_stable_low_rial(self, base_intel, base_priors):
        """Test STABLE classification with low Rial rate and inflation."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 500000},
            "inflation": {"official_annual_percent": 20}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)
        assert sim._get_economic_stress() == EconomicStress.STABLE

    def test_missing_economic_conditions_raises(self, base_intel, base_priors):
        """Test that missing economic_conditions raises ValueError."""
        del base_intel["current_state"]["economic_conditions"]
        sim = IranCrisisSimulation(base_intel, base_priors)
        with pytest.raises(ValueError, match="missing economic_conditions"):
            sim._get_economic_stress()

    def test_missing_rial_raises(self, base_intel, base_priors):
        """Test that missing rial_usd_rate raises ValueError."""
        base_intel["current_state"]["economic_conditions"] = {
            "inflation": {"official_annual_percent": 35}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)
        with pytest.raises(ValueError, match="missing rial_usd_rate"):
            sim._get_economic_stress()

    def test_missing_inflation_raises(self, base_intel, base_priors):
        """Test that missing inflation raises ValueError."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 900000}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)
        with pytest.raises(ValueError, match="missing inflation"):
            sim._get_economic_stress()

    def test_all_rial_paths_none_raises(self, base_intel, base_priors):
        """Test that all-None rial paths raises ValueError."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": None, "mid": None, "value": None},
            "inflation": {"official_annual_percent": 35}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)
        with pytest.raises(ValueError, match="rial_usd_rate value"):
            sim._get_economic_stress()

    def test_all_inflation_paths_none_raises(self, base_intel, base_priors):
        """Test that all-None inflation paths raises ValueError."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 900000},
            "inflation": {"official_annual_percent": None, "mid": None, "value": None}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)
        with pytest.raises(ValueError, match="inflation value"):
            sim._get_economic_stress()

    def test_economic_stress_cached(self, base_intel, base_priors):
        """Test that economic stress is cached after first call."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 1500000},
            "inflation": {"official_annual_percent": 25}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)

        # First call
        stress1 = sim._get_economic_stress()

        # Manually change the intel (shouldn't affect cached value)
        sim.intel["current_state"]["economic_conditions"]["rial_usd_rate"]["market"] = 500000

        # Second call should return cached value
        stress2 = sim._get_economic_stress()

        assert stress1 == stress2 == EconomicStress.CRITICAL


class TestEconomicModifiers:
    """Test suite for economic probability modifiers."""

    @pytest.fixture
    def base_intel(self):
        return {
            "current_state": {
                "casualties": {"protesters": {"killed": {"mid": 50}}},
                "economic_conditions": {}
            }
        }

    @pytest.fixture
    def base_priors(self):
        # Same as above
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

    def test_critical_increases_escalation(self, base_intel, base_priors):
        """Test that CRITICAL stress increases protest escalation probability."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 1500000},
            "inflation": {"official_annual_percent": 25}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)

        base_prob = 0.50
        adjusted = sim._apply_economic_modifiers(base_prob, "protest_escalation")

        # Should be 0.50 * 1.20 = 0.60
        assert adjusted == pytest.approx(0.60, rel=0.01)

    def test_critical_increases_defection(self, base_intel, base_priors):
        """Test that CRITICAL stress increases defection probability."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 1500000},
            "inflation": {"official_annual_percent": 25}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)

        base_prob = 0.50
        adjusted = sim._apply_economic_modifiers(base_prob, "security_defection")

        # Should be 0.50 * 1.15 = 0.575
        assert adjusted == pytest.approx(0.575, rel=0.01)

    def test_modifier_caps_at_95(self, base_intel, base_priors):
        """Test that modifier caps probability at 95%."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 1500000},
            "inflation": {"official_annual_percent": 25}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)

        base_prob = 0.90
        adjusted = sim._apply_economic_modifiers(base_prob, "elite_fracture")

        # 0.90 * 1.30 = 1.17, but should be capped at 0.95
        assert adjusted == 0.95

    def test_stable_no_modifier(self, base_intel, base_priors):
        """Test that STABLE stress applies no modifier."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 500000},
            "inflation": {"official_annual_percent": 20}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)

        base_prob = 0.50
        adjusted = sim._apply_economic_modifiers(base_prob, "protest_escalation")

        # Should be unchanged
        assert adjusted == 0.50

    def test_pressured_moderate_modifier(self, base_intel, base_priors):
        """Test that PRESSURED stress applies moderate modifier."""
        base_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 900000},
            "inflation": {"official_annual_percent": 35}
        }
        sim = IranCrisisSimulation(base_intel, base_priors)

        base_prob = 0.50
        adjusted = sim._apply_economic_modifiers(base_prob, "protest_escalation")

        # Should be 0.50 * 1.10 = 0.55
        assert adjusted == pytest.approx(0.55, rel=0.01)

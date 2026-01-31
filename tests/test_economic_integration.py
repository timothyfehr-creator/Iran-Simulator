"""Integration tests for economic data flow."""
import pytest
import json
import subprocess
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestEconomicIntegration:
    """Integration tests for economic data in simulation pipeline."""

    @pytest.fixture
    def test_intel(self):
        """Test intel with economic data."""
        return {
            "_schema_version": "2.0",
            "current_state": {
                "as_of": "2026-01-17T12:00:00Z",
                "casualties": {"protesters": {"killed": {"mid": 50}}},
                "economic_conditions": {
                    "rial_usd_rate": {"market": 1500000},
                    "inflation": {"official_annual_percent": 42}
                }
            }
        }

    @pytest.fixture
    def test_priors(self):
        """Minimal priors for testing."""
        return {
            "regime_outcomes": {
                "REGIME_SURVIVES_STATUS_QUO": {"probability": {"low": 0.4, "mode": 0.55, "high": 0.7}},
                "REGIME_SURVIVES_WITH_CONCESSIONS": {"probability": {"low": 0.08, "mode": 0.15, "high": 0.25}},
                "MANAGED_TRANSITION": {"probability": {"low": 0.05, "mode": 0.1, "high": 0.18}},
                "REGIME_COLLAPSE_CHAOTIC": {"probability": {"low": 0.05, "mode": 0.12, "high": 0.22}},
                "ETHNIC_FRAGMENTATION": {"probability": {"low": 0.03, "mode": 0.08, "high": 0.15}},
            },
            "transition_probabilities": {
                "khamenei_death_90d": {"probability": {"low": 0.03, "mode": 0.08, "high": 0.15, "window_days": 90, "anchor": "t0"}},
                "orderly_succession_given_khamenei_death": {"probability": {"low": 0.5, "mode": 0.7, "high": 0.85, "window_days": 1, "anchor": "khamenei_death_day"}},
                "protests_escalate_14d": {"probability": {"low": 0.2, "mode": 0.35, "high": 0.5, "window_days": 14, "anchor": "t0"}},
                "protests_sustain_30d": {"probability": {"low": 0.3, "mode": 0.45, "high": 0.6, "window_days": 30, "anchor": "t0"}},
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
                "information_ops": {"probability": {"low": 0.5, "mode": 0.7, "high": 0.85, "window_days": 30, "anchor": "t0"}},
                "economic_escalation": {"probability": {"low": 0.3, "mode": 0.5, "high": 0.7, "window_days": 30, "anchor": "t0"}},
                "covert_support_given_protests_30d": {"probability": {"low": 0.15, "mode": 0.35, "high": 0.55, "window_days": 60, "anchor": "t0", "start_offset_days": 30}},
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

    def test_simulation_includes_economic_analysis(self, test_intel, test_priors):
        """Test that simulation output includes economic_analysis section."""
        from src.simulation import IranCrisisSimulation

        sim = IranCrisisSimulation(test_intel, test_priors)
        results = sim.run_monte_carlo(n_runs=100)

        assert "economic_analysis" in results
        assert results["economic_analysis"]["stress_level"] == "critical"
        assert results["economic_analysis"]["rial_rate_used"] == 1500000
        assert results["economic_analysis"]["inflation_used"] == 42

    def test_economic_analysis_modifiers(self, test_intel, test_priors):
        """Test that economic modifiers are correctly reported."""
        from src.simulation import IranCrisisSimulation

        sim = IranCrisisSimulation(test_intel, test_priors)
        results = sim.run_monte_carlo(n_runs=100)

        modifiers = results["economic_analysis"]["modifiers_applied"]
        assert modifiers["protest_escalation"] == pytest.approx(1.20, rel=0.01)
        assert modifiers["elite_fracture"] == pytest.approx(1.30, rel=0.01)
        assert modifiers["security_defection"] == pytest.approx(1.15, rel=0.01)

    def test_stable_economy_no_modifiers(self, test_intel, test_priors):
        """Test that stable economy has no modifiers."""
        # Modify intel for stable economy
        test_intel["current_state"]["economic_conditions"] = {
            "rial_usd_rate": {"market": 500000},
            "inflation": {"official_annual_percent": 20}
        }

        from src.simulation import IranCrisisSimulation

        sim = IranCrisisSimulation(test_intel, test_priors)
        results = sim.run_monte_carlo(n_runs=100)

        assert results["economic_analysis"]["stress_level"] == "stable"
        modifiers = results["economic_analysis"]["modifiers_applied"]
        assert modifiers["protest_escalation"] == 1.0
        assert modifiers["elite_fracture"] == 1.0
        assert modifiers["security_defection"] == 1.0


class TestIODAIntegration:
    """Integration tests for IODA fetcher."""

    def test_ioda_fetcher_importable(self):
        """Test that IODA fetcher can be imported."""
        from src.ingest.fetch_ioda import IODAFetcher, fetch
        assert IODAFetcher is not None
        assert fetch is not None

    def test_ioda_config_in_sources(self):
        """Test that IODA is configured in sources.yaml."""
        import yaml
        sources_path = Path(__file__).parent.parent / "config" / "sources.yaml"

        with open(sources_path) as f:
            config = yaml.safe_load(f)

        # Find IODA source
        ioda_source = None
        for source in config.get("sources", []):
            if source.get("id") == "ioda":
                ioda_source = source
                break

        assert ioda_source is not None
        assert ioda_source["bucket"] == "internet_monitoring"
        assert ioda_source["enabled"] == True
        assert ioda_source["fetcher"] == "src.ingest.fetch_ioda"

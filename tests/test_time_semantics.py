import os
import sys
import json
import unittest
import random

# Ensure src is on path
HERE = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from simulation import IranCrisisSimulation, SimulationState, RegimeState, ProtestState, USPosture, validate_priors


def load_priors():
    priors_path = os.path.join(REPO_ROOT, "data", "analyst_priors.json")
    with open(priors_path, "r", encoding="utf-8") as f:
        return json.load(f)


class TestTimeSemantics(unittest.TestCase):
    def test_window_active_helper(self):
        state = SimulationState()
        state.day = 5
        state.escalation_start_day = 5
        prob_obj = {"anchor": "escalation_start", "start_offset_days": 0, "window_days": 3}
        self.assertTrue(IranCrisisSimulation._window_active(state, prob_obj))
        state.day = 7
        self.assertTrue(IranCrisisSimulation._window_active(state, prob_obj))
        state.day = 8
        self.assertFalse(IranCrisisSimulation._window_active(state, prob_obj))

    def test_crackdown_sets_start_day(self):
        priors = load_priors()
        # make crackdown essentially certain
        priors["transition_probabilities"]["mass_casualty_crackdown_given_escalation"]["probability"]["low"] = 1.0
        priors["transition_probabilities"]["mass_casualty_crackdown_given_escalation"]["probability"]["mode"] = 1.0
        priors["transition_probabilities"]["mass_casualty_crackdown_given_escalation"]["probability"]["high"] = 1.0

        sim = IranCrisisSimulation(intel={}, priors=priors)
        state = SimulationState()
        state.day = 1
        state.protest_state = ProtestState.ESCALATING
        state.escalation_start_day = 1
        state.regime_state = RegimeState.STATUS_QUO

        random.seed(0)
        sim._check_regime_transitions(state)
        self.assertEqual(state.regime_state, RegimeState.CRACKDOWN)
        self.assertEqual(state.crackdown_start_day, 1)

    def test_cyber_not_before_crackdown_start_day(self):
        priors = load_priors()
        # make cyber certain if it were active
        priors["us_intervention_probabilities"]["cyber_attack_given_crackdown"]["probability"]["low"] = 1.0
        priors["us_intervention_probabilities"]["cyber_attack_given_crackdown"]["probability"]["mode"] = 1.0
        priors["us_intervention_probabilities"]["cyber_attack_given_crackdown"]["probability"]["high"] = 1.0

        sim = IranCrisisSimulation(intel={}, priors=priors)
        state = SimulationState()
        state.day = 3
        state.regime_state = RegimeState.CRACKDOWN
        state.crackdown_start_day = None  # missing anchor
        state.us_posture = USPosture.RHETORICAL

        random.seed(0)
        sim._update_us_posture(state)
        self.assertEqual(state.us_posture, USPosture.RHETORICAL)

    def test_defection_not_when_declining(self):
        priors = load_priors()
        priors["transition_probabilities"]["security_force_defection_given_protests_30d"]["probability"]["low"] = 1.0
        priors["transition_probabilities"]["security_force_defection_given_protests_30d"]["probability"]["mode"] = 1.0
        priors["transition_probabilities"]["security_force_defection_given_protests_30d"]["probability"]["high"] = 1.0

        sim = IranCrisisSimulation(intel={}, priors=priors)
        state = SimulationState()
        state.day = 40
        state.protest_state = ProtestState.DECLINING
        state.regime_state = RegimeState.STATUS_QUO

        random.seed(0)
        sim._check_defection(state)
        self.assertFalse(state.defection_occurred)

    def test_validate_priors_requires_concessions_collapse(self):
        priors = load_priors()
        del priors["transition_probabilities"]["protests_collapse_given_concessions_30d"]
        with self.assertRaises(Exception):
            validate_priors(priors)

    def test_fragmentation_terminalization_uses_prior(self):
        priors = load_priors()
        priors["transition_probabilities"]["fragmentation_outcome_given_ethnic_uprising"]["probability"]["low"] = 1.0
        priors["transition_probabilities"]["fragmentation_outcome_given_ethnic_uprising"]["probability"]["mode"] = 1.0
        priors["transition_probabilities"]["fragmentation_outcome_given_ethnic_uprising"]["probability"]["high"] = 1.0

        sim = IranCrisisSimulation(intel={}, priors=priors)
        state = SimulationState()
        state.day = 10
        state.ethnic_uprising = True
        state.ethnic_uprising_day = 10

        random.seed(0)
        sim._check_fragmentation_outcome(state)
        self.assertEqual(state.final_outcome, "ETHNIC_FRAGMENTATION")


if __name__ == "__main__":
    unittest.main()

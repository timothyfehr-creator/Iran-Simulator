#!/usr/bin/env python3
"""
Bayesian Network Prototype for Iran Crisis Simulation
======================================================

This module implements a CausalEngine class that wraps a pgmpy Bayesian Network
for causal reasoning about the Iran crisis simulation. It provides:
1. Explicit causal structure with uncertainty quantification
2. "What-if" queries impossible with pure Monte Carlo sampling
3. Sensitivity analysis on causal pathways
4. Foundation for future causal inference

Usage:
    # Build and visualize DAG
    python scripts/prototype_causal_graph.py --visualize

    # Export prompts for reasoning model
    python scripts/prototype_causal_graph.py --export-prompts prompts/cpt_derivation/

    # Load CPTs and validate
    python scripts/prototype_causal_graph.py --load-cpts prompts/cpt_derivation/responses/ --validate

    # Run inference
    python scripts/prototype_causal_graph.py --infer --evidence '{"Economic_Stress": "CRITICAL"}'

    # Compare to Monte Carlo
    python scripts/prototype_causal_graph.py --compare-mc runs/RUN_20260117_daily/simulation_results.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

try:
    # pgmpy >= 0.1.26 uses DiscreteBayesianNetwork
    try:
        from pgmpy.models import DiscreteBayesianNetwork as BayesianNetwork
    except ImportError:
        from pgmpy.models import BayesianNetwork
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination
    import networkx as nx
except ImportError:
    print("Error: pgmpy and networkx are required. Install with:")
    print("  pip install pgmpy networkx")
    sys.exit(1)


# =============================================================================
# NODE DEFINITIONS
# =============================================================================

# Root Nodes (Observable/Exogenous)
ROOT_NODES = {
    "Rial_Rate": ["LOW", "MODERATE", "HIGH"],
    "Inflation": ["LOW", "MODERATE", "HIGH"],
    "Khamenei_Health": ["ALIVE", "DEAD"],
    "US_Policy_Disposition": ["RHETORICAL", "ECONOMIC", "COVERT", "KINETIC"],
}

# Intermediate Nodes
INTERMEDIATE_NODES = {
    # Economic
    "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
    # Protest dynamics
    "Protest_Escalation": ["NO", "YES"],
    "Protest_Sustained": ["NO", "YES"],
    "Protest_State": ["DECLINING", "STABLE", "ESCALATING", "ORGANIZED", "COLLAPSED"],
    # Regime response
    "Regime_Response": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
    "Internet_Status": ["ON", "THROTTLED", "OFF"],
    # Security dynamics
    "Security_Loyalty": ["LOYAL", "WAVERING", "DEFECTED"],
    "Elite_Cohesion": ["COHESIVE", "FRACTURED", "COLLAPSED"],
    # Ethnic dynamics
    "Ethnic_Uprising": ["NO", "YES"],
    "Fragmentation_Outcome": ["NO", "YES"],
    # Succession
    "Succession_Type": ["ORDERLY", "CHAOTIC"],
    # Regional cascade
    "Regional_Instability": ["NONE", "MODERATE", "SEVERE"],
    "Iraq_Stability": ["STABLE", "STRESSED", "CRISIS"],
    "Syria_Stability": ["STABLE", "STRESSED", "CRISIS"],
    # External actors
    "Israel_Posture": ["RESTRAINED", "STRIKING"],
    "Russia_Posture": ["NEUTRAL", "SUPPORTING"],
    "Gulf_Realignment": ["NO", "YES"],
}

# Terminal Outcome Node
TERMINAL_NODES = {
    "Regime_Outcome": ["STATUS_QUO", "CONCESSIONS", "TRANSITION", "COLLAPSE", "FRAGMENTATION"],
}

# All nodes combined
ALL_NODES = {**ROOT_NODES, **INTERMEDIATE_NODES, **TERMINAL_NODES}

# =============================================================================
# EDGE DEFINITIONS (25 edges as specified in plan)
# =============================================================================

EDGES = [
    # Economic
    ("Rial_Rate", "Economic_Stress"),
    ("Inflation", "Economic_Stress"),

    # Protest dynamics (equilibrium model - no cycles)
    # Protest escalation is driven by economic stress
    ("Economic_Stress", "Protest_Escalation"),
    # Protest state depends on escalation and sustained (no direct Regime_Response edge to avoid cycle)
    ("Protest_Escalation", "Protest_State"),
    ("Protest_Sustained", "Protest_State"),
    # Protest sustained depends on escalation, response, and internet
    ("Protest_Escalation", "Protest_Sustained"),
    ("Regime_Response", "Protest_Sustained"),
    ("Internet_Status", "Protest_Sustained"),  # Blackouts affect coordination

    # Internet status depends on regime response
    ("Regime_Response", "Internet_Status"),

    # Regime response depends on economic stress (proxy for protest pressure)
    # Note: We removed Protest_State -> Regime_Response to break cycle
    # Economic stress serves as proxy for protest pressure in equilibrium model
    ("Economic_Stress", "Regime_Response"),
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

    # Regional cascade (equilibrium model)
    # Note: Regime_Outcome -> Regional_Instability removed to break cycle
    # Regional instability is driven by US policy and economic stress
    ("US_Policy_Disposition", "Regional_Instability"),
    ("Economic_Stress", "Regional_Instability"),  # Economic crisis affects region
    ("Regional_Instability", "Iraq_Stability"),
    ("Regional_Instability", "Syria_Stability"),

    # External actors
    ("Security_Loyalty", "Israel_Posture"),
    ("US_Policy_Disposition", "Israel_Posture"),
    ("Regional_Instability", "Russia_Posture"),
    ("Regime_Outcome", "Gulf_Realignment"),
]

# =============================================================================
# CPT CLASSIFICATION
# =============================================================================

# Simple CPTs that can be derived directly from priors
SIMPLE_CPTS = [
    "Rial_Rate",
    "Inflation",
    "Khamenei_Health",
    "US_Policy_Disposition",
    "Economic_Stress",
    "Succession_Type",
    "Fragmentation_Outcome",
    "Iraq_Stability",
    "Syria_Stability",
    "Israel_Posture",
    "Russia_Posture",
    "Gulf_Realignment",
]

# Complex CPTs that require reasoning model
COMPLEX_CPTS = [
    "Protest_State",
    "Protest_Escalation",
    "Protest_Sustained",
    "Security_Loyalty",
    "Regime_Response",
    "Elite_Cohesion",
    "Regime_Outcome",
    "Ethnic_Uprising",
    "Internet_Status",
    "Regional_Instability",
]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def window_to_daily_hazard(p_window: float, window_days: int) -> float:
    """Convert P(event within window) to constant daily hazard rate.

    Uses numerically stable formula: -expm1(log1p(-p) / n)

    Args:
        p_window: Probability of event occurring within the window
        window_days: Length of window in days

    Returns:
        Daily hazard rate (probability per day)
    """
    if p_window <= 0:
        return 0.0
    if p_window >= 1:
        return 1.0
    return -math.expm1(math.log1p(-p_window) / window_days)


def window_to_marginal(p_window: float, window_days: int, total_days: int = 90) -> float:
    """Convert window probability to expected fraction of time in state.

    Approximation: If event occurs with p_window within window_days,
    and once it occurs it persists, the marginal probability is roughly:

    p_marginal ≈ p_window * (total_days - window_days/2) / total_days

    Args:
        p_window: Window probability from priors
        window_days: Window length in days
        total_days: Total simulation horizon (default 90)

    Returns:
        Marginal probability for BN
    """
    expected_onset = window_days / 2  # Expected onset day within window
    duration_if_occurs = total_days - expected_onset
    return p_window * (duration_if_occurs / total_days)


def load_json(path: Path) -> dict:
    """Load JSON file with error handling."""
    with open(path, 'r') as f:
        return json.load(f)


def get_prob_mode(prob_dict: dict) -> float:
    """Extract mode (most likely value) from probability dict."""
    return prob_dict.get("mode", prob_dict.get("point", 0.5))


# =============================================================================
# DAG BUILDER
# =============================================================================

def build_dag() -> BayesianNetwork:
    """Build the Bayesian Network DAG structure.

    Returns:
        BayesianNetwork with edges defined but no CPDs yet
    """
    model = BayesianNetwork(EDGES)
    return model


def get_parents(node: str) -> list[str]:
    """Get parent nodes for a given node."""
    return [edge[0] for edge in EDGES if edge[1] == node]


def get_cardinality(node: str) -> int:
    """Get the number of states for a node."""
    return len(ALL_NODES[node])


# =============================================================================
# SIMPLE CPT CONSTRUCTORS
# =============================================================================

def build_rial_rate_cpd(priors: dict, intel: dict | None = None) -> TabularCPD:
    """Build CPD for Rial_Rate based on current intel or priors.

    If intel contains current rial rate, use deterministic assignment.
    Otherwise, use uninformative prior.
    """
    # Default: uninformative prior
    values = [[0.33], [0.34], [0.33]]  # LOW, MODERATE, HIGH

    if intel:
        # Get thresholds from priors
        thresholds = priors.get("economic_thresholds", {})
        rial_critical = thresholds.get("rial_critical_threshold", 1200000)
        rial_pressured = thresholds.get("rial_pressured_threshold", 800000)

        # Check intel for current rate
        econ = intel.get("kiq_summaries", {}).get("kiq_1_regime_stability", {})
        econ_data = econ.get("economic_conditions", {})
        rial_rate = econ_data.get("rial_rate")

        if rial_rate:
            if rial_rate >= rial_critical:
                values = [[0.0], [0.0], [1.0]]  # HIGH
            elif rial_rate >= rial_pressured:
                values = [[0.0], [1.0], [0.0]]  # MODERATE
            else:
                values = [[1.0], [0.0], [0.0]]  # LOW

    return TabularCPD(
        variable="Rial_Rate",
        variable_card=3,
        values=values,
        state_names={"Rial_Rate": ["LOW", "MODERATE", "HIGH"]}
    )


def build_inflation_cpd(priors: dict, intel: dict | None = None) -> TabularCPD:
    """Build CPD for Inflation based on current intel or priors."""
    values = [[0.33], [0.34], [0.33]]  # LOW, MODERATE, HIGH

    if intel:
        thresholds = priors.get("economic_thresholds", {})
        inf_critical = thresholds.get("inflation_critical_threshold", 50)
        inf_pressured = thresholds.get("inflation_pressured_threshold", 30)

        econ = intel.get("kiq_summaries", {}).get("kiq_1_regime_stability", {})
        econ_data = econ.get("economic_conditions", {})
        inflation = econ_data.get("inflation_rate")

        if inflation:
            if inflation >= inf_critical:
                values = [[0.0], [0.0], [1.0]]  # HIGH
            elif inflation >= inf_pressured:
                values = [[0.0], [1.0], [0.0]]  # MODERATE
            else:
                values = [[1.0], [0.0], [0.0]]  # LOW

    return TabularCPD(
        variable="Inflation",
        variable_card=3,
        values=values,
        state_names={"Inflation": ["LOW", "MODERATE", "HIGH"]}
    )


def build_khamenei_health_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Khamenei_Health based on 90-day death probability."""
    trans_probs = priors.get("transition_probabilities", {})
    death_prob = trans_probs.get("khamenei_death_90d", {})
    p_death = get_prob_mode(death_prob.get("probability", {"mode": 0.08}))

    return TabularCPD(
        variable="Khamenei_Health",
        variable_card=2,
        values=[[1 - p_death], [p_death]],  # [ALIVE, DEAD]
        state_names={"Khamenei_Health": ["ALIVE", "DEAD"]}
    )


def build_us_policy_cpd(priors: dict) -> TabularCPD:
    """Build CPD for US_Policy_Disposition based on intervention priors."""
    us_probs = priors.get("us_intervention_probabilities", {})

    # Extract probabilities for each posture level
    p_info_ops = get_prob_mode(us_probs.get("information_ops", {}).get("probability", {"mode": 0.7}))
    p_econ = get_prob_mode(us_probs.get("economic_escalation", {}).get("probability", {"mode": 0.5}))
    p_covert = get_prob_mode(us_probs.get("covert_support_given_protests_30d", {}).get("probability", {"mode": 0.35}))
    p_kinetic = get_prob_mode(us_probs.get("kinetic_strike_given_crackdown", {}).get("probability", {"mode": 0.25}))

    # These are conditional probs, need to convert to marginal distribution
    # Use rough approximation: weight by escalation likelihood
    total = p_info_ops + p_econ + p_covert + p_kinetic
    if total > 0:
        values = [
            [p_info_ops / total],  # RHETORICAL
            [p_econ / total],      # ECONOMIC
            [p_covert / total],    # COVERT
            [p_kinetic / total],   # KINETIC
        ]
    else:
        values = [[0.4], [0.3], [0.2], [0.1]]

    return TabularCPD(
        variable="US_Policy_Disposition",
        variable_card=4,
        values=values,
        state_names={"US_Policy_Disposition": ["RHETORICAL", "ECONOMIC", "COVERT", "KINETIC"]}
    )


def build_economic_stress_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Economic_Stress given Rial_Rate and Inflation.

    Economic stress is deterministic based on the max of both indicators:
    - Either HIGH → CRITICAL
    - Either MODERATE (and none HIGH) → PRESSURED
    - Both LOW → STABLE
    """
    # 3x3 = 9 columns for (Rial_Rate x Inflation)
    # Ordering: Rial LOW/MOD/HIGH (slowest), Inflation LOW/MOD/HIGH (fastest)
    # Column order: (LOW,LOW), (LOW,MOD), (LOW,HIGH), (MOD,LOW), (MOD,MOD), (MOD,HIGH), ...

    # STABLE, PRESSURED, CRITICAL
    values = [
        # Rial=LOW           Rial=MOD           Rial=HIGH
        # Inf=L  M  H        Inf=L  M  H        Inf=L  M  H
        [1.0, 0.0, 0.0,     0.0, 0.0, 0.0,     0.0, 0.0, 0.0],  # STABLE
        [0.0, 1.0, 0.0,     1.0, 1.0, 0.0,     0.0, 0.0, 0.0],  # PRESSURED
        [0.0, 0.0, 1.0,     0.0, 0.0, 1.0,     1.0, 1.0, 1.0],  # CRITICAL
    ]

    return TabularCPD(
        variable="Economic_Stress",
        variable_card=3,
        values=values,
        evidence=["Rial_Rate", "Inflation"],
        evidence_card=[3, 3],
        state_names={
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
            "Rial_Rate": ["LOW", "MODERATE", "HIGH"],
            "Inflation": ["LOW", "MODERATE", "HIGH"],
        }
    )


def build_succession_type_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Succession_Type given Khamenei_Health and Elite_Cohesion.

    If Khamenei alive: succession N/A (set to ORDERLY as default)
    If Khamenei dead: depends on elite cohesion
    """
    trans_probs = priors.get("transition_probabilities", {})
    orderly_prob = trans_probs.get("orderly_succession_given_khamenei_death", {})
    p_orderly = get_prob_mode(orderly_prob.get("probability", {"mode": 0.7}))

    # Parents: Khamenei_Health (2), Elite_Cohesion (3)
    # 2 x 3 = 6 columns
    # Khamenei: ALIVE, DEAD; Elite: COHESIVE, FRACTURED, COLLAPSED

    # When alive, succession is N/A - we'll say ORDERLY (doesn't matter)
    # When dead, cohesion affects orderly succession
    values = [
        # Kham=ALIVE                    Kham=DEAD
        # Elite=COH  FRAC  COLL         Elite=COH  FRAC  COLL
        [1.0, 1.0, 1.0,                 p_orderly, p_orderly * 0.5, 0.1],  # ORDERLY
        [0.0, 0.0, 0.0,                 1 - p_orderly, 1 - p_orderly * 0.5, 0.9],  # CHAOTIC
    ]

    return TabularCPD(
        variable="Succession_Type",
        variable_card=2,
        values=values,
        evidence=["Khamenei_Health", "Elite_Cohesion"],
        evidence_card=[2, 3],
        state_names={
            "Succession_Type": ["ORDERLY", "CHAOTIC"],
            "Khamenei_Health": ["ALIVE", "DEAD"],
            "Elite_Cohesion": ["COHESIVE", "FRACTURED", "COLLAPSED"],
        }
    )


def build_fragmentation_outcome_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Fragmentation_Outcome given Ethnic_Uprising."""
    trans_probs = priors.get("transition_probabilities", {})
    frag_prob = trans_probs.get("fragmentation_outcome_given_ethnic_uprising", {})
    p_frag = get_prob_mode(frag_prob.get("probability", {"mode": 0.3}))

    # Parent: Ethnic_Uprising (NO, YES)
    values = [
        [1.0, 1 - p_frag],  # NO fragmentation
        [0.0, p_frag],      # YES fragmentation
    ]

    return TabularCPD(
        variable="Fragmentation_Outcome",
        variable_card=2,
        values=values,
        evidence=["Ethnic_Uprising"],
        evidence_card=[2],
        state_names={
            "Fragmentation_Outcome": ["NO", "YES"],
            "Ethnic_Uprising": ["NO", "YES"],
        }
    )


def build_iraq_stability_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Iraq_Stability given Regional_Instability."""
    regional = priors.get("regional_cascade_probabilities", {})

    p_stressed = get_prob_mode(
        regional.get("iraq_stressed_given_iran_crisis", {}).get("probability", {"mode": 0.25})
    )
    p_crisis = get_prob_mode(
        regional.get("iraq_crisis_given_iran_collapse", {}).get("probability", {"mode": 0.45})
    )

    # Parent: Regional_Instability (NONE, MODERATE, SEVERE)
    # Build each column to sum to 1.0
    # NONE: mostly stable
    col_none = [0.85, 0.12, 0.03]  # STABLE, STRESSED, CRISIS

    # MODERATE: use p_stressed from priors, distribute rest
    col_mod = [0.60, p_stressed, 1.0 - 0.60 - p_stressed]

    # SEVERE: use p_crisis from priors, distribute rest
    col_sev = [1.0 - p_crisis - 0.25, 0.25, p_crisis]

    values = [
        [col_none[0], col_mod[0], col_sev[0]],  # STABLE
        [col_none[1], col_mod[1], col_sev[1]],  # STRESSED
        [col_none[2], col_mod[2], col_sev[2]],  # CRISIS
    ]

    return TabularCPD(
        variable="Iraq_Stability",
        variable_card=3,
        values=values,
        evidence=["Regional_Instability"],
        evidence_card=[3],
        state_names={
            "Iraq_Stability": ["STABLE", "STRESSED", "CRISIS"],
            "Regional_Instability": ["NONE", "MODERATE", "SEVERE"],
        }
    )


def build_syria_stability_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Syria_Stability given Regional_Instability."""
    regional = priors.get("regional_cascade_probabilities", {})

    p_crisis = get_prob_mode(
        regional.get("syria_crisis_given_iran_collapse", {}).get("probability", {"mode": 0.50})
    )

    # Build each column to sum to 1.0
    # NONE: mostly stable
    col_none = [0.75, 0.20, 0.05]  # STABLE, STRESSED, CRISIS

    # MODERATE: moderate stress
    col_mod = [0.50, 0.35, 0.15]

    # SEVERE: use p_crisis from priors, distribute rest
    col_sev = [1.0 - p_crisis - 0.25, 0.25, p_crisis]

    values = [
        [col_none[0], col_mod[0], col_sev[0]],  # STABLE
        [col_none[1], col_mod[1], col_sev[1]],  # STRESSED
        [col_none[2], col_mod[2], col_sev[2]],  # CRISIS
    ]

    return TabularCPD(
        variable="Syria_Stability",
        variable_card=3,
        values=values,
        evidence=["Regional_Instability"],
        evidence_card=[3],
        state_names={
            "Syria_Stability": ["STABLE", "STRESSED", "CRISIS"],
            "Regional_Instability": ["NONE", "MODERATE", "SEVERE"],
        }
    )


def build_israel_posture_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Israel_Posture given Security_Loyalty and US_Policy_Disposition."""
    regional = priors.get("regional_cascade_probabilities", {})

    p_strike = get_prob_mode(
        regional.get("israel_strikes_given_defection", {}).get("probability", {"mode": 0.45})
    )

    # Parents: Security_Loyalty (3), US_Policy_Disposition (4)
    # 3 x 4 = 12 columns
    # Security: LOYAL, WAVERING, DEFECTED
    # US: RHETORICAL, ECONOMIC, COVERT, KINETIC

    # Higher strike probability when: defection occurs, US is kinetic
    values = []
    for sec in ["LOYAL", "WAVERING", "DEFECTED"]:
        for us in ["RHETORICAL", "ECONOMIC", "COVERT", "KINETIC"]:
            # Base: low strike probability
            p = 0.10

            # Security weakness increases strike likelihood
            if sec == "WAVERING":
                p += 0.15
            elif sec == "DEFECTED":
                p = p_strike

            # US kinetic action emboldens Israel
            if us == "KINETIC":
                p = min(p + 0.20, 0.95)
            elif us == "COVERT":
                p = min(p + 0.10, 0.90)

            values.append([1 - p, p])

    # Transpose to get [RESTRAINED row, STRIKING row] x 12 columns
    values_t = list(zip(*values))

    return TabularCPD(
        variable="Israel_Posture",
        variable_card=2,
        values=list(values_t),
        evidence=["Security_Loyalty", "US_Policy_Disposition"],
        evidence_card=[3, 4],
        state_names={
            "Israel_Posture": ["RESTRAINED", "STRIKING"],
            "Security_Loyalty": ["LOYAL", "WAVERING", "DEFECTED"],
            "US_Policy_Disposition": ["RHETORICAL", "ECONOMIC", "COVERT", "KINETIC"],
        }
    )


def build_russia_posture_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Russia_Posture given Regional_Instability."""
    regional = priors.get("regional_cascade_probabilities", {})

    p_support = get_prob_mode(
        regional.get("russia_support_given_iran_threatened", {}).get("probability", {"mode": 0.25})
    )

    # More support when regional instability is high (Iran threatened)
    values = [
        # Reg=NONE  MODERATE  SEVERE
        [0.95,     0.85,     1 - p_support],  # NEUTRAL
        [0.05,     0.15,     p_support],      # SUPPORTING
    ]

    return TabularCPD(
        variable="Russia_Posture",
        variable_card=2,
        values=values,
        evidence=["Regional_Instability"],
        evidence_card=[3],
        state_names={
            "Russia_Posture": ["NEUTRAL", "SUPPORTING"],
            "Regional_Instability": ["NONE", "MODERATE", "SEVERE"],
        }
    )


def build_gulf_realignment_cpd(priors: dict) -> TabularCPD:
    """Build CPD for Gulf_Realignment given Regime_Outcome."""
    regional = priors.get("regional_cascade_probabilities", {})

    p_realign = get_prob_mode(
        regional.get("gulf_realignment_given_collapse", {}).get("probability", {"mode": 0.70})
    )

    # Regime_Outcome: STATUS_QUO, CONCESSIONS, TRANSITION, COLLAPSE, FRAGMENTATION
    # Realignment most likely if collapse or fragmentation
    values = [
        # SQ    CONC   TRANS   COLLAPSE  FRAG
        [0.95, 0.90,  0.70,   1 - p_realign, 1 - p_realign],  # NO
        [0.05, 0.10,  0.30,   p_realign, p_realign],          # YES
    ]

    return TabularCPD(
        variable="Gulf_Realignment",
        variable_card=2,
        values=values,
        evidence=["Regime_Outcome"],
        evidence_card=[5],
        state_names={
            "Gulf_Realignment": ["NO", "YES"],
            "Regime_Outcome": ["STATUS_QUO", "CONCESSIONS", "TRANSITION", "COLLAPSE", "FRAGMENTATION"],
        }
    )


# =============================================================================
# COMPLEX CPT PLACEHOLDERS
# =============================================================================

def build_protest_escalation_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Protest_Escalation.

    Parent: Economic_Stress
    Should be replaced with reasoning model output.
    """
    trans_probs = priors.get("transition_probabilities", {})
    p_escalate = get_prob_mode(
        trans_probs.get("protests_escalate_14d", {}).get("probability", {"mode": 0.35})
    )

    # Convert window probability to marginal
    p_esc_marginal = window_to_marginal(p_escalate, 14, 90)

    # Economic modifiers from priors
    modifiers = priors.get("economic_modifiers", {})
    crit_mult = modifiers.get("critical_protest_escalation_multiplier", 1.20)
    press_mult = modifiers.get("pressured_protest_escalation_multiplier", 1.10)

    # Apply modifiers
    p_stable = p_esc_marginal
    p_pressured = min(p_esc_marginal * press_mult, 0.95)
    p_critical = min(p_esc_marginal * crit_mult, 0.95)

    values = [
        # Econ=STABLE  PRESSURED  CRITICAL
        [1 - p_stable, 1 - p_pressured, 1 - p_critical],  # NO
        [p_stable, p_pressured, p_critical],              # YES
    ]

    return TabularCPD(
        variable="Protest_Escalation",
        variable_card=2,
        values=values,
        evidence=["Economic_Stress"],
        evidence_card=[3],
        state_names={
            "Protest_Escalation": ["NO", "YES"],
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
        }
    )


def build_protest_sustained_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Protest_Sustained.

    Parents: Protest_Escalation, Regime_Response, Internet_Status
    """
    trans_probs = priors.get("transition_probabilities", {})
    p_sustain = get_prob_mode(
        trans_probs.get("protests_sustain_30d", {}).get("probability", {"mode": 0.45})
    )
    p_collapse_crack = get_prob_mode(
        trans_probs.get("protests_collapse_given_crackdown_30d", {}).get("probability", {"mode": 0.55})
    )
    p_collapse_conc = get_prob_mode(
        trans_probs.get("protests_collapse_given_concessions_30d", {}).get("probability", {"mode": 0.65})
    )

    p_sust_marginal = window_to_marginal(p_sustain, 30, 90)

    # Build CPT: Escalation(2) x Response(4) x Internet(3) = 24 columns
    values_no = []
    values_yes = []

    for esc in ["NO", "YES"]:
        for resp in ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"]:
            for inet in ["ON", "THROTTLED", "OFF"]:
                # Base probability
                if esc == "NO":
                    p = 0.1  # No escalation → low sustained probability
                else:
                    p = p_sust_marginal

                # Regime response effects
                if resp == "CRACKDOWN":
                    p *= (1 - p_collapse_crack)
                elif resp == "CONCESSIONS":
                    p *= (1 - p_collapse_conc)
                elif resp == "SUPPRESSED":
                    p = 0.05

                # Internet effects (blackouts hurt coordination)
                if inet == "THROTTLED":
                    p *= 0.7
                elif inet == "OFF":
                    p *= 0.3

                p = max(min(p, 0.95), 0.05)
                values_no.append(1 - p)
                values_yes.append(p)

    return TabularCPD(
        variable="Protest_Sustained",
        variable_card=2,
        values=[values_no, values_yes],
        evidence=["Protest_Escalation", "Regime_Response", "Internet_Status"],
        evidence_card=[2, 4, 3],
        state_names={
            "Protest_Sustained": ["NO", "YES"],
            "Protest_Escalation": ["NO", "YES"],
            "Regime_Response": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
            "Internet_Status": ["ON", "THROTTLED", "OFF"],
        }
    )


def build_protest_state_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Protest_State.

    Parents: Protest_Escalation, Protest_Sustained
    States: DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED

    Note: Regime_Response removed as parent to break cycle.
    Protest state is determined by escalation and sustainability.
    """
    # 2 x 2 = 4 columns
    # This is a complex CPT - placeholder uses simplified logic
    values = []

    for esc in [0, 1]:  # NO, YES
        for sust in [0, 1]:  # NO, YES
            col = [0.0] * 5  # DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED

            if esc == 0:  # No escalation
                if sust == 0:
                    # No escalation, not sustained -> declining
                    col[0] = 0.65  # DECLINING
                    col[1] = 0.30  # STABLE
                    col[4] = 0.05  # COLLAPSED (protests fizzle out)
                else:
                    # No escalation but sustained -> stable
                    col[1] = 0.60  # STABLE
                    col[0] = 0.30  # DECLINING
                    col[2] = 0.10  # Some escalation possible
            else:  # Escalation occurred
                if sust == 0:
                    # Escalated but not sustained -> escalating but may decline
                    col[2] = 0.50  # ESCALATING
                    col[0] = 0.30  # DECLINING
                    col[1] = 0.15  # STABLE
                    col[4] = 0.05  # Could collapse
                else:
                    # Escalated and sustained -> can become organized
                    col[3] = 0.35  # ORGANIZED
                    col[2] = 0.40  # ESCALATING
                    col[1] = 0.20  # STABLE
                    col[0] = 0.05  # Low chance of declining

            values.append(col)

    # Transpose
    values_t = list(zip(*values))

    return TabularCPD(
        variable="Protest_State",
        variable_card=5,
        values=[list(row) for row in values_t],
        evidence=["Protest_Escalation", "Protest_Sustained"],
        evidence_card=[2, 2],
        state_names={
            "Protest_State": ["DECLINING", "STABLE", "ESCALATING", "ORGANIZED", "COLLAPSED"],
            "Protest_Escalation": ["NO", "YES"],
            "Protest_Sustained": ["NO", "YES"],
        }
    )


def build_internet_status_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Internet_Status given Regime_Response."""
    # Parent: Regime_Response (4 states)
    # Higher crackdown → more likely blackout
    values = [
        # Resp=STATUS_QUO  CRACKDOWN  CONCESSIONS  SUPPRESSED
        [0.9,              0.3,       0.8,         0.1],  # ON
        [0.08,             0.4,       0.15,        0.3],  # THROTTLED
        [0.02,             0.3,       0.05,        0.6],  # OFF
    ]

    return TabularCPD(
        variable="Internet_Status",
        variable_card=3,
        values=values,
        evidence=["Regime_Response"],
        evidence_card=[4],
        state_names={
            "Internet_Status": ["ON", "THROTTLED", "OFF"],
            "Regime_Response": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
        }
    )


def build_regime_response_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Regime_Response.

    Parents: Economic_Stress, Regional_Instability
    (Economic_Stress serves as proxy for protest pressure in equilibrium model)
    """
    trans_probs = priors.get("transition_probabilities", {})
    p_crackdown = get_prob_mode(
        trans_probs.get("mass_casualty_crackdown_given_escalation", {}).get("probability", {"mode": 0.4})
    )
    p_concessions = get_prob_mode(
        trans_probs.get("meaningful_concessions_given_protests_30d", {}).get("probability", {"mode": 0.15})
    )

    # 3 x 3 = 9 columns
    # Economic_Stress: STABLE, PRESSURED, CRITICAL
    # Regional_Instability: NONE, MODERATE, SEVERE
    values = []

    for econ in range(3):  # Economic stress
        for reg in range(3):  # Regional instability
            col = [0.0] * 4  # STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED

            if econ == 0:  # STABLE - economy OK, little protest pressure
                col[0] = 0.75  # STATUS_QUO most likely
                col[1] = 0.10  # Some baseline crackdown
                col[2] = 0.10  # Some concessions
                col[3] = 0.05  # Low suppression
            elif econ == 1:  # PRESSURED - moderate protest pressure
                col[0] = 0.40
                col[1] = p_crackdown * 0.7  # Moderate crackdown
                col[2] = p_concessions  # Concessions possible
                col[3] = 0.15
            else:  # CRITICAL - high protest pressure
                # Regional instability increases crackdown likelihood
                crack_mult = 1.0 + reg * 0.15
                col[1] = min(p_crackdown * crack_mult, 0.55)
                col[2] = p_concessions * 0.5  # Less likely to concede under pressure
                col[0] = 0.20
                col[3] = max(0.10, 1 - col[0] - col[1] - col[2])

            # Normalize
            total = sum(col)
            col = [c / total if total > 0 else 0.25 for c in col]
            values.append(col)

    values_t = list(zip(*values))

    return TabularCPD(
        variable="Regime_Response",
        variable_card=4,
        values=[list(row) for row in values_t],
        evidence=["Economic_Stress", "Regional_Instability"],
        evidence_card=[3, 3],
        state_names={
            "Regime_Response": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
            "Regional_Instability": ["NONE", "MODERATE", "SEVERE"],
        }
    )


def build_security_loyalty_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Security_Loyalty.

    Parents: Economic_Stress, Protest_State, Regime_Response
    """
    trans_probs = priors.get("transition_probabilities", {})
    p_defect = get_prob_mode(
        trans_probs.get("security_force_defection_given_protests_30d", {}).get("probability", {"mode": 0.08})
    )

    modifiers = priors.get("economic_modifiers", {})
    crit_mult = modifiers.get("critical_security_defection_multiplier", 1.15)
    press_mult = modifiers.get("pressured_security_defection_multiplier", 1.08)

    # 3 x 5 x 4 = 60 columns
    values = []

    for econ in range(3):  # STABLE, PRESSURED, CRITICAL
        for prot in range(5):  # Protest states
            for resp in range(4):  # Regime responses
                col = [0.0] * 3  # LOYAL, WAVERING, DEFECTED

                # Base defection probability
                p_def = p_defect

                # Economic modifier
                if econ == 1:  # PRESSURED
                    p_def *= press_mult
                elif econ == 2:  # CRITICAL
                    p_def *= crit_mult

                # Protest state modifier
                if prot in [0, 4]:  # DECLINING or COLLAPSED
                    p_def = 0.0  # No defection when protests weak
                elif prot == 3:  # ORGANIZED
                    p_def *= 1.5
                elif prot == 2:  # ESCALATING
                    p_def *= 1.2

                # Concession dampening
                if resp == 2:  # CONCESSIONS
                    p_def *= 0.7

                p_def = min(p_def, 0.15)  # Cap at 15%

                # Wavering is ~2-3x defection
                p_waver = min(p_def * 2.5, 0.3)
                p_loyal = max(1 - p_def - p_waver, 0.55)

                # Normalize
                total = p_loyal + p_waver + p_def
                col = [p_loyal / total, p_waver / total, p_def / total]
                values.append(col)

    values_t = list(zip(*values))

    return TabularCPD(
        variable="Security_Loyalty",
        variable_card=3,
        values=[list(row) for row in values_t],
        evidence=["Economic_Stress", "Protest_State", "Regime_Response"],
        evidence_card=[3, 5, 4],
        state_names={
            "Security_Loyalty": ["LOYAL", "WAVERING", "DEFECTED"],
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
            "Protest_State": ["DECLINING", "STABLE", "ESCALATING", "ORGANIZED", "COLLAPSED"],
            "Regime_Response": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
        }
    )


def build_elite_cohesion_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Elite_Cohesion.

    Parents: Economic_Stress, Security_Loyalty

    Note: This uses a "tipping point" model - elite cohesion remains high
    until a critical threshold is reached, then collapses rapidly.
    """
    trans_probs = priors.get("transition_probabilities", {})
    p_fracture = get_prob_mode(
        trans_probs.get("elite_fracture_given_economic_collapse", {}).get("probability", {"mode": 0.3})
    )

    # 3 x 3 = 9 columns
    # Economic: STABLE, PRESSURED, CRITICAL
    # Security: LOYAL, WAVERING, DEFECTED
    values = []

    for econ in range(3):
        for sec in range(3):
            col = [0.0] * 3  # COHESIVE, FRACTURED, COLLAPSED

            # Tipping point logic
            if sec == 2:  # DEFECTED - always triggers fracture
                if econ == 2:  # CRITICAL + DEFECTED = COLLAPSE
                    col = [0.05, 0.25, 0.70]
                else:
                    col = [0.10, 0.60, 0.30]
            elif sec == 1:  # WAVERING
                if econ == 2:  # CRITICAL
                    col = [0.20, p_fracture * 1.5, 1 - 0.20 - p_fracture * 1.5]
                elif econ == 1:  # PRESSURED
                    col = [0.50, p_fracture, 0.50 - p_fracture]
                else:
                    col = [0.75, 0.20, 0.05]
            else:  # LOYAL
                if econ == 2:
                    col = [0.50, p_fracture, 0.50 - p_fracture]
                elif econ == 1:
                    col = [0.75, 0.20, 0.05]
                else:
                    col = [0.90, 0.08, 0.02]

            # Normalize
            total = sum(col)
            col = [c / total for c in col]
            values.append(col)

    values_t = list(zip(*values))

    return TabularCPD(
        variable="Elite_Cohesion",
        variable_card=3,
        values=[list(row) for row in values_t],
        evidence=["Economic_Stress", "Security_Loyalty"],
        evidence_card=[3, 3],
        state_names={
            "Elite_Cohesion": ["COHESIVE", "FRACTURED", "COLLAPSED"],
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
            "Security_Loyalty": ["LOYAL", "WAVERING", "DEFECTED"],
        }
    )


def build_ethnic_uprising_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Ethnic_Uprising.

    Parents: Protest_Sustained, Economic_Stress
    """
    trans_probs = priors.get("transition_probabilities", {})
    p_ethnic = get_prob_mode(
        trans_probs.get("ethnic_coordination_given_protests_30d", {}).get("probability", {"mode": 0.25})
    )

    p_ethnic_marginal = window_to_marginal(p_ethnic, 60, 90)

    # 2 x 3 = 6 columns
    values = []

    for sust in [0, 1]:  # NO, YES
        for econ in range(3):  # STABLE, PRESSURED, CRITICAL
            if sust == 0:
                p = 0.02  # Low probability without sustained protests
            else:
                p = p_ethnic_marginal
                # Economic stress increases ethnic mobilization
                if econ == 1:
                    p *= 1.15
                elif econ == 2:
                    p *= 1.30

            p = min(p, 0.5)
            values.append([1 - p, p])

    values_t = list(zip(*values))

    return TabularCPD(
        variable="Ethnic_Uprising",
        variable_card=2,
        values=[list(row) for row in values_t],
        evidence=["Protest_Sustained", "Economic_Stress"],
        evidence_card=[2, 3],
        state_names={
            "Ethnic_Uprising": ["NO", "YES"],
            "Protest_Sustained": ["NO", "YES"],
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
        }
    )


def build_regional_instability_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Regional_Instability.

    Parents: US_Policy_Disposition, Economic_Stress
    (Economic_Stress serves as proxy for Iran crisis severity in equilibrium model)
    """
    # 4 x 3 = 12 columns
    # US: RHETORICAL, ECONOMIC, COVERT, KINETIC
    # Economic: STABLE, PRESSURED, CRITICAL
    values = []

    for us in range(4):
        for econ in range(3):
            col = [0.0] * 3  # NONE, MODERATE, SEVERE

            # Base on economic stress (proxy for crisis severity)
            if econ == 0:  # STABLE - low crisis
                col = [0.75, 0.20, 0.05]
            elif econ == 1:  # PRESSURED - moderate crisis
                col = [0.45, 0.40, 0.15]
            else:  # CRITICAL - high crisis
                col = [0.20, 0.40, 0.40]

            # US policy action increases instability
            if us == 3:  # KINETIC
                col[2] += 0.25
                col[0] -= 0.20
                col[1] -= 0.05
            elif us == 2:  # COVERT
                col[2] += 0.10
                col[1] += 0.05
                col[0] -= 0.15
            elif us == 1:  # ECONOMIC
                col[1] += 0.10
                col[0] -= 0.10

            # Normalize
            col = [max(c, 0.01) for c in col]
            total = sum(col)
            col = [c / total for c in col]
            values.append(col)

    values_t = list(zip(*values))

    return TabularCPD(
        variable="Regional_Instability",
        variable_card=3,
        values=[list(row) for row in values_t],
        evidence=["US_Policy_Disposition", "Economic_Stress"],
        evidence_card=[4, 3],
        state_names={
            "Regional_Instability": ["NONE", "MODERATE", "SEVERE"],
            "US_Policy_Disposition": ["RHETORICAL", "ECONOMIC", "COVERT", "KINETIC"],
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
        }
    )


def build_regime_outcome_cpd_placeholder(priors: dict) -> TabularCPD:
    """Placeholder CPD for Regime_Outcome (terminal node).

    Parents: Security_Loyalty, Succession_Type, Fragmentation_Outcome, Elite_Cohesion
    """
    regime_probs = priors.get("regime_outcomes", {})
    trans_probs = priors.get("transition_probabilities", {})

    # Get base probabilities
    p_sq = get_prob_mode(
        regime_probs.get("REGIME_SURVIVES_STATUS_QUO", {}).get("probability", {"mode": 0.55})
    )
    p_conc = get_prob_mode(
        regime_probs.get("REGIME_SURVIVES_WITH_CONCESSIONS", {}).get("probability", {"mode": 0.15})
    )
    p_trans = get_prob_mode(
        regime_probs.get("MANAGED_TRANSITION", {}).get("probability", {"mode": 0.10})
    )
    p_coll = get_prob_mode(
        regime_probs.get("REGIME_COLLAPSE_CHAOTIC", {}).get("probability", {"mode": 0.12})
    )
    p_frag = get_prob_mode(
        regime_probs.get("ETHNIC_FRAGMENTATION", {}).get("probability", {"mode": 0.08})
    )

    p_collapse_defect = get_prob_mode(
        trans_probs.get("regime_collapse_given_defection", {}).get("probability", {"mode": 0.65})
    )

    # 3 x 2 x 2 x 3 = 36 columns
    # Security: LOYAL, WAVERING, DEFECTED
    # Succession: ORDERLY, CHAOTIC
    # Fragmentation: NO, YES
    # Elite: COHESIVE, FRACTURED, COLLAPSED
    values = []

    for sec in range(3):
        for succ in range(2):
            for frag in range(2):
                for elite in range(3):
                    col = [0.0] * 5  # SQ, CONC, TRANS, COLLAPSE, FRAG

                    # Fragmentation outcome overrides others
                    if frag == 1:  # Fragmentation occurred
                        col[4] = 0.7  # FRAGMENTATION likely
                        col[3] = 0.2  # Some collapse
                        col[0] = 0.1
                    elif sec == 2:  # Defection occurred
                        col[3] = p_collapse_defect  # High collapse probability
                        col[2] = 0.2  # Some transition possible
                        col[4] = 0.1
                        col[0] = 1 - col[3] - col[2] - col[4]
                    elif elite == 2:  # Elite collapsed
                        col[3] = 0.5  # Collapse likely
                        col[2] = 0.3  # Transition possible
                        col[4] = 0.15
                        col[0] = 0.05
                    elif succ == 1:  # Chaotic succession
                        col[2] = 0.4  # Transition
                        col[3] = 0.3  # Collapse
                        col[0] = 0.2
                        col[1] = 0.1
                    elif elite == 1:  # Elite fractured
                        col[1] = 0.3  # Concessions likely
                        col[2] = 0.25
                        col[0] = 0.35
                        col[3] = 0.1
                    elif sec == 1:  # Wavering
                        col[0] = 0.4
                        col[1] = 0.3
                        col[2] = 0.2
                        col[3] = 0.1
                    else:  # All stable
                        col[0] = p_sq / (p_sq + p_conc) * 0.9
                        col[1] = p_conc / (p_sq + p_conc) * 0.9
                        col[2] = 0.05
                        col[3] = 0.03
                        col[4] = 0.02

                    # Normalize
                    total = sum(col)
                    col = [c / total if total > 0 else 0.2 for c in col]
                    values.append(col)

    values_t = list(zip(*values))

    return TabularCPD(
        variable="Regime_Outcome",
        variable_card=5,
        values=[list(row) for row in values_t],
        evidence=["Security_Loyalty", "Succession_Type", "Fragmentation_Outcome", "Elite_Cohesion"],
        evidence_card=[3, 2, 2, 3],
        state_names={
            "Regime_Outcome": ["STATUS_QUO", "CONCESSIONS", "TRANSITION", "COLLAPSE", "FRAGMENTATION"],
            "Security_Loyalty": ["LOYAL", "WAVERING", "DEFECTED"],
            "Succession_Type": ["ORDERLY", "CHAOTIC"],
            "Fragmentation_Outcome": ["NO", "YES"],
            "Elite_Cohesion": ["COHESIVE", "FRACTURED", "COLLAPSED"],
        }
    )


# =============================================================================
# CAUSAL ENGINE CLASS
# =============================================================================

class CausalEngine:
    """Wrapper for pgmpy Bayesian Network with causal query interface.

    Provides:
    - infer(): Query P(Outcome | evidence)
    - sensitivity(): Which parents most affect target node?
    - what_if(): P(query | do(intervention)) using do-calculus
    - load_cpt(): Load CPT values from JSON files
    """

    def __init__(self, priors_path: str | Path, intel_path: str | Path | None = None,
                 cpt_dir: str | Path | None = None):
        """Initialize CausalEngine with priors and optional intel.

        Args:
            priors_path: Path to analyst_priors.json
            intel_path: Optional path to iran_crisis_intel.json for evidence
            cpt_dir: Optional path to directory containing CPT JSON files
        """
        self.priors_path = Path(priors_path)
        self.intel_path = Path(intel_path) if intel_path else None
        self.cpt_dir = Path(cpt_dir) if cpt_dir else None

        self.priors = load_json(self.priors_path)
        self.intel = load_json(self.intel_path) if self.intel_path else None

        self.model = self._build_model()
        self._inference = None

        # Load custom CPTs if directory provided
        if self.cpt_dir and self.cpt_dir.exists():
            self.load_cpts_from_dir(self.cpt_dir)

    def _build_model(self) -> BayesianNetwork:
        """Build complete BN with all CPDs."""
        model = build_dag()

        # Add simple CPDs
        model.add_cpds(
            build_rial_rate_cpd(self.priors, self.intel),
            build_inflation_cpd(self.priors, self.intel),
            build_khamenei_health_cpd(self.priors),
            build_us_policy_cpd(self.priors),
            build_economic_stress_cpd(self.priors),
            build_succession_type_cpd(self.priors),
            build_fragmentation_outcome_cpd(self.priors),
            build_iraq_stability_cpd(self.priors),
            build_syria_stability_cpd(self.priors),
            build_israel_posture_cpd(self.priors),
            build_russia_posture_cpd(self.priors),
            build_gulf_realignment_cpd(self.priors),
        )

        # Add complex CPDs (placeholders)
        model.add_cpds(
            build_protest_escalation_cpd_placeholder(self.priors),
            build_protest_sustained_cpd_placeholder(self.priors),
            build_protest_state_cpd_placeholder(self.priors),
            build_internet_status_cpd_placeholder(self.priors),
            build_regime_response_cpd_placeholder(self.priors),
            build_security_loyalty_cpd_placeholder(self.priors),
            build_elite_cohesion_cpd_placeholder(self.priors),
            build_ethnic_uprising_cpd_placeholder(self.priors),
            build_regional_instability_cpd_placeholder(self.priors),
            build_regime_outcome_cpd_placeholder(self.priors),
        )

        return model

    def load_cpts_from_dir(self, cpt_dir: Path):
        """Load CPT values from JSON files in directory.

        Expected JSON format:
        {
            "variable": "NodeName",
            "states": ["State1", "State2", ...],
            "parents": ["Parent1", "Parent2", ...],
            "parent_states": {
                "Parent1": ["State1", "State2", ...],
                ...
            },
            "values": [[...], [...], ...]  # rows=child states, cols=parent combinations
        }

        Args:
            cpt_dir: Directory containing CPT JSON files (*.json)
        """
        for cpt_file in cpt_dir.glob("*.json"):
            try:
                cpt_data = load_json(cpt_file)
                self._load_single_cpt(cpt_data)
                print(f"Loaded CPT from {cpt_file.name}")
            except Exception as e:
                print(f"Warning: Failed to load {cpt_file.name}: {e}")

    def _load_single_cpt(self, cpt_data: dict):
        """Load a single CPT from parsed JSON data."""
        variable = cpt_data["variable"]
        states = cpt_data["states"]
        values = np.array(cpt_data["values"])

        parents = cpt_data.get("parents", [])
        parent_states = cpt_data.get("parent_states", {})

        # Build state_names dict
        state_names = {variable: states}
        evidence_card = []
        for parent in parents:
            if parent in parent_states:
                state_names[parent] = parent_states[parent]
                evidence_card.append(len(parent_states[parent]))

        # Create new CPD
        if parents:
            new_cpd = TabularCPD(
                variable=variable,
                variable_card=len(states),
                values=values.tolist(),
                evidence=parents,
                evidence_card=evidence_card,
                state_names=state_names
            )
        else:
            new_cpd = TabularCPD(
                variable=variable,
                variable_card=len(states),
                values=values.tolist(),
                state_names=state_names
            )

        # Remove old CPD and add new one
        old_cpd = self.model.get_cpds(variable)
        if old_cpd:
            self.model.remove_cpds(old_cpd)
        self.model.add_cpds(new_cpd)

        # Reset inference cache
        self._inference = None

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the model structure and CPDs.

        Returns:
            (is_valid, list of error messages)
        """
        errors = []

        # Check DAG is acyclic
        try:
            g = nx.DiGraph(EDGES)
            if not nx.is_directed_acyclic_graph(g):
                errors.append("Graph contains cycles")
        except Exception as e:
            errors.append(f"Graph structure error: {e}")

        # Check model validity
        try:
            if not self.model.check_model():
                errors.append("pgmpy model.check_model() failed")
        except Exception as e:
            errors.append(f"Model check error: {e}")

        # Check CPD column sums
        for cpd in self.model.get_cpds():
            values = cpd.get_values()
            col_sums = values.sum(axis=0)
            if not np.allclose(col_sums, 1.0, atol=0.01):
                errors.append(f"CPD {cpd.variable}: columns don't sum to 1.0")

        return len(errors) == 0, errors

    @property
    def inference(self) -> VariableElimination:
        """Lazy-load inference engine."""
        if self._inference is None:
            self._inference = VariableElimination(self.model)
        return self._inference

    def infer(self, evidence: dict[str, str]) -> dict[str, np.ndarray]:
        """Query posterior distribution given evidence.

        Args:
            evidence: Dict mapping node names to observed states

        Returns:
            Dict mapping query nodes to probability arrays

        Example:
            engine.infer({"Economic_Stress": "CRITICAL"})
            # Returns: {"Regime_Outcome": array([0.45, 0.12, 0.08, 0.25, 0.10])}
        """
        # Query all nodes not in evidence
        query_nodes = [n for n in ALL_NODES if n not in evidence]

        results = {}
        for node in query_nodes:
            try:
                result = self.inference.query([node], evidence=evidence)
                results[node] = result.values
            except Exception as e:
                print(f"Warning: Could not query {node}: {e}")

        return results

    def compute_surprise(self, posterior: dict[str, float], target: str = "Regime_Outcome") -> dict[str, Any]:
        """Compute surprise score as KL divergence between posterior and prior.

        High surprise indicates the model found a hidden correlation the analyst missed.

        Args:
            posterior: Dict mapping states to posterior probabilities
            target: Target node (default: Regime_Outcome)

        Returns:
            Dict with surprise_score, surprise_flag, and surprise_drivers
        """
        # Get prior distribution from analyst_priors
        prior = self._get_analyst_prior(target)

        # Compute KL divergence: sum(P * log(P/Q))
        surprise = 0.0
        state_surprises = {}

        for state, p in posterior.items():
            q = prior.get(state, 0.01)  # Avoid division by zero
            if p > 0.001:
                state_surprise = p * math.log2(p / max(q, 0.001))
                surprise += state_surprise
                state_surprises[state] = state_surprise

        # Identify top surprise drivers
        sorted_states = sorted(state_surprises.items(), key=lambda x: abs(x[1]), reverse=True)
        surprise_drivers = [s[0] for s in sorted_states[:2] if abs(s[1]) > 0.05]

        # Flag if surprise exceeds threshold
        surprise_threshold = 0.3
        surprise_flag = surprise > surprise_threshold

        return {
            "surprise_score": float(surprise),
            "surprise_flag": surprise_flag,
            "surprise_drivers": surprise_drivers,
            "state_surprises": {k: float(v) for k, v in state_surprises.items()},
        }

    def _get_analyst_prior(self, target: str) -> dict[str, float]:
        """Get analyst prior distribution for a target node."""
        if target == "Regime_Outcome":
            regime_probs = self.priors.get("regime_outcomes", {})
            prior_map = {
                "STATUS_QUO": "REGIME_SURVIVES_STATUS_QUO",
                "CONCESSIONS": "REGIME_SURVIVES_WITH_CONCESSIONS",
                "TRANSITION": "MANAGED_TRANSITION",
                "COLLAPSE": "REGIME_COLLAPSE_CHAOTIC",
                "FRAGMENTATION": "ETHNIC_FRAGMENTATION",
            }
            prior = {}
            for bn_name, prior_name in prior_map.items():
                prob_data = regime_probs.get(prior_name, {}).get("probability", {})
                prior[bn_name] = get_prob_mode(prob_data) if prob_data else 0.2
            return prior
        else:
            # Default uniform prior for other nodes
            states = ALL_NODES.get(target, [])
            return {s: 1.0 / len(states) for s in states} if states else {}

    def infer_with_surprise(self, target: str, evidence: dict[str, str]) -> dict[str, Any]:
        """Query target node with surprise analysis.

        Args:
            target: Node to query
            evidence: Observed evidence

        Returns:
            Dict with posterior, surprise_score, surprise_flag, and surprise_drivers
        """
        posterior = self.infer_single(target, evidence)
        surprise_info = self.compute_surprise(posterior, target)

        return {
            "posterior": posterior,
            "evidence": evidence,
            **surprise_info,
        }

    def infer_single(self, target: str, evidence: dict[str, str]) -> dict[str, float]:
        """Query single target node given evidence.

        Args:
            target: Node to query
            evidence: Observed evidence

        Returns:
            Dict mapping state names to probabilities
        """
        result = self.inference.query([target], evidence=evidence)
        states = ALL_NODES[target]
        return {state: float(prob) for state, prob in zip(states, result.values)}

    def sensitivity(self, target: str = "Regime_Outcome") -> dict[str, float]:
        """Compute sensitivity of target to each parent using mutual information.

        Args:
            target: Target node to analyze

        Returns:
            Dict mapping parent names to mutual information values
        """
        parents = get_parents(target)
        sensitivities = {}

        # Get marginal distribution of target
        p_target = self.inference.query([target]).values
        h_target = -np.sum(p_target * np.log2(p_target + 1e-10))

        for parent in parents:
            # Get joint distribution
            try:
                joint = self.inference.query([target, parent])
                joint_values = joint.values

                # Compute conditional entropy H(Target | Parent)
                p_parent = self.inference.query([parent]).values
                h_cond = 0

                for i, p_par in enumerate(p_parent):
                    if p_par > 0:
                        # P(Target | Parent = i)
                        p_cond = joint_values[:, i] / (p_par + 1e-10)
                        h_cond += p_par * (-np.sum(p_cond * np.log2(p_cond + 1e-10)))

                # Mutual information I(Target; Parent) = H(Target) - H(Target | Parent)
                mi = h_target - h_cond
                sensitivities[parent] = float(max(mi, 0))
            except Exception as e:
                print(f"Warning: Could not compute sensitivity for {parent}: {e}")
                sensitivities[parent] = 0.0

        # Sort by sensitivity (descending)
        return dict(sorted(sensitivities.items(), key=lambda x: x[1], reverse=True))

    def what_if(self, intervention: dict[str, str], query: str) -> dict[str, float]:
        """Causal intervention query using do-calculus.

        Computes P(query | do(intervention)) by removing edges into intervened nodes.

        Args:
            intervention: Dict of node→state to intervene on
            query: Node to query

        Returns:
            Dict mapping states to probabilities
        """
        # Create modified model with edges removed
        modified_edges = [
            edge for edge in EDGES
            if edge[1] not in intervention
        ]

        modified_model = BayesianNetwork(modified_edges)

        # Copy CPDs, modifying intervened nodes to be deterministic
        for cpd in self.model.get_cpds():
            if cpd.variable in intervention:
                # Create deterministic CPD
                state_idx = ALL_NODES[cpd.variable].index(intervention[cpd.variable])
                new_values = np.zeros((len(ALL_NODES[cpd.variable]), 1))
                new_values[state_idx] = 1.0

                new_cpd = TabularCPD(
                    variable=cpd.variable,
                    variable_card=len(ALL_NODES[cpd.variable]),
                    values=new_values,
                    state_names={cpd.variable: ALL_NODES[cpd.variable]}
                )
                modified_model.add_cpds(new_cpd)
            else:
                # Check if this CPD needs to be modified (parent removed)
                original_parents = get_parents(cpd.variable)
                new_parents = [p for p in original_parents if p not in intervention]

                if len(new_parents) < len(original_parents):
                    # Need to marginalize out intervened parents
                    # For simplicity, just use the original CPD with intervention as evidence
                    modified_model.add_cpds(cpd)
                else:
                    modified_model.add_cpds(cpd)

        # Query the modified model
        try:
            inference = VariableElimination(modified_model)
            result = inference.query([query], evidence=intervention)
            states = ALL_NODES[query]
            return {state: float(prob) for state, prob in zip(states, result.values)}
        except Exception as e:
            print(f"Warning: what_if query failed: {e}")
            return {state: 0.0 for state in ALL_NODES[query]}

    def compare_to_mc(self, mc_results_path: str | Path) -> dict[str, Any]:
        """Compare BN marginals to Monte Carlo simulation results.

        Args:
            mc_results_path: Path to simulation_results.json

        Returns:
            Comparison metrics including KL divergence and max difference
        """
        mc_results = load_json(Path(mc_results_path))

        # Get BN marginal for Regime_Outcome
        bn_result = self.inference.query(["Regime_Outcome"])
        bn_dist = bn_result.values

        # Get MC distribution - try both possible keys
        outcomes = mc_results.get("outcome_distribution", mc_results.get("outcomes", {}))
        mc_outcomes = ["REGIME_SURVIVES_STATUS_QUO", "REGIME_SURVIVES_WITH_CONCESSIONS",
                       "MANAGED_TRANSITION", "REGIME_COLLAPSE_CHAOTIC", "ETHNIC_FRAGMENTATION"]
        bn_outcomes = ["STATUS_QUO", "CONCESSIONS", "TRANSITION", "COLLAPSE", "FRAGMENTATION"]

        mc_dist = []
        # Try to get probability directly, fallback to count-based calculation
        for o in mc_outcomes:
            outcome_data = outcomes.get(o, {})
            if "probability" in outcome_data:
                mc_dist.append(outcome_data["probability"])
            elif "count" in outcome_data:
                total = sum(outcomes.get(x, {}).get("count", 0) for x in mc_outcomes)
                mc_dist.append(outcome_data["count"] / total if total > 0 else 0.2)
            else:
                mc_dist.append(0.2)  # Fallback
        mc_dist = np.array(mc_dist)

        # Compute metrics
        kl_div = np.sum(mc_dist * np.log2((mc_dist + 1e-10) / (bn_dist + 1e-10)))
        total_var = np.sum(np.abs(bn_dist - mc_dist)) / 2
        max_diff = np.max(np.abs(bn_dist - mc_dist))

        return {
            "bn_distribution": {bn_outcomes[i]: float(bn_dist[i]) for i in range(5)},
            "mc_distribution": {bn_outcomes[i]: float(mc_dist[i]) for i in range(5)},
            "kl_divergence": float(kl_div),
            "total_variation": float(total_var),
            "max_difference": float(max_diff),
            "validation": {
                "kl_pass": kl_div < 0.10,
                "max_diff_pass": max_diff < 0.08,
            }
        }

    def check_black_swan_preservation(self) -> dict[str, Any]:
        """Check that BN preserves low-probability but significant outcomes.

        For any outcome with analyst prior > 1%, BN should output > 0.5%.
        """
        regime_probs = self.priors.get("regime_outcomes", {})
        bn_result = self.inference.query(["Regime_Outcome"])
        bn_dist = bn_result.values

        # Map priors outcome names to BN outcome names
        name_map = {
            "REGIME_SURVIVES_STATUS_QUO": 0,
            "REGIME_SURVIVES_WITH_CONCESSIONS": 1,
            "MANAGED_TRANSITION": 2,
            "REGIME_COLLAPSE_CHAOTIC": 3,
            "ETHNIC_FRAGMENTATION": 4,
        }

        results = {}
        failures = []

        for prior_name, idx in name_map.items():
            prior_data = regime_probs.get(prior_name, {})
            prior_prob = get_prob_mode(prior_data.get("probability", {"mode": 0.0}))
            bn_prob = float(bn_dist[idx])

            passed = True
            if prior_prob > 0.01 and bn_prob < 0.005:
                passed = False
                failures.append(f"{prior_name}: analyst={prior_prob:.2%}, BN={bn_prob:.2%}")

            results[prior_name] = {
                "analyst_prior": prior_prob,
                "bn_probability": bn_prob,
                "passed": passed,
            }

        return {
            "outcomes": results,
            "all_passed": len(failures) == 0,
            "failures": failures,
        }


# =============================================================================
# PROMPT EXPORT
# =============================================================================

def export_cpt_prompts(output_dir: Path, priors: dict):
    """Export CPT derivation prompts for reasoning model.

    Args:
        output_dir: Directory to write prompt files
        priors: Analyst priors for reference
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Common header
    header = """# CPT Derivation Request

You are a Geopolitical Actuary. Your task is to fill a Conditional Probability Table (CPT)
for a Bayesian Network modeling the Iran crisis simulation.

## Window-to-Marginal Conversion Formula

For converting window probabilities to BN marginals:
```python
def window_to_marginal(p_window, window_days, total_days=90):
    expected_onset = window_days / 2
    duration_if_occurs = total_days - expected_onset
    return p_window * (duration_if_occurs / total_days)
```

## Output Format Requirements

Return your CPT as a JSON object with this structure:
```json
{
  "cpt_values": {
    "columns": [
      {"Parent1": "State1", "Parent2": "State1"},
      ...
    ],
    "rows": ["ChildState1", "ChildState2", ...],
    "matrix": [[...], [...], ...]
  },
  "derivation_steps": [
    "Step 1: ...",
    "Step 2: ...",
    ...
  ],
  "validation": {
    "column_sums": "all 1.0",
    "probability_range": [min, max]
  }
}
```

## Constraints
1. Each column must sum to exactly 1.0
2. All probabilities must be in [0, 1]
3. Provide reasoning for each probability assignment

"""

    # Security_Loyalty prompt
    security_loyalty_prompt = header + f"""## CPT: P(Security_Loyalty | Economic_Stress, Protest_State, Regime_Response)

### Node Definitions
- **Security_Loyalty**: {{LOYAL, WAVERING, DEFECTED}} (3 states)
- **Economic_Stress**: {{STABLE, PRESSURED, CRITICAL}} (3 states)
- **Protest_State**: {{DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED}} (5 states)
- **Regime_Response**: {{STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED}} (4 states)

Total CPT size: 3 × 3 × 5 × 4 = 180 parameters (60 independent columns × 3 rows)

### Source Priors
```json
{json.dumps(priors.get("transition_probabilities", {}).get("security_force_defection_given_protests_30d", {}), indent=2)}
```

### Economic Modifiers
```json
{json.dumps(priors.get("economic_modifiers", {}), indent=2)}
```

### Historical Anchor
- 0 defections in 5 major Iranian protests (1999, 2009, 2017-18, 2019, 2022)
- Current 8% estimate elevated due to unprecedented protest scale/diversity

### Modifier Rules
1. **Economic modifier**:
   - CRITICAL: multiply base by 1.15
   - PRESSURED: multiply base by 1.08
   - STABLE: no modifier

2. **Concession dampening**:
   - If Regime_Response == CONCESSIONS: multiply by 0.7

3. **Condition for defection**:
   - Only if Protest_State in {{STABLE, ESCALATING, ORGANIZED}}
   - If Protest_State == COLLAPSED or DECLINING: defection probability → 0

4. **Wavering**:
   - P(WAVERING) should be ~2-3× P(DEFECTED) in relevant conditions
   - P(LOYAL) is the complement

### Constraints
1. Each column must sum to 1.0
2. P(DEFECTED) must be 0 when Protest_State ∈ {{COLLAPSED, DECLINING}}
3. P(DEFECTED) maximum should not exceed ~0.12 (CRITICAL + no concessions)
"""

    with open(output_dir / "security_loyalty.md", "w") as f:
        f.write(security_loyalty_prompt)

    # Elite_Cohesion prompt (with tipping point note)
    elite_cohesion_prompt = header + f"""## CPT: P(Elite_Cohesion | Economic_Stress, Security_Loyalty)

### Node Definitions
- **Elite_Cohesion**: {{COHESIVE, FRACTURED, COLLAPSED}} (3 states)
- **Economic_Stress**: {{STABLE, PRESSURED, CRITICAL}} (3 states)
- **Security_Loyalty**: {{LOYAL, WAVERING, DEFECTED}} (3 states)

Total CPT size: 3 × 3 × 3 = 27 parameters (9 columns × 3 rows)

### Source Priors
```json
{json.dumps(priors.get("transition_probabilities", {}).get("elite_fracture_given_economic_collapse", {}), indent=2)}
```

### CRITICAL: Tipping Point Model

Elite fractures are rare but catastrophic. This CPT should NOT be linear.

**The correct model:**
- Elite Cohesion remains HIGH even under stress
- UNTIL a "Tipping Point" of Defection + Critical Economy is reached
- THEN it collapses instantly to COLLAPSED

**Example distribution:**
- (STABLE, LOYAL): [0.90, 0.08, 0.02]
- (CRITICAL, WAVERING): [0.40, 0.35, 0.25]
- (CRITICAL, DEFECTED): [0.05, 0.25, 0.70]  ← Tipping point crossed

### Constraints
1. Each column must sum to 1.0
2. P(COLLAPSED) should be <5% unless both stress and loyalty problems exist
3. Security defection is the primary trigger for elite collapse
"""

    with open(output_dir / "elite_cohesion.md", "w") as f:
        f.write(elite_cohesion_prompt)

    # Regime_Outcome prompt
    regime_outcome_prompt = header + f"""## CPT: P(Regime_Outcome | Security_Loyalty, Succession_Type, Fragmentation_Outcome, Elite_Cohesion)

### Node Definitions
- **Regime_Outcome**: {{STATUS_QUO, CONCESSIONS, TRANSITION, COLLAPSE, FRAGMENTATION}} (5 states)
- **Security_Loyalty**: {{LOYAL, WAVERING, DEFECTED}} (3 states)
- **Succession_Type**: {{ORDERLY, CHAOTIC}} (2 states)
- **Fragmentation_Outcome**: {{NO, YES}} (2 states)
- **Elite_Cohesion**: {{COHESIVE, FRACTURED, COLLAPSED}} (3 states)

Total CPT size: 5 × 3 × 2 × 2 × 3 = 180 parameters (36 columns × 5 rows)

### Source Priors (Regime Outcomes)
```json
{json.dumps(priors.get("regime_outcomes", {}), indent=2)}
```

### Key Conditional Probabilities
```json
{{
  "regime_collapse_given_defection": {json.dumps(priors.get("transition_probabilities", {}).get("regime_collapse_given_defection", {}), indent=4)}
}}
```

### Causal Priority Rules
1. **Fragmentation_Outcome = YES** → FRAGMENTATION outcome most likely (~70%)
2. **Security_Loyalty = DEFECTED** → COLLAPSE highly likely (65% per prior)
3. **Elite_Cohesion = COLLAPSED** → COLLAPSE or TRANSITION
4. **Succession_Type = CHAOTIC** → TRANSITION more likely than STATUS_QUO
5. **All stable** → STATUS_QUO most likely, with some CONCESSIONS

### Constraints
1. Each column must sum to 1.0
2. When Fragmentation_Outcome = YES: P(FRAGMENTATION) > 0.5
3. When Security_Loyalty = DEFECTED: P(COLLAPSE) ≈ 0.65
4. Base case (all favorable): P(STATUS_QUO) > 0.5
"""

    with open(output_dir / "regime_outcome.md", "w") as f:
        f.write(regime_outcome_prompt)

    # Protest_State prompt
    protest_state_prompt = header + f"""## CPT: P(Protest_State | Protest_Escalation, Protest_Sustained, Regime_Response)

### Node Definitions
- **Protest_State**: {{DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED}} (5 states)
- **Protest_Escalation**: {{NO, YES}} (2 states)
- **Protest_Sustained**: {{NO, YES}} (2 states)
- **Regime_Response**: {{STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED}} (4 states)

Total CPT size: 5 × 2 × 2 × 4 = 80 parameters (16 columns × 5 rows)

### Source Priors
```json
{{
  "protests_escalate_14d": {json.dumps(priors.get("transition_probabilities", {}).get("protests_escalate_14d", {}), indent=4)},
  "protests_sustain_30d": {json.dumps(priors.get("transition_probabilities", {}).get("protests_sustain_30d", {}), indent=4)},
  "protests_collapse_given_crackdown_30d": {json.dumps(priors.get("transition_probabilities", {}).get("protests_collapse_given_crackdown_30d", {}), indent=4)},
  "protests_collapse_given_concessions_30d": {json.dumps(priors.get("transition_probabilities", {}).get("protests_collapse_given_concessions_30d", {}), indent=4)}
}}
```

### Logical Rules
1. **Regime_Response = SUPPRESSED** → P(COLLAPSED) high (~70%)
2. **Escalation = NO, Sustained = NO** → DECLINING most likely
3. **Escalation = YES, Sustained = YES, Response = STATUS_QUO** → ORGANIZED possible
4. **Crackdown** → Can trigger COLLAPSED or ESCALATING (backfire)
5. **Concessions** → Tends toward DECLINING or STABLE

### Constraints
1. Each column must sum to 1.0
2. ORGANIZED requires both Escalation and Sustained = YES
3. COLLAPSED requires either SUPPRESSED or CRACKDOWN (with some probability)
"""

    with open(output_dir / "protest_state.md", "w") as f:
        f.write(protest_state_prompt)

    # Protest_Sustained prompt
    protest_sustained_prompt = header + f"""## CPT: P(Protest_Sustained | Protest_Escalation, Regime_Response, Internet_Status)

### Node Definitions
- **Protest_Sustained**: {{NO, YES}} (2 states)
- **Protest_Escalation**: {{NO, YES}} (2 states)
- **Regime_Response**: {{STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED}} (4 states)
- **Internet_Status**: {{ON, THROTTLED, OFF}} (3 states)

Total CPT size: 2 × 2 × 4 × 3 = 48 parameters (24 columns × 2 rows)

### Source Priors
```json
{{
  "protests_sustain_30d": {json.dumps(priors.get("transition_probabilities", {}).get("protests_sustain_30d", {}), indent=4)},
  "protests_collapse_given_crackdown_30d": {json.dumps(priors.get("transition_probabilities", {}).get("protests_collapse_given_crackdown_30d", {}), indent=4)},
  "protests_collapse_given_concessions_30d": {json.dumps(priors.get("transition_probabilities", {}).get("protests_collapse_given_concessions_30d", {}), indent=4)}
}}
```

### Internet Blackout Effects
Internet blackouts fundamentally change protest coordination:
- **ON**: Full coordination capability
- **THROTTLED**: Reduced coordination (~70% effectiveness)
- **OFF**: Severely impaired coordination (~30% effectiveness)

### Rules
1. No Escalation → very low sustained probability (~10%)
2. CRACKDOWN → reduces sustained by collapse_given_crackdown rate
3. CONCESSIONS → reduces sustained by collapse_given_concessions rate
4. SUPPRESSED → very low sustained (~5%)
5. Internet OFF → multiply sustained probability by 0.3

### Constraints
1. Each column must sum to 1.0
2. P(Sustained=YES) should be <0.15 when Escalation=NO
3. Internet blackout should reduce sustained probability significantly
"""

    with open(output_dir / "protest_sustained.md", "w") as f:
        f.write(protest_sustained_prompt)

    # Regime_Response prompt
    regime_response_prompt = header + f"""## CPT: P(Regime_Response | Protest_State, Regional_Instability)

### Node Definitions
- **Regime_Response**: {{STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED}} (4 states)
- **Protest_State**: {{DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED}} (5 states)
- **Regional_Instability**: {{NONE, MODERATE, SEVERE}} (3 states)

Total CPT size: 4 × 5 × 3 = 60 parameters (15 columns × 4 rows)

### Source Priors
```json
{{
  "mass_casualty_crackdown_given_escalation": {json.dumps(priors.get("transition_probabilities", {}).get("mass_casualty_crackdown_given_escalation", {}), indent=4)},
  "meaningful_concessions_given_protests_30d": {json.dumps(priors.get("transition_probabilities", {}).get("meaningful_concessions_given_protests_30d", {}), indent=4)}
}}
```

### Logical Rules
1. **Protest_State = COLLAPSED** → SUPPRESSED most likely (~90%)
2. **Protest_State = DECLINING** → STATUS_QUO most likely
3. **Protest_State in {{ESCALATING, ORGANIZED}}** → CRACKDOWN more likely
4. **Regional_Instability = SEVERE** → increases CRACKDOWN probability (20% boost)
5. **CONCESSIONS** are rare but possible when protests are stable/organized

### Constraints
1. Each column must sum to 1.0
2. SUPPRESSED requires prior protest collapse
3. CRACKDOWN probability ≈ 40% for escalating protests
4. CONCESSIONS probability ≈ 15% for sustained protests
"""

    with open(output_dir / "regime_response.md", "w") as f:
        f.write(regime_response_prompt)

    # Ethnic_Uprising prompt
    ethnic_uprising_prompt = header + f"""## CPT: P(Ethnic_Uprising | Protest_Sustained, Economic_Stress)

### Node Definitions
- **Ethnic_Uprising**: {{NO, YES}} (2 states)
- **Protest_Sustained**: {{NO, YES}} (2 states)
- **Economic_Stress**: {{STABLE, PRESSURED, CRITICAL}} (3 states)

Total CPT size: 2 × 2 × 3 = 12 parameters (6 columns × 2 rows)

### Source Priors
```json
{json.dumps(priors.get("transition_probabilities", {}).get("ethnic_coordination_given_protests_30d", {}), indent=2)}
```

### Window-to-Marginal Conversion
Base probability: P(ethnic coordination in 60-day window starting day 30) = 25%
Marginal approximation: 25% × 0.5 ≈ 12.5%

### Rules
1. Without sustained protests, ethnic uprising is unlikely (~2%)
2. With sustained protests, base probability ~12.5%
3. CRITICAL economic stress increases by 30%
4. PRESSURED economic stress increases by 15%

### Constraints
1. Each column must sum to 1.0
2. P(YES) should be <5% when Sustained=NO
3. P(YES) should not exceed 50% in any condition
"""

    with open(output_dir / "ethnic_uprising.md", "w") as f:
        f.write(ethnic_uprising_prompt)

    # Internet_Status prompt
    internet_status_prompt = header + f"""## CPT: P(Internet_Status | Regime_Response)

### Node Definitions
- **Internet_Status**: {{ON, THROTTLED, OFF}} (3 states)
- **Regime_Response**: {{STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED}} (4 states)

Total CPT size: 3 × 4 = 12 parameters (4 columns × 3 rows)

### Historical Context
- Iran has repeatedly used internet blackouts during protests (2019 November, 2022)
- Throttling is common during unrest
- Full blackouts are reserved for severe crackdowns

### Rules
1. **STATUS_QUO**: Internet mostly ON (~90%)
2. **CRACKDOWN**: High probability of throttling (~40%) or blackout (~30%)
3. **CONCESSIONS**: Internet mostly ON (~80%), some throttling
4. **SUPPRESSED**: High probability of blackout (~60%), throttling (~30%)

### Constraints
1. Each column must sum to 1.0
2. P(OFF) should be highest for CRACKDOWN and SUPPRESSED
3. P(ON) should be highest for STATUS_QUO and CONCESSIONS
"""

    with open(output_dir / "internet_status.md", "w") as f:
        f.write(internet_status_prompt)

    print(f"Exported 8 CPT prompts to {output_dir}")


# =============================================================================
# VISUALIZATION
# =============================================================================

def visualize_dag(output_path: Path | None = None):
    """Visualize the DAG structure.

    Args:
        output_path: Optional path to save visualization
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib required for visualization. Install with: pip install matplotlib")
        return

    g = nx.DiGraph(EDGES)

    # Create layout
    pos = nx.spring_layout(g, k=2, iterations=50, seed=42)

    # Color nodes by type
    node_colors = []
    for node in g.nodes():
        if node in ROOT_NODES:
            node_colors.append("#90EE90")  # Light green
        elif node in TERMINAL_NODES:
            node_colors.append("#FFB6C1")  # Light pink
        else:
            node_colors.append("#ADD8E6")  # Light blue

    plt.figure(figsize=(16, 12))
    nx.draw(
        g, pos,
        with_labels=True,
        node_color=node_colors,
        node_size=2000,
        font_size=8,
        font_weight="bold",
        arrows=True,
        arrowsize=15,
        edge_color="#666666",
    )

    plt.title("Iran Crisis Simulation - Bayesian Network DAG")
    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved visualization to {output_path}")
    else:
        plt.show()


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Bayesian Network Prototype for Iran Crisis Simulation"
    )
    parser.add_argument(
        "--priors", type=Path, default=Path("data/analyst_priors.json"),
        help="Path to analyst_priors.json"
    )
    parser.add_argument(
        "--intel", type=Path, default=None,
        help="Path to iran_crisis_intel.json (optional)"
    )
    parser.add_argument(
        "--visualize", action="store_true",
        help="Visualize the DAG structure"
    )
    parser.add_argument(
        "--export-prompts", type=Path, metavar="DIR",
        help="Export CPT derivation prompts to directory"
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate the model"
    )
    parser.add_argument(
        "--infer", action="store_true",
        help="Run inference query"
    )
    parser.add_argument(
        "--surprise", action="store_true",
        help="Include surprise analysis in inference output"
    )
    parser.add_argument(
        "--evidence", type=str, default="{}",
        help="Evidence for inference as JSON string"
    )
    parser.add_argument(
        "--sensitivity", type=str, metavar="NODE",
        help="Compute sensitivity for target node"
    )
    parser.add_argument(
        "--compare-mc", type=Path, metavar="FILE",
        help="Compare to Monte Carlo results"
    )
    parser.add_argument(
        "--check-black-swan", action="store_true",
        help="Check black swan preservation"
    )
    parser.add_argument(
        "--load-cpts", type=Path, metavar="DIR",
        help="Load CPT JSON files from directory"
    )
    parser.add_argument(
        "--output", "-o", type=Path,
        help="Output path for visualization"
    )

    args = parser.parse_args()

    # Resolve paths relative to script location
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    priors_path = args.priors
    if not priors_path.is_absolute():
        priors_path = project_root / priors_path

    intel_path = args.intel
    if intel_path and not intel_path.is_absolute():
        intel_path = project_root / intel_path

    # Handle visualization (doesn't need full model)
    if args.visualize:
        output_path = args.output or (project_root / "outputs" / "dag_visualization.png")
        visualize_dag(output_path)
        return

    # Handle prompt export (doesn't need full model)
    if args.export_prompts:
        priors = load_json(priors_path)
        output_dir = args.export_prompts
        if not output_dir.is_absolute():
            output_dir = project_root / output_dir
        export_cpt_prompts(output_dir, priors)
        return

    # Resolve CPT directory if provided
    cpt_dir = args.load_cpts
    if cpt_dir and not cpt_dir.is_absolute():
        cpt_dir = project_root / cpt_dir

    # Build model for other operations
    print(f"Loading priors from {priors_path}")
    if cpt_dir:
        print(f"Loading custom CPTs from {cpt_dir}")
    engine = CausalEngine(priors_path, intel_path, cpt_dir)

    if args.validate:
        print("\nValidating model...")
        is_valid, errors = engine.validate()
        if is_valid:
            print("✓ Model validation passed")
        else:
            print("✗ Model validation failed:")
            for err in errors:
                print(f"  - {err}")

        # Also run black swan check
        print("\nChecking black swan preservation...")
        bs_result = engine.check_black_swan_preservation()
        if bs_result["all_passed"]:
            print("✓ Black swan preservation check passed")
        else:
            print("✗ Black swan preservation check failed:")
            for f in bs_result["failures"]:
                print(f"  - {f}")

    if args.infer:
        evidence = json.loads(args.evidence)
        print(f"\nRunning inference with evidence: {evidence}")

        # Query Regime_Outcome with optional surprise analysis
        if args.surprise:
            result = engine.infer_with_surprise("Regime_Outcome", evidence)
            print("\nP(Regime_Outcome | evidence):")
            for state, prob in result["posterior"].items():
                print(f"  {state}: {prob:.2%}")

            print(f"\nSurprise Analysis:")
            print(f"  Surprise Score: {result['surprise_score']:.3f}")
            if result["surprise_flag"]:
                print(f"  ⚠️  MODEL DISAGREEMENT DETECTED")
                if result["surprise_drivers"]:
                    print(f"  Surprise Drivers: {', '.join(result['surprise_drivers'])}")
            else:
                print(f"  ✓ Within expected range")
        else:
            result = engine.infer_single("Regime_Outcome", evidence)
            print("\nP(Regime_Outcome | evidence):")
            for state, prob in result.items():
                print(f"  {state}: {prob:.2%}")

    if args.sensitivity:
        print(f"\nComputing sensitivity for {args.sensitivity}...")
        sens = engine.sensitivity(args.sensitivity)
        print(f"\nSensitivity ranking (mutual information):")
        for parent, mi in sens.items():
            print(f"  {parent}: {mi:.4f}")

    if args.compare_mc:
        mc_path = args.compare_mc
        if not mc_path.is_absolute():
            mc_path = project_root / mc_path

        print(f"\nComparing to Monte Carlo results from {mc_path}")
        comparison = engine.compare_to_mc(mc_path)

        print("\nBN Distribution:")
        for state, prob in comparison["bn_distribution"].items():
            print(f"  {state}: {prob:.2%}")

        print("\nMC Distribution:")
        for state, prob in comparison["mc_distribution"].items():
            print(f"  {state}: {prob:.2%}")

        print(f"\nMetrics:")
        print(f"  KL Divergence: {comparison['kl_divergence']:.4f} {'✓' if comparison['validation']['kl_pass'] else '✗'}")
        print(f"  Total Variation: {comparison['total_variation']:.4f}")
        print(f"  Max Difference: {comparison['max_difference']:.4f} {'✓' if comparison['validation']['max_diff_pass'] else '✗'}")

    if args.check_black_swan:
        print("\nChecking black swan preservation...")
        result = engine.check_black_swan_preservation()

        print("\nOutcome comparison:")
        for name, data in result["outcomes"].items():
            status = "✓" if data["passed"] else "✗"
            print(f"  {status} {name}: analyst={data['analyst_prior']:.2%}, BN={data['bn_probability']:.2%}")

        if result["all_passed"]:
            print("\n✓ All black swan checks passed")
        else:
            print(f"\n✗ {len(result['failures'])} black swan check(s) failed")


if __name__ == "__main__":
    main()

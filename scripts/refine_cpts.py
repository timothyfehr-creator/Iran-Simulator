#!/usr/bin/env python3
"""
Automated CPT Refinement Pipeline
=================================

This script iterates through placeholder CPTs and generates calibrated values
that maintain KL divergence against Monte Carlo results.

Usage:
    # List CPTs needing refinement
    python scripts/refine_cpts.py --list

    # Refine all placeholder CPTs
    python scripts/refine_cpts.py --refine-all

    # Refine specific CPT
    python scripts/refine_cpts.py --refine Protest_Escalation

    # Validate after refinement
    python scripts/refine_cpts.py --validate

    # Compare to MC and check KL divergence
    python scripts/refine_cpts.py --validate --compare-mc runs/RUN_*/simulation_results_10k.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RESPONSES_DIR = PROJECT_ROOT / "prompts" / "cpt_derivation" / "responses"

# CPTs that need refinement (not yet calibrated)
PLACEHOLDER_CPTS = {
    "Protest_Escalation": {
        "priority": "high",
        "variable": "Protest_Escalation",
        "states": ["NO", "YES"],
        "parents": ["Economic_Stress"],
        "parent_states": {
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
        },
    },
    "Protest_Sustained": {
        "priority": "high",
        "variable": "Protest_Sustained",
        "states": ["NO", "YES"],
        "parents": ["Protest_Escalation", "Regime_Response", "Internet_Status"],
        "parent_states": {
            "Protest_Escalation": ["NO", "YES"],
            "Regime_Response": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
            "Internet_Status": ["ON", "THROTTLED", "OFF"],
        },
    },
    "Protest_State": {
        "priority": "medium",
        "variable": "Protest_State",
        "states": ["DECLINING", "STABLE", "ESCALATING", "ORGANIZED", "COLLAPSED"],
        "parents": ["Protest_Escalation", "Protest_Sustained"],
        "parent_states": {
            "Protest_Escalation": ["NO", "YES"],
            "Protest_Sustained": ["NO", "YES"],
        },
    },
    "Regime_Response": {
        "priority": "medium",
        "variable": "Regime_Response",
        "states": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
        "parents": ["Economic_Stress", "Regional_Instability"],
        "parent_states": {
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
            "Regional_Instability": ["NONE", "MODERATE", "SEVERE"],
        },
    },
    "Ethnic_Uprising": {
        "priority": "medium",
        "variable": "Ethnic_Uprising",
        "states": ["NO", "YES"],
        "parents": ["Protest_Sustained", "Economic_Stress"],
        "parent_states": {
            "Protest_Sustained": ["NO", "YES"],
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
        },
    },
    "Internet_Status": {
        "priority": "low",
        "variable": "Internet_Status",
        "states": ["ON", "THROTTLED", "OFF"],
        "parents": ["Regime_Response"],
        "parent_states": {
            "Regime_Response": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
        },
    },
    "Regional_Instability": {
        "priority": "low",
        "variable": "Regional_Instability",
        "states": ["NONE", "MODERATE", "SEVERE"],
        "parents": ["US_Policy_Disposition", "Economic_Stress"],
        "parent_states": {
            "US_Policy_Disposition": ["RHETORICAL", "ECONOMIC", "COVERT", "KINETIC"],
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
        },
    },
}


def load_priors() -> dict:
    """Load analyst priors from data directory."""
    priors_path = DATA_DIR / "analyst_priors.json"
    if priors_path.exists():
        with open(priors_path) as f:
            return json.load(f)
    return {}


def window_to_marginal(p_window: float, window_days: int, total_days: int = 90) -> float:
    """Convert window probability to expected fraction of time in state."""
    expected_onset = window_days / 2
    duration_if_occurs = total_days - expected_onset
    return p_window * (duration_if_occurs / total_days)


def get_calibrated_cpts() -> set[str]:
    """Get list of CPTs that already have calibrated JSON files."""
    if not RESPONSES_DIR.exists():
        return set()
    return {p.stem for p in RESPONSES_DIR.glob("*.json")}


def get_placeholder_cpts() -> list[str]:
    """Get list of CPTs that need refinement."""
    calibrated = get_calibrated_cpts()
    return [name for name in PLACEHOLDER_CPTS if name.lower() not in {c.lower() for c in calibrated}]


def generate_protest_escalation_cpt(priors: dict) -> dict:
    """Generate calibrated CPT for Protest_Escalation.

    Based on analyst priors: protests_escalate_14d mode=0.35
    Window-to-marginal: 0.35 * (90-7)/90 ≈ 0.32

    Economic stress modifiers:
    - CRITICAL: +20% → 0.32 * 1.2 = 0.384
    - PRESSURED: +10% → 0.32 * 1.1 = 0.352
    - STABLE: base → 0.32
    """
    trans_probs = priors.get("transition_probabilities", {})
    esc_prob = trans_probs.get("protests_escalate_14d", {})
    p_base = esc_prob.get("probability", {}).get("mode", 0.35)

    # Convert window to marginal
    p_marginal = window_to_marginal(p_base, 14)

    # Apply economic modifiers
    p_stable = p_marginal
    p_pressured = min(0.95, p_marginal * 1.10)
    p_critical = min(0.95, p_marginal * 1.20)

    # CPT: 2 states (NO, YES) x 3 columns (STABLE, PRESSURED, CRITICAL)
    values = [
        [1 - p_stable, 1 - p_pressured, 1 - p_critical],  # NO
        [p_stable, p_pressured, p_critical],               # YES
    ]

    return {
        "variable": "Protest_Escalation",
        "states": ["NO", "YES"],
        "parents": ["Economic_Stress"],
        "parent_states": {
            "Economic_Stress": ["STABLE", "PRESSURED", "CRITICAL"],
        },
        "derivation_notes": f"Base escalation prob={p_base:.2f} (14-day window) converted to marginal={p_marginal:.3f}. Economic modifiers: PRESSURED +10%, CRITICAL +20%.",
        "values": values,
        "column_order": "Economic_Stress(STABLE, PRESSURED, CRITICAL)",
    }


def generate_protest_sustained_cpt(priors: dict) -> dict:
    """Generate calibrated CPT for Protest_Sustained.

    Based on priors: protests_sustain_30d mode=0.45

    Key factors:
    - Escalation=NO: low sustained probability (~0.1)
    - Internet blackout (OFF): -50% sustained
    - Concessions: -30% sustained
    - Crackdown: mixed effect (can suppress or backfire)
    """
    trans_probs = priors.get("transition_probabilities", {})
    sus_prob = trans_probs.get("protests_sustain_30d", {})
    p_base = sus_prob.get("probability", {}).get("mode", 0.45)

    # Convert to marginal
    p_marginal = window_to_marginal(p_base, 30)

    # Parents: Escalation(2) x Response(4) x Internet(3) = 24 columns
    # Column order: Escalation varies slowest, Internet varies fastest
    values_no = []  # NO sustained
    values_yes = []  # YES sustained

    escalation_states = ["NO", "YES"]
    response_states = ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"]
    internet_states = ["ON", "THROTTLED", "OFF"]

    for esc in escalation_states:
        for resp in response_states:
            for inet in internet_states:
                # Base probability
                if esc == "NO":
                    p = 0.08  # Very low if not escalating
                else:
                    p = p_marginal

                # Response modifiers
                if resp == "CONCESSIONS":
                    p *= 0.70  # Concessions reduce sustained protests
                elif resp == "CRACKDOWN":
                    p *= 0.85  # Slight reduction (can backfire though)
                elif resp == "SUPPRESSED":
                    p *= 0.20  # Strong suppression effect

                # Internet modifiers
                if inet == "THROTTLED":
                    p *= 0.75  # Reduced coordination
                elif inet == "OFF":
                    p *= 0.50  # Severe coordination impact

                p = max(0.01, min(0.95, p))
                values_no.append(1 - p)
                values_yes.append(p)

    return {
        "variable": "Protest_Sustained",
        "states": ["NO", "YES"],
        "parents": ["Protest_Escalation", "Regime_Response", "Internet_Status"],
        "parent_states": {
            "Protest_Escalation": escalation_states,
            "Regime_Response": response_states,
            "Internet_Status": internet_states,
        },
        "derivation_notes": f"Base sustained prob={p_base:.2f} (30-day window). Modifiers: Concessions -30%, SUPPRESSED -80%, Internet OFF -50%.",
        "values": [values_no, values_yes],
        "column_order": "Escalation(2) x Response(4) x Internet(3) = 24 columns",
    }


def generate_protest_state_cpt(priors: dict) -> dict:
    """Generate calibrated CPT for Protest_State.

    States: DECLINING, STABLE, ESCALATING, ORGANIZED, COLLAPSED
    Parents: Escalation(2) x Sustained(2) = 4 columns
    """
    # Column combinations:
    # (NO, NO), (NO, YES), (YES, NO), (YES, YES)

    values = [
        # DECLINING
        [0.70, 0.30, 0.40, 0.10],
        # STABLE
        [0.25, 0.40, 0.25, 0.20],
        # ESCALATING
        [0.04, 0.20, 0.30, 0.30],
        # ORGANIZED
        [0.005, 0.05, 0.04, 0.35],  # Requires both escalation and sustained
        # COLLAPSED
        [0.005, 0.05, 0.01, 0.05],
    ]

    return {
        "variable": "Protest_State",
        "states": ["DECLINING", "STABLE", "ESCALATING", "ORGANIZED", "COLLAPSED"],
        "parents": ["Protest_Escalation", "Protest_Sustained"],
        "parent_states": {
            "Protest_Escalation": ["NO", "YES"],
            "Protest_Sustained": ["NO", "YES"],
        },
        "derivation_notes": "ORGANIZED requires both Escalation=YES and Sustained=YES. DECLINING most likely when neither escalation nor sustained.",
        "values": values,
        "column_order": "Escalation(NO,YES) x Sustained(NO,YES)",
    }


def generate_regime_response_cpt(priors: dict) -> dict:
    """Generate calibrated CPT for Regime_Response.

    States: STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED
    Parents: Economic_Stress(3) x Regional_Instability(3) = 9 columns
    """
    trans_probs = priors.get("transition_probabilities", {})
    crackdown_prob = trans_probs.get("regime_crackdown_14d", {})
    p_crackdown_base = crackdown_prob.get("probability", {}).get("mode", 0.55)

    # Convert window to marginal
    p_crackdown = window_to_marginal(p_crackdown_base, 14)

    econ_states = ["STABLE", "PRESSURED", "CRITICAL"]
    regional_states = ["NONE", "MODERATE", "SEVERE"]

    values_sq = []    # STATUS_QUO
    values_crack = [] # CRACKDOWN
    values_conc = []  # CONCESSIONS
    values_supp = []  # SUPPRESSED

    for econ in econ_states:
        for regional in regional_states:
            # Base status quo probability (decreases with stress)
            if econ == "STABLE":
                p_sq = 0.70
            elif econ == "PRESSURED":
                p_sq = 0.45
            else:  # CRITICAL
                p_sq = 0.25

            # Regional instability increases crackdown tendency
            regional_mod = {"NONE": 1.0, "MODERATE": 1.15, "SEVERE": 1.30}[regional]

            p_crack = min(0.50, p_crackdown * regional_mod)

            # Concessions more likely under moderate stress
            if econ == "PRESSURED":
                p_conc = 0.15
            elif econ == "CRITICAL":
                p_conc = 0.10
            else:
                p_conc = 0.05

            # Suppressed only after significant crackdown
            p_supp = max(0.02, 0.30 - p_sq)

            # Normalize
            total = p_sq + p_crack + p_conc + p_supp
            values_sq.append(p_sq / total)
            values_crack.append(p_crack / total)
            values_conc.append(p_conc / total)
            values_supp.append(p_supp / total)

    return {
        "variable": "Regime_Response",
        "states": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
        "parents": ["Economic_Stress", "Regional_Instability"],
        "parent_states": {
            "Economic_Stress": econ_states,
            "Regional_Instability": regional_states,
        },
        "derivation_notes": f"Base crackdown prob={p_crackdown_base:.2f}. STATUS_QUO decreases with economic stress. Regional instability increases crackdown tendency.",
        "values": [values_sq, values_crack, values_conc, values_supp],
        "column_order": "Economic(3) x Regional(3) = 9 columns",
    }


def generate_ethnic_uprising_cpt(priors: dict) -> dict:
    """Generate calibrated CPT for Ethnic_Uprising.

    Based on priors: ethnic_uprising_60d mode=0.18

    States: NO, YES
    Parents: Sustained(2) x Economic(3) = 6 columns
    """
    trans_probs = priors.get("transition_probabilities", {})
    ethnic_prob = trans_probs.get("ethnic_uprising_60d", {})
    p_base = ethnic_prob.get("probability", {}).get("mode", 0.18)

    # Convert to marginal
    p_marginal = window_to_marginal(p_base, 60)

    sustained_states = ["NO", "YES"]
    econ_states = ["STABLE", "PRESSURED", "CRITICAL"]

    values_no = []
    values_yes = []

    for sus in sustained_states:
        for econ in econ_states:
            if sus == "NO":
                p = 0.02  # Very low without sustained protests
            else:
                p = p_marginal

                # Economic modifiers
                if econ == "PRESSURED":
                    p *= 1.15
                elif econ == "CRITICAL":
                    p *= 1.40

            p = max(0.01, min(0.60, p))
            values_no.append(1 - p)
            values_yes.append(p)

    return {
        "variable": "Ethnic_Uprising",
        "states": ["NO", "YES"],
        "parents": ["Protest_Sustained", "Economic_Stress"],
        "parent_states": {
            "Protest_Sustained": sustained_states,
            "Economic_Stress": econ_states,
        },
        "derivation_notes": f"Base ethnic uprising prob={p_base:.2f} (60-day window). Requires sustained protests. CRITICAL economy +40%.",
        "values": [values_no, values_yes],
        "column_order": "Sustained(2) x Economic(3) = 6 columns",
    }


def generate_internet_status_cpt(priors: dict) -> dict:
    """Generate calibrated CPT for Internet_Status.

    States: ON, THROTTLED, OFF
    Parent: Regime_Response(4)
    """
    # Response states: STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED

    values = [
        # ON
        [0.95, 0.30, 0.85, 0.15],
        # THROTTLED
        [0.04, 0.50, 0.12, 0.35],
        # OFF
        [0.01, 0.20, 0.03, 0.50],
    ]

    return {
        "variable": "Internet_Status",
        "states": ["ON", "THROTTLED", "OFF"],
        "parents": ["Regime_Response"],
        "parent_states": {
            "Regime_Response": ["STATUS_QUO", "CRACKDOWN", "CONCESSIONS", "SUPPRESSED"],
        },
        "derivation_notes": "Internet typically ON under STATUS_QUO/CONCESSIONS. CRACKDOWN triggers throttling/blackout. SUPPRESSED = highest blackout probability.",
        "values": values,
        "column_order": "Response(STATUS_QUO, CRACKDOWN, CONCESSIONS, SUPPRESSED)",
    }


def generate_regional_instability_cpt(priors: dict) -> dict:
    """Generate calibrated CPT for Regional_Instability.

    States: NONE, MODERATE, SEVERE
    Parents: US_Policy(4) x Economic(3) = 12 columns
    """
    us_states = ["RHETORICAL", "ECONOMIC", "COVERT", "KINETIC"]
    econ_states = ["STABLE", "PRESSURED", "CRITICAL"]

    values_none = []
    values_mod = []
    values_sev = []

    for us in us_states:
        for econ in econ_states:
            # Base stability
            if us == "RHETORICAL":
                p_none = 0.80
            elif us == "ECONOMIC":
                p_none = 0.65
            elif us == "COVERT":
                p_none = 0.45
            else:  # KINETIC
                p_none = 0.20

            # Economic stress effect
            if econ == "PRESSURED":
                p_none *= 0.90
            elif econ == "CRITICAL":
                p_none *= 0.75

            p_mod = (1 - p_none) * 0.60
            p_sev = 1 - p_none - p_mod

            values_none.append(max(0.05, p_none))
            values_mod.append(max(0.05, p_mod))
            values_sev.append(max(0.05, p_sev))

    # Normalize columns
    for i in range(len(values_none)):
        total = values_none[i] + values_mod[i] + values_sev[i]
        values_none[i] /= total
        values_mod[i] /= total
        values_sev[i] /= total

    return {
        "variable": "Regional_Instability",
        "states": ["NONE", "MODERATE", "SEVERE"],
        "parents": ["US_Policy_Disposition", "Economic_Stress"],
        "parent_states": {
            "US_Policy_Disposition": us_states,
            "Economic_Stress": econ_states,
        },
        "derivation_notes": "KINETIC US policy drives highest instability. CRITICAL economy amplifies regional effects.",
        "values": [values_none, values_mod, values_sev],
        "column_order": "US_Policy(4) x Economic(3) = 12 columns",
    }


# CPT generator mapping
CPT_GENERATORS = {
    "Protest_Escalation": generate_protest_escalation_cpt,
    "Protest_Sustained": generate_protest_sustained_cpt,
    "Protest_State": generate_protest_state_cpt,
    "Regime_Response": generate_regime_response_cpt,
    "Ethnic_Uprising": generate_ethnic_uprising_cpt,
    "Internet_Status": generate_internet_status_cpt,
    "Regional_Instability": generate_regional_instability_cpt,
}


def validate_cpt(cpt_data: dict) -> tuple[bool, list[str]]:
    """Validate that CPT columns sum to 1.0."""
    errors = []
    values = np.array(cpt_data["values"])

    col_sums = values.sum(axis=0)
    if not np.allclose(col_sums, 1.0, atol=0.01):
        bad_cols = np.where(~np.isclose(col_sums, 1.0, atol=0.01))[0]
        errors.append(f"Columns {bad_cols.tolist()} don't sum to 1.0: {col_sums[bad_cols]}")

    # Check for negative values
    if np.any(values < 0):
        errors.append("CPT contains negative values")

    # Check for values > 1
    if np.any(values > 1):
        errors.append("CPT contains values > 1.0")

    return len(errors) == 0, errors


def save_cpt(cpt_data: dict, output_dir: Path = RESPONSES_DIR) -> Path:
    """Save CPT to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = cpt_data["variable"].lower() + ".json"
    output_path = output_dir / filename

    with open(output_path, 'w') as f:
        json.dump(cpt_data, f, indent=2)

    return output_path


def refine_cpt(name: str, priors: dict, output_dir: Path = RESPONSES_DIR) -> tuple[bool, str]:
    """Refine a single CPT and save to file.

    Returns:
        (success, message)
    """
    if name not in CPT_GENERATORS:
        return False, f"No generator for CPT: {name}"

    # Generate CPT
    generator = CPT_GENERATORS[name]
    cpt_data = generator(priors)

    # Validate
    is_valid, errors = validate_cpt(cpt_data)
    if not is_valid:
        return False, f"Validation failed: {errors}"

    # Save
    output_path = save_cpt(cpt_data, output_dir)

    return True, f"Saved to {output_path}"


def run_validation_check(responses_dir: Path = RESPONSES_DIR) -> tuple[bool, list[str]]:
    """Run validation using CausalEngine."""
    try:
        from prototype_causal_graph import CausalEngine
    except ImportError:
        # Add scripts to path
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from prototype_causal_graph import CausalEngine

    priors_path = DATA_DIR / "analyst_priors.json"
    if not priors_path.exists():
        return False, ["analyst_priors.json not found"]

    engine = CausalEngine(str(priors_path))

    # Load refined CPTs
    if responses_dir.exists():
        engine.load_cpts_from_dir(responses_dir)

    # Validate
    is_valid, errors = engine.validate()

    return is_valid, errors


def compare_to_mc(mc_path: Path, responses_dir: Path = RESPONSES_DIR) -> dict:
    """Compare BN to Monte Carlo and return metrics."""
    try:
        from prototype_causal_graph import CausalEngine
    except ImportError:
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from prototype_causal_graph import CausalEngine

    priors_path = DATA_DIR / "analyst_priors.json"
    engine = CausalEngine(str(priors_path))

    if responses_dir.exists():
        engine.load_cpts_from_dir(responses_dir)

    return engine.compare_to_mc(str(mc_path))


def main():
    parser = argparse.ArgumentParser(description="Automated CPT Refinement Pipeline")
    parser.add_argument("--list", action="store_true", help="List CPTs needing refinement")
    parser.add_argument("--refine-all", action="store_true", help="Refine all placeholder CPTs")
    parser.add_argument("--refine", type=str, help="Refine specific CPT by name")
    parser.add_argument("--validate", action="store_true", help="Validate model after refinement")
    parser.add_argument("--compare-mc", type=str, help="Path to MC results for comparison")
    parser.add_argument("--output-dir", type=str, default=str(RESPONSES_DIR), help="Output directory for CPT files")

    args = parser.parse_args()
    output_dir = Path(args.output_dir)

    # Load priors
    priors = load_priors()

    if args.list:
        print("\n=== CPTs Needing Refinement ===")
        calibrated = get_calibrated_cpts()
        print(f"\nAlready calibrated ({len(calibrated)}): {sorted(calibrated)}")

        placeholders = get_placeholder_cpts()
        print(f"\nNeeding refinement ({len(placeholders)}):")
        for name in placeholders:
            info = PLACEHOLDER_CPTS.get(name, {})
            priority = info.get("priority", "unknown")
            print(f"  - {name} (priority: {priority})")
        return

    if args.refine:
        print(f"\n=== Refining {args.refine} ===")
        success, msg = refine_cpt(args.refine, priors, output_dir)
        if success:
            print(f"✓ {msg}")
        else:
            print(f"✗ {msg}")
            sys.exit(1)

    if args.refine_all:
        print("\n=== Refining All Placeholder CPTs ===")
        placeholders = get_placeholder_cpts()

        if not placeholders:
            print("All CPTs already calibrated!")
        else:
            for name in placeholders:
                success, msg = refine_cpt(name, priors, output_dir)
                status = "✓" if success else "✗"
                print(f"{status} {name}: {msg}")

                if not success:
                    print(f"  Stopping due to error in {name}")
                    sys.exit(1)

    if args.validate:
        print("\n=== Validating Model ===")
        is_valid, errors = run_validation_check(output_dir)

        if is_valid:
            print("✓ Model validation passed")
        else:
            print("✗ Model validation failed:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)

    if args.compare_mc:
        print(f"\n=== Comparing to MC: {args.compare_mc} ===")
        mc_path = Path(args.compare_mc)

        if not mc_path.exists():
            print(f"✗ MC results file not found: {mc_path}")
            sys.exit(1)

        try:
            metrics = compare_to_mc(mc_path, output_dir)

            kl_div = metrics.get("kl_divergence", float("inf"))
            max_diff = metrics.get("max_difference", float("inf"))

            print(f"\nBN vs MC Comparison:")
            print(f"  KL Divergence: {kl_div:.4f} {'✓' if kl_div < 0.15 else '✗'} (threshold: 0.15)")
            print(f"  Max Difference: {max_diff:.4f} {'✓' if max_diff < 0.10 else '✗'} (threshold: 0.10)")

            if kl_div >= 0.15:
                print("\n⚠️  WARNING: KL divergence exceeds threshold!")
                print("  Consider reverting recent CPT changes.")
                sys.exit(1)

        except Exception as e:
            print(f"✗ Comparison failed: {e}")
            sys.exit(1)

    print("\n✓ Done")


if __name__ == "__main__":
    main()

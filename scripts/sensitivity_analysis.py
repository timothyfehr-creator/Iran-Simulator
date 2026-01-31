#!/usr/bin/env python3
"""
Sensitivity Analysis Script for Iran Crisis Simulation
=======================================================

Systematically varies each prior probability by ±20% and measures
impact on outcome distribution. Identifies which parameters most
affect simulation results.

Usage:
    python scripts/sensitivity_analysis.py \
        --intel data/iran_crisis_intel.json \
        --priors data/analyst_priors.json \
        --runs 1000 \
        --output outputs/sensitivity_analysis.json

Output:
    - Ranked list of parameters by outcome sensitivity
    - Variance metrics for each parameter perturbation
    - Visualization of sensitivity tornado chart
"""

import json
import copy
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import statistics

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from simulation import IranCrisisSimulation


def get_probability_paths(priors: dict) -> List[Tuple[str, str]]:
    """Extract all probability paths from priors structure.

    Returns:
        List of (category, key) tuples for each probability estimate
    """
    paths = []

    def is_probability_entry(entry) -> bool:
        """Check if entry is a valid probability dict (not metadata)."""
        return isinstance(entry, dict) and "probability" in entry

    # Transition probabilities
    if "transition_probabilities" in priors:
        for key, value in priors["transition_probabilities"].items():
            if is_probability_entry(value):
                paths.append(("transition", key))

    # US intervention probabilities
    if "us_intervention_probabilities" in priors:
        for key, value in priors["us_intervention_probabilities"].items():
            if is_probability_entry(value):
                paths.append(("us_intervention", key))

    # Regional cascade probabilities
    if "regional_cascade_probabilities" in priors:
        for key, value in priors["regional_cascade_probabilities"].items():
            if is_probability_entry(value):
                paths.append(("regional", key))

    return paths


def perturb_prior(priors: dict, category: str, key: str, factor: float) -> dict:
    """Create a copy of priors with one probability perturbed.

    Args:
        priors: Original priors dict
        category: Category name (transition, us_intervention, regional)
        key: Specific probability key
        factor: Multiplicative factor (e.g., 0.8 for -20%, 1.2 for +20%)

    Returns:
        New priors dict with perturbed value
    """
    perturbed = copy.deepcopy(priors)

    # Map category to actual key in priors
    category_map = {
        "transition": "transition_probabilities",
        "us_intervention": "us_intervention_probabilities",
        "regional": "regional_cascade_probabilities"
    }

    actual_category = category_map.get(category)
    if not actual_category or actual_category not in perturbed:
        return perturbed

    if key not in perturbed[actual_category]:
        return perturbed

    prob = perturbed[actual_category][key]["probability"]

    # Perturb low, mode/point, high - keeping within [0, 1]
    for field in ["low", "mode", "point", "high"]:
        if field in prob:
            new_val = prob[field] * factor
            prob[field] = max(0.0, min(1.0, new_val))

    # Ensure low <= mode <= high
    if "low" in prob and "mode" in prob:
        prob["mode"] = max(prob["low"], prob["mode"])
    if "mode" in prob and "high" in prob:
        prob["high"] = max(prob["mode"], prob["high"])
    if "low" in prob and "point" in prob:
        prob["point"] = max(prob["low"], prob["point"])
    if "point" in prob and "high" in prob:
        prob["high"] = max(prob["point"], prob["high"])

    return perturbed


def run_simulation_batch(intel: dict, priors: dict, n_runs: int) -> dict:
    """Run a batch of simulations and return outcome distribution."""
    sim = IranCrisisSimulation(intel, priors)
    results = sim.run_monte_carlo(n_runs)
    return results["outcome_distribution"]


def compute_outcome_variance(base_dist: dict, perturbed_dist: dict) -> float:
    """Compute variance between two outcome distributions.

    Uses sum of squared differences in probabilities.
    """
    outcomes = set(base_dist.keys()) | set(perturbed_dist.keys())
    variance = 0.0

    for outcome in outcomes:
        base_prob = base_dist.get(outcome, {}).get("probability", 0.0)
        pert_prob = perturbed_dist.get(outcome, {}).get("probability", 0.0)
        variance += (base_prob - pert_prob) ** 2

    return variance


def compute_directional_impact(base_dist: dict, perturbed_dist: dict) -> Dict[str, float]:
    """Compute how each outcome's probability changed."""
    outcomes = set(base_dist.keys()) | set(perturbed_dist.keys())
    impacts = {}

    for outcome in outcomes:
        base_prob = base_dist.get(outcome, {}).get("probability", 0.0)
        pert_prob = perturbed_dist.get(outcome, {}).get("probability", 0.0)
        impacts[outcome] = pert_prob - base_prob

    return impacts


def run_sensitivity_analysis(
    intel: dict,
    priors: dict,
    n_runs: int = 1000,
    perturbation: float = 0.20,
    verbose: bool = True
) -> dict:
    """Run full sensitivity analysis.

    Args:
        intel: Intelligence data
        priors: Analyst priors
        n_runs: Simulations per variant
        perturbation: Perturbation magnitude (0.20 = ±20%)
        verbose: Print progress

    Returns:
        Sensitivity analysis results
    """
    paths = get_probability_paths(priors)

    if verbose:
        print(f"Found {len(paths)} probability parameters to analyze")
        print(f"Running {n_runs} simulations per variant...")
        print(f"Total simulations: {len(paths) * 2 * n_runs + n_runs} (baseline + perturbations)")
        print()

    # Run baseline
    if verbose:
        print("Running baseline simulation...")
    base_dist = run_simulation_batch(intel, priors, n_runs)

    # Results storage
    sensitivity_results = []

    for i, (category, key) in enumerate(paths):
        param_name = f"{category}.{key}"

        if verbose:
            print(f"[{i+1}/{len(paths)}] Analyzing {param_name}...")

        # Perturb down (-20%)
        priors_down = perturb_prior(priors, category, key, 1.0 - perturbation)
        dist_down = run_simulation_batch(intel, priors_down, n_runs)
        variance_down = compute_outcome_variance(base_dist, dist_down)
        impacts_down = compute_directional_impact(base_dist, dist_down)

        # Perturb up (+20%)
        priors_up = perturb_prior(priors, category, key, 1.0 + perturbation)
        dist_up = run_simulation_batch(intel, priors_up, n_runs)
        variance_up = compute_outcome_variance(base_dist, dist_up)
        impacts_up = compute_directional_impact(base_dist, dist_up)

        # Combined sensitivity score (max of up/down variance)
        sensitivity_score = max(variance_down, variance_up)

        sensitivity_results.append({
            "parameter": param_name,
            "category": category,
            "key": key,
            "sensitivity_score": sensitivity_score,
            "variance_down": variance_down,
            "variance_up": variance_up,
            "impacts_down": impacts_down,
            "impacts_up": impacts_up,
            "most_affected_outcome": max(
                set(impacts_down.keys()) | set(impacts_up.keys()),
                key=lambda o: max(abs(impacts_down.get(o, 0)), abs(impacts_up.get(o, 0)))
            )
        })

    # Sort by sensitivity score (highest first)
    sensitivity_results.sort(key=lambda x: -x["sensitivity_score"])

    # Compute summary statistics
    scores = [r["sensitivity_score"] for r in sensitivity_results]

    return {
        "metadata": {
            "n_runs_per_variant": n_runs,
            "perturbation_magnitude": perturbation,
            "total_parameters": len(paths),
            "baseline_outcomes": {k: v["probability"] for k, v in base_dist.items()}
        },
        "summary": {
            "mean_sensitivity": statistics.mean(scores) if scores else 0,
            "max_sensitivity": max(scores) if scores else 0,
            "min_sensitivity": min(scores) if scores else 0,
            "std_sensitivity": statistics.stdev(scores) if len(scores) > 1 else 0
        },
        "ranked_parameters": sensitivity_results,
        "top_10_most_sensitive": [
            {
                "rank": i + 1,
                "parameter": r["parameter"],
                "sensitivity_score": r["sensitivity_score"],
                "most_affected_outcome": r["most_affected_outcome"]
            }
            for i, r in enumerate(sensitivity_results[:10])
        ]
    }


def create_tornado_chart(results: dict, output_path: str):
    """Create tornado chart visualization of sensitivity results."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed - skipping tornado chart")
        return

    # Get top 15 parameters
    top_params = results["ranked_parameters"][:15]

    fig, ax = plt.subplots(figsize=(12, 8))

    params = [p["parameter"].replace(".", "\n") for p in reversed(top_params)]
    scores = [p["sensitivity_score"] for p in reversed(top_params)]

    # Color by category
    colors = {
        "transition": "#3498db",
        "us_intervention": "#e74c3c",
        "regional": "#27ae60"
    }
    bar_colors = [colors.get(p["category"], "#95a5a6") for p in reversed(top_params)]

    bars = ax.barh(params, scores, color=bar_colors, edgecolor='black', linewidth=0.5)

    ax.set_xlabel("Sensitivity Score (Outcome Distribution Variance)", fontsize=11)
    ax.set_title("Parameter Sensitivity Analysis\n(Higher = More Impact on Outcomes)", fontsize=13)

    # Add legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=colors["transition"], label="Transition Probabilities"),
        Patch(facecolor=colors["us_intervention"], label="US Intervention"),
        Patch(facecolor=colors["regional"], label="Regional Cascade")
    ]
    ax.legend(handles=legend_elements, loc='lower right', fontsize=9)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved tornado chart to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Sensitivity Analysis for Iran Crisis Simulation"
    )
    parser.add_argument(
        "--intel", required=True,
        help="Path to intel JSON file"
    )
    parser.add_argument(
        "--priors", required=True,
        help="Path to analyst priors JSON file"
    )
    parser.add_argument(
        "--runs", type=int, default=1000,
        help="Number of simulation runs per variant (default: 1000)"
    )
    parser.add_argument(
        "--perturbation", type=float, default=0.20,
        help="Perturbation magnitude (default: 0.20 for ±20%%)"
    )
    parser.add_argument(
        "--output", default="outputs/sensitivity_analysis.json",
        help="Output file path"
    )
    parser.add_argument(
        "--chart", default=None,
        help="Path for tornado chart PNG (optional)"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Load inputs
    with open(args.intel, 'r') as f:
        intel = json.load(f)

    with open(args.priors, 'r') as f:
        priors = json.load(f)

    # Run analysis
    results = run_sensitivity_analysis(
        intel=intel,
        priors=priors,
        n_runs=args.runs,
        perturbation=args.perturbation,
        verbose=not args.quiet
    )

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to {args.output}")

    # Print summary
    print("\n" + "=" * 60)
    print("SENSITIVITY ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"\nTotal parameters analyzed: {results['metadata']['total_parameters']}")
    print(f"Simulations per variant: {results['metadata']['n_runs_per_variant']}")
    print(f"Perturbation: ±{results['metadata']['perturbation_magnitude']*100:.0f}%")

    print("\nTOP 10 MOST SENSITIVE PARAMETERS:")
    print("-" * 60)
    for item in results["top_10_most_sensitive"]:
        print(f"  {item['rank']:2d}. {item['parameter']}")
        print(f"      Score: {item['sensitivity_score']:.6f}")
        print(f"      Most affects: {item['most_affected_outcome']}")
        print()

    # Generate chart if requested
    if args.chart:
        create_tornado_chart(results, args.chart)
    elif not args.quiet:
        # Default chart location
        chart_path = str(output_path.parent / "sensitivity_tornado.png")
        create_tornado_chart(results, chart_path)


if __name__ == "__main__":
    main()

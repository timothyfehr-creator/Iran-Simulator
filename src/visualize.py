"""
Iran Crisis Visualization
==========================

Generates maps and charts from simulation results.

Usage:
    python visualize.py --results outputs/simulation_results.json --intel data/iran_crisis_intel.json

Outputs:
    - outputs/outcome_distribution.png
    - outputs/iran_protest_map.svg
    - outputs/scenario_timeline.png
"""

import json
import argparse
from pathlib import Path

# Note: These imports may need to be installed
# pip install matplotlib seaborn geopandas

def create_outcome_chart(results: dict, output_path: str):
    """Create bar chart of outcome distribution"""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        print("matplotlib/seaborn not installed. Run: pip install matplotlib seaborn")
        return
    
    outcomes = results["outcome_distribution"]
    
    # Sort by probability
    sorted_outcomes = sorted(outcomes.items(), key=lambda x: -x[1]["probability"])
    
    labels = [o[0].replace("_", "\n") for o in sorted_outcomes]
    probs = [o[1]["probability"] for o in sorted_outcomes]
    ci_low = [o[1]["ci_low"] for o in sorted_outcomes]
    ci_high = [o[1]["ci_high"] for o in sorted_outcomes]
    
    # Calculate error bars
    errors = [[p - l for p, l in zip(probs, ci_low)],
              [h - p for p, h in zip(probs, ci_high)]]
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    colors = {
        "REGIME_SURVIVES_STATUS_QUO": "#2ecc71",
        "REGIME_SURVIVES_WITH_CONCESSIONS": "#27ae60",
        "MANAGED_TRANSITION": "#3498db",
        "REGIME_COLLAPSE_CHAOTIC": "#e74c3c",
        "ETHNIC_FRAGMENTATION": "#9b59b6"
    }
    
    bar_colors = [colors.get(o[0], "#95a5a6") for o in sorted_outcomes]
    
    bars = ax.bar(range(len(labels)), probs, color=bar_colors, edgecolor='black', linewidth=0.5)
    ax.errorbar(range(len(labels)), probs, yerr=errors, fmt='none', color='black', capsize=5)

    # TAIL RISK ANNOTATIONS: Highlight low-probability, high-impact outcomes
    # These require contingency planning despite low probability
    TAIL_RISK_THRESHOLD = 0.10  # Outcomes below 10% probability
    HIGH_IMPACT_OUTCOMES = {"REGIME_COLLAPSE_CHAOTIC", "ETHNIC_FRAGMENTATION"}

    tail_risk_indices = []
    for i, (outcome_tuple, prob) in enumerate(zip(sorted_outcomes, probs)):
        outcome_name = outcome_tuple[0]
        is_high_impact = outcome_name in HIGH_IMPACT_OUTCOMES
        is_low_prob = prob < TAIL_RISK_THRESHOLD

        if is_high_impact and is_low_prob:
            # Mark as tail risk: red border + hatching
            bars[i].set_edgecolor('#c0392b')
            bars[i].set_linewidth(2.5)
            bars[i].set_hatch('//')
            tail_risk_indices.append(i)

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("Probability", fontsize=12)
    ax.set_title("Iran Crisis: 90-Day Outcome Distribution\n(Monte Carlo Simulation)", fontsize=14)

    # Add probability labels on bars
    for i, (bar, prob) in enumerate(zip(bars, probs)):
        label_text = f'{prob:.1%}'
        if i in tail_risk_indices:
            label_text = f'{prob:.1%}\nTAIL RISK'
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                label_text, ha='center', va='bottom', fontsize=9,
                color='#c0392b' if i in tail_risk_indices else 'black',
                fontweight='bold' if i in tail_risk_indices else 'normal')

    ax.set_ylim(0, max(probs) * 1.25)  # Extra space for tail risk labels

    # Add tail risk legend if any tail risks exist
    if tail_risk_indices:
        from matplotlib.patches import Patch
        tail_risk_patch = Patch(facecolor='white', edgecolor='#c0392b',
                                linewidth=2.5, hatch='//',
                                label='Tail Risk: Low probability,\nhigh-impact (plan contingencies)')
        ax.legend(handles=[tail_risk_patch], loc='upper right', fontsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved outcome chart to {output_path}")


def create_iran_map(intel: dict, output_path: str):
    """Create SVG map of Iran with protest intensity overlay"""
    
    # Province data from intel
    provinces = intel.get("geographic_data", {}).get("provinces", [])
    
    # Build a simple SVG map
    # Note: In production, use geopandas with actual shapefiles
    
    svg_content = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" width="800" height="600">
  <style>
    .province { stroke: #333; stroke-width: 1; }
    .high { fill: #e74c3c; }
    .medium { fill: #f39c12; }
    .low { fill: #f1c40f; }
    .none { fill: #ecf0f1; }
    .label { font-family: Arial, sans-serif; font-size: 10px; fill: #333; }
    .title { font-family: Arial, sans-serif; font-size: 18px; font-weight: bold; fill: #2c3e50; }
    .legend-text { font-family: Arial, sans-serif; font-size: 12px; fill: #333; }
  </style>
  
  <text x="400" y="30" text-anchor="middle" class="title">Iran Protest Intensity Map - January 10, 2026</text>
  
  <!-- Simplified province representations - approximate positions -->
  <!-- In production, use actual GeoJSON boundaries -->
  
  <!-- Legend -->
  <rect x="650" y="80" width="20" height="20" class="high"/>
  <text x="680" y="95" class="legend-text">High Intensity</text>
  
  <rect x="650" y="110" width="20" height="20" class="medium"/>
  <text x="680" y="125" class="legend-text">Medium Intensity</text>
  
  <rect x="650" y="140" width="20" height="20" class="low"/>
  <text x="680" y="155" class="legend-text">Low Intensity</text>
  
  <rect x="650" y="170" width="20" height="20" class="none"/>
  <text x="680" y="185" class="legend-text">No Reports</text>
  
  <!-- Placeholder map outline -->
  <path d="M150,150 L250,100 L400,80 L550,100 L650,180 L680,300 L650,450 L500,520 L350,500 L200,450 L100,350 L120,250 Z" 
        class="province none" fill-opacity="0.5"/>
  
  <!-- Key hotspot markers based on intel -->
  <circle cx="300" cy="200" r="15" class="high" opacity="0.7">
    <title>Tehran - High Intensity</title>
  </circle>
  <text x="300" y="230" text-anchor="middle" class="label">Tehran</text>
  
  <circle cx="180" cy="280" r="12" class="high" opacity="0.7">
    <title>Kurdistan/Kermanshah - High Intensity</title>
  </circle>
  <text x="180" y="310" text-anchor="middle" class="label">Kermanshah</text>
  
  <circle cx="220" cy="220" r="10" class="high" opacity="0.7">
    <title>Lorestan - High Intensity</title>
  </circle>
  <text x="220" y="245" text-anchor="middle" class="label">Lorestan</text>
  
  <circle cx="580" cy="400" r="12" class="high" opacity="0.7">
    <title>Sistan-Baluchestan - High Intensity</title>
  </circle>
  <text x="580" y="430" text-anchor="middle" class="label">Zahedan</text>
  
  <circle cx="400" cy="350" r="10" class="medium" opacity="0.7">
    <title>Isfahan - Medium Intensity</title>
  </circle>
  <text x="400" y="375" text-anchor="middle" class="label">Isfahan</text>
  
  <circle cx="300" cy="420" r="10" class="medium" opacity="0.7">
    <title>Fars/Shiraz - Medium Intensity</title>
  </circle>
  <text x="300" y="445" text-anchor="middle" class="label">Shiraz</text>
  
  <!-- Ethnic region labels -->
  <text x="160" y="260" class="label" style="font-style: italic; fill: #8e44ad;">Kurdish Region</text>
  <text x="560" y="380" class="label" style="font-style: italic; fill: #8e44ad;">Baloch Region</text>
  
  <!-- Note -->
  <text x="400" y="570" text-anchor="middle" class="legend-text" style="font-style: italic;">
    Note: Simplified representation. See intel data for complete provincial breakdown.
  </text>
  
</svg>
"""
    
    with open(output_path, 'w') as f:
        f.write(svg_content)
    
    print(f"Saved map to {output_path}")


def create_sensitivity_chart(results: dict, output_path: str):
    """Create sensitivity analysis visualization"""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed")
        return
    
    event_rates = results["key_event_rates"]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    events = list(event_rates.keys())
    rates = list(event_rates.values())
    
    colors = ['#e74c3c', '#3498db', '#9b59b6', '#f39c12']
    
    bars = ax.barh(events, rates, color=colors[:len(events)], edgecolor='black', linewidth=0.5)
    
    ax.set_xlabel("Frequency Across Simulations", fontsize=12)
    ax.set_title("Key Event Occurrence Rates\n(Monte Carlo Simulation)", fontsize=14)
    
    # Add percentage labels
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
                f'{rate:.1%}', va='center', fontsize=10)
    
    ax.set_xlim(0, max(rates) * 1.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved sensitivity chart to {output_path}")


def create_scenario_narratives(results: dict, intel: dict, output_path: str):
    """Generate narrative descriptions of key scenarios"""
    
    narratives = []
    
    narratives.append("# Iran Crisis Scenario Analysis\n")
    narratives.append(f"*Generated from {results['n_runs']:,} Monte Carlo simulations*\n\n")
    
    narratives.append("## Outcome Probability Distribution\n\n")
    
    for outcome, data in sorted(results["outcome_distribution"].items(),
                                key=lambda x: -x[1]["probability"]):
        narratives.append(f"### {outcome.replace('_', ' ').title()}\n")
        narratives.append(f"**Probability:** {data['probability']:.1%} ")
        narratives.append(f"(95% CI: {data['ci_low']:.1%} - {data['ci_high']:.1%})\n\n")
        
        # Add timing if available
        if outcome in results.get("outcome_timing", {}):
            timing = results["outcome_timing"][outcome]
            narratives.append(f"**Typical timing:** Day {timing['median_day']:.0f} ")
            narratives.append(f"(range: Day {timing['min_day']} - {timing['max_day']})\n\n")
        
        # Scenario description
        descriptions = {
            "REGIME_SURVIVES_STATUS_QUO": 
                "The regime successfully suppresses protests through a combination of "
                "security force deployments, internet blackouts, and targeted arrests. "
                "Protest momentum declines as economic conditions stabilize or protesters "
                "face exhaustion. No significant concessions are made.",
            
            "REGIME_SURVIVES_WITH_CONCESSIONS":
                "The regime survives but is forced to make meaningful policy changes. "
                "This could include economic reforms, personnel changes in government, "
                "or limited political opening. The Islamic Republic structure remains intact.",
            
            "MANAGED_TRANSITION":
                "Khamenei dies or is incapacitated, triggering the succession process. "
                "The Assembly of Experts selects a new Supreme Leader. The transition "
                "is relatively orderly, though the new leader may face immediate challenges.",
            
            "REGIME_COLLAPSE_CHAOTIC":
                "Security force defections or elite fragmentation leads to regime collapse. "
                "No orderly transition occurs. Power vacuum emerges with competing factions. "
                "Significant risk of violence and regional spillover.",
            
            "ETHNIC_FRAGMENTATION":
                "One or more peripheral regions (Kurdistan, Balochistan, Khuzestan) "
                "achieve de facto autonomy or active separatist conflict. Could occur "
                "alongside other outcomes. Triggers regional responses from neighbors."
        }
        
        if outcome in descriptions:
            narratives.append(f"{descriptions[outcome]}\n\n")
    
    narratives.append("## Key Event Analysis\n\n")
    
    for event, rate in results["key_event_rates"].items():
        narratives.append(f"- **{event.replace('_', ' ').title()}:** {rate:.1%} of simulations\n")
    
    narratives.append("\n## Sample Trajectories\n\n")
    
    for i, traj in enumerate(results.get("sample_trajectories", [])[:5], 1):
        narratives.append(f"### Trajectory {i}: {traj['outcome']}\n")
        narratives.append(f"*Resolved on Day {traj['outcome_day']}*\n\n")
        for event in traj["events"]:
            narratives.append(f"- {event}\n")
        narratives.append("\n")
    
    with open(output_path, 'w') as f:
        f.write("".join(narratives))
    
    print(f"Saved scenario narratives to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Iran Crisis Visualization")
    parser.add_argument("--results", required=True, help="Path to simulation results JSON")
    parser.add_argument("--intel", required=True, help="Path to intel JSON file")
    parser.add_argument("--output-dir", default="outputs", help="Output directory")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Load data
    with open(args.results, 'r') as f:
        results = json.load(f)
    
    with open(args.intel, 'r') as f:
        intel = json.load(f)
    
    # Generate visualizations
    create_outcome_chart(results, str(output_dir / "outcome_distribution.png"))
    create_iran_map(intel, str(output_dir / "iran_protest_map.svg"))
    create_sensitivity_chart(results, str(output_dir / "event_rates.png"))
    create_scenario_narratives(results, intel, str(output_dir / "scenario_narratives.md"))
    
    print("\nVisualization complete!")


if __name__ == "__main__":
    main()

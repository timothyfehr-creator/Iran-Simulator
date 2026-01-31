#!/usr/bin/env python3
"""
Generate consolidated simulation report (HTML + Markdown).

Produces single-artifact reports with:
- Run manifest and inputs
- Outcome distribution with confidence intervals
- Time-to-event analysis
- Event rates and sensitivity analysis
- Top scenario pathways
- Data quality indicators

Usage:
    python -m src.report.generate_report \
        --run_dir runs/RUN_20260111_v3 \
        --output_html runs/RUN_20260111_v3/report.html \
        --output_md runs/RUN_20260111_v3/report.md
"""

import argparse
import json
import base64
import io
import os
import sys
from typing import Dict, List, Any, Tuple
from datetime import datetime

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np


def load_run_data(run_dir: str) -> Dict[str, Any]:
    """Load all relevant data files from a run directory."""
    data = {}

    # Load simulation results
    sim_path = os.path.join(run_dir, "simulation_results.json")
    if os.path.exists(sim_path):
        with open(sim_path, 'r') as f:
            data['simulation'] = json.load(f)

    # Load compiled intel
    intel_path = os.path.join(run_dir, "compiled_intel.json")
    if os.path.exists(intel_path):
        with open(intel_path, 'r') as f:
            data['intel'] = json.load(f)

    # Load QA report
    qa_path = os.path.join(run_dir, "qa_report.json")
    if os.path.exists(qa_path):
        with open(qa_path, 'r') as f:
            data['qa'] = json.load(f)

    # Load merge report
    merge_path = os.path.join(run_dir, "merge_report.json")
    if os.path.exists(merge_path):
        with open(merge_path, 'r') as f:
            data['merge'] = json.load(f)

    # Load run manifest
    manifest_path = os.path.join(run_dir, "run_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as f:
            data['manifest'] = json.load(f)

    # Load import warnings
    warnings_path = os.path.join(run_dir, "import_warnings.json")
    if os.path.exists(warnings_path):
        with open(warnings_path, 'r') as f:
            data['warnings'] = json.load(f)

    # Load coverage report (if v3 strict validation was used)
    coverage_path = os.path.join(run_dir, "coverage_report.json")
    if os.path.exists(coverage_path):
        with open(coverage_path, 'r') as f:
            data['coverage'] = json.load(f)

    # Load priors (if available)
    priors_path = os.path.join(run_dir, "priors_resolved.json")
    if os.path.exists(priors_path):
        with open(priors_path, 'r') as f:
            data['priors'] = json.load(f)

    return data


def fig_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 string for HTML embedding."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64


def create_outcome_chart(data: Dict[str, Any]) -> str:
    """Create outcome distribution chart with confidence intervals."""
    sim = data['simulation']
    outcomes = sim['outcome_distribution']

    # Sort by probability descending
    sorted_outcomes = sorted(outcomes.items(), key=lambda x: x[1]['probability'], reverse=True)

    labels = []
    probs = []
    ci_lows = []
    ci_highs = []

    for outcome, stats in sorted_outcomes:
        # Format label
        label = outcome.replace('_', ' ').title()
        labels.append(label)
        probs.append(stats['probability'] * 100)
        ci_lows.append(stats['ci_low'] * 100)
        ci_highs.append(stats['ci_high'] * 100)

    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))

    x = np.arange(len(labels))
    colors = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c', '#95a5a6']

    bars = ax.bar(x, probs, color=colors[:len(labels)], alpha=0.8, edgecolor='black')

    # Add error bars for confidence intervals
    errors = [[probs[i] - ci_lows[i], ci_highs[i] - probs[i]] for i in range(len(probs))]
    ax.errorbar(x, probs, yerr=np.array(errors).T, fmt='none', ecolor='black',
                capsize=5, capthick=2, alpha=0.7)

    # Add value labels on bars
    for i, (bar, prob) in enumerate(zip(bars, probs)):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                f'{prob:.1f}%', ha='center', va='bottom', fontweight='bold', fontsize=11)

    ax.set_ylabel('Probability (%)', fontsize=12, fontweight='bold')
    ax.set_title('Iran Crisis: 90-Day Outcome Distribution\n(Monte Carlo Simulation)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha='right')
    ax.set_ylim(0, max(probs) * 1.15)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()
    return fig_to_base64(fig)


def create_time_to_event_chart(data: Dict[str, Any]) -> str:
    """Create time-to-event distribution chart."""
    sim = data['simulation']
    timing = sim['outcome_timing']

    fig, ax = plt.subplots(figsize=(12, 6))

    outcomes = list(timing.keys())
    means = [timing[o]['mean_day'] for o in outcomes]
    medians = [timing[o]['median_day'] for o in outcomes]

    x = np.arange(len(outcomes))
    width = 0.35

    bars1 = ax.bar(x - width/2, means, width, label='Mean Day', alpha=0.8, color='#3498db')
    bars2 = ax.bar(x + width/2, medians, width, label='Median Day', alpha=0.8, color='#e74c3c')

    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{int(height)}', ha='center', va='bottom', fontsize=9)

    ax.set_ylabel('Day (1-90)', fontsize=12, fontweight='bold')
    ax.set_title('Time to Event: When Outcomes Occur', fontsize=14, fontweight='bold', pad=20)
    ax.set_xticks(x)
    labels = [o.replace('_', ' ').title() for o in outcomes]
    ax.set_xticklabels(labels, rotation=15, ha='right', fontsize=10)
    ax.set_ylim(0, 100)
    ax.legend(loc='upper right', fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')

    plt.tight_layout()
    return fig_to_base64(fig)


def create_event_rates_chart(data: Dict[str, Any]) -> str:
    """Create key event occurrence rates chart."""
    sim = data['simulation']
    events = sim.get('key_event_rates', {})

    if not events:
        # Fallback: create empty chart
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No event rate data available',
                ha='center', va='center', fontsize=14)
        ax.axis('off')
        return fig_to_base64(fig)

    # Sort by rate
    sorted_events = sorted(events.items(), key=lambda x: x[1], reverse=True)

    labels = [e[0].replace('_', ' ').title() for e in sorted_events]
    rates = [e[1] * 100 for e in sorted_events]

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ['#e74c3c' if r > 50 else '#f39c12' if r > 10 else '#3498db' for r in rates]
    bars = ax.barh(labels, rates, color=colors, alpha=0.8, edgecolor='black')

    # Add value labels
    for i, (bar, rate) in enumerate(zip(bars, rates)):
        width = bar.get_width()
        ax.text(width + 1, bar.get_y() + bar.get_height()/2.,
                f'{rate:.1f}%', ha='left', va='center', fontweight='bold', fontsize=10)

    ax.set_xlabel('Frequency Across Simulations (%)', fontsize=12, fontweight='bold')
    ax.set_title('Key Event Occurrence Rates\n(Monte Carlo Simulation)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.set_xlim(0, max(rates) * 1.15)
    ax.grid(axis='x', alpha=0.3, linestyle='--')

    plt.tight_layout()
    return fig_to_base64(fig)


def create_tornado_chart(data: Dict[str, Any]) -> str:
    """Create sensitivity analysis tornado chart (placeholder - needs sensitivity data)."""
    # This would require running sensitivity analysis
    # For now, create placeholder based on merge report conflicts

    merge = data.get('merge', {})
    merge_notes = merge.get('merge_notes', [])

    # Extract claims with multiple candidates as proxy for sensitivity
    sensitive_paths = []
    for note in merge_notes:
        candidates = note.get('candidates', 1)
        # Handle both list and int formats for candidates
        candidate_count = len(candidates) if isinstance(candidates, list) else candidates
        if candidate_count > 1:
            path = note.get('path', '')
            if path:
                sensitive_paths.append((path, candidate_count))

    # Sort by candidate count and take top 10
    sensitive_paths.sort(key=lambda x: x[1], reverse=True)
    top_10 = sensitive_paths[:10]

    if not top_10:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(0.5, 0.5, 'No sensitivity data available\n(Run dedicated sensitivity analysis)',
                ha='center', va='center', fontsize=12)
        ax.axis('off')
        return fig_to_base64(fig)

    labels = [p[0].split('.')[-1][:30] for p in top_10]  # Last component, truncated
    values = [p[1] for p in top_10]

    fig, ax = plt.subplots(figsize=(10, 8))

    colors = plt.cm.RdYlGn_r(np.linspace(0.3, 0.7, len(labels)))
    bars = ax.barh(labels, values, color=colors, alpha=0.8, edgecolor='black')

    # Add value labels
    for bar, val in zip(bars, values):
        width = bar.get_width()
        ax.text(width + 0.1, bar.get_y() + bar.get_height()/2.,
                f'{int(val)}', ha='left', va='center', fontweight='bold')

    ax.set_xlabel('Number of Competing Claims', fontsize=12, fontweight='bold')
    ax.set_title('Top Contested Claims (Proxy for Sensitivity)\n(More candidates = higher uncertainty)',
                 fontsize=14, fontweight='bold', pad=20)
    ax.grid(axis='x', alpha=0.3, linestyle='--')

    plt.tight_layout()
    return fig_to_base64(fig)


def extract_top_pathways(data: Dict[str, Any], n: int = 5) -> List[Dict[str, Any]]:
    """Extract top scenario pathways from sample trajectories."""
    sim = data['simulation']
    trajectories = sim.get('sample_trajectories', [])

    if not trajectories:
        return []

    # Take first n trajectories as representatives
    top_pathways = []
    for i, traj in enumerate(trajectories[:n]):
        pathway = {
            'id': i + 1,
            'outcome': traj.get('outcome', 'UNKNOWN'),
            'resolved_day': traj.get('outcome_day', traj.get('resolved_on_day', 'N/A')),
            'events': traj.get('events', [])
        }
        top_pathways.append(pathway)

    return top_pathways


def generate_html_report(data: Dict[str, Any], output_path: str):
    """Generate self-contained HTML report with embedded images."""

    # Generate all charts
    outcome_chart = create_outcome_chart(data)
    time_chart = create_time_to_event_chart(data)
    events_chart = create_event_rates_chart(data)
    tornado_chart = create_tornado_chart(data)

    # Extract data
    sim = data.get('simulation', {})
    manifest = data.get('manifest', {})
    qa = data.get('qa', {})
    warnings = data.get('warnings', {})
    coverage = data.get('coverage', {})

    n_runs = sim.get('n_runs', 0)
    outcomes = sim.get('outcome_distribution', {})
    events = sim.get('key_event_rates', {})

    # Extract top pathways
    pathways = extract_top_pathways(data, n=5)

    # Build HTML
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Iran Crisis Simulation Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .section {{
            background: white;
            padding: 25px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #2c3e50;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .section h3 {{
            color: #34495e;
            margin-top: 20px;
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .metric {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #667eea;
        }}
        .metric-label {{
            font-size: 0.9em;
            color: #666;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .chart {{
            margin: 20px 0;
            text-align: center;
        }}
        .chart img {{
            max-width: 100%;
            height: auto;
            border-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #667eea;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background: #f5f5f5;
        }}
        .pathway {{
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
        }}
        .pathway-header {{
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .event-list {{
            margin-left: 20px;
            color: #555;
        }}
        .alert {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }}
        .alert.danger {{
            background: #f8d7da;
            border-left-color: #dc3545;
        }}
        .alert.success {{
            background: #d4edda;
            border-left-color: #28a745;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🇮🇷 Iran Crisis Simulation Report</h1>
        <p>Monte Carlo Analysis • {n_runs:,} Simulations • Generated {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</p>
    </div>

    <div class="section">
        <h2>📊 Run Manifest & Inputs</h2>
        <div class="metric-grid">
            <div class="metric">
                <div class="metric-label">Simulations Run</div>
                <div class="metric-value">{n_runs:,}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Data Cutoff</div>
                <div class="metric-value">{manifest.get('data_cutoff_utc', 'N/A')[:10]}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Evidence Docs</div>
                <div class="metric-value">{coverage.get('total_docs', qa.get('import_summary', {}).get('dropped_docs', 'N/A'))}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Source Buckets</div>
                <div class="metric-value">{coverage.get('bucket_count', 'N/A')}</div>
            </div>
        </div>

        {"<div class='alert danger'>" + "<br>".join(coverage.get('failures', [])) + "</div>" if coverage.get('failures') else ""}
        {"<div class='alert'>" + "<br>".join(coverage.get('warnings', [])) + "</div>" if coverage.get('warnings') else ""}
    </div>

    <div class="section">
        <h2>🎯 Outcome Distribution</h2>
        <div class="chart">
            <img src="data:image/png;base64,{outcome_chart}" alt="Outcome Distribution">
        </div>

        <table>
            <tr>
                <th>Outcome</th>
                <th>Probability</th>
                <th>95% CI</th>
                <th>Count</th>
            </tr>
"""

    # Add outcome table rows
    for outcome, stats in sorted(outcomes.items(), key=lambda x: x[1]['probability'], reverse=True):
        outcome_name = outcome.replace('_', ' ').title()
        prob = stats['probability'] * 100
        ci_low = stats['ci_low'] * 100
        ci_high = stats['ci_high'] * 100
        count = stats['count']

        html += f"""
            <tr>
                <td><strong>{outcome_name}</strong></td>
                <td>{prob:.1f}%</td>
                <td>{ci_low:.1f}% - {ci_high:.1f}%</td>
                <td>{count:,}</td>
            </tr>
"""

    html += f"""
        </table>
    </div>

    <div class="section">
        <h2>⏱️ Time-to-Event Analysis</h2>
        <div class="chart">
            <img src="data:image/png;base64,{time_chart}" alt="Time to Event">
        </div>
    </div>

    <div class="section">
        <h2>🔔 Key Event Rates</h2>
        <div class="chart">
            <img src="data:image/png;base64,{events_chart}" alt="Event Rates">
        </div>
    </div>

    <div class="section">
        <h2>🌪️ Sensitivity Analysis</h2>
        <div class="chart">
            <img src="data:image/png;base64,{tornado_chart}" alt="Sensitivity">
        </div>
        <p><em>Note: This shows contested claims from merge process. Run dedicated sensitivity analysis for full parameter sweep.</em></p>
    </div>

    <div class="section">
        <h2>🛤️ Top Scenario Pathways</h2>
        <p>Sample trajectories showing how different outcomes unfold:</p>
"""

    # Add pathways
    for pathway in pathways:
        outcome_name = pathway['outcome'].replace('_', ' ').title()
        html += f"""
        <div class="pathway">
            <div class="pathway-header">
                Pathway {pathway['id']}: {outcome_name} (Day {pathway['resolved_day']})
            </div>
            <ul class="event-list">
"""
        for event in pathway['events']:
            # Handle both string and dict events
            if isinstance(event, str):
                html += f"                <li>{event}</li>\n"
            else:
                day = event.get('day', '?')
                desc = event.get('description', event.get('event', 'Unknown'))
                html += f"                <li>Day {day}: {desc}</li>\n"

        html += """
            </ul>
        </div>
"""

    html += f"""
    </div>

    <div class="section">
        <h2>📋 Data Quality Indicators</h2>
        <h3>Import Summary</h3>
        <table>
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Dropped Docs (Cutoff)</td>
                <td>{qa.get('dropped_docs', warnings.get('summary', {}).get('dropped_docs', 0))}</td>
            </tr>
            <tr>
                <td>Dropped Claims</td>
                <td>{qa.get('dropped_claims', warnings.get('summary', {}).get('dropped_claims', 0))}</td>
            </tr>
            <tr>
                <td>Normalized Claim Classes</td>
                <td>{qa.get('normalized_fields', {}).get('claim_classes', warnings.get('summary', {}).get('normalized_claim_classes', 0))}</td>
            </tr>
            <tr>
                <td>Timestamp Anomalies</td>
                <td>{qa.get('timestamp_anomalies', warnings.get('summary', {}).get('timestamp_anomalies', 0))}</td>
            </tr>
        </table>

        <h3>QA Status</h3>
        <div class="alert {"success" if qa.get('status') == 'OK' else 'danger'}">
            <strong>Status:</strong> {qa.get('status', 'UNKNOWN')}
        </div>
    </div>

    <div class="footer">
        <p>Generated by Iran Crisis Simulator • Open Source Intelligence Analysis</p>
        <p>For official use only • UNCLASSIFIED</p>
    </div>
</body>
</html>
"""

    # Write HTML file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"✓ HTML report written to {output_path}")


def generate_markdown_report(data: Dict[str, Any], output_path: str):
    """Generate Notion-friendly Markdown report."""

    sim = data.get('simulation', {})
    manifest = data.get('manifest', {})
    qa = data.get('qa', {})
    coverage = data.get('coverage', {})

    n_runs = sim.get('n_runs', 0)
    outcomes = sim.get('outcome_distribution', {})
    events = sim.get('key_event_rates', {})

    pathways = extract_top_pathways(data, n=5)

    md = f"""# Iran Crisis Simulation Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
**Simulations:** {n_runs:,}
**Data Cutoff:** {manifest.get('data_cutoff_utc', 'N/A')}

---

## 📊 Run Manifest & Inputs

| Metric | Value |
|--------|-------|
| Simulations Run | {n_runs:,} |
| Data Cutoff | {manifest.get('data_cutoff_utc', 'N/A')} |
| Evidence Docs | {coverage.get('total_docs', 'N/A')} |
| Farsi Docs | {coverage.get('farsi_docs', 'N/A')} |
| Source Buckets | {coverage.get('bucket_count', 'N/A')} ({', '.join(coverage.get('buckets_found', []))}) |

"""

    if coverage.get('failures'):
        md += "### ⚠️ Coverage Failures\n\n"
        for failure in coverage.get('failures', []):
            md += f"- ❌ {failure}\n"
        md += "\n"

    md += """
---

## 🎯 Outcome Distribution (90-Day Horizon)

| Outcome | Probability | 95% CI | Count |
|---------|------------|--------|-------|
"""

    for outcome, stats in sorted(outcomes.items(), key=lambda x: x[1]['probability'], reverse=True):
        outcome_name = outcome.replace('_', ' ').title()
        prob = stats['probability'] * 100
        ci_low = stats['ci_low'] * 100
        ci_high = stats['ci_high'] * 100
        count = stats['count']

        md += f"| **{outcome_name}** | {prob:.1f}% | {ci_low:.1f}% - {ci_high:.1f}% | {count:,} |\n"

    md += "\n---\n\n## ⏱️ Time-to-Event Analysis\n\n| Outcome | Mean Day | Median Day | Range |\n|---------|----------|------------|-------|\n"

    timing = sim.get('outcome_timing', {})
    for outcome, stats in timing.items():
        outcome_name = outcome.replace('_', ' ').title()
        mean_day = stats['mean_day']
        median_day = stats['median_day']
        min_day = stats['min_day']
        max_day = stats['max_day']

        md += f"| {outcome_name} | {mean_day:.1f} | {median_day} | {min_day}-{max_day} |\n"

    md += "\n---\n\n## 🔔 Key Event Rates\n\n| Event | Frequency |\n|-------|----------|\n"

    for event, rate in sorted(events.items(), key=lambda x: x[1], reverse=True):
        event_name = event.replace('_', ' ').title()
        md += f"| {event_name} | {rate*100:.1f}% |\n"

    md += "\n---\n\n## 🛤️ Top Scenario Pathways\n\n"

    for pathway in pathways:
        outcome_name = pathway['outcome'].replace('_', ' ').title()
        md += f"### Pathway {pathway['id']}: {outcome_name}\n\n"
        md += f"**Resolved:** Day {pathway['resolved_day']}\n\n"
        md += "**Timeline:**\n"
        for event in pathway['events']:
            # Handle both string and dict events
            if isinstance(event, str):
                md += f"- {event}\n"
            else:
                day = event.get('day', '?')
                desc = event.get('description', event.get('event', 'Unknown'))
                md += f"- Day {day}: {desc}\n"
        md += "\n"

    md += """---

## 📋 Data Quality Summary

| Metric | Value |
|--------|-------|
"""

    md += f"| Dropped Docs (Cutoff) | {qa.get('dropped_docs', 0)} |\n"
    md += f"| Dropped Claims | {qa.get('dropped_claims', 0)} |\n"
    md += f"| Normalized Claim Classes | {qa.get('normalized_fields', {}).get('claim_classes', 0)} |\n"
    md += f"| Timestamp Anomalies | {qa.get('timestamp_anomalies', 0)} |\n"
    md += f"| QA Status | **{qa.get('status', 'UNKNOWN')}** |\n"

    md += "\n---\n\n*Generated by Iran Crisis Simulator • Open Source Intelligence Analysis*\n"

    # Write Markdown file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md)

    print(f"✓ Markdown report written to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate consolidated simulation report (HTML + Markdown)"
    )
    parser.add_argument(
        "--run_dir",
        required=True,
        help="Run directory containing all output files"
    )
    parser.add_argument(
        "--output_html",
        help="Output path for HTML report (default: run_dir/report.html)"
    )
    parser.add_argument(
        "--output_md",
        help="Output path for Markdown report (default: run_dir/report.md)"
    )

    args = parser.parse_args()

    # Set default output paths if not provided
    if not args.output_html:
        args.output_html = os.path.join(args.run_dir, "report.html")
    if not args.output_md:
        args.output_md = os.path.join(args.run_dir, "report.md")

    print(f"Loading data from {args.run_dir}...")
    data = load_run_data(args.run_dir)

    if not data.get('simulation'):
        print("ERROR: No simulation_results.json found in run directory")
        sys.exit(1)

    print("Generating reports...")
    generate_html_report(data, args.output_html)
    generate_markdown_report(data, args.output_md)

    print("\n✓ Report generation complete!")
    print(f"  HTML: {args.output_html}")
    print(f"  Markdown: {args.output_md}")


if __name__ == "__main__":
    main()

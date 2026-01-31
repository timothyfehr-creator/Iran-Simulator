#!/usr/bin/env python3
"""
Generate human-readable Markdown report from diff_report.json.

Usage:
    python -m src.report.generate_diff_report runs/RUN_20260112_daily/diff_report.json --output runs/RUN_20260112_daily/daily_summary.md
"""

import argparse
import json
import sys
from datetime import datetime


def format_outcome_table(outcome_changes: dict) -> str:
    """Format outcome probability changes as Markdown table."""
    if not outcome_changes:
        return "_No outcome data available_\n"

    # Filter for significant or any non-zero changes
    significant_changes = {
        k: v for k, v in outcome_changes.items()
        if v.get('significant') or abs(v.get('delta', 0)) > 0.5
    }

    if not significant_changes:
        return "_No significant outcome changes_\n"

    rows = []
    rows.append("| Outcome | Previous | Current | Change |")
    rows.append("|---------|----------|---------|--------|")

    for outcome, change in significant_changes.items():
        outcome_name = outcome.replace('_', ' ').title()
        prev = f"{change['previous']:.1f}%"
        curr = f"{change['current']:.1f}%"

        delta = change['delta']
        if delta > 0:
            change_str = f"🔺 +{delta:.1f}%"
        elif delta < 0:
            change_str = f"🔻 {delta:.1f}%"
        else:
            change_str = f"{delta:.1f}%"

        rows.append(f"| {outcome_name} | {prev} | {curr} | {change_str} |")

    return "\n".join(rows) + "\n"


def format_event_table(event_changes: dict) -> str:
    """Format event rate changes as Markdown table."""
    if not event_changes:
        return "_No event rate data available_\n"

    # Filter for significant changes
    significant_changes = {
        k: v for k, v in event_changes.items()
        if v.get('significance') in ['HIGH', 'MEDIUM'] or abs(v.get('delta', 0)) > 1
    }

    if not significant_changes:
        return "_No significant event rate changes_\n"

    rows = []
    rows.append("| Event | Previous | Current | Change |")
    rows.append("|-------|----------|---------|--------|")

    for event, change in significant_changes.items():
        event_name = event.replace('_', ' ').title()
        prev = f"{change['previous']:.1f}%"
        curr = f"{change['current']:.1f}%"

        delta = change['delta']
        if delta > 0:
            change_str = f"🔺 +{delta:.1f}%"
        elif delta < 0:
            change_str = f"🔻 {delta:.1f}%"
        else:
            change_str = f"{delta:.1f}%"

        rows.append(f"| {event_name} | {prev} | {curr} | {change_str} |")

    return "\n".join(rows) + "\n"


def format_claim_changes(claim_changes: list) -> str:
    """Format changed claim winners as numbered list."""
    if not claim_changes:
        return "_No changed assessments_\n"

    lines = []
    for i, change in enumerate(claim_changes[:10], 1):  # Top 10
        path = change['path'].split('.')[-1].replace('_', ' ').title()
        prev_winner = change.get('previous_winner', 'Unknown')
        curr_winner = change.get('current_winner', 'Unknown')

        lines.append(f"{i}. **{path}**: Winner changed from {prev_winner} to {curr_winner}")

    if len(claim_changes) > 10:
        lines.append(f"\n_...and {len(claim_changes) - 10} more changed assessments_")

    return "\n".join(lines) + "\n"


def format_coverage_changes(coverage_changes: dict) -> str:
    """Format coverage improvements as bullet list."""
    if not coverage_changes:
        return "_No coverage data available_\n"

    lines = []

    if 'total_docs' in coverage_changes:
        docs = coverage_changes['total_docs']
        if docs['delta'] != 0:
            lines.append(f"- Evidence docs: {docs['previous']} → {docs['current']} ({docs['delta']:+d})")

    if 'farsi_docs' in coverage_changes:
        farsi = coverage_changes['farsi_docs']
        if farsi['delta'] != 0:
            lines.append(f"- Farsi sources: {farsi['previous']} → {farsi['current']} ({farsi['delta']:+d})")

    if 'bucket_count' in coverage_changes:
        buckets = coverage_changes['bucket_count']
        if buckets['delta'] != 0:
            lines.append(f"- Source buckets: {buckets['previous']} → {buckets['current']} ({buckets['delta']:+d})")

    if coverage_changes.get('status_change'):
        status = coverage_changes['status_change']
        if 'PASS' in status:
            lines.append(f"- Coverage status: {status} ✅")
        elif 'FAIL' in status:
            lines.append(f"- Coverage status: {status} ⚠️")
        else:
            lines.append(f"- Coverage status: {status}")

    if not lines:
        return "_No coverage changes_\n"

    return "\n".join(lines) + "\n"


def format_coverage_deltas(coverage_deltas: dict) -> str:
    """Format coverage deltas showing bucket changes."""
    if not coverage_deltas:
        return ""

    lines = []

    buckets_lost = coverage_deltas.get('buckets_lost', [])
    buckets_recovered = coverage_deltas.get('buckets_recovered', [])

    if buckets_lost:
        lines.append("**Buckets Now Missing:**")
        for bucket in buckets_lost:
            lines.append(f"- {bucket}")

    if buckets_recovered:
        lines.append("**Buckets Recovered:**")
        for bucket in buckets_recovered:
            lines.append(f"- {bucket} ✅")

    if not lines:
        return ""

    return "\n".join(lines) + "\n"


def format_health_deltas(health_deltas: dict) -> str:
    """Format health status changes."""
    if not health_deltas:
        return ""

    transitions = health_deltas.get('transitions', [])
    if not transitions:
        return ""

    lines = ["**Source Health Transitions:**"]

    for t in transitions:
        source = t['source']
        from_status = t['from']
        to_status = t['to']

        if to_status == 'DOWN':
            lines.append(f"- {source}: {from_status} → **{to_status}** ⚠️")
        elif to_status == 'DEGRADED':
            lines.append(f"- {source}: {from_status} → {to_status}")
        elif to_status == 'OK':
            lines.append(f"- {source}: {from_status} → {to_status} ✅")
        else:
            lines.append(f"- {source}: {from_status} → {to_status}")

    overall = health_deltas.get('overall_status', 'UNKNOWN')
    lines.append(f"\n**Overall Health Status:** {overall}")

    return "\n".join(lines) + "\n"


def format_contested_claims(contested_claims: list) -> str:
    """Format contested claims section."""
    if not contested_claims:
        return ""

    lines = []

    # Only show claims with actual conflicts (not just high candidate count)
    true_conflicts = [c for c in contested_claims if 'tie' in c.get('reason', '').lower() or 'conflict' in c.get('reason', '').lower()]

    if true_conflicts:
        lines.append("**Conflicting Claims (value set to null):**")
        for claim in true_conflicts[:5]:
            path = claim['path'].split('.')[-1].replace('_', ' ').title()
            lines.append(f"- {path}: {claim.get('reason', 'conflict')}")

    # High candidate count
    high_candidates = [c for c in contested_claims if c.get('candidates', 0) >= 3 and c not in true_conflicts]
    if high_candidates:
        if lines:
            lines.append("")
        lines.append("**High Contention (3+ claims):**")
        for claim in high_candidates[:5]:
            path = claim['path'].split('.')[-1].replace('_', ' ').title()
            lines.append(f"- {path}: {claim.get('candidates', 0)} competing claims")

    if not lines:
        return ""

    return "\n".join(lines) + "\n"


def generate_markdown_report(diff_data: dict) -> str:
    """Generate complete Markdown report."""
    comparison = diff_data.get('comparison', {})
    prev_run = comparison.get('previous_run', 'Unknown')
    curr_run = comparison.get('current_run', 'Unknown')
    generated_at = comparison.get('generated_at', '')

    # Parse date from current_run
    try:
        run_date = curr_run.split('_')[1]  # Extract YYYYMMDD
        formatted_date = f"{run_date[:4]}-{run_date[4:6]}-{run_date[6:8]}"
    except:
        formatted_date = "Unknown"

    lines = [
        f"# Daily Update Summary: {formatted_date}",
        "",
        f"**Previous Run:** {prev_run}",
        f"**Current Run:** {curr_run}",
        f"**Generated:** {generated_at[:19]} UTC" if generated_at else "",
        "",
        "---",
        "",
        "## Key Changes",
        ""
    ]

    # Outcome probabilities
    lines.append("### Outcome Probabilities")
    lines.append("")
    lines.append(format_outcome_table(diff_data.get('outcome_changes', {})))

    # Event rates
    lines.append("### Key Event Rates")
    lines.append("")
    lines.append(format_event_table(diff_data.get('event_rate_changes', {})))

    # Changed assessments
    claim_changes = diff_data.get('claim_winner_changes', [])
    if claim_changes:
        lines.append("### Changed Assessments")
        lines.append("")
        lines.append(format_claim_changes(claim_changes))

    # Coverage improvements
    coverage_changes = diff_data.get('coverage_changes', {})
    if coverage_changes and any(c.get('delta', 0) != 0 for c in coverage_changes.values() if isinstance(c, dict)):
        lines.append("### Coverage Changes")
        lines.append("")
        lines.append(format_coverage_changes(coverage_changes))

    # Coverage deltas (buckets lost/recovered)
    coverage_deltas = diff_data.get('coverage_deltas', {})
    coverage_deltas_text = format_coverage_deltas(coverage_deltas)
    if coverage_deltas_text:
        lines.append("### Bucket Coverage Deltas")
        lines.append("")
        lines.append(coverage_deltas_text)

    # Health deltas
    health_deltas = diff_data.get('health_deltas', {})
    health_deltas_text = format_health_deltas(health_deltas)
    if health_deltas_text:
        lines.append("### Source Health Changes")
        lines.append("")
        lines.append(health_deltas_text)

    # Contested claims
    contested_claims = diff_data.get('contested_claims', [])
    contested_text = format_contested_claims(contested_claims)
    if contested_text:
        lines.append("### Contested Claims")
        lines.append("")
        lines.append(contested_text)

    # Summary
    summary = diff_data.get('summary', {})
    lines.extend([
        "---",
        "",
        "## Summary",
        "",
        f"**Major Changes:** {summary.get('major_changes', 0)}",
        f"**Minor Changes:** {summary.get('minor_changes', 0)}",
        f"**Contested Claims:** {summary.get('contested_claim_count', 0)}",
        f"**Health Transitions:** {summary.get('health_transitions', 0)}",
        f"**Overall Assessment:** {summary.get('overall_assessment', 'Unknown')}",
        ""
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate Markdown diff report")
    parser.add_argument('diff_json', help="Path to diff_report.json")
    parser.add_argument('--output', default='daily_summary.md', help="Output Markdown file")

    args = parser.parse_args()

    # Load diff report
    try:
        with open(args.diff_json, 'r') as f:
            diff_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Diff report not found: {args.diff_json}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {args.diff_json}: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate Markdown
    markdown = generate_markdown_report(diff_data)

    # Write output
    with open(args.output, 'w') as f:
        f.write(markdown)

    print(f"✓ Daily summary written to {args.output}")


if __name__ == '__main__':
    main()

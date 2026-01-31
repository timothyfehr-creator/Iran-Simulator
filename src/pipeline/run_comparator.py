#!/usr/bin/env python3
"""
Compare two simulation runs and generate diff report.

Usage:
    python -m src.pipeline.run_comparator runs/RUN_20260111_daily runs/RUN_20260112_daily --output runs/RUN_20260112_daily/diff_report.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_run_data(run_dir: str) -> Dict[str, Any]:
    """
    Load all relevant data from a run directory.

    Args:
        run_dir: Path to run directory

    Returns:
        Dictionary with simulation_results, merge_report, coverage_report, etc.
    """
    data = {}

    # Required files
    required_files = {
        'simulation_results': 'simulation_results.json',
        'merge_report': 'merge_report.json',
        'compiled_intel': 'compiled_intel.json'
    }

    for key, filename in required_files.items():
        path = os.path.join(run_dir, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                data[key] = json.load(f)
        else:
            print(f"Warning: {filename} not found in {run_dir}", file=sys.stderr)
            data[key] = None

    # Optional files
    optional_files = {
        'coverage_report': 'coverage_report.json',
        'qa_report': 'qa_report.json',
        'run_manifest': 'run_manifest.json'
    }

    for key, filename in optional_files.items():
        path = os.path.join(run_dir, filename)
        if os.path.exists(path):
            with open(path, 'r') as f:
                data[key] = json.load(f)

    return data


def compare_outcomes(current: Dict, previous: Dict) -> Dict[str, Any]:
    """
    Compare outcome probability distributions.

    Args:
        current: Current simulation_results
        previous: Previous simulation_results

    Returns:
        Outcome changes dictionary
    """
    if not current or not previous:
        return {}

    outcome_changes = {}

    # Get outcome distributions
    curr_dist = current.get('outcome_distribution', {})
    prev_dist = previous.get('outcome_distribution', {})

    for outcome in curr_dist.keys():
        curr_prob = curr_dist[outcome]['probability'] * 100  # Convert to percentage
        prev_prob = prev_dist.get(outcome, {}).get('probability', 0) * 100

        delta = curr_prob - prev_prob

        # Check CI overlap
        curr_ci = curr_dist[outcome].get('ci_95', [curr_prob, curr_prob])
        prev_ci = prev_dist.get(outcome, {}).get('ci_95', [prev_prob, prev_prob])
        ci_overlap = not (curr_ci[1] < prev_ci[0] or prev_ci[1] < curr_ci[0])

        outcome_changes[outcome] = {
            'previous': round(prev_prob, 2),
            'current': round(curr_prob, 2),
            'delta': round(delta, 2),
            'direction': 'INCREASED' if delta > 0 else 'DECREASED' if delta < 0 else 'UNCHANGED',
            'ci_overlap': ci_overlap,
            'significant': abs(delta) > 1.0 and not ci_overlap  # >1% change with no CI overlap
        }

    return outcome_changes


def compare_event_rates(current: Dict, previous: Dict) -> Dict[str, Any]:
    """
    Compare key event occurrence rates.

    Args:
        current: Current simulation_results
        previous: Previous simulation_results

    Returns:
        Event rate changes dictionary
    """
    if not current or not previous:
        return {}

    event_changes = {}

    curr_rates = current.get('key_event_rates', {})
    prev_rates = previous.get('key_event_rates', {})

    for event in curr_rates.keys():
        curr_rate = curr_rates[event] * 100  # Convert to percentage
        prev_rate = prev_rates.get(event, 0) * 100

        delta = curr_rate - prev_rate

        event_changes[event] = {
            'previous': round(prev_rate, 2),
            'current': round(curr_rate, 2),
            'delta': round(delta, 2),
            'direction': 'INCREASED' if delta > 0 else 'DECREASED' if delta < 0 else 'UNCHANGED',
            'significance': 'HIGH' if abs(delta) > 5 else 'MEDIUM' if abs(delta) > 2 else 'LOW'
        }

    return event_changes


def compare_merge_notes(current: Dict, previous: Dict) -> List[Dict[str, Any]]:
    """
    Identify paths where claim winners changed.

    Args:
        current: Current merge_report
        previous: Previous merge_report

    Returns:
        List of changed claim winners
    """
    if not current or not previous:
        return []

    changes = []

    curr_notes = {note['path']: note for note in current.get('merge_notes', [])}
    prev_notes = {note['path']: note for note in previous.get('merge_notes', [])}

    for path, curr_note in curr_notes.items():
        prev_note = prev_notes.get(path)

        if not prev_note:
            continue

        curr_winner = curr_note.get('winner_claim_id')
        prev_winner = prev_note.get('winner_claim_id')

        if curr_winner != prev_winner and curr_winner and prev_winner:
            # Winner changed
            change = {
                'path': path,
                'previous_winner': prev_winner,
                'current_winner': curr_winner,
                'selector': curr_note.get('selector', {})
            }

            # Try to extract values (if available in compiled_intel)
            changes.append(change)

    return changes


def compare_coverage(current: Dict, previous: Dict) -> Dict[str, Any]:
    """
    Track changes in source diversity and quality.

    Args:
        current: Current coverage_report
        previous: Previous coverage_report

    Returns:
        Coverage changes dictionary
    """
    if not current or not previous:
        return {}

    coverage_changes = {}

    metrics = ['total_docs', 'farsi_docs', 'bucket_count']

    for metric in metrics:
        curr_val = current.get(metric, 0)
        prev_val = previous.get(metric, 0)
        delta = curr_val - prev_val

        coverage_changes[metric] = {
            'previous': prev_val,
            'current': curr_val,
            'delta': delta
        }

    # Status change
    curr_status = current.get('status', 'UNKNOWN')
    prev_status = previous.get('status', 'UNKNOWN')

    if curr_status != prev_status:
        coverage_changes['status_change'] = f"{prev_status} -> {curr_status}"
    else:
        coverage_changes['status_change'] = None

    return coverage_changes


def compute_coverage_deltas(current: Dict, previous: Dict) -> Dict[str, Any]:
    """
    Compute detailed coverage deltas including bucket changes.

    Args:
        current: Current coverage_report
        previous: Previous coverage_report

    Returns:
        Coverage deltas dictionary with buckets_missing_now/prev (full lists per spec)
    """
    if not current:
        return {}

    curr_missing = set(current.get('buckets_missing', []))
    prev_missing = set(previous.get('buckets_missing', [])) if previous else set()
    curr_present = set(current.get('buckets_present', []))
    prev_present = set(previous.get('buckets_present', [])) if previous else set()

    return {
        # Full lists per spec (not just deltas)
        'buckets_missing_now': list(curr_missing),  # Full current missing list
        'buckets_missing_prev': list(prev_missing),  # Full previous missing list
        # Delta lists (helpful for quick analysis)
        'buckets_recovered': list(prev_missing - curr_missing),  # Was missing, now present
        'buckets_lost': list(curr_missing - prev_missing),  # Was present, now missing
        'status_current': current.get('status', 'UNKNOWN'),
        'status_previous': previous.get('status', 'UNKNOWN') if previous else None
    }


def compute_health_deltas(current: Dict, previous: Dict) -> Dict[str, Any]:
    """
    Compute health status changes between runs.

    Args:
        current: Current coverage_report (with health_summary)
        previous: Previous coverage_report (with health_summary)

    Returns:
        Health deltas dictionary
    """
    curr_health = current.get('health_summary', {}) if current else {}
    prev_health = previous.get('health_summary', {}) if previous else {}

    curr_degraded = set(curr_health.get('degraded_sources', []))
    curr_down = set(curr_health.get('down_sources', []))
    prev_degraded = set(prev_health.get('degraded_sources', []))
    prev_down = set(prev_health.get('down_sources', []))

    # Compute transitions
    transitions = []

    # OK -> DEGRADED
    for source in curr_degraded - prev_degraded - prev_down:
        transitions.append({
            'source': source,
            'from': 'OK',
            'to': 'DEGRADED'
        })

    # OK/DEGRADED -> DOWN
    for source in curr_down - prev_down:
        if source in prev_degraded:
            transitions.append({'source': source, 'from': 'DEGRADED', 'to': 'DOWN'})
        else:
            transitions.append({'source': source, 'from': 'OK', 'to': 'DOWN'})

    # DOWN -> DEGRADED (recovering)
    for source in curr_degraded & prev_down:
        transitions.append({'source': source, 'from': 'DOWN', 'to': 'DEGRADED'})

    # DEGRADED/DOWN -> OK (recovered)
    for source in (prev_degraded | prev_down) - curr_degraded - curr_down:
        prev_status = 'DOWN' if source in prev_down else 'DEGRADED'
        transitions.append({'source': source, 'from': prev_status, 'to': 'OK'})

    return {
        'overall_status': curr_health.get('overall_status', 'UNKNOWN'),
        'transitions': transitions,
        'sources_degraded': list(curr_degraded),
        'sources_down': list(curr_down)
    }


def extract_contested_claims(current_merge: Dict) -> List[Dict[str, Any]]:
    """
    Extract claims with conflict groups (contested claims).

    Args:
        current_merge: Current merge_report

    Returns:
        List of contested claims with conflict details
    """
    if not current_merge:
        return []

    contested = []

    for note in current_merge.get('merge_notes', []):
        if note.get('conflict', False):
            contested.append({
                'path': note.get('path'),
                'conflict_group': note.get('conflicting_values', []),
                'winner': note.get('winner_claim_id'),
                'reason': note.get('reason', 'source_grade tie with different values'),
                'candidates': note.get('candidates', 0)
            })
        elif note.get('candidates', 0) >= 3:
            # High candidate count is also noteworthy
            contested.append({
                'path': note.get('path'),
                'conflict_group': [c.get('claim_id') for c in note.get('all_candidates', [])],
                'winner': note.get('winner_claim_id'),
                'reason': f'High candidate count ({note.get("candidates")} claims)',
                'candidates': note.get('candidates')
            })

    return contested


def generate_diff_report(previous_run: str, current_run: str) -> Dict[str, Any]:
    """
    Generate comprehensive diff report.

    Args:
        previous_run: Path to previous run directory
        current_run: Path to current run directory

    Returns:
        Diff report dictionary
    """
    print(f"Loading previous run: {previous_run}")
    prev_data = load_run_data(previous_run)

    print(f"Loading current run: {current_run}")
    curr_data = load_run_data(current_run)

    # Compare outcomes
    print("Comparing outcome distributions...")
    outcome_changes = compare_outcomes(curr_data['simulation_results'], prev_data['simulation_results'])

    # Compare event rates
    print("Comparing event rates...")
    event_changes = compare_event_rates(curr_data['simulation_results'], prev_data['simulation_results'])

    # Compare merge notes
    print("Comparing claim winners...")
    claim_changes = compare_merge_notes(curr_data['merge_report'], prev_data['merge_report'])

    # Compare coverage
    print("Comparing coverage...")
    coverage_changes = compare_coverage(curr_data.get('coverage_report'), prev_data.get('coverage_report'))

    # Compute coverage deltas (buckets_missing_now/prev)
    print("Computing coverage deltas...")
    coverage_deltas = compute_coverage_deltas(curr_data.get('coverage_report'), prev_data.get('coverage_report'))

    # Compute health deltas
    print("Computing health deltas...")
    health_deltas = compute_health_deltas(curr_data.get('coverage_report'), prev_data.get('coverage_report'))

    # Extract contested claims
    print("Extracting contested claims...")
    contested_claims = extract_contested_claims(curr_data.get('merge_report'))

    # Generate summary
    major_changes = sum(1 for oc in outcome_changes.values() if oc.get('significant', False))
    major_changes += sum(1 for ec in event_changes.values() if ec.get('significance') == 'HIGH')
    major_changes += len(claim_changes)

    minor_changes = sum(1 for oc in outcome_changes.values() if not oc.get('significant', False) and oc['delta'] != 0)
    minor_changes += sum(1 for ec in event_changes.values() if ec.get('significance') in ['LOW', 'MEDIUM'] and ec['delta'] != 0)

    # Determine overall assessment
    overall_assessment = "No significant changes"
    if major_changes > 5:
        overall_assessment = "Major shifts in crisis dynamics"
    elif major_changes > 2:
        overall_assessment = "Increased instability signals"
    elif major_changes > 0:
        overall_assessment = "Minor assessment updates"

    # Add health-related assessment
    if health_deltas.get('transitions'):
        down_transitions = [t for t in health_deltas['transitions'] if t['to'] == 'DOWN']
        if down_transitions:
            overall_assessment += f" (WARNING: {len(down_transitions)} source(s) went DOWN)"

    diff_report = {
        'comparison': {
            'previous_run': os.path.basename(previous_run),
            'current_run': os.path.basename(current_run),
            'generated_at': datetime.now(timezone.utc).isoformat()
        },
        'outcome_changes': outcome_changes,
        'event_rate_changes': event_changes,
        'claim_winner_changes': claim_changes,
        'contested_claims': contested_claims,
        'coverage_changes': coverage_changes,
        'coverage_deltas': coverage_deltas,
        'health_deltas': health_deltas,
        'summary': {
            'major_changes': major_changes,
            'minor_changes': minor_changes,
            'overall_assessment': overall_assessment,
            'contested_claim_count': len(contested_claims),
            'health_transitions': len(health_deltas.get('transitions', []))
        }
    }

    return diff_report


def main():
    parser = argparse.ArgumentParser(description="Compare two simulation runs")
    parser.add_argument('previous_run', help="Previous run directory")
    parser.add_argument('current_run', help="Current run directory")
    parser.add_argument('--output', default='diff_report.json', help="Output file path")

    args = parser.parse_args()

    # Verify directories exist
    if not os.path.isdir(args.previous_run):
        print(f"Error: Previous run directory not found: {args.previous_run}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.current_run):
        print(f"Error: Current run directory not found: {args.current_run}", file=sys.stderr)
        sys.exit(1)

    # Generate diff report
    diff_report = generate_diff_report(args.previous_run, args.current_run)

    # Write output
    with open(args.output, 'w') as f:
        json.dump(diff_report, f, indent=2)

    print(f"\n✓ Diff report written to {args.output}")
    print(f"  Major changes: {diff_report['summary']['major_changes']}")
    print(f"  Minor changes: {diff_report['summary']['minor_changes']}")
    print(f"  Assessment: {diff_report['summary']['overall_assessment']}")


if __name__ == '__main__':
    main()

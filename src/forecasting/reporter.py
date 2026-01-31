"""
Report generation for forecast scoring.

Generates JSON and markdown reports summarizing forecast
accuracy and calibration.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from . import ledger
from . import scorer


REPORTS_DIR = Path("forecasting/reports")


def ensure_reports_dir(reports_dir: Path = REPORTS_DIR) -> None:
    """Create reports directory if it doesn't exist."""
    reports_dir.mkdir(parents=True, exist_ok=True)


def generate_scorecard_json(
    scores: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate scorecard in JSON format.

    Args:
        scores: Score results from scorer.compute_scores()
        metadata: Optional additional metadata

    Returns:
        Complete scorecard dictionary
    """
    scorecard = {
        "scorecard_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scores": scores,
    }

    if metadata:
        scorecard["metadata"] = metadata

    return scorecard


def format_calibration_table(calibration: Dict[str, Any]) -> str:
    """
    Format calibration data as markdown table.

    Args:
        calibration: Calibration results from scorer

    Returns:
        Markdown table string
    """
    bins = calibration.get("bins", [])
    if not bins:
        return "*No calibration data available*"

    lines = [
        "| Bin | Count | Mean Forecast | Observed Freq | Error |",
        "|-----|-------|---------------|---------------|-------|",
    ]

    for b in bins:
        bin_range = f"{b['bin_start']:.1f}-{b['bin_end']:.1f}"
        count = b["count"]

        if count > 0:
            mean_f = f"{b['mean_forecast']:.3f}"
            obs_f = f"{b['observed_frequency']:.3f}"
            error = f"{b['absolute_error']:.3f}"
        else:
            mean_f = obs_f = error = "-"

        lines.append(f"| {bin_range} | {count} | {mean_f} | {obs_f} | {error} |")

    return "\n".join(lines)


def format_coverage_table(coverage: Dict[str, Any]) -> str:
    """
    Format coverage metrics as markdown table.

    Args:
        coverage: Coverage metrics from scorer

    Returns:
        Markdown table string
    """
    lines = [
        "| Metric | Value |",
        "|--------|-------|",
        f"| Forecasts Due | {coverage.get('forecasts_due', 0)} |",
        f"| Resolved (Known) | {coverage.get('resolved_known', 0)} |",
        f"| Resolved (Unknown) | {coverage.get('resolved_unknown', 0)} |",
        f"| Abstained | {coverage.get('abstained', 0)} |",
        f"| Unresolved | {coverage.get('unresolved', 0)} |",
        f"| Coverage Rate | {coverage.get('coverage_rate', 0):.1%} |",
        f"| Unknown Rate | {coverage.get('unknown_rate', 0):.1%} |",
        f"| Abstain Rate | {coverage.get('abstain_rate', 0):.1%} |",
    ]
    return "\n".join(lines)


def format_mode_scores_table(core: Dict[str, Any], claims: Dict[str, Any], combined: Dict[str, Any]) -> str:
    """
    Format scores by resolution mode as markdown table.

    Args:
        core: Core scores (external_auto + external_manual)
        claims: Claims inferred scores
        combined: Combined scores

    Returns:
        Markdown table string
    """
    def fmt(val):
        return f"{val:.4f}" if val is not None else "-"

    lines = [
        "| Mode | Brier | Log | Count |",
        "|------|-------|-----|-------|",
        f"| Core (external) | {fmt(core.get('brier_score'))} | {fmt(core.get('log_score'))} | {core.get('count', 0)} |",
        f"| Claims Inferred | {fmt(claims.get('brier_score'))} | {fmt(claims.get('log_score'))} | {claims.get('count', 0)} |",
        f"| Combined* | {fmt(combined.get('brier_score'))} | {fmt(combined.get('log_score'))} | {combined.get('count', 0)} |",
    ]
    return "\n".join(lines)


def format_multi_outcome_calibration_table(
    calibration: Dict[str, Any],
    event_id: str,
    event_type: str,
    forecaster_id: Optional[str] = None,
    horizon_days: Optional[int] = None
) -> str:
    """
    Format multi-outcome calibration data as markdown table.

    Args:
        calibration: Per-outcome calibration results from scorer
        event_id: Event identifier
        event_type: Event type (categorical/binned_continuous)
        forecaster_id: Optional forecaster filter
        horizon_days: Optional horizon filter

    Returns:
        Markdown table string
    """
    per_outcome = calibration.get("per_outcome", {})
    if not per_outcome:
        return "*No calibration data available*"

    # Header
    header_parts = [f"## Calibration: {event_id} ({event_type})"]
    filter_parts = []
    if forecaster_id:
        filter_parts.append(f"Forecaster: {forecaster_id}")
    if horizon_days:
        filter_parts.append(f"Horizon: {horizon_days} days")
    if filter_parts:
        header_parts.append(" | ".join(filter_parts))
    header_parts.append("")

    lines = header_parts + [
        "| Outcome | Bin | Count | Mean P | Observed | Error |",
        "|---------|-----|-------|--------|----------|-------|",
    ]

    for outcome, outcome_data in sorted(per_outcome.items()):
        bins = outcome_data.get("bins", [])
        for b in bins:
            if b["count"] == 0:
                continue

            # Format bin range (last bin includes 1.0)
            bin_end_str = f"{b['bin_end']:.1f}" if b['bin_end'] < 1.0 else "1.0]"
            if b['bin_end'] < 1.0:
                bin_range = f"[{b['bin_start']:.1f}, {b['bin_end']:.1f})"
            else:
                bin_range = f"[{b['bin_start']:.1f}, 1.0]"

            mean_f = f"{b['mean_forecast']:.3f}" if b['mean_forecast'] is not None else "-"
            obs_f = f"{b['observed_frequency']:.3f}" if b['observed_frequency'] is not None else "-"
            error = f"{b['absolute_error']:.3f}" if b['absolute_error'] is not None else "-"

            lines.append(f"| {outcome} | {bin_range} | {b['count']} | {mean_f} | {obs_f} | {error} |")

    # Aggregate error
    agg_error = calibration.get("aggregate_calibration_error")
    if agg_error is not None:
        lines.append("")
        lines.append(f"Aggregate Calibration Error: {agg_error:.3f}")

    return "\n".join(lines)


def format_forecaster_comparison_table(scores_by_forecaster: Dict[str, Dict[str, Any]]) -> str:
    """
    Format forecaster comparison as markdown table.

    Args:
        scores_by_forecaster: Scores grouped by forecaster_id

    Returns:
        Markdown table string
    """
    if not scores_by_forecaster:
        return "*No forecaster data available*"

    def fmt(val):
        if val is None:
            return "-"
        if isinstance(val, float):
            return f"{val:.4f}"
        return str(val)

    def fmt_skill(val):
        if val is None:
            return "-"
        if val >= 0:
            return f"+{val:.2f}"
        return f"{val:.2f}"

    lines = [
        "## Forecaster Performance",
        "",
        "| Forecaster | Brier (norm) | Binary | Multi | Count |",
        "|------------|--------------|--------|-------|-------|",
    ]

    for forecaster_id, scores in sorted(scores_by_forecaster.items()):
        brier = scores.get("brier_score")
        binary_brier = scores.get("binary_brier_score")
        multi_brier = scores.get("multi_brier_score")
        count = scores.get("count", 0)

        lines.append(
            f"| {forecaster_id} | {fmt(brier)} | {fmt(binary_brier)} | {fmt(multi_brier)} | {count} |"
        )

    return "\n".join(lines)


def format_scores_by_type_table(scores_by_type: Dict[str, Dict[str, Any]]) -> str:
    """
    Format scores by event type as markdown table.

    Args:
        scores_by_type: Scores grouped by event type

    Returns:
        Markdown table string
    """
    if not scores_by_type:
        return "*No type breakdown available*"

    def fmt(val):
        if val is None:
            return "-"
        return f"{val:.4f}"

    lines = [
        "## Scores by Event Type",
        "",
        "| Type | Brier | Log | Count |",
        "|------|-------|-----|-------|",
    ]

    for event_type in ["binary", "categorical", "binned_continuous"]:
        if event_type not in scores_by_type:
            continue
        scores = scores_by_type[event_type]
        brier = scores.get("brier_score")
        log = scores.get("log_score")
        count = scores.get("count", 0)
        lines.append(f"| {event_type} | {fmt(brier)} | {fmt(log)} | {count} |")

    return "\n".join(lines)


def format_baselines_table(baselines: Dict[str, Dict[str, Any]]) -> str:
    """
    Format baselines with fallback warnings as markdown table.

    Phase 3B Red-Team Fix 3: Show fallback status prominently.

    Args:
        baselines: Baselines metadata from compute_scores()

    Returns:
        Markdown table string
    """
    if not baselines:
        return "*No baseline data available*"

    def fmt(val):
        if val is None:
            return "-"
        return f"{val:.4f}"

    lines = [
        "## Baselines",
        "",
        "| Baseline | Brier | History N | Fallback |",
        "|----------|-------|-----------|----------|",
    ]

    for baseline_name in ["climatology", "persistence"]:
        if baseline_name not in baselines:
            continue

        baseline = baselines[baseline_name]
        brier = baseline.get("brier_score")
        history_n = baseline.get("history_n", 0)
        fallback = baseline.get("fallback")

        # Add warning emoji if fallback is used
        if fallback:
            prefix = "⚠️ "
            fallback_str = fallback
        else:
            prefix = ""
            fallback_str = "-"

        lines.append(
            f"| {prefix}{baseline_name.capitalize()} | {fmt(brier)} | {history_n} | {fallback_str} |"
        )

    return "\n".join(lines)


def format_warnings(warnings: list) -> str:
    """
    Format warnings as markdown callout.

    Args:
        warnings: List of warning strings

    Returns:
        Markdown string with warnings
    """
    if not warnings:
        return ""

    lines = [
        "## ⚠️ Warnings",
        "",
    ]

    for warning in warnings:
        lines.append(f"- {warning}")

    lines.append("")
    lines.append("*Skill scores may be unreliable when baselines use fallback.*")
    lines.append("")

    return "\n".join(lines)


def generate_leaderboard(
    leaderboard_data: List[Dict[str, Any]],
    by_horizon: bool = True
) -> str:
    """
    Generate leaderboard markdown from computed leaderboard data.

    Decision D5: Coverage computed per (forecaster_id, event_type, horizon_days) tuple.

    Args:
        leaderboard_data: List of leaderboard entries from compute_leaderboard_data()
        by_horizon: If True, include horizon in grouping

    Returns:
        Markdown string with leaderboard tables
    """
    if not leaderboard_data:
        return "## Forecaster Leaderboard\n\n*No data available*\n"

    lines = ["## Forecaster Leaderboard", ""]

    # Group by event_type
    event_types = sorted(set(d.get("event_type", "binary") for d in leaderboard_data))

    for event_type in event_types:
        type_entries = [d for d in leaderboard_data if d.get("event_type") == event_type]

        if by_horizon:
            # Group by horizon
            horizons = sorted(set(d.get("horizon_days", 0) for d in type_entries))

            for horizon in horizons:
                horizon_entries = [d for d in type_entries if d.get("horizon_days") == horizon]

                if horizon_entries:
                    lines.append(f"### {event_type.replace('_', ' ').title()} Events - {horizon} Day Horizon")
                    lines.append("")
                    lines.append(format_leaderboard_table(horizon_entries))
                    lines.append("")
        else:
            # Aggregate across horizons
            if type_entries:
                lines.append(f"### {event_type.replace('_', ' ').title()} Events")
                lines.append("")
                lines.append(format_leaderboard_table(type_entries))
                lines.append("")

    return "\n".join(lines)


def format_leaderboard_table(
    entries: List[Dict[str, Any]],
    include_fallback: bool = True,
    include_baseline_metadata: bool = True
) -> str:
    """
    Format leaderboard entries as markdown table.

    Decision D5: Coverage rate is per-slice, not global.
    Decision D6: Baseline fallback uses MIN for history_n, ANY for fallback.
    TWEAK 5: Non-baseline forecasters show "-" for Fallback column.
    Phase 3D-2: Show baseline history_n, staleness, and fallback warnings.

    Args:
        entries: List of leaderboard entries
        include_fallback: Whether to include fallback column
        include_baseline_metadata: Whether to include baseline metadata columns

    Returns:
        Markdown table string
    """
    if not entries:
        return "*No entries*"

    def fmt(val, decimals=3):
        if val is None:
            return "-"
        if isinstance(val, float):
            return f"{val:.{decimals}f}"
        return str(val)

    def fmt_pct(val):
        if val is None:
            return "-"
        return f"{val:.0%}"

    # Sort by primary_brier (ascending - lower is better)
    sorted_entries = sorted(
        entries,
        key=lambda x: (x.get("primary_brier") or float('inf'))
    )

    # Check if any baseline entries have metadata
    has_baseline_metadata = any(
        e.get("forecaster_id", "").startswith("oracle_baseline_") and
        e.get("baseline_history_n") is not None
        for e in entries
    )

    # Build header
    header = "| Forecaster | Primary Brier | Log | Coverage | Eff. Penalty | N |"
    divider = "|------------|---------------|-----|----------|--------------|---|"

    if include_baseline_metadata and has_baseline_metadata:
        header += " History N | Staleness |"
        divider += "-----------|-----------|"

    if include_fallback:
        header += " Fallback |"
        divider += "----------|"

    lines = [header, divider]

    for entry in sorted_entries:
        forecaster_id = entry.get("forecaster_id", "unknown")
        primary_brier = entry.get("primary_brier")
        log_score = entry.get("log_score")
        coverage_rate = entry.get("coverage_rate")
        effective_penalty = entry.get("effective_penalty")
        resolved_n = entry.get("resolved_n", 0)
        baseline_fallback = entry.get("baseline_fallback")
        baseline_history_n = entry.get("baseline_history_n")
        baseline_staleness_days = entry.get("baseline_staleness_days")

        # TWEAK 5: Non-baseline forecasters show "-" for Fallback
        is_baseline = forecaster_id.startswith("oracle_baseline_")

        # Add warning emoji for baselines with fallback
        brier_str = fmt(primary_brier)
        if is_baseline and baseline_fallback:
            brier_str = f"⚠️ {brier_str}"

        row = f"| {forecaster_id} | {brier_str} | {fmt(log_score, 2)} | {fmt_pct(coverage_rate)} | {fmt(effective_penalty)} | {resolved_n} |"

        if include_baseline_metadata and has_baseline_metadata:
            if is_baseline:
                history_str = str(baseline_history_n) if baseline_history_n is not None else "-"
                staleness_str = f"{baseline_staleness_days}d" if baseline_staleness_days is not None else "-"
            else:
                history_str = "-"
                staleness_str = "-"
            row += f" {history_str} | {staleness_str} |"

        if include_fallback:
            if is_baseline:
                fallback_str = baseline_fallback or "-"
            else:
                fallback_str = "-"
            row += f" {fallback_str} |"

        lines.append(row)

    # Add footnote for warnings
    has_warnings = any(
        e.get("baseline_fallback") and e.get("forecaster_id", "").startswith("oracle_baseline_")
        for e in entries
    )
    if has_warnings:
        lines.append("")
        lines.append("⚠️ Baseline has insufficient history. Skill comparison unreliable.")

    return "\n".join(lines)


def format_accuracy_metrics(accuracy: Dict[str, Any], penalty: Dict[str, Any]) -> str:
    """
    Format accuracy and penalty metrics as markdown section.

    Phase 3B Red-Team Fix 2: Separate accuracy from penalty.

    Args:
        accuracy: Accuracy metrics (non-UNKNOWN only)
        penalty: Penalty metrics (includes UNKNOWN/abstain penalties)

    Returns:
        Markdown string
    """
    def fmt(val):
        if val is None:
            return "-"
        return f"{val:.4f}"

    lines = [
        "## Accuracy Metrics (Primary)",
        "",
        "Scores computed on resolved forecasts with known outcomes (excludes UNKNOWN).",
        "",
        f"- **Primary Brier Score:** {fmt(accuracy.get('brier_score'))} (lower is better)",
        f"- **Log Score:** {fmt(accuracy.get('log_score'))}",
        f"- **Calibration Error:** {fmt(accuracy.get('calibration_error'))}",
        "",
        "## Penalty Metrics",
        "",
        "Separate penalties for UNKNOWN outcomes and abstentions.",
        "",
        f"- **Effective Brier:** {fmt(penalty.get('effective_brier'))} (includes UNKNOWN penalty)",
        f"- **UNKNOWN/Abstain Penalty:** {fmt(penalty.get('unknown_abstain_penalty'))}",
        "",
    ]

    return "\n".join(lines)


def generate_scorecard_md(
    scores: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate scorecard in markdown format.

    Args:
        scores: Score results from scorer.compute_scores()
        metadata: Optional additional metadata

    Returns:
        Markdown string
    """
    lines = [
        "# Oracle Forecast Scorecard",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]

    # Summary counts
    counts = scores.get("counts", {})
    lines.extend([
        "## Summary",
        "",
        f"- **Total Forecasts:** {counts.get('total_forecasts', 0)}",
        f"- **Resolved:** {counts.get('resolved', 0)}",
        f"- **Unresolved:** {counts.get('unresolved', 0)}",
        f"- **Abstained:** {counts.get('abstained', 0)}",
        f"- **Unknown Outcome:** {counts.get('unknown', 0)}",
        "",
    ])

    # Coverage metrics
    coverage = scores.get("coverage", {})
    if coverage:
        lines.extend([
            "## Coverage Metrics",
            "",
            format_coverage_table(coverage),
            "",
        ])

    # Filters
    filters = scores.get("filters", {})
    if filters.get("event_id") or filters.get("horizon_days"):
        lines.extend([
            "## Filters Applied",
            "",
        ])
        if filters.get("event_id"):
            lines.append(f"- Event ID: `{filters['event_id']}`")
        if filters.get("horizon_days"):
            lines.append(f"- Horizon: {filters['horizon_days']} days")
        lines.append("")

    # Core Accuracy Metrics (external_auto + external_manual only)
    core_scores = scores.get("core_scores", {})
    if core_scores.get("count", 0) > 0:
        lines.extend([
            "## Core Accuracy (External Resolution)",
            "",
            "Scores based on `external_auto` and `external_manual` resolutions only.",
            "",
            f"- **Brier Score:** {core_scores.get('brier_score', 0):.4f} (lower is better)",
            f"- **Log Score:** {core_scores.get('log_score', 0):.4f}",
            f"- **Count:** {core_scores.get('count', 0)}",
            "",
        ])

    # Claims Inferred Scores (separate section)
    claims_scores = scores.get("claims_inferred_scores", {})
    if claims_scores.get("count", 0) > 0:
        lines.extend([
            "## Claims Inferred Scores",
            "",
            "Scores based on `claims_inferred` resolutions. These are separate from core accuracy.",
            "",
            f"- **Brier Score:** {claims_scores.get('brier_score', 0):.4f}",
            f"- **Log Score:** {claims_scores.get('log_score', 0):.4f}",
            f"- **Count:** {claims_scores.get('count', 0)}",
            "",
        ])

    # Scores by Mode Table
    combined_scores = scores.get("combined_scores", {})
    if core_scores or claims_scores or combined_scores:
        lines.extend([
            "## Scores by Resolution Mode",
            "",
            format_mode_scores_table(core_scores, claims_scores, combined_scores),
            "",
            "*Combined scores are for reference only. Core scores are the primary accuracy metric.*",
            "",
        ])

    # Effective Brier
    if "effective_brier" in scores and scores["effective_brier"] is not None:
        lines.extend([
            "## Effective Brier Score",
            "",
            f"**Effective Brier:** {scores['effective_brier']:.4f}",
            "",
            "UNKNOWN outcomes are treated as outcome=0.5, penalizing overconfident predictions",
            "that could not be verified. Abstained forecasts use p=0.5 as their prediction.",
            "",
        ])

    # Legacy Overall Scores (for backwards compatibility)
    if "brier_score" in scores:
        lines.extend([
            "## Overall Accuracy Metrics (Legacy)",
            "",
            f"- **Brier Score:** {scores['brier_score']:.4f} (lower is better)",
            f"- **Baseline (Climatology):** {scores['baseline_brier']:.4f}",
            f"- **Skill Score:** {scores['skill_score']:.4f} (positive = better than baseline)",
            f"- **Climatology P(YES):** {scores.get('climatology_p', 0.5):.2%}",
            "",
        ])
    elif "scoring_note" in scores:
        lines.extend([
            "## Overall Accuracy Metrics",
            "",
            f"*{scores['scoring_note']}*",
            "",
        ])

    # Calibration
    if "calibration" in scores:
        cal = scores["calibration"]
        lines.extend([
            "## Calibration",
            "",
            f"**Mean Calibration Error:** {cal.get('calibration_error', 0):.4f}",
            "",
            format_calibration_table(cal),
            "",
        ])

    # NEW: Scores by forecaster
    scores_by_forecaster = scores.get("scores_by_forecaster", {})
    if scores_by_forecaster:
        lines.extend([
            format_forecaster_comparison_table(scores_by_forecaster),
            "",
        ])

    # NEW: Scores by event type
    scores_by_type = scores.get("scores_by_type", {})
    if scores_by_type:
        lines.extend([
            format_scores_by_type_table(scores_by_type),
            "",
        ])

    # NEW Phase 3B Red-Team Fix 2: Accuracy vs Penalty metrics
    accuracy = scores.get("accuracy", {})
    penalty_metrics = scores.get("penalty_metrics", {})
    if accuracy or penalty_metrics:
        lines.extend([
            format_accuracy_metrics(accuracy, penalty_metrics),
            "",
        ])

    # NEW Phase 3B Red-Team Fix 3: Baselines with fallback warnings
    baselines = scores.get("baselines", {})
    if baselines:
        lines.extend([
            format_baselines_table(baselines),
            "",
        ])

    # Warnings section (fallback alerts)
    warnings = scores.get("warnings", [])
    if warnings:
        lines.extend([
            format_warnings(warnings),
            "",
        ])

    # NEW: Leaderboard section
    leaderboard_data = scores.get("leaderboard_data", [])
    if leaderboard_data:
        lines.extend([
            generate_leaderboard(leaderboard_data, by_horizon=True),
            "",
        ])

    # Interpretation
    lines.extend([
        "## Interpretation Guide",
        "",
        "- **Brier Score**: Measures accuracy. 0 = perfect, 0.25 = random guessing.",
        "- **Skill Score**: Compares to baseline. Positive = better than always predicting climatology.",
        "- **Calibration Error**: How well probabilities match observed frequencies. 0 = perfect calibration.",
        "- **Coverage Rate**: Fraction of due forecasts with known (YES/NO) resolutions.",
        "- **Core vs Claims Inferred**: Core scores use external data sources; claims inferred uses fallback resolution.",
        "- **Multi-Outcome Brier**: For categorical/binned events, normalized to [0,1] range (raw/2).",
        "- **Fallback Warning**: When a baseline uses uniform fallback due to insufficient history, skill scores are unreliable.",
        "- **Primary vs Effective Brier**: Primary excludes UNKNOWN; Effective penalizes UNKNOWN/abstain.",
        "",
    ])

    return "\n".join(lines)


def generate_report(
    ledger_dir: Path = ledger.LEDGER_DIR,
    reports_dir: Path = REPORTS_DIR,
    output_format: str = "both",
    event_id: Optional[str] = None,
    horizon_days: Optional[int] = None
) -> Dict[str, Path]:
    """
    Generate forecast accuracy report.

    Args:
        ledger_dir: Path to ledger directory
        reports_dir: Path to output directory
        output_format: "json", "md", or "both"
        event_id: Optional filter by event ID
        horizon_days: Optional filter by horizon

    Returns:
        Dictionary mapping format to output path
    """
    ensure_reports_dir(reports_dir)

    # Compute scores
    scores = scorer.compute_scores(ledger_dir, event_id, horizon_days)

    # Metadata
    metadata = {
        "ledger_dir": str(ledger_dir),
        "event_id_filter": event_id,
        "horizon_filter": horizon_days,
    }

    outputs = {}

    if output_format in ("json", "both"):
        scorecard = generate_scorecard_json(scores, metadata)
        json_path = reports_dir / "scorecard.json"
        with open(json_path, 'w') as f:
            json.dump(scorecard, f, indent=2)
        outputs["json"] = json_path

    if output_format in ("md", "both"):
        md_content = generate_scorecard_md(scores, metadata)
        md_path = reports_dir / "scorecard.md"
        with open(md_path, 'w') as f:
            f.write(md_content)
        outputs["md"] = md_path

    return outputs


def generate_status_report(ledger_dir: Path = ledger.LEDGER_DIR) -> Dict[str, Any]:
    """
    Generate status summary for CLI output.

    Args:
        ledger_dir: Path to ledger directory

    Returns:
        Status dictionary
    """
    forecasts = ledger.get_forecasts(ledger_dir)
    resolutions = ledger.get_resolutions(ledger_dir)
    pending = ledger.get_pending_forecasts(ledger_dir)

    # Count by event
    event_counts = {}
    for f in forecasts:
        event_id = f.get("event_id", "unknown")
        if event_id not in event_counts:
            event_counts[event_id] = {"total": 0, "resolved": 0, "pending": 0}
        event_counts[event_id]["total"] += 1

    resolved_ids = {r["forecast_id"] for r in resolutions}
    for f in forecasts:
        event_id = f.get("event_id", "unknown")
        if f["forecast_id"] in resolved_ids:
            event_counts[event_id]["resolved"] += 1
        else:
            event_counts[event_id]["pending"] += 1

    return {
        "total_forecasts": len(forecasts),
        "total_resolutions": len(resolutions),
        "pending_count": len(pending),
        "coverage_rate": len(resolutions) / len(forecasts) if forecasts else 0.0,
        "by_event": event_counts,
    }

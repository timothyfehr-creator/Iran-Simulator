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

    # Interpretation
    lines.extend([
        "## Interpretation Guide",
        "",
        "- **Brier Score**: Measures accuracy. 0 = perfect, 0.25 = random guessing.",
        "- **Skill Score**: Compares to baseline. Positive = better than always predicting climatology.",
        "- **Calibration Error**: How well probabilities match observed frequencies. 0 = perfect calibration.",
        "- **Coverage Rate**: Fraction of due forecasts with known (YES/NO) resolutions.",
        "- **Core vs Claims Inferred**: Core scores use external data sources; claims inferred uses fallback resolution.",
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

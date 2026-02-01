#!/usr/bin/env python3
"""Generate public artifacts for R2 publishing.

Data flow:
  - Live wire data is read from a LOCAL working copy (data/live_wire/latest.json).
    In CI, the daily.yml workflow downloads this from R2 before calling us.
    If the local file is missing, we attempt an R2 download as a fallback.
    If R2 also has nothing (first-ever run), live_wire_summary and
    defcon_status degrade to null/UNKNOWN -- never fabricated.
  - Simulation results are read from the run directory (local, committed to git).
  - Scorecard is read from forecasting/reports/ (local, generated earlier in pipeline).
  - Output goes to latest/ (local ephemeral, .gitignored).  The workflow
    uploads latest/ to R2 (the source of truth for public artifacts).

Produces:
  - latest/war_room_summary.json
  - latest/leaderboard.json
  - latest/live_wire_state.json

Usage:
    python scripts/generate_public_artifacts.py \
        --run-dir runs/RUN_xxx \
        --live-wire data/live_wire/latest.json \
        --scorecard forecasting/reports/scorecard.json \
        --output-dir latest/
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def load_json(path: str) -> Optional[dict]:
    """Load JSON file, return None if missing."""
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def download_from_r2(r2_key: str, local_path: str) -> bool:
    """Download a file from R2. Returns True on success."""
    bucket = os.environ.get("R2_BUCKET_NAME")
    account_id = os.environ.get("R2_ACCOUNT_ID")
    if not bucket or not account_id:
        return False

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    try:
        result = subprocess.run(
            ["aws", "s3", "cp", f"s3://{bucket}/{r2_key}", local_path,
             "--endpoint-url", endpoint],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def derive_defcon(derived_states: Optional[dict], signal_quality: Optional[dict]) -> str:
    """Derive DEFCON status from Live Wire states.

    RED = economic CRITICAL or internet BLACKOUT
    ORANGE = economic PRESSURED or internet SEVERELY_DEGRADED
    YELLOW = any signal STALE/FAILED or news ELEVATED
    GREEN = all stable
    """
    if not derived_states:
        return "UNKNOWN"

    econ = derived_states.get("economic_stress")
    internet = derived_states.get("internet_status")
    news = derived_states.get("news_activity")

    # RED conditions
    if econ == "CRITICAL" or internet == "BLACKOUT":
        return "RED"

    # ORANGE conditions
    if econ == "PRESSURED" or internet == "SEVERELY_DEGRADED":
        return "ORANGE"

    # YELLOW conditions
    if news == "ELEVATED" or news == "SURGE":
        return "YELLOW"

    # Check for degraded signal quality
    if signal_quality:
        for sq in signal_quality.values():
            status = sq.get("status") if isinstance(sq, dict) else None
            if status in ("STALE", "FAILED"):
                return "YELLOW"

    return "GREEN"


def load_headline_chart(series_path: str) -> List[dict]:
    """Load pre-built 7-day series for the headline chart.

    The Live Wire runner produces ``data/live_wire/series.json`` (and uploads
    it to R2 as ``latest/live_wire_series.json``) so we never need to
    download or decompress snapshot history here.
    """
    data = load_json(series_path)
    if data and isinstance(data, list):
        return data
    return []


def generate_war_room_summary(
    run_dir: Optional[str],
    live_wire: Optional[dict],
    scorecard: Optional[dict],
    series_path: str = "data/live_wire/series.json",
) -> dict:
    """Generate war_room_summary.json content."""
    now = datetime.now(timezone.utc).isoformat()

    # Extract live wire info
    derived_states = live_wire.get("derived_states") if live_wire else None
    signal_quality = live_wire.get("signal_quality") if live_wire else None
    signals = live_wire.get("signals", {}) if live_wire else {}

    defcon = derive_defcon(derived_states, signal_quality)

    # Headline KPIs
    headline_kpis = []

    # From simulation results
    sim_results = None
    if run_dir:
        sim_results = load_json(os.path.join(run_dir, "simulation_results.json"))

    if sim_results:
        outcomes = sim_results.get("outcome_distribution", sim_results.get("outcomes", {}))
        regime_survives = outcomes.get("STATUS_QUO", outcomes.get("status_quo"))
        if regime_survives is not None:
            headline_kpis.append({
                "label": "Regime Survives (P)",
                "value": regime_survives,
                "format": "percent",
            })

    # From live wire
    usdt_rate = signals.get("usdt_irt_rate", {}).get("value")
    if usdt_rate is not None:
        headline_kpis.append({
            "label": "USDT/IRR Rate",
            "value": usdt_rate,
            "format": "number",
            "units": "IRR",
        })

    conn_index = signals.get("connectivity_index", {}).get("value")
    if conn_index is not None:
        headline_kpis.append({
            "label": "Connectivity Index",
            "value": conn_index,
            "format": "number",
            "units": "index_0_100",
        })

    # From scorecard
    scores = scorecard.get("scores", {}) if scorecard else {}
    accuracy = scores.get("accuracy", scores.get("core_scores", {}))
    brier = accuracy.get("brier_score")
    if brier is not None:
        headline_kpis.append({
            "label": "Forecast Accuracy (Brier)",
            "value": brier,
            "format": "number",
        })

    # Headline chart — loaded from pre-built series.json (no snapshot scanning)
    headline_chart = load_headline_chart(series_path)

    # Forecast summary
    forecast_summary = None
    if scores:
        cal = scores.get("calibration", {})
        forecast_summary = {
            "brier_score": accuracy.get("brier_score"),
            "calibration_error": cal.get("calibration_error"),
            "total_forecasts": scores.get("counts", {}).get("total_forecasts", 0),
        }

    # Alerts
    alerts: List[dict] = []
    if signal_quality:
        for sig_name, sq in signal_quality.items():
            if isinstance(sq, dict) and sq.get("status") == "FAILED":
                alerts.append({
                    "type": "signal_failed",
                    "signal": sig_name,
                    "consecutive_failures": sq.get("consecutive_failures", 0),
                    "message": f"Signal {sig_name} fetch failed ({sq.get('consecutive_failures', 0)} consecutive)",
                })

    return {
        "_schema_version": "1.0.0",
        "generated_at_utc": now,
        "defcon_status": defcon,
        "headline_kpis": headline_kpis,
        "headline_chart": headline_chart,
        "live_wire_summary": derived_states,
        "forecast_summary": forecast_summary,
        "alerts": alerts,
        "map_data": {"regions": []},
    }


def generate_leaderboard(scorecard: Optional[dict]) -> dict:
    """Generate leaderboard.json from scorecard data."""
    now = datetime.now(timezone.utc).isoformat()

    if not scorecard:
        return {
            "_schema_version": "1.0.0",
            "generated_at_utc": now,
            "metrics": {"primary": "brier_score"},
            "top_forecasters": [],
            "question_groups": [],
        }

    scores = scorecard.get("scores", {})
    leaderboard_data = scores.get("leaderboard_data", [])

    # Top forecasters sorted by primary_brier
    top = sorted(leaderboard_data, key=lambda x: x.get("primary_brier") or float("inf"))
    top_forecasters = [
        {
            "forecaster_id": e.get("forecaster_id"),
            "primary_brier": e.get("primary_brier"),
            "skill_score": e.get("skill_score"),
            "resolved_n": e.get("resolved_n", 0),
        }
        for e in top
    ]

    # Group by (event_type, horizon_days)
    groups: Dict[str, dict] = {}
    for entry in leaderboard_data:
        et = entry.get("event_type", "binary")
        hd = entry.get("horizon_days", 0)
        key = f"{et}_{hd}"
        if key not in groups:
            groups[key] = {
                "event_type": et,
                "horizon_days": hd,
                "entries": [],
            }
        groups[key]["entries"].append({
            "forecaster_id": entry.get("forecaster_id"),
            "primary_brier": entry.get("primary_brier"),
            "resolved_n": entry.get("resolved_n", 0),
        })

    # Compute per-group average brier
    question_groups = []
    for g in groups.values():
        briers = [e["primary_brier"] for e in g["entries"] if e["primary_brier"] is not None]
        avg_brier = sum(briers) / len(briers) if briers else None
        question_groups.append({
            "event_type": g["event_type"],
            "horizon_days": g["horizon_days"],
            "avg_brier": avg_brier,
            "forecaster_count": len(g["entries"]),
        })

    return {
        "_schema_version": "1.0.0",
        "generated_at_utc": now,
        "metrics": {"primary": "brier_score"},
        "top_forecasters": top_forecasters,
        "question_groups": question_groups,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate public artifacts for R2")
    parser.add_argument("--run-dir", help="Simulation run directory")
    parser.add_argument("--live-wire", default="data/live_wire/latest.json",
                        help="Live Wire latest.json path")
    parser.add_argument("--series", default="data/live_wire/series.json",
                        help="Pre-built 7-day series JSON (from runner or R2)")
    parser.add_argument("--scorecard", default="forecasting/reports/scorecard.json",
                        help="Scorecard JSON path")
    parser.add_argument("--output-dir", default="latest/", help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Load live wire (with R2 fallback)
    live_wire = load_json(args.live_wire)
    if live_wire is None:
        logger.info("Live wire not found locally, trying R2...")
        tmp = os.path.join(args.output_dir, "_tmp_live_wire.json")
        if download_from_r2("latest/live_wire_state.json", tmp):
            live_wire = load_json(tmp)
            try:
                os.unlink(tmp)
            except OSError:
                pass
    if live_wire is None:
        logger.warning("No live wire data available; defcon will be UNKNOWN")

    # Load series (with R2 fallback)
    series_path = args.series
    if not os.path.exists(series_path):
        logger.info("Series file not found locally, trying R2...")
        tmp_series = os.path.join(args.output_dir, "_tmp_series.json")
        if download_from_r2("latest/live_wire_series.json", tmp_series):
            series_path = tmp_series
        else:
            logger.warning("No series data available; headline chart will be empty")

    # Load scorecard
    scorecard = load_json(args.scorecard)
    if scorecard is None:
        logger.warning("No scorecard available; leaderboard will be empty")

    # Generate war room summary
    war_room = generate_war_room_summary(args.run_dir, live_wire, scorecard, series_path=series_path)
    war_room_path = os.path.join(args.output_dir, "war_room_summary.json")
    with open(war_room_path, "w") as f:
        json.dump(war_room, f, indent=2)
    logger.info(f"Wrote {war_room_path}")

    # Generate leaderboard
    lb = generate_leaderboard(scorecard)
    lb_path = os.path.join(args.output_dir, "leaderboard.json")
    with open(lb_path, "w") as f:
        json.dump(lb, f, indent=2)
    logger.info(f"Wrote {lb_path}")

    # Copy live wire state
    lw_path = os.path.join(args.output_dir, "live_wire_state.json")
    if live_wire:
        with open(lw_path, "w") as f:
            json.dump(live_wire, f, indent=2)
        logger.info(f"Wrote {lw_path}")
    else:
        logger.warning("Skipped live_wire_state.json (no data)")

    logger.info("Public artifact generation complete")


if __name__ == "__main__":
    main()

"""Live Wire main orchestrator.

Source of truth: R2 bucket (state, latest, snapshots).
Local files under data/live_wire/ are ephemeral working copies created during
each CI run. They are .gitignored and should never be committed. Outside CI,
local devs can populate them via ``scripts/pull_live_wire.py`` or by running
the pipeline with R2 env vars set.

Flow:
1. Load config/live_wire.json
2. Download state.json from R2 → local working copy (create default if first run)
3. Fetch 4 signals: bonbast, nobitex, ioda, gdelt
4. Update SignalQuality per signal
5. Write JSONL snapshot (local ephemeral)
6. Compute EMA
7. Classify + hysteresis
8. Write data/live_wire/latest.json (local ephemeral)
9. Upload state.json + latest.json + snapshot to R2 (authoritative)
"""

import gzip
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Add project root for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.ingest.live_wire.signal_quality import (
    SignalStatus,
    quality_to_dict,
    update_signal_quality,
)
from src.ingest.live_wire.rule_engine import (
    apply_hysteresis,
    classify_economic_stress,
    classify_internet,
    classify_news,
)
from src.ingest.live_wire.smoothing import compute_ema
from src.ingest.live_wire.fetch_gdelt import fetch_gdelt_iran_count

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("live_wire")

CONFIG_PATH = "config/live_wire.json"
TOMAN_TO_RIAL = 10


def load_config(path: str = CONFIG_PATH) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def default_state() -> dict:
    return {
        "snapshot_counter": 0,
        "signal_quality": {},
        "hysteresis": {},
        "ema": {},
    }


def load_state_local(path: str) -> dict:
    """Load state from local file."""
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return default_state()


def download_state_from_r2(r2_key: str, local_path: str) -> dict:
    """Download state.json from R2. Returns default if not found."""
    bucket = os.environ.get("R2_BUCKET_NAME")
    account_id = os.environ.get("R2_ACCOUNT_ID")

    if not bucket or not account_id:
        logger.info("R2 env vars not set, using local state")
        return load_state_local(local_path)

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    try:
        result = subprocess.run(
            [
                "aws", "s3", "cp",
                f"s3://{bucket}/{r2_key}",
                local_path,
                "--endpoint-url", endpoint,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return load_state_local(local_path)
        logger.info("No state in R2 (first run), using defaults")
    except Exception as e:
        logger.warning(f"R2 download failed: {e}")

    return default_state()


def upload_to_r2(local_path: str, r2_key: str, cache_control: str = "") -> bool:
    """Upload a file to R2. Returns True on success."""
    bucket = os.environ.get("R2_BUCKET_NAME")
    account_id = os.environ.get("R2_ACCOUNT_ID")

    if not bucket or not account_id:
        logger.info("R2 env vars not set, skipping upload")
        return False

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    cmd = [
        "aws", "s3", "cp",
        local_path,
        f"s3://{bucket}/{r2_key}",
        "--endpoint-url", endpoint,
    ]
    if cache_control:
        cmd.extend(["--cache-control", cache_control])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception as e:
        logger.warning(f"R2 upload failed for {r2_key}: {e}")
        return False


def fetch_bonbast_signal() -> Tuple[Optional[float], Optional[datetime]]:
    """Fetch Bonbast USD/IRR mid rate. Returns (value_irr, source_ts)."""
    try:
        from src.ingest.fetch_bonbast import BonbastFetcher

        config = {
            "id": "bonbast",
            "name": "Bonbast",
            "bucket": "econ_fx",
            "access_grade": "B",
            "bias_grade": 1,
        }
        fetcher = BonbastFetcher(config)
        docs, error = fetcher.fetch()
        if error or not docs:
            return None, None

        sd = docs[0].get("structured_data", {})
        mid = sd.get("rial_usd_rate", {}).get("market")
        # Bonbast has no source timestamp - use fetch time
        return float(mid) if mid else None, None
    except Exception as e:
        logger.warning(f"Bonbast fetch failed: {e}")
        return None, None


def fetch_nobitex_signal() -> Tuple[Optional[float], Optional[datetime]]:
    """Fetch Nobitex USDT/IRT latest. Returns (value_irr, source_ts)."""
    try:
        from src.ingest.fetch_nobitex import NobitexFetcher

        config = {
            "id": "nobitex",
            "name": "Nobitex",
            "bucket": "econ_fx",
            "access_grade": "B",
            "bias_grade": 1,
        }
        fetcher = NobitexFetcher(config)
        docs, error = fetcher.fetch()
        if error or not docs:
            return None, None

        sd = docs[0].get("structured_data", {})
        latest = sd.get("usdt_irt_rate", {}).get("latest")
        source_ts_str = sd.get("source_timestamp_utc")
        source_ts = None
        if source_ts_str:
            try:
                source_ts = datetime.fromisoformat(source_ts_str)
            except (ValueError, TypeError):
                pass
        return float(latest) if latest else None, source_ts
    except Exception as e:
        logger.warning(f"Nobitex fetch failed: {e}")
        return None, None


def fetch_ioda_signal() -> Tuple[Optional[float], Optional[datetime]]:
    """Fetch IODA connectivity index. Returns (value_0_100, source_ts)."""
    try:
        from src.ingest.fetch_ioda import IODAFetcher

        config = {
            "id": "ioda",
            "name": "IODA",
            "bucket": "internet_monitoring",
            "access_grade": "A",
            "bias_grade": 1,
        }
        fetcher = IODAFetcher(config)
        docs, error = fetcher.fetch()
        if error or not docs:
            return None, None

        sd = docs[0].get("structured_data", {})
        index = sd.get("connectivity_index")
        # IODA provides 'until' timestamp
        ts_epoch = sd.get("measurement_timestamp")
        source_ts = None
        if ts_epoch:
            try:
                source_ts = datetime.fromtimestamp(ts_epoch, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                pass
        return float(index) if index is not None else None, source_ts
    except Exception as e:
        logger.warning(f"IODA fetch failed: {e}")
        return None, None


def fetch_gdelt_signal() -> Tuple[Optional[int], Optional[datetime]]:
    """Fetch GDELT 24h Iran article count. No source timestamp."""
    count, fetched_at = fetch_gdelt_iran_count()
    return count, None  # GDELT has no per-result source timestamp


def run_live_wire(config_path: str = CONFIG_PATH) -> Dict[str, Any]:
    """Execute one Live Wire cycle.

    Returns:
        The latest.json content dict
    """
    config = load_config(config_path)
    now = datetime.now(timezone.utc)
    signals_config = config["signals"]
    rule_config = config["rule_engine"]
    alpha = config["ema_alpha"]
    hysteresis_cycles = rule_config["hysteresis_cycles"]

    # State paths
    state_local = "data/live_wire/state.json"
    state_r2_key = config["state_r2_key"]
    os.makedirs("data/live_wire/snapshots", exist_ok=True)
    os.makedirs("data/live_wire", exist_ok=True)

    # Load state
    state = download_state_from_r2(state_r2_key, state_local)
    counter = state.get("snapshot_counter", 0) + 1
    state["snapshot_counter"] = counter
    snapshot_id = f"{now.strftime('%Y%m%dT%H%M%SZ')}-{counter:06d}"

    # Fetch all 4 signals
    logger.info("Fetching signals...")
    fetchers = {
        "rial_usd_rate": (fetch_bonbast_signal, signals_config.get("rial_usd_rate", {})),
        "usdt_irt_rate": (fetch_nobitex_signal, signals_config.get("usdt_irt_rate", {})),
        "connectivity_index": (fetch_ioda_signal, signals_config.get("connectivity_index", {})),
        "news_volume": (fetch_gdelt_signal, signals_config.get("news_volume", {})),
    }

    signal_values: Dict[str, Optional[float]] = {}
    signal_audit: Dict[str, dict] = {}
    signal_qualities: Dict[str, dict] = {}

    for sig_name, (fetch_fn, sig_conf) in fetchers.items():
        if not sig_conf.get("enabled", True):
            logger.info(f"  {sig_name}: disabled, skipping")
            signal_values[sig_name] = None
            continue

        logger.info(f"  Fetching {sig_name}...")
        value, source_ts = fetch_fn()
        stale_hours = sig_conf.get("stale_after_hours", 12)

        prev_quality = state.get("signal_quality", {}).get(sig_name)
        quality = update_signal_quality(prev_quality, value, now, stale_hours, source_ts)

        signal_values[sig_name] = quality.value
        signal_qualities[sig_name] = quality_to_dict(quality)
        signal_audit[sig_name] = {
            "endpoint": sig_conf.get("endpoint", ""),
            "status": quality.status.value,
            "value": quality.value,
            "units": "IRR" if "rate" in sig_name else None,
            "source_timestamp_utc": quality.source_timestamp_utc,
            "freshness": quality.freshness,
        }

        logger.info(f"    {sig_name}: {quality.status.value} = {quality.value}")

    state["signal_quality"] = signal_qualities

    # Compute EMAs
    prev_ema = state.get("ema", {})
    new_ema: Dict[str, Optional[float]] = {}
    for sig_name in fetchers:
        last_good = signal_qualities.get(sig_name, {}).get("last_good_value")
        new_ema[sig_name] = compute_ema(
            signal_values.get(sig_name),
            prev_ema.get(sig_name),
            alpha,
            last_good,
        )
    state["ema"] = new_ema

    # Classify
    primary_econ = rule_config["primary_economic_signal"]
    econ_rate = signal_values.get(primary_econ)
    raw_econ = classify_economic_stress(econ_rate, rule_config["economic_stress"])
    raw_internet = classify_internet(
        signal_values.get("connectivity_index"), rule_config["internet_status"]
    )
    raw_news = classify_news(
        signal_values.get("news_volume"),
        new_ema.get("news_volume"),
        rule_config["news_activity"],
    )

    # Apply hysteresis
    prev_hyst = state.get("hysteresis", {})
    hyst_econ = apply_hysteresis(raw_econ, prev_hyst.get("economic_stress"), hysteresis_cycles)
    hyst_internet = apply_hysteresis(raw_internet, prev_hyst.get("internet_status"), hysteresis_cycles)
    hyst_news = apply_hysteresis(raw_news, prev_hyst.get("news_activity"), hysteresis_cycles)

    state["hysteresis"] = {
        "economic_stress": hyst_econ,
        "internet_status": hyst_internet,
        "news_activity": hyst_news,
    }

    # Build latest.json
    derived_states = {
        "economic_stress": hyst_econ["confirmed_state"],
        "internet_status": hyst_internet["confirmed_state"],
        "news_activity": hyst_news["confirmed_state"],
    }

    latest = {
        "_schema_version": config["_schema_version"],
        "rule_version": rule_config["rule_version"],
        "snapshot_id": snapshot_id,
        "generated_at_utc": now.isoformat(),
        "signals": {
            "rial_usd_rate": {
                "value": signal_values.get("rial_usd_rate"),
                "units": "IRR",
                "source": "bonbast",
            },
            "usdt_irt_rate": {
                "value": signal_values.get("usdt_irt_rate"),
                "units": "IRR",
                "source": "nobitex",
            },
            "connectivity_index": {
                "value": signal_values.get("connectivity_index"),
                "units": "index_0_100",
                "source": "ioda",
            },
            "news_volume": {
                "value": signal_values.get("news_volume"),
                "units": "count_24h",
                "source": "gdelt",
                "avg_tone": None,
            },
        },
        "signal_quality": signal_qualities,
        "smoothed": new_ema,
        "derived_states": derived_states,
        "hysteresis": {
            "economic_stress": hyst_econ,
            "internet_status": hyst_internet,
            "news_activity": hyst_news,
        },
    }

    # Write latest.json
    latest_path = config["latest_path"]
    os.makedirs(os.path.dirname(latest_path), exist_ok=True)
    with open(latest_path, "w") as f:
        json.dump(latest, f, indent=2)
    logger.info(f"Wrote {latest_path}")

    # Write JSONL snapshot
    snapshot_entry = {
        **latest,
        "signal_audit": signal_audit,
    }
    today_str = now.strftime("%Y-%m-%d")
    snapshot_jsonl_path = os.path.join(config["snapshot_dir"], f"{today_str}.jsonl")
    os.makedirs(config["snapshot_dir"], exist_ok=True)
    with open(snapshot_jsonl_path, "a") as f:
        f.write(json.dumps(snapshot_entry) + "\n")
    logger.info(f"Appended snapshot to {snapshot_jsonl_path}")

    # Build 7-day series from local snapshots (small file for headline chart).
    # This avoids daily.yml needing to download + decompress all snapshot history.
    series = _build_series(config["snapshot_dir"], max_days=7)
    series_path = os.path.join(os.path.dirname(latest_path), "series.json")
    with open(series_path, "w") as f:
        json.dump(series, f, indent=2)
    logger.info(f"Wrote {series_path} ({len(series)} entries)")

    # Write state
    with open(state_local, "w") as f:
        json.dump(state, f, indent=2)

    # Upload to R2
    upload_to_r2(state_local, state_r2_key)
    upload_to_r2(
        latest_path,
        "latest/live_wire_state.json",
        cache_control="public, max-age=300, stale-while-revalidate=60",
    )
    upload_to_r2(
        series_path,
        "latest/live_wire_series.json",
        cache_control="public, max-age=300, stale-while-revalidate=60",
    )

    # Compress and upload snapshot
    gz_path = snapshot_jsonl_path + ".gz"
    try:
        with open(snapshot_jsonl_path, "rb") as f_in:
            with gzip.open(gz_path, "wb") as f_out:
                f_out.write(f_in.read())
        upload_to_r2(gz_path, f"snapshots/{today_str}.jsonl.gz")
    except Exception as e:
        logger.warning(f"Snapshot compression/upload failed: {e}")

    # Local cleanup: remove snapshot files older than max_snapshot_days
    max_days = config.get("max_snapshot_days", 7)
    _cleanup_old_snapshots(config["snapshot_dir"], max_days)

    logger.info(f"Live Wire cycle complete: {snapshot_id}")
    return latest


def _build_series(snapshot_dir: str, max_days: int = 7) -> list:
    """Build a compact 7-day series from local snapshot JSONL files.

    Returns a list of ``{"date", "rial_usd_rate", "connectivity_index"}``
    dicts (one per day, last entry of each day).  This is uploaded to R2 as
    ``latest/live_wire_series.json`` so daily.yml can download a single small
    file instead of the full snapshot archive.
    """
    series = []
    snap_path = Path(snapshot_dir)
    if not snap_path.exists():
        return series

    files = sorted(snap_path.glob("*.jsonl"))[-max_days:]
    for f in files:
        try:
            with open(f, "r") as fh:
                lines = fh.readlines()
            if not lines:
                continue
            entry = json.loads(lines[-1])
            signals = entry.get("signals", {})
            series.append({
                "date": entry.get("generated_at_utc", "")[:10],
                "rial_usd_rate": signals.get("usdt_irt_rate", {}).get("value"),
                "connectivity_index": signals.get("connectivity_index", {}).get("value"),
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return series


def _cleanup_old_snapshots(snapshot_dir: str, max_days: int) -> None:
    """Remove local snapshot files older than max_days."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_days)
    snapshot_path = Path(snapshot_dir)
    if not snapshot_path.exists():
        return

    for f in snapshot_path.iterdir():
        if f.suffix in (".jsonl", ".gz"):
            try:
                # Parse date from filename YYYY-MM-DD.jsonl
                date_str = f.stem.split(".")[0]
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if file_date < cutoff:
                    f.unlink()
                    logger.info(f"Cleaned up old snapshot: {f.name}")
            except (ValueError, IndexError):
                pass


if __name__ == "__main__":
    run_live_wire()

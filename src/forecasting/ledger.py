"""
Append-only JSONL ledger for forecasts and resolutions.

Provides atomic append operations and filtered reads for forecast,
resolution, and correction records.
"""

import hashlib
import json
import os
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable


LEDGER_DIR = Path("forecasting/ledger")
FORECASTS_FILE = "forecasts.jsonl"
RESOLUTIONS_FILE = "resolutions.jsonl"
CORRECTIONS_FILE = "corrections.jsonl"


class LedgerError(Exception):
    """Raised when ledger operations fail."""
    pass


def compute_manifest_id(manifest_path: Path) -> str:
    """
    Compute manifest_id as SHA256 hash of run_manifest.json contents.

    Args:
        manifest_path: Path to run_manifest.json file

    Returns:
        String in format "sha256:<fullhash>"
    """
    with open(manifest_path, 'rb') as f:
        content = f.read()
    hash_digest = hashlib.sha256(content).hexdigest()
    return f"sha256:{hash_digest}"


def ensure_ledger_dir(ledger_dir: Path = LEDGER_DIR) -> None:
    """Create ledger directory if it doesn't exist."""
    ledger_dir.mkdir(parents=True, exist_ok=True)


def append_record(file_path: Path, record: Dict[str, Any]) -> None:
    """
    Atomically append a record to a JSONL file.

    Uses file locking to ensure safe concurrent writes.

    Args:
        file_path: Path to JSONL file
        record: Record dictionary to append

    Raises:
        LedgerError: If append fails
    """
    ensure_ledger_dir(file_path.parent)

    try:
        # Serialize first to catch JSON errors before touching file
        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"

        # Open with append mode, create if doesn't exist
        with open(file_path, 'a') as f:
            # Acquire exclusive lock
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    except (IOError, OSError) as e:
        raise LedgerError(f"Failed to append record: {e}")
    except (TypeError, ValueError) as e:
        raise LedgerError(f"Failed to serialize record: {e}")


def read_records(
    file_path: Path,
    filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
) -> List[Dict[str, Any]]:
    """
    Read all records from a JSONL file, optionally filtered.

    Args:
        file_path: Path to JSONL file
        filter_fn: Optional predicate function to filter records

    Returns:
        List of matching record dictionaries

    Raises:
        LedgerError: If read fails
    """
    if not file_path.exists():
        return []

    records = []
    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    if filter_fn is None or filter_fn(record):
                        records.append(record)
                except json.JSONDecodeError as e:
                    raise LedgerError(f"Invalid JSON on line {line_num}: {e}")
    except IOError as e:
        raise LedgerError(f"Failed to read ledger: {e}")

    return records


def append_forecast(record: Dict[str, Any], ledger_dir: Path = LEDGER_DIR) -> None:
    """
    Append a forecast record to the forecasts ledger.

    Args:
        record: Forecast record dictionary
        ledger_dir: Directory containing ledger files
    """
    record["record_type"] = "forecast"
    append_record(ledger_dir / FORECASTS_FILE, record)


def append_resolution(record: Dict[str, Any], ledger_dir: Path = LEDGER_DIR) -> None:
    """
    Append a resolution record to the resolutions ledger.

    Args:
        record: Resolution record dictionary
        ledger_dir: Directory containing ledger files
    """
    record["record_type"] = "resolution"
    append_record(ledger_dir / RESOLUTIONS_FILE, record)


def append_correction(record: Dict[str, Any], ledger_dir: Path = LEDGER_DIR) -> None:
    """
    Append a correction record to the corrections ledger.

    Args:
        record: Correction record dictionary
        ledger_dir: Directory containing ledger files
    """
    record["record_type"] = "correction"
    append_record(ledger_dir / CORRECTIONS_FILE, record)


def get_forecasts(
    ledger_dir: Path = LEDGER_DIR,
    event_id: Optional[str] = None,
    run_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get forecast records, optionally filtered.

    Args:
        ledger_dir: Directory containing ledger files
        event_id: Optional event ID filter
        run_id: Optional run ID filter

    Returns:
        List of matching forecast records
    """
    def filter_fn(r: Dict[str, Any]) -> bool:
        if event_id and r.get("event_id") != event_id:
            return False
        if run_id and r.get("run_id") != run_id:
            return False
        return True

    return read_records(ledger_dir / FORECASTS_FILE, filter_fn)


def get_resolutions(
    ledger_dir: Path = LEDGER_DIR,
    event_id: Optional[str] = None,
    forecast_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get resolution records, optionally filtered.

    Args:
        ledger_dir: Directory containing ledger files
        event_id: Optional event ID filter
        forecast_id: Optional forecast ID filter

    Returns:
        List of matching resolution records
    """
    def filter_fn(r: Dict[str, Any]) -> bool:
        if event_id and r.get("event_id") != event_id:
            return False
        if forecast_id and r.get("forecast_id") != forecast_id:
            return False
        return True

    return read_records(ledger_dir / RESOLUTIONS_FILE, filter_fn)


def get_pending_forecasts(ledger_dir: Path = LEDGER_DIR) -> List[Dict[str, Any]]:
    """
    Get forecasts that haven't been resolved yet.

    A forecast is pending if no resolution record exists with its forecast_id.

    Args:
        ledger_dir: Directory containing ledger files

    Returns:
        List of pending forecast records
    """
    forecasts = get_forecasts(ledger_dir)
    resolutions = get_resolutions(ledger_dir)

    # Build set of resolved forecast IDs
    resolved_ids = {r.get("forecast_id") for r in resolutions}

    # Filter to unresolved
    return [f for f in forecasts if f.get("forecast_id") not in resolved_ids]


def get_forecast_by_id(
    forecast_id: str,
    ledger_dir: Path = LEDGER_DIR
) -> Optional[Dict[str, Any]]:
    """
    Get a specific forecast by ID.

    Args:
        forecast_id: Forecast identifier
        ledger_dir: Directory containing ledger files

    Returns:
        Forecast record or None if not found
    """
    forecasts = read_records(
        ledger_dir / FORECASTS_FILE,
        lambda r: r.get("forecast_id") == forecast_id
    )
    return forecasts[0] if forecasts else None


def get_resolution_by_forecast_id(
    forecast_id: str,
    ledger_dir: Path = LEDGER_DIR
) -> Optional[Dict[str, Any]]:
    """
    Get resolution for a specific forecast.

    Args:
        forecast_id: Forecast identifier
        ledger_dir: Directory containing ledger files

    Returns:
        Resolution record or None if not resolved
    """
    resolutions = read_records(
        ledger_dir / RESOLUTIONS_FILE,
        lambda r: r.get("forecast_id") == forecast_id
    )
    return resolutions[0] if resolutions else None


def get_pending_manual_adjudication(
    ledger_dir: Path = LEDGER_DIR,
    catalog: Optional[Dict[str, Any]] = None,
    grace_days: int = 7
) -> List[Dict[str, Any]]:
    """
    Get forecasts awaiting manual adjudication.

    Returns forecasts where:
    1. Event has requires_manual_resolution: true
    2. target_date_utc has passed
    3. No resolution record exists

    Each result includes:
    - forecast: The forecast record
    - event_id: Event identifier
    - due_date_utc: target_date + grace_days
    - days_overdue: Negative if not yet due, positive if overdue
    - status: "overdue" | "due_soon" | "pending"

    Args:
        ledger_dir: Directory containing ledger files
        catalog: Event catalog (loads from config/event_catalog.json if not provided)
        grace_days: Days after target_date before considered overdue

    Returns:
        List sorted by due_date_utc (most overdue first)
    """
    from datetime import datetime as dt, timezone as tz, timedelta

    # Load catalog if not provided
    if catalog is None:
        from . import catalog as cat_module
        catalog = cat_module.load_catalog(Path("config/event_catalog.json"))

    from . import catalog as cat_module

    # Get pending forecasts and identify those needing manual resolution
    pending = get_pending_forecasts(ledger_dir)
    now = dt.now(tz.utc)

    results = []
    for forecast in pending:
        event_id = forecast.get("event_id")
        if not event_id:
            continue

        event = cat_module.get_event(catalog, event_id)
        if not event:
            continue

        # Only include events requiring manual resolution
        if not event.get("requires_manual_resolution", False):
            continue

        # Parse target date
        target_str = forecast.get("target_date_utc")
        if not target_str:
            continue

        try:
            target_str = target_str.replace('Z', '+00:00')
            target_date = dt.fromisoformat(target_str)
            if target_date.tzinfo is None:
                target_date = target_date.replace(tzinfo=tz.utc)
        except ValueError:
            continue

        # Skip if target date not yet reached
        if target_date > now:
            continue

        # Calculate due date and overdue status
        due_date = target_date + timedelta(days=grace_days)
        days_overdue = (now - due_date).days

        if days_overdue > 0:
            status = "overdue"
        elif days_overdue >= -2:  # Within 2 days of being due
            status = "due_soon"
        else:
            status = "pending"

        results.append({
            "forecast": forecast,
            "event_id": event_id,
            "due_date_utc": due_date.isoformat(),
            "days_overdue": days_overdue,
            "status": status,
        })

    # Sort by days_overdue descending (most overdue first)
    results.sort(key=lambda x: -x["days_overdue"])

    return results

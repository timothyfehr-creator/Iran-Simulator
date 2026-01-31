"""
History-based baseline forecasters with no-lookahead guarantees.

Builds a history index from resolved forecasts and computes
climatology (Dirichlet-smoothed frequencies) and persistence
(stickiness + staleness decay) baseline distributions.

Critical constraints:
- No lookahead: Only uses resolutions with resolved_at_utc <= as_of_utc
- Correction handling: Latest correction wins for each resolution_id
- UNKNOWN exclusion: UNKNOWN outcomes excluded from training (unless configured)
"""

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

from . import ledger
from . import resolver

logger = logging.getLogger(__name__)

# Default config path
DEFAULT_CONFIG_PATH = Path("config/baseline_config.json")
DEFAULT_SCHEMA_PATH = Path("config/schemas/baseline_config.schema.json")


class BaselineHistoryError(Exception):
    """Raised when baseline history operations fail."""
    pass


@dataclass
class HistoryEntry:
    """History statistics for (event_id, horizon_days) tuple."""
    event_id: str
    horizon_days: int
    counts_by_outcome: Dict[str, int] = field(default_factory=dict)
    history_n: int = 0
    last_resolved_outcome: Optional[str] = None
    last_verified_at: Optional[datetime] = None
    staleness_days: int = 0
    excluded_counts_by_reason: Dict[str, int] = field(default_factory=dict)


class HistoryIndex:
    """
    Cached history entries for baseline computation.

    Builds an index of historical resolutions per (event_id, horizon_days),
    ensuring no lookahead (only resolutions at or before as_of_utc).
    """

    def __init__(self, as_of_utc: datetime, config: Dict[str, Any]):
        """
        Initialize history index.

        Args:
            as_of_utc: Timestamp for lookahead prevention
            config: Baseline configuration
        """
        self.as_of_utc = as_of_utc
        self.config = config
        self._entries: Dict[Tuple[str, int], HistoryEntry] = {}

    def build(self, ledger_dir: Path) -> None:
        """
        Build index from ledger resolutions.

        Args:
            ledger_dir: Path to ledger directory
        """
        # Load resolutions and corrections
        resolutions = ledger.get_resolutions(ledger_dir)
        corrections = ledger.get_corrections(ledger_dir, before_utc=self.as_of_utc)

        # Apply corrections
        corrected_resolutions = apply_corrections(resolutions, corrections)

        # Get defaults and build index
        defaults = self.config.get("defaults", {})
        overrides = self.config.get("overrides", {})

        # Group by (event_id, horizon_days)
        grouped: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}

        for res in corrected_resolutions:
            event_id = res.get("event_id")
            horizon_days = res.get("horizon_days")

            if not event_id or horizon_days is None:
                continue

            key = (event_id, horizon_days)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(res)

        # Build entries
        for key, res_list in grouped.items():
            event_id, horizon_days = key
            event_config = get_event_config(event_id, defaults, overrides)

            entry = self._build_entry(event_id, horizon_days, res_list, event_config)
            self._entries[key] = entry

    def _build_entry(
        self,
        event_id: str,
        horizon_days: int,
        resolutions: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> HistoryEntry:
        """
        Build a single history entry from resolutions.

        Args:
            event_id: Event identifier
            horizon_days: Forecast horizon
            resolutions: List of resolution records
            config: Event-specific config

        Returns:
            HistoryEntry with computed statistics
        """
        entry = HistoryEntry(event_id=event_id, horizon_days=horizon_days)

        # Get config values
        resolution_modes = config.get("resolution_modes", ["external_auto", "external_manual"])
        include_unknown = config.get("include_unknown", False)
        window_days = config.get("window_days")

        # Calculate window cutoff
        window_cutoff = None
        if window_days is not None:
            window_cutoff = self.as_of_utc - timedelta(days=window_days)

        # Filter and count
        counts: Dict[str, int] = {}
        excluded: Dict[str, int] = {}
        last_outcome = None
        last_verified_at = None

        # Sort by resolved_at_utc for deterministic last outcome
        sorted_resolutions = sorted(
            resolutions,
            key=lambda r: r.get("resolved_at_utc", "")
        )

        for res in sorted_resolutions:
            # Check lookahead
            resolved_at_str = res.get("resolved_at_utc")
            if not resolved_at_str:
                excluded["missing_resolved_at"] = excluded.get("missing_resolved_at", 0) + 1
                continue

            resolved_at = parse_datetime(resolved_at_str)
            if resolved_at is None:
                excluded["invalid_resolved_at"] = excluded.get("invalid_resolved_at", 0) + 1
                continue

            # NO LOOKAHEAD: Only include resolutions at or before as_of_utc
            if resolved_at > self.as_of_utc:
                excluded["future_lookahead"] = excluded.get("future_lookahead", 0) + 1
                continue

            # Check window
            if window_cutoff is not None and resolved_at < window_cutoff:
                excluded["outside_window"] = excluded.get("outside_window", 0) + 1
                continue

            # Check resolution mode
            mode = resolver.get_resolution_mode(res)
            if mode not in resolution_modes:
                excluded[f"mode_{mode}"] = excluded.get(f"mode_{mode}", 0) + 1
                continue

            # Get outcome
            outcome = res.get("resolved_outcome")
            if outcome is None:
                excluded["missing_outcome"] = excluded.get("missing_outcome", 0) + 1
                continue

            # Handle UNKNOWN
            if outcome == "UNKNOWN" and not include_unknown:
                excluded["unknown_outcome"] = excluded.get("unknown_outcome", 0) + 1
                continue

            # Count this resolution
            counts[outcome] = counts.get(outcome, 0) + 1

            # Track last outcome for persistence
            last_outcome = outcome
            last_verified_at = resolved_at

        # Compute staleness
        staleness_days = 0
        if last_verified_at is not None:
            delta = self.as_of_utc - last_verified_at
            staleness_days = max(0, delta.days)

        entry.counts_by_outcome = counts
        entry.history_n = sum(counts.values())
        entry.last_resolved_outcome = last_outcome
        entry.last_verified_at = last_verified_at
        entry.staleness_days = staleness_days
        entry.excluded_counts_by_reason = excluded

        return entry

    def get_entry(self, event_id: str, horizon_days: int) -> Optional[HistoryEntry]:
        """
        Get history entry for specific event/horizon.

        Args:
            event_id: Event identifier
            horizon_days: Forecast horizon

        Returns:
            HistoryEntry or None if no history
        """
        return self._entries.get((event_id, horizon_days))

    def get_all_entries(self) -> Dict[Tuple[str, int], HistoryEntry]:
        """Get all history entries."""
        return self._entries.copy()


def load_baseline_config(
    config_path: Path = DEFAULT_CONFIG_PATH
) -> Dict[str, Any]:
    """
    Load baseline configuration from JSON file.

    Args:
        config_path: Path to baseline_config.json

    Returns:
        Configuration dictionary

    Raises:
        BaselineHistoryError: If config can't be loaded
    """
    try:
        with open(config_path) as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        logger.warning(f"Baseline config not found at {config_path}, using defaults")
        return {
            "config_version": "1.0.0",
            "defaults": {
                "min_history_n": 20,
                "window_days": 180,
                "smoothing_alpha": 1.0,
                "include_unknown": False,
                "persistence_stickiness": 0.7,
                "max_staleness_days": 30,
                "staleness_decay": "linear",
                "resolution_modes": ["external_auto", "external_manual"]
            },
            "overrides": {}
        }
    except json.JSONDecodeError as e:
        raise BaselineHistoryError(f"Invalid baseline config JSON: {e}")


def get_event_config(
    event_id: str,
    defaults: Dict[str, Any],
    overrides: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Merge defaults with event-specific overrides.

    Args:
        event_id: Event identifier
        defaults: Default configuration
        overrides: Per-event override dictionary

    Returns:
        Merged configuration for event
    """
    config = defaults.copy()
    event_overrides = overrides.get(event_id, {})
    config.update(event_overrides)
    return config


def build_history_index(
    as_of_utc: datetime,
    ledger_dir: Path = ledger.LEDGER_DIR,
    config: Optional[Dict[str, Any]] = None
) -> HistoryIndex:
    """
    Build history index with lookahead prevention.

    Args:
        as_of_utc: Timestamp for lookahead prevention
        ledger_dir: Path to ledger directory
        config: Baseline configuration (loads from file if None)

    Returns:
        HistoryIndex populated with historical data
    """
    if config is None:
        config = load_baseline_config()

    index = HistoryIndex(as_of_utc, config)
    index.build(ledger_dir)

    return index


def apply_corrections(
    resolutions: List[Dict[str, Any]],
    corrections: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Apply corrections to resolutions (latest correction wins).

    Corrections modify the resolved_outcome of an existing resolution.

    Args:
        resolutions: List of resolution records
        corrections: List of correction records

    Returns:
        List of resolutions with corrections applied
    """
    if not corrections:
        return resolutions

    # Build correction map: resolution_id -> latest correction
    correction_map: Dict[str, Dict[str, Any]] = {}
    for corr in corrections:
        res_id = corr.get("resolution_id")
        if not res_id:
            continue

        # Sort by correction timestamp, latest wins
        corr_at = corr.get("corrected_at_utc", "")
        existing = correction_map.get(res_id)
        if existing is None or corr_at > existing.get("corrected_at_utc", ""):
            correction_map[res_id] = corr

    # Apply corrections
    result = []
    for res in resolutions:
        res_id = res.get("resolution_id")
        correction = correction_map.get(res_id)

        if correction:
            # Apply correction by updating resolved_outcome
            corrected = res.copy()
            new_outcome = correction.get("corrected_outcome")
            if new_outcome is not None:
                corrected["resolved_outcome"] = new_outcome
                corrected["_corrected"] = True
                corrected["_correction_id"] = correction.get("correction_id")
            result.append(corrected)
        else:
            result.append(res)

    return result


def compute_climatology_distribution(
    entry: HistoryEntry,
    outcomes: List[str],
    config: Dict[str, Any]
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Compute climatology distribution using Dirichlet/Laplace smoothing.

    Formula: p_k = (count_k + alpha) / (N + K * alpha)

    Args:
        entry: History entry with counts
        outcomes: List of possible outcomes (excluding UNKNOWN)
        config: Event-specific configuration

    Returns:
        Tuple of (probabilities, metadata)
    """
    min_history_n = config.get("min_history_n", 20)
    alpha = config.get("smoothing_alpha", 1.0)

    metadata = {
        "baseline_history_n": entry.history_n,
        "baseline_fallback": None,
        "baseline_config_version": config.get("config_version", "1.0.0") if isinstance(config, dict) else "1.0.0",
        "baseline_excluded_counts_by_reason": entry.excluded_counts_by_reason.copy(),
    }

    K = len(outcomes)
    if K == 0:
        return {}, metadata

    # Fallback to uniform if insufficient history
    if entry.history_n < min_history_n:
        uniform_prob = round(1.0 / K, 6)
        probs = {o: uniform_prob for o in outcomes}
        # Fix rounding
        total = sum(probs.values())
        if total != 1.0:
            probs[outcomes[0]] = round(probs[outcomes[0]] + (1.0 - total), 6)
        metadata["baseline_fallback"] = "uniform"
        return probs, metadata

    # Compute Dirichlet-smoothed probabilities
    N = entry.history_n
    probs = {}
    for outcome in outcomes:
        count = entry.counts_by_outcome.get(outcome, 0)
        prob = (count + alpha) / (N + K * alpha)
        probs[outcome] = prob

    # Normalize to ensure sum == 1.0
    total = sum(probs.values())
    if total > 0:
        probs = {o: p / total for o, p in probs.items()}

    # Round to 6 decimal places
    probs = {o: round(p, 6) for o, p in probs.items()}

    # Fix final rounding to ensure sum == 1.0
    total = sum(probs.values())
    if abs(total - 1.0) > 1e-9:
        probs[outcomes[0]] = round(probs[outcomes[0]] + (1.0 - total), 6)

    return probs, metadata


def compute_persistence_distribution(
    entry: HistoryEntry,
    outcomes: List[str],
    config: Dict[str, Any],
    climatology_probs: Optional[Dict[str, float]] = None
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """
    Compute persistence distribution with stickiness and staleness decay.

    Formula: p = p_stick * one_hot(last_outcome) + (1 - p_stick) * climatology

    Args:
        entry: History entry with last outcome
        outcomes: List of possible outcomes (excluding UNKNOWN)
        config: Event-specific configuration
        climatology_probs: Pre-computed climatology (computed if None)

    Returns:
        Tuple of (probabilities, metadata)
    """
    # Get climatology if not provided
    if climatology_probs is None:
        clim_probs, _ = compute_climatology_distribution(entry, outcomes, config)
    else:
        clim_probs = climatology_probs

    # Get config values
    base_stickiness = config.get("persistence_stickiness", 0.7)
    max_staleness = config.get("max_staleness_days", 30)
    staleness_decay_type = config.get("staleness_decay", "linear")
    min_history_n = config.get("min_history_n", 20)

    metadata = {
        "baseline_history_n": entry.history_n,
        "baseline_last_verified_at": entry.last_verified_at.isoformat() if entry.last_verified_at else None,
        "baseline_staleness_days": entry.staleness_days,
        "baseline_fallback": None,
        "baseline_config_version": config.get("config_version", "1.0.0") if isinstance(config, dict) else "1.0.0",
        "baseline_excluded_counts_by_reason": entry.excluded_counts_by_reason.copy(),
    }

    K = len(outcomes)
    if K == 0:
        return {}, metadata

    # If no last outcome or insufficient history, fall back to climatology
    if entry.last_resolved_outcome is None or entry.history_n < min_history_n:
        # Use climatology
        uniform_prob = round(1.0 / K, 6)
        probs = clim_probs if clim_probs else {o: uniform_prob for o in outcomes}
        if entry.history_n < min_history_n:
            metadata["baseline_fallback"] = "uniform"
        return probs, metadata

    # Compute decayed stickiness
    p_stick = decay_stickiness(
        base_stickiness,
        entry.staleness_days,
        max_staleness,
        staleness_decay_type
    )

    # If fully decayed, return climatology
    if p_stick <= 0:
        return clim_probs, metadata

    # Build persistence distribution
    last_outcome = entry.last_resolved_outcome
    probs = {}
    for outcome in outcomes:
        clim_p = clim_probs.get(outcome, 1.0 / K)
        if outcome == last_outcome:
            # Sticky outcome gets extra weight
            prob = p_stick + (1 - p_stick) * clim_p
        else:
            prob = (1 - p_stick) * clim_p
        probs[outcome] = prob

    # Normalize to ensure sum == 1.0
    total = sum(probs.values())
    if total > 0:
        probs = {o: p / total for o, p in probs.items()}

    # Round to 6 decimal places
    probs = {o: round(p, 6) for o, p in probs.items()}

    # Fix final rounding
    total = sum(probs.values())
    if abs(total - 1.0) > 1e-9:
        probs[outcomes[0]] = round(probs[outcomes[0]] + (1.0 - total), 6)

    return probs, metadata


def decay_stickiness(
    base_stickiness: float,
    staleness_days: int,
    max_staleness_days: int,
    decay_type: str = "linear"
) -> float:
    """
    Compute decayed stickiness based on staleness.

    Args:
        base_stickiness: Base stickiness value (0-1)
        staleness_days: Days since last verified outcome
        max_staleness_days: Days until full decay
        decay_type: "linear" or "exponential"

    Returns:
        Decayed stickiness value (0 to base_stickiness)
    """
    if staleness_days >= max_staleness_days:
        return 0.0

    if staleness_days <= 0:
        return base_stickiness

    if decay_type == "linear":
        decay_factor = 1 - (staleness_days / max_staleness_days)
    elif decay_type == "exponential":
        # Exponential decay with half-life at max_staleness_days/2
        halflife = max_staleness_days / 2
        decay_factor = math.pow(0.5, staleness_days / halflife)
    else:
        # Default to linear
        decay_factor = 1 - (staleness_days / max_staleness_days)

    return base_stickiness * max(0.0, min(1.0, decay_factor))


def parse_datetime(dt_str: str) -> Optional[datetime]:
    """
    Parse ISO 8601 datetime string.

    Args:
        dt_str: ISO datetime string

    Returns:
        datetime object with UTC timezone, or None if invalid
    """
    if not dt_str:
        return None

    try:
        # Handle 'Z' suffix
        dt_str = dt_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, AttributeError):
        return None

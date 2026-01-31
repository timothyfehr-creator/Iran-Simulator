"""
Source health tracking for ingestion reliability monitoring.

Tracks per-source success/failure history and computes health status.
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path


# Health status thresholds
CONSECUTIVE_FAILURES_DEGRADED = 3
CONSECUTIVE_FAILURES_DOWN = 7

# Rolling average window
ROLLING_AVERAGE_RUNS = 7


@dataclass
class SourceHealth:
    """Health status for a single source."""
    source_id: str
    name: str = ""
    bucket: str = ""
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    docs_fetched_last_run: int = 0
    docs_history: List[int] = field(default_factory=list)  # Last N runs
    avg_docs_per_run_last_7: float = 0.0
    status: str = "OK"  # OK, DEGRADED, DOWN

    def update_status(self):
        """Update status based on consecutive failures."""
        if self.consecutive_failures >= CONSECUTIVE_FAILURES_DOWN:
            self.status = "DOWN"
        elif self.consecutive_failures >= CONSECUTIVE_FAILURES_DEGRADED:
            self.status = "DEGRADED"
        else:
            self.status = "OK"

    def record_success(self, docs_fetched: int, timestamp: Optional[datetime] = None):
        """Record a successful fetch."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        self.last_success_at = timestamp.isoformat()
        self.consecutive_failures = 0
        self.last_error = None
        self.docs_fetched_last_run = docs_fetched

        # Update history
        self.docs_history.append(docs_fetched)
        if len(self.docs_history) > ROLLING_AVERAGE_RUNS:
            self.docs_history = self.docs_history[-ROLLING_AVERAGE_RUNS:]

        # Compute rolling average
        if self.docs_history:
            self.avg_docs_per_run_last_7 = sum(self.docs_history) / len(self.docs_history)

        self.update_status()

    def record_failure(self, error: str, timestamp: Optional[datetime] = None):
        """Record a failed fetch."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        self.last_failure_at = timestamp.isoformat()
        self.consecutive_failures += 1
        self.last_error = error
        self.docs_fetched_last_run = 0

        # Update history with 0
        self.docs_history.append(0)
        if len(self.docs_history) > ROLLING_AVERAGE_RUNS:
            self.docs_history = self.docs_history[-ROLLING_AVERAGE_RUNS:]

        # Compute rolling average
        if self.docs_history:
            self.avg_docs_per_run_last_7 = sum(self.docs_history) / len(self.docs_history)

        self.update_status()


@dataclass
class HealthTracker:
    """Tracks health for all sources across runs."""
    sources: Dict[str, SourceHealth] = field(default_factory=dict)
    last_updated_at: Optional[str] = None

    def get_or_create(self, source_id: str, name: str = "", bucket: str = "") -> SourceHealth:
        """Get existing source health or create new one."""
        if source_id not in self.sources:
            self.sources[source_id] = SourceHealth(
                source_id=source_id,
                name=name,
                bucket=bucket
            )
        return self.sources[source_id]

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of health across all sources."""
        statuses = {"OK": 0, "DEGRADED": 0, "DOWN": 0}
        for source in self.sources.values():
            statuses[source.status] = statuses.get(source.status, 0) + 1

        degraded_sources = [s.source_id for s in self.sources.values() if s.status == "DEGRADED"]
        down_sources = [s.source_id for s in self.sources.values() if s.status == "DOWN"]

        return {
            "total_sources": len(self.sources),
            "status_counts": statuses,
            "degraded_sources": degraded_sources,
            "down_sources": down_sources,
            "overall_status": "DOWN" if down_sources else ("DEGRADED" if degraded_sources else "OK")
        }

    def get_newly_degraded_or_down(self, previous: Optional["HealthTracker"] = None) -> Dict[str, List[str]]:
        """Compare to previous state and find newly degraded/down sources."""
        newly_degraded = []
        newly_down = []

        for source_id, health in self.sources.items():
            prev_health = previous.sources.get(source_id) if previous else None
            prev_status = prev_health.status if prev_health else "OK"

            if health.status == "DEGRADED" and prev_status == "OK":
                newly_degraded.append(source_id)
            elif health.status == "DOWN" and prev_status in ["OK", "DEGRADED"]:
                newly_down.append(source_id)

        return {
            "newly_degraded": newly_degraded,
            "newly_down": newly_down
        }

    def to_dict(self) -> Dict:
        """Serialize to dict."""
        return {
            "last_updated_at": self.last_updated_at,
            "sources": {k: asdict(v) for k, v in self.sources.items()},
            "summary": self.get_summary()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "HealthTracker":
        """Deserialize from dict."""
        tracker = cls()
        tracker.last_updated_at = data.get("last_updated_at")

        for source_id, source_data in data.get("sources", {}).items():
            health = SourceHealth(
                source_id=source_data.get("source_id", source_id),
                name=source_data.get("name", ""),
                bucket=source_data.get("bucket", ""),
                last_success_at=source_data.get("last_success_at"),
                last_failure_at=source_data.get("last_failure_at"),
                consecutive_failures=source_data.get("consecutive_failures", 0),
                last_error=source_data.get("last_error"),
                docs_fetched_last_run=source_data.get("docs_fetched_last_run", 0),
                docs_history=source_data.get("docs_history", []),
                avg_docs_per_run_last_7=source_data.get("avg_docs_per_run_last_7", 0.0),
                status=source_data.get("status", "OK")
            )
            tracker.sources[source_id] = health

        return tracker


def get_health_file_path() -> str:
    """Get path to sources_health.json in runs/_meta/."""
    meta_dir = Path("runs/_meta")
    meta_dir.mkdir(parents=True, exist_ok=True)
    return str(meta_dir / "sources_health.json")


def load_health_tracker() -> HealthTracker:
    """Load health tracker from disk, or create new one."""
    health_path = get_health_file_path()

    if os.path.exists(health_path):
        try:
            with open(health_path, 'r') as f:
                data = json.load(f)
            return HealthTracker.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load health tracker: {e}")
            return HealthTracker()

    return HealthTracker()


def save_health_tracker(tracker: HealthTracker):
    """Save health tracker to disk."""
    tracker.last_updated_at = datetime.now(timezone.utc).isoformat()
    health_path = get_health_file_path()

    with open(health_path, 'w') as f:
        json.dump(tracker.to_dict(), f, indent=2)

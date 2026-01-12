"""
Pipeline data models for evidence → claims → compiler MVP.

These are intentionally lightweight (stdlib only) so the project stays easy to run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class EvidenceDoc:
    doc_id: str
    source_name: str
    url: str
    published_at_utc: str
    retrieved_at_utc: str
    language: str
    raw_text: str
    translation_en: Optional[str] = None
    translation_confidence: str = "UNKNOWN"
    notes: str = ""


@dataclass
class Source:
    id: str
    organization: str
    title: str
    date: str  # YYYY-MM-DD
    url: str
    access_grade: str
    bias_grade: str
    language: str = "en"
    translation_confidence: str = "UNKNOWN"
    notes: str = ""


@dataclass
class ClaimConflict:
    source_id: str
    value: Any
    note: str = ""


@dataclass
class Claim:
    claim_id: str
    path: str
    value: Any
    units: str
    as_of: str
    source_grade: str
    source_ids: List[str] = field(default_factory=list)
    selector: Optional[Dict[str, Any]] = None
    confidence: str = "LOW"
    triangulated: bool = False
    null_reason: Optional[str] = None
    notes: str = ""
    conflicts: List[ClaimConflict] = field(default_factory=list)

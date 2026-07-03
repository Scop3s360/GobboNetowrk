"""
Project Model
=============
Defines the Project entity structure for workspace isolation.
"""

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

def _new_uuid() -> str:
    return str(uuid.uuid4())

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Project:
    """
    Represents an isolated workspace project.
    """
    name: str
    description: str = ""
    type: str = "Other"  # Game, Software, Writing, Research, Other
    tags: list[str] = field(default_factory=list)
    id: str = field(default_factory=_new_uuid)
    source_dir: str | None = None
    created_at: str = field(default_factory=_utc_now_iso)
    last_opened_at: str = field(default_factory=_utc_now_iso)

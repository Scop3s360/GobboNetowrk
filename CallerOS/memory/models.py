"""
Memory Models
=============
Immutable memory records and memory type enums.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MemoryType(Enum):
    """Types of memory supported by GoblinOS."""
    CONVERSATION = "CONVERSATION"
    PROJECT = "PROJECT"
    AGENT = "AGENT"


def _new_uuid() -> str:
    """Generate a new unique identifier."""
    return str(uuid.uuid4())


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass(frozen=True)
class MemoryRecord:
    """
    An immutable memory record.

    Attributes:
        type:       The category of this memory (MemoryType).
        content:    The main text content of the memory.
        source:     The creator or origin of this memory (e.g., worker_id, user).
        id:         Unique identifier (UUID as a string). Auto-generated if not provided.
        tags:       A list of tag strings associated with the memory.
        project:    Optional project tag.
        agent:      Optional agent identifier who owns or generated the memory.
        importance: An integer importance rating (e.g. 1 to 10). Defaults to 1.
        created_at: ISO-8601 UTC timestamp of creation.
        updated_at: ISO-8601 UTC timestamp of the last update.
    """

    type: MemoryType
    content: str
    source: str
    id: str = field(default_factory=_new_uuid)
    tags: list[str] = field(default_factory=list)
    project: str | None = None
    agent: str | None = None
    importance: int = 1
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)

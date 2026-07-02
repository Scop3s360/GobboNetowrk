"""
Memory Search
=============
Dataclass defining search criteria for memory querying.
"""

from __future__ import annotations

from dataclasses import dataclass
from memory.models import MemoryType


@dataclass(frozen=True)
class MemorySearchQuery:
    """
    Search criteria for querying the memory system.

    Attributes:
        keyword:     Substrings to look for in the memory content.
        tags:        List of tags. Returns memories containing ALL of these tags.
        project:     Filter by project identifier.
        agent:       Filter by agent identifier.
        memory_type: Filter by MemoryType.
        importance:  Filter by exact importance level.
        start_date:  ISO-8601 UTC timestamp; returns memories created on or after this.
        end_date:    ISO-8601 UTC timestamp; returns memories created on or before this.
    """

    keyword: str | None = None
    tags: list[str] | None = None
    project: str | None = None
    agent: str | None = None
    memory_type: MemoryType | None = None
    importance: int | None = None
    start_date: str | None = None
    end_date: str | None = None

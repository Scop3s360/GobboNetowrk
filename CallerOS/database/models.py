"""
Database Models
===============
Dataclasses representing structured database entities for GoblinOS.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _new_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def _utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 string format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Conversation:
    """
    Represents an ongoing chat thread context with an AI agent.
    """
    title: str
    id: str = field(default_factory=_new_uuid)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class Message:
    """
    Represents an individual message text within a Conversation.
    """
    conversation_id: str
    role: str
    content: str
    id: str = field(default_factory=_new_uuid)
    timestamp: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class Memory:
    """
    Represents a persistent unit of memory (e.g. Conversation, Project, Agent).
    """
    type: str
    content: str
    source: str
    id: str = field(default_factory=_new_uuid)
    project: str | None = None
    agent: str | None = None
    tags: list[str] = field(default_factory=list)
    importance: int = 1
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class WorkflowHistory:
    """
    Represents a logged execution record of a multi-step workflow run.
    """
    workflow_id: str
    state: str
    request: str
    response: str
    id: str = field(default_factory=_new_uuid)
    timestamp: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class Setting:
    """
    Represents an application key/value configuration setting.
    """
    key: str
    value: str


@dataclass(frozen=True)
class LogEntry:
    """
    Represents a structured system log message.
    """
    timestamp: str
    level: str
    message: str
    id: int | None = None

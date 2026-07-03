from __future__ import annotations

from dataclasses import dataclass, field

@dataclass(frozen=True)
class DeveloperRequest:
    """
    Describes a development task.
    """
    prompt: str
    context: str = ""

@dataclass(frozen=True)
class DeveloperResult:
    """
    Structured output from a completed developer task.
    """
    explanation: str
    code: str
    notes: str
    raw_response: str | None = None

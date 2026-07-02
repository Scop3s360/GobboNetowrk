"""
Tool Models
===========
Immutable request and response models for tool execution.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _new_correlation_id() -> str:
    """Generate a new unique correlation id."""
    return str(uuid.uuid4())


@dataclass(frozen=True)
class ToolRequest:
    """
    An immutable request to execute a tool.

    Attributes:
        tool_name:      The name of the tool to execute.
        arguments:      A dictionary of arguments to pass to the tool.
        correlation_id: A unique identifier for tracing and correlation.
        timestamp:      UTC ISO-8601 timestamp when the request was created.
    """

    tool_name: str
    arguments: dict[str, object]
    correlation_id: str = field(default_factory=_new_correlation_id)
    timestamp: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class ToolResponse:
    """
    An immutable response returned after tool execution.

    Attributes:
        success:           True if the tool executed successfully, False otherwise.
        output:            The output of the tool execution (None on failure).
        error:             The error message if execution failed (None on success).
        execution_time_ms: The execution time in milliseconds.
    """

    success: bool
    output: object = None
    error: str | None = None
    execution_time_ms: float = 0.0

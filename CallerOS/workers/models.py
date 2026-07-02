"""
Worker Models
=============
Immutable data transfer objects for worker communication.

WorkerRequest  — carries a unit of work into a worker.
WorkerResponse — carries the result (or error) back out.

Architectural decision:
    Both types are frozen dataclasses rather than plain dicts so that:
      - Fields are explicit and type-checked at construction.
      - Instances cannot be mutated after creation, preventing subtle bugs
        where a caller modifies a request/response it has already handed off.
      - No third-party serialisation library is required at this stage.

    ``duration_ms`` is stored as a float rather than an int to preserve
    sub-millisecond precision without adding a dependency on datetime.timedelta.

    ``metadata`` is typed as ``dict[str, object]`` on both models.  The value
    type is ``object`` (not ``Any``) to document the intent that arbitrary
    values are permitted while still being inspectable.  Callers are
    responsible for narrowing types when they read metadata back.

    ``created_at`` is a UTC ISO-8601 string (not a datetime object) to keep
    the model JSON-serialisable without any extra work.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


def _new_request_id() -> str:
    """Generate a new unique request id."""
    return str(uuid.uuid4())


@dataclass(frozen=True)
class WorkerRequest:
    """
    An immutable unit of work delivered to a worker.

    Attributes:
        request_id: Unique identifier for this request.  Auto-generated if
                    not provided, which covers the common case where the caller
                    does not need to track the id ahead of time.
        worker_id:  The id of the worker this request is addressed to.
        payload:    The actual work data.  Shape is worker-specific.
        metadata:   Optional key/value pairs for tracing, tagging, etc.
        created_at: UTC ISO-8601 timestamp set at construction time.
    """

    worker_id: str
    payload: object
    request_id: str = field(default_factory=_new_request_id)
    metadata: dict[str, object] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)


@dataclass(frozen=True)
class WorkerResponse:
    """
    An immutable result returned by a worker after processing a request.

    Attributes:
        request_id:  Echoes the id from the originating WorkerRequest so the
                     caller can correlate request → response.
        success:     True if the worker completed without error.
        result:      The output produced by the worker (None on failure).
        error:       Human-readable error description (None on success).
        metadata:    Optional key/value pairs added by the worker.
        duration_ms: Wall-clock time the worker spent in execute(), in
                     milliseconds.  Useful for performance analysis.
    """

    request_id: str
    success: bool
    result: object = None
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
    duration_ms: float = 0.0

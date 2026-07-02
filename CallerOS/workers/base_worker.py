"""
Base Worker
===========
Abstract base class that every GoblinOS worker inherits from.

BaseWorker defines the standard worker lifecycle and the identity contract
(id, name, description, version, capabilities, status).

Architectural decisions:

    ABC enforcement:
        Python's ``abc.ABC`` / ``@abstractmethod`` is used so that forgetting
        to implement ``initialize``, ``execute``, or ``shutdown`` is caught at
        class definition time rather than silently producing a broken worker.

    Status as enum:
        WorkerStatus is an enum rather than a string so that:
          - Typos in status names are impossible.
          - Valid transitions can be checked centrally.
          - IDE tooling autocompletes correctly.

    State transition guard:
        _transition() validates that a move to a new state is legal before
        applying it.  This catches programming errors (e.g. calling execute()
        on a stopped worker) immediately rather than silently producing wrong
        behaviour.

    Timing in execute():
        BaseWorker times the call to _execute() using time.perf_counter so
        that WorkerResponse.duration_ms is always populated without requiring
        each subclass to implement its own timing.

    No AI, no tools, no routing:
        BaseWorker knows nothing about AI providers, tools, memory, or routing.
        It is pure lifecycle management.
"""

from __future__ import annotations

import abc
import logging
import time
from enum import Enum, auto

from workers.exceptions import (
    WorkerExecutionError,
    WorkerInitializationError,
    WorkerShutdownError,
)
from workers.models import WorkerRequest, WorkerResponse

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker Status
# ---------------------------------------------------------------------------

class WorkerStatus(Enum):
    """
    Lifecycle states of a worker.

    Valid transitions:
        CREATED      → INITIALIZING
        INITIALIZING → IDLE  (success) | FAILED  (error)
        IDLE         → RUNNING
        RUNNING      → IDLE  (success) | FAILED  (error)
        IDLE         → STOPPING
        STOPPING     → STOPPED (success) | FAILED (error)
        FAILED       → (terminal — worker must be replaced)
    """

    CREATED = auto()
    INITIALIZING = auto()
    IDLE = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    FAILED = auto()


# Explicit transition table.  Key: current state, Value: allowed next states.
_VALID_TRANSITIONS: dict[WorkerStatus, set[WorkerStatus]] = {
    WorkerStatus.CREATED:      {WorkerStatus.INITIALIZING},
    WorkerStatus.INITIALIZING: {WorkerStatus.IDLE, WorkerStatus.FAILED},
    WorkerStatus.IDLE:         {WorkerStatus.RUNNING, WorkerStatus.STOPPING},
    WorkerStatus.RUNNING:      {WorkerStatus.IDLE, WorkerStatus.FAILED},
    WorkerStatus.STOPPING:     {WorkerStatus.STOPPED, WorkerStatus.FAILED},
    WorkerStatus.STOPPED:      set(),   # terminal
    WorkerStatus.FAILED:       set(),   # terminal
}


# ---------------------------------------------------------------------------
# Base Worker
# ---------------------------------------------------------------------------

class BaseWorker(abc.ABC):
    """
    Abstract base class for all GoblinOS workers.

    Subclasses must implement:
        _initialize()  — one-time setup (load prompts, open resources, etc.)
        _execute(request)  — process a WorkerRequest and return a WorkerResponse
        _shutdown()  — release resources cleanly

    Subclasses should NOT override the public ``initialize``, ``execute``, or
    ``shutdown`` methods — those enforce state transitions and logging.

    Identity attributes (``id``, ``name``, ``description``, ``version``,
    ``capabilities``) are set via constructor parameters so that subclass
    instances can be uniquely identified without any magic.
    """

    def __init__(
        self,
        worker_id: str,
        name: str,
        description: str,
        version: str,
        capabilities: list[str],
    ) -> None:
        self._id = worker_id
        self._name = name
        self._description = description
        self._version = version
        self._capabilities: list[str] = list(capabilities)  # defensive copy
        self._status = WorkerStatus.CREATED

    # ------------------------------------------------------------------
    # Identity properties (read-only)
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        """Unique identifier for this worker instance."""
        return self._id

    @property
    def name(self) -> str:
        """Human-readable worker name."""
        return self._name

    @property
    def description(self) -> str:
        """What this worker does."""
        return self._description

    @property
    def version(self) -> str:
        """Semantic version of this worker implementation."""
        return self._version

    @property
    def capabilities(self) -> list[str]:
        """List of capability tags this worker supports."""
        return list(self._capabilities)  # defensive copy — callers cannot mutate

    @property
    def status(self) -> WorkerStatus:
        """Current lifecycle status."""
        return self._status

    # ------------------------------------------------------------------
    # Public lifecycle methods (not overridable by subclasses)
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """
        Execute the worker's one-time startup sequence.

        Transitions: CREATED → INITIALIZING → IDLE (or FAILED).

        Raises:
            WorkerInitializationError: If _initialize() raises.
        """
        self._transition(WorkerStatus.INITIALIZING)
        log.info("Worker initializing: id=%s  name=%s", self._id, self._name)
        try:
            self._initialize()
        except Exception as exc:
            self._transition(WorkerStatus.FAILED)
            log.error(
                "Worker initialization failed: id=%s  error=%s",
                self._id, exc, exc_info=True,
            )
            raise WorkerInitializationError(
                f"Worker '{self._id}' failed to initialize: {exc}"
            ) from exc

        self._transition(WorkerStatus.IDLE)
        log.info("Worker initialized: id=%s  name=%s", self._id, self._name)

    def execute(self, request: WorkerRequest) -> WorkerResponse:
        """
        Process a WorkerRequest and return a WorkerResponse.

        Transitions: IDLE → RUNNING → IDLE (success) or FAILED (error).

        Timing is applied around ``_execute()`` and stored in
        ``WorkerResponse.duration_ms``.

        Raises:
            WorkerExecutionError: If _execute() raises.
        """
        self._transition(WorkerStatus.RUNNING)
        log.info(
            "Worker execution started: id=%s  request_id=%s",
            self._id, request.request_id,
        )
        start = time.perf_counter()
        try:
            response = self._execute(request)
        except Exception as exc:
            self._transition(WorkerStatus.FAILED)
            log.error(
                "Worker execution failed: id=%s  request_id=%s  error=%s",
                self._id, request.request_id, exc, exc_info=True,
            )
            raise WorkerExecutionError(
                f"Worker '{self._id}' failed to execute request "
                f"'{request.request_id}': {exc}"
            ) from exc
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000

        # Only reach IDLE if no exception was raised.
        self._transition(WorkerStatus.IDLE)
        log.info(
            "Worker execution completed: id=%s  request_id=%s  duration_ms=%.2f",
            self._id, request.request_id, elapsed_ms,
        )

        # Re-attach timing even if the subclass already set duration_ms.
        # Using object.__setattr__ because WorkerResponse is frozen.
        return _attach_duration(response, elapsed_ms)

    def shutdown(self) -> None:
        """
        Release resources and transition to STOPPED.

        Transitions: IDLE → STOPPING → STOPPED (or FAILED).

        Raises:
            WorkerShutdownError: If _shutdown() raises.
        """
        self._transition(WorkerStatus.STOPPING)
        log.info("Worker shutting down: id=%s  name=%s", self._id, self._name)
        try:
            self._shutdown()
        except Exception as exc:
            self._transition(WorkerStatus.FAILED)
            log.error(
                "Worker shutdown failed: id=%s  error=%s",
                self._id, exc, exc_info=True,
            )
            raise WorkerShutdownError(
                f"Worker '{self._id}' failed to shut down cleanly: {exc}"
            ) from exc

        self._transition(WorkerStatus.STOPPED)
        log.info("Worker shutdown complete: id=%s  name=%s", self._id, self._name)

    # ------------------------------------------------------------------
    # Abstract hooks — subclasses implement these
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def _initialize(self) -> None:
        """Subclass-specific startup logic."""

    @abc.abstractmethod
    def _execute(self, request: WorkerRequest) -> WorkerResponse:
        """Subclass-specific execution logic."""

    @abc.abstractmethod
    def _shutdown(self) -> None:
        """Subclass-specific teardown logic."""

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _transition(self, new_status: WorkerStatus) -> None:
        """
        Validate and apply a state transition.

        Raises:
            RuntimeError: If the transition from the current state to
                          ``new_status`` is not permitted.
        """
        allowed = _VALID_TRANSITIONS.get(self._status, set())
        if new_status not in allowed:
            raise RuntimeError(
                f"Worker '{self._id}': invalid state transition "
                f"{self._status.name} → {new_status.name}. "
                f"Allowed next states: "
                f"{[s.name for s in allowed] or '(none — terminal state)'}."
            )
        self._status = new_status


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _attach_duration(response: WorkerResponse, duration_ms: float) -> WorkerResponse:
    """
    Return a copy of ``response`` with ``duration_ms`` set.

    WorkerResponse is frozen, so we must create a new instance.  This is
    intentional — the subclass should not be responsible for timing itself.
    """
    # object.__setattr__ would fail on a frozen dataclass; we build a new one.
    from dataclasses import replace
    return replace(response, duration_ms=duration_ms)

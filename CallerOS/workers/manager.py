"""
Worker Manager
==============
Coordinates the lifecycle of workers registered in a WorkerRegistry.

Responsibilities — exactly these, nothing more:
    - Initialize workers (call worker.initialize())
    - Execute a worker by id (call worker.execute(request))
    - Shutdown workers (call worker.shutdown())

Architectural decision:
    WorkerManager is deliberately thin.  It does not decide WHICH worker to
    call for a given request — that is the Director's job (Stage 5).  It only
    knows HOW to operate a worker whose id it has been given explicitly.

    Relationship to WorkerRegistry:
        WorkerManager depends on WorkerRegistry via constructor injection
        (not by creating its own registry), so the two can be tested
        independently and the same registry instance can be shared if needed.

    Initialization strategy:
        ``initialize_all()`` initializes workers in id-sorted order for
        determinism.  If any worker fails, the error is wrapped in
        WorkerInitializationError and propagated immediately.  Workers
        initialized before the failure remain in IDLE state — the caller is
        responsible for deciding whether to continue or abort the whole
        application startup.

    Shutdown strategy:
        ``shutdown_all()`` attempts to stop every worker regardless of
        individual failures, collecting errors and re-raising at the end.
        This mirrors the Stage 1 LifecycleManager pattern.
"""

import logging

from workers.base_worker import BaseWorker
from workers.exceptions import (
    WorkerInitializationError,
    WorkerNotFoundError,
    WorkerShutdownError,
)
from workers.models import WorkerRequest, WorkerResponse
from workers.registry import WorkerRegistry

log = logging.getLogger(__name__)


class WorkerManager:
    """
    Manages initialization, execution, and shutdown of workers.

    Usage::

        registry = WorkerRegistry()
        registry.register(my_worker)

        manager = WorkerManager(registry)
        manager.initialize_all()
        response = manager.execute("my-worker-id", request)
        manager.shutdown_all()
    """

    def __init__(self, registry: WorkerRegistry) -> None:
        # Injected — WorkerManager does not own or create the registry.
        self._registry = registry

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize_all(self) -> None:
        """
        Initialize every worker in the registry (id-sorted order).

        Raises:
            WorkerInitializationError: If any worker fails to initialize.
                                       Workers initialized before the failure
                                       remain in IDLE state.
        """
        workers = self._registry.list_workers()
        log.info("WorkerManager: initializing %d worker(s).", len(workers))
        for worker in workers:
            self._initialize_one(worker)
        log.info("WorkerManager: all workers initialized.")

    def initialize_worker(self, worker_id: str) -> None:
        """
        Initialize a single worker by id.

        Args:
            worker_id: The id of the worker to initialize.

        Raises:
            WorkerNotFoundError:      If no worker with that id is registered.
            WorkerInitializationError: If the worker raises during initialize().
        """
        worker = self._registry.get(worker_id)
        self._initialize_one(worker)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, worker_id: str, request: WorkerRequest) -> WorkerResponse:
        """
        Execute a worker by id with the given request.

        Args:
            worker_id: The id of the worker to run.
            request:   The WorkerRequest to process.

        Returns:
            The WorkerResponse produced by the worker.

        Raises:
            WorkerNotFoundError:   If no worker with that id is registered.
            WorkerExecutionError:  If the worker raises during execute().
        """
        worker = self._registry.get(worker_id)
        log.info(
            "WorkerManager: dispatching request_id=%s to worker id=%s",
            request.request_id, worker_id,
        )
        # WorkerExecutionError propagates naturally from worker.execute().
        return worker.execute(request)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown_all(self) -> None:
        """
        Shut down every worker in the registry (reverse id-sorted order).

        All workers are given a chance to shut down even if earlier shutdowns
        fail.  All errors are collected and re-raised together as a single
        WorkerShutdownError after all workers have been attempted.

        Raises:
            WorkerShutdownError: If one or more workers fail during shutdown().
        """
        # Reverse order mirrors LIFO teardown convention from Stage 1.
        workers = list(reversed(self._registry.list_workers()))
        log.info("WorkerManager: shutting down %d worker(s).", len(workers))
        errors: list[str] = []

        for worker in workers:
            try:
                self._shutdown_one(worker)
            except WorkerShutdownError as exc:
                errors.append(str(exc))

        log.info("WorkerManager: shutdown complete.")
        if errors:
            raise WorkerShutdownError(
                "One or more workers did not shut down cleanly:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def shutdown_worker(self, worker_id: str) -> None:
        """
        Shut down a single worker by id.

        Args:
            worker_id: The id of the worker to stop.

        Raises:
            WorkerNotFoundError: If no worker with that id is registered.
            WorkerShutdownError: If the worker raises during shutdown().
        """
        worker = self._registry.get(worker_id)
        self._shutdown_one(worker)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _initialize_one(self, worker: BaseWorker) -> None:
        """Call initialize() on a single worker, wrapping any error."""
        try:
            worker.initialize()
        except WorkerInitializationError:
            # Already wrapped — re-raise as-is.
            raise
        except Exception as exc:
            # Unexpected exception from somewhere other than worker.initialize().
            raise WorkerInitializationError(
                f"Unexpected error initializing worker '{worker.id}': {exc}"
            ) from exc

    def _shutdown_one(self, worker: BaseWorker) -> None:
        """Call shutdown() on a single worker, wrapping any error."""
        try:
            worker.shutdown()
        except WorkerShutdownError:
            # Already wrapped — re-raise as-is.
            raise
        except Exception as exc:
            raise WorkerShutdownError(
                f"Unexpected error shutting down worker '{worker.id}': {exc}"
            ) from exc

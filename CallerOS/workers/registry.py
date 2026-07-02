"""
Worker Registry
===============
Manages the set of known workers, keyed by worker id.

Responsibilities — exactly these, nothing more:
    - Register a worker (reject duplicates)
    - Unregister a worker
    - Look up a worker by id
    - List all registered workers

Architectural decision:
    WorkerRegistry is deliberately separate from Stage 1's ServiceRegistry.
    The ServiceRegistry manages application-level infrastructure objects
    (logging, config, etc.).  WorkerRegistry manages domain objects (workers).
    Mixing the two would blur the boundary between infrastructure and domain.

    No routing logic lives here.  The registry does not know what a worker
    does or which requests it should receive.  Routing is a Stage 5 concern
    (Director Agent).

    Workers are keyed by ``worker.id`` (a string) rather than by name, because
    in the future multiple instances of the same worker type may coexist and
    each must be uniquely addressable.
"""

import logging
from typing import Iterator

from workers.base_worker import BaseWorker
from workers.exceptions import WorkerAlreadyRegisteredError, WorkerNotFoundError

log = logging.getLogger(__name__)


class WorkerRegistry:
    """
    Maps worker ids to BaseWorker instances.

    Usage::

        registry = WorkerRegistry()
        registry.register(my_worker)
        worker = registry.get("worker-id-123")
        registry.unregister("worker-id-123")
    """

    def __init__(self) -> None:
        self._workers: dict[str, BaseWorker] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, worker: BaseWorker) -> None:
        """
        Add a worker to the registry.

        Args:
            worker: The worker instance to register.  Its ``id`` must be
                    unique within this registry.

        Raises:
            WorkerAlreadyRegisteredError: If a worker with the same id is
                                          already registered.
        """
        if worker.id in self._workers:
            raise WorkerAlreadyRegisteredError(
                f"Worker with id '{worker.id}' is already registered. "
                "Each worker id must be unique."
            )
        self._workers[worker.id] = worker
        log.info(
            "Worker registered: id=%s  name=%s  version=%s",
            worker.id, worker.name, worker.version,
        )

    def unregister(self, worker_id: str) -> None:
        """
        Remove a worker from the registry by id.

        Silently does nothing if the id is not registered — this prevents
        callers from having to guard with ``get()`` before cleanup.

        Args:
            worker_id: The id of the worker to remove.
        """
        removed = self._workers.pop(worker_id, None)
        if removed is not None:
            log.info("Worker unregistered: id=%s  name=%s", worker_id, removed.name)
        else:
            log.debug("Worker unregister called for unknown id: %s", worker_id)

    def get(self, worker_id: str) -> BaseWorker:
        """
        Return the worker registered under ``worker_id``.

        Args:
            worker_id: The unique worker identifier.

        Returns:
            The registered BaseWorker instance.

        Raises:
            WorkerNotFoundError: If no worker is registered under the given id.
        """
        worker = self._workers.get(worker_id)
        if worker is None:
            raise WorkerNotFoundError(
                f"No worker registered with id '{worker_id}'. "
                f"Registered ids: {self._registered_ids()}"
            )
        return worker

    def list_workers(self) -> list[BaseWorker]:
        """
        Return a list of all registered workers, ordered by id.

        Returns a new list on every call — modifications to the returned list
        do not affect the registry.
        """
        return [self._workers[wid] for wid in sorted(self._workers)]

    def is_registered(self, worker_id: str) -> bool:
        """Return True if a worker with ``worker_id`` is registered."""
        return worker_id in self._workers

    def clear(self) -> None:
        """Remove all workers.  Intended for test teardown only."""
        self._workers.clear()
        log.debug("Worker registry cleared.")

    def __len__(self) -> int:
        """Return the number of registered workers."""
        return len(self._workers)

    def __iter__(self) -> Iterator[BaseWorker]:
        """Iterate over registered workers in id order."""
        for wid in sorted(self._workers):
            yield self._workers[wid]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _registered_ids(self) -> str:
        ids = sorted(self._workers.keys())
        return ", ".join(ids) if ids else "(none)"

"""
Tests: WorkerManager (workers/manager.py)
==========================================
Covers:
  - initialize_all() calls initialize() on all registered workers.
  - initialize_worker(id) initializes a single worker.
  - initialize_worker() with unknown id raises WorkerNotFoundError.
  - initialize_all() propagates WorkerInitializationError on failure.
  - execute() dispatches request to correct worker and returns response.
  - execute() with unknown id raises WorkerNotFoundError.
  - execute() propagates WorkerExecutionError on worker failure.
  - shutdown_all() calls shutdown() on all initialized workers.
  - shutdown_all() collects errors and raises WorkerShutdownError.
  - shutdown_worker(id) shuts down a single worker.
  - shutdown_worker() with unknown id raises WorkerNotFoundError.
  - shutdown_all() continues past individual failures.
"""

from __future__ import annotations

import pytest

from workers.exceptions import (
    WorkerExecutionError,
    WorkerInitializationError,
    WorkerNotFoundError,
    WorkerShutdownError,
)
from workers.manager import WorkerManager
from workers.models import WorkerRequest
from workers.registry import WorkerRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager(*workers) -> tuple[WorkerRegistry, WorkerManager]:
    """Build a registry+manager pre-populated with ``workers``."""
    registry = WorkerRegistry()
    for w in workers:
        registry.register(w)
    return registry, WorkerManager(registry)


def _req(worker_id: str = "dummy-01", payload: object = "data") -> WorkerRequest:
    return WorkerRequest(worker_id=worker_id, payload=payload)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestManagerInitialize:
    def test_initialize_all_inits_all_workers(self, dummy_worker):
        _, manager = _make_manager(dummy_worker)
        manager.initialize_all()
        assert dummy_worker.init_calls == 1

    def test_initialize_all_multiple_workers(self):
        from tests.conftest import DummyWorker

        a = DummyWorker(worker_id="a")
        b = DummyWorker(worker_id="b")
        _, manager = _make_manager(a, b)
        manager.initialize_all()
        assert a.init_calls == 1
        assert b.init_calls == 1

    def test_initialize_worker_by_id(self, dummy_worker):
        _, manager = _make_manager(dummy_worker)
        manager.initialize_worker("dummy-01")
        assert dummy_worker.init_calls == 1

    def test_initialize_worker_unknown_id_raises(self):
        _, manager = _make_manager()
        with pytest.raises(WorkerNotFoundError):
            manager.initialize_worker("ghost")

    def test_initialize_all_propagates_failure(self):
        from tests.conftest import FailingInitWorker

        worker = FailingInitWorker()
        _, manager = _make_manager(worker)
        with pytest.raises(WorkerInitializationError, match="init boom"):
            manager.initialize_all()

    def test_initialize_all_empty_registry_ok(self):
        _, manager = _make_manager()
        # Should not raise on empty registry.
        manager.initialize_all()


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


class TestManagerExecute:
    def test_execute_returns_response(self, idle_worker, make_request):
        registry, manager = _make_manager(idle_worker)
        response = manager.execute("dummy-01", make_request())
        assert response.success is True

    def test_execute_response_has_correct_request_id(self, idle_worker):
        registry, manager = _make_manager(idle_worker)
        req = _req()
        response = manager.execute("dummy-01", req)
        assert response.request_id == req.request_id

    def test_execute_dispatches_to_correct_worker(self):
        from tests.conftest import DummyWorker

        a = DummyWorker(worker_id="a")
        b = DummyWorker(worker_id="b")
        a.initialize()
        b.initialize()
        _, manager = _make_manager(a, b)
        manager.execute("b", WorkerRequest(worker_id="b", payload="ping"))
        assert b.exec_calls == 1
        assert a.exec_calls == 0

    def test_execute_unknown_id_raises(self):
        _, manager = _make_manager()
        with pytest.raises(WorkerNotFoundError):
            manager.execute("ghost", _req("ghost"))

    def test_execute_failure_propagates(self):
        from tests.conftest import FailingExecWorker

        worker = FailingExecWorker()
        worker.initialize()
        _, manager = _make_manager(worker)
        req = WorkerRequest(worker_id="fail-exec", payload=None)
        with pytest.raises(WorkerExecutionError, match="exec boom"):
            manager.execute("fail-exec", req)

    def test_response_duration_ms_populated(self, idle_worker, make_request):
        _, manager = _make_manager(idle_worker)
        response = manager.execute("dummy-01", make_request())
        assert response.duration_ms >= 0.0


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


class TestManagerShutdown:
    def test_shutdown_all_calls_shutdown(self, idle_worker):
        _, manager = _make_manager(idle_worker)
        manager.shutdown_all()
        assert idle_worker.shutdown_calls == 1

    def test_shutdown_all_multiple_workers(self):
        from tests.conftest import DummyWorker

        a = DummyWorker(worker_id="a")
        b = DummyWorker(worker_id="b")
        a.initialize()
        b.initialize()
        _, manager = _make_manager(a, b)
        manager.shutdown_all()
        assert a.shutdown_calls == 1
        assert b.shutdown_calls == 1

    def test_shutdown_worker_by_id(self, idle_worker):
        _, manager = _make_manager(idle_worker)
        manager.shutdown_worker("dummy-01")
        assert idle_worker.shutdown_calls == 1

    def test_shutdown_worker_unknown_id_raises(self):
        _, manager = _make_manager()
        with pytest.raises(WorkerNotFoundError):
            manager.shutdown_worker("ghost")

    def test_shutdown_all_collects_errors_and_raises(self):
        from tests.conftest import DummyWorker, FailingShutdownWorker

        good = DummyWorker(worker_id="good")
        good.initialize()
        failing = FailingShutdownWorker()
        failing.initialize()
        _, manager = _make_manager(good, failing)

        with pytest.raises(WorkerShutdownError, match="did not shut down cleanly"):
            manager.shutdown_all()

    def test_shutdown_all_continues_past_failure(self):
        """All workers get a shutdown attempt even if one fails."""
        from tests.conftest import DummyWorker, FailingShutdownWorker

        good = DummyWorker(worker_id="good")
        good.initialize()
        failing = FailingShutdownWorker()
        failing.initialize()
        _, manager = _make_manager(failing, good)

        with pytest.raises(WorkerShutdownError):
            manager.shutdown_all()

        # The good worker must still have been shut down.
        assert good.shutdown_calls == 1

    def test_shutdown_all_empty_registry_ok(self):
        _, manager = _make_manager()
        # Should not raise on empty registry.
        manager.shutdown_all()

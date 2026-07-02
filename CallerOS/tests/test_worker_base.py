"""
Tests: BaseWorker lifecycle (workers/base_worker.py)
=====================================================
Covers:
  - Identity properties (id, name, description, version, capabilities).
  - Full happy-path lifecycle: CREATED → IDLE → RUNNING → IDLE → STOPPED.
  - Status transitions at each stage.
  - initialize() failure → FAILED status, WorkerInitializationError raised.
  - execute() failure → FAILED status, WorkerExecutionError raised.
  - shutdown() failure → FAILED status, WorkerShutdownError raised.
  - Illegal state transitions raise RuntimeError.
  - Cannot instantiate abstract class directly.
  - capabilities returns a defensive copy (mutation doesn't affect worker).
  - duration_ms is populated on WorkerResponse.
  - execute() increments _execute() exactly once per call.
"""

from __future__ import annotations

import pytest

from workers.base_worker import WorkerStatus
from workers.exceptions import (
    WorkerExecutionError,
    WorkerInitializationError,
    WorkerShutdownError,
)
from workers.models import WorkerRequest, WorkerResponse


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

class TestWorkerIdentity:
    def test_id(self, dummy_worker):
        assert dummy_worker.id == "dummy-01"

    def test_name(self, dummy_worker):
        assert dummy_worker.name == "Dummy Worker"

    def test_description(self, dummy_worker):
        assert dummy_worker.description == "A test worker."

    def test_version(self, dummy_worker):
        assert dummy_worker.version == "0.1.0"

    def test_capabilities(self, dummy_worker):
        assert dummy_worker.capabilities == ["test"]

    def test_capabilities_is_copy(self, dummy_worker):
        """Mutating the returned list must not affect the worker's own list."""
        caps = dummy_worker.capabilities
        caps.append("hacked")
        assert "hacked" not in dummy_worker.capabilities

    def test_initial_status_is_created(self, dummy_worker):
        assert dummy_worker.status is WorkerStatus.CREATED


# ---------------------------------------------------------------------------
# Happy-path lifecycle
# ---------------------------------------------------------------------------

class TestWorkerLifecycle:
    def test_initialize_transitions_to_idle(self, dummy_worker):
        dummy_worker.initialize()
        assert dummy_worker.status is WorkerStatus.IDLE

    def test_initialize_calls_hook(self, dummy_worker):
        dummy_worker.initialize()
        assert dummy_worker.init_calls == 1

    def test_execute_transitions_back_to_idle(self, idle_worker, make_request):
        idle_worker.execute(make_request())
        assert idle_worker.status is WorkerStatus.IDLE

    def test_execute_calls_hook(self, idle_worker, make_request):
        idle_worker.execute(make_request())
        assert idle_worker.exec_calls == 1

    def test_execute_returns_worker_response(self, idle_worker, make_request):
        response = idle_worker.execute(make_request())
        assert isinstance(response, WorkerResponse)

    def test_execute_response_success_true(self, idle_worker, make_request):
        response = idle_worker.execute(make_request())
        assert response.success is True

    def test_execute_response_request_id_matches(self, idle_worker, make_request):
        req = make_request()
        response = idle_worker.execute(req)
        assert response.request_id == req.request_id

    def test_execute_duration_ms_is_positive(self, idle_worker, make_request):
        response = idle_worker.execute(make_request())
        assert response.duration_ms >= 0.0

    def test_shutdown_transitions_to_stopped(self, idle_worker):
        idle_worker.shutdown()
        assert idle_worker.status is WorkerStatus.STOPPED

    def test_shutdown_calls_hook(self, idle_worker):
        idle_worker.shutdown()
        assert idle_worker.shutdown_calls == 1

    def test_full_lifecycle(self, dummy_worker, make_request):
        """End-to-end: CREATED → IDLE → (exec) → IDLE → STOPPED."""
        assert dummy_worker.status is WorkerStatus.CREATED
        dummy_worker.initialize()
        assert dummy_worker.status is WorkerStatus.IDLE
        dummy_worker.execute(make_request())
        assert dummy_worker.status is WorkerStatus.IDLE
        dummy_worker.shutdown()
        assert dummy_worker.status is WorkerStatus.STOPPED

    def test_multiple_executions(self, idle_worker, make_request):
        """Worker can execute multiple requests while remaining IDLE."""
        for _ in range(3):
            idle_worker.execute(make_request())
        assert idle_worker.exec_calls == 3
        assert idle_worker.status is WorkerStatus.IDLE


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------

class TestWorkerFailurePaths:
    def test_init_failure_sets_failed_status(self):
        from tests.conftest import FailingInitWorker
        w = FailingInitWorker()
        with pytest.raises(WorkerInitializationError):
            w.initialize()
        assert w.status is WorkerStatus.FAILED

    def test_init_failure_raises_initialization_error(self):
        from tests.conftest import FailingInitWorker
        w = FailingInitWorker()
        with pytest.raises(WorkerInitializationError, match="init boom"):
            w.initialize()

    def test_exec_failure_sets_failed_status(self):
        from tests.conftest import FailingExecWorker
        w = FailingExecWorker()
        w.initialize()
        req = WorkerRequest(worker_id="fail-exec", payload=None)
        with pytest.raises(WorkerExecutionError):
            w.execute(req)
        assert w.status is WorkerStatus.FAILED

    def test_exec_failure_raises_execution_error(self):
        from tests.conftest import FailingExecWorker
        w = FailingExecWorker()
        w.initialize()
        req = WorkerRequest(worker_id="fail-exec", payload=None)
        with pytest.raises(WorkerExecutionError, match="exec boom"):
            w.execute(req)

    def test_shutdown_failure_sets_failed_status(self):
        from tests.conftest import FailingShutdownWorker
        w = FailingShutdownWorker()
        w.initialize()
        with pytest.raises(WorkerShutdownError):
            w.shutdown()
        assert w.status is WorkerStatus.FAILED

    def test_shutdown_failure_raises_shutdown_error(self):
        from tests.conftest import FailingShutdownWorker
        w = FailingShutdownWorker()
        w.initialize()
        with pytest.raises(WorkerShutdownError, match="shutdown boom"):
            w.shutdown()


# ---------------------------------------------------------------------------
# Illegal state transitions
# ---------------------------------------------------------------------------

class TestIllegalTransitions:
    def test_execute_before_initialize_raises(self, dummy_worker, make_request):
        """Cannot execute a CREATED worker — must initialize first."""
        with pytest.raises(RuntimeError, match="invalid state transition"):
            dummy_worker.execute(make_request())

    def test_shutdown_before_initialize_raises(self, dummy_worker):
        """Cannot shut down a CREATED worker."""
        with pytest.raises(RuntimeError, match="invalid state transition"):
            dummy_worker.shutdown()

    def test_double_initialize_raises(self, idle_worker):
        """Calling initialize() on an IDLE worker is illegal."""
        with pytest.raises(RuntimeError, match="invalid state transition"):
            idle_worker.initialize()

    def test_shutdown_after_stopped_raises(self, idle_worker):
        """STOPPED is a terminal state."""
        idle_worker.shutdown()
        with pytest.raises(RuntimeError, match="invalid state transition"):
            idle_worker.shutdown()


# ---------------------------------------------------------------------------
# Abstractness
# ---------------------------------------------------------------------------

class TestAbstractness:
    def test_cannot_instantiate_base_worker_directly(self):
        import abc
        from workers.base_worker import BaseWorker

        with pytest.raises(TypeError):
            BaseWorker(  # type: ignore[abstract]
                worker_id="x",
                name="x",
                description="x",
                version="x",
                capabilities=[],
            )

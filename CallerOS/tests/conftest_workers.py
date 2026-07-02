"""
Shared fixtures and helpers for Stage 2 worker tests.

DummyWorker is the canonical concrete worker used across all test modules.
It does the minimum required to implement BaseWorker so tests stay focused
on the framework behaviour rather than the worker's own logic.

Separate variants (FailingInitWorker, FailingExecWorker, FailingShutdownWorker)
cover error path tests without polluting the happy-path dummy.
"""

from __future__ import annotations

import pytest

from workers.base_worker import BaseWorker
from workers.models import WorkerRequest, WorkerResponse


# ---------------------------------------------------------------------------
# Concrete worker implementations used in tests
# ---------------------------------------------------------------------------


class DummyWorker(BaseWorker):
    """
    Minimal concrete worker for testing happy paths.

    Tracks call counts so tests can assert that lifecycle methods ran.
    """

    def __init__(self, worker_id: str = "dummy-01", **kwargs) -> None:
        super().__init__(
            worker_id=worker_id,
            name=kwargs.get("name", "Dummy Worker"),
            description=kwargs.get("description", "A test worker."),
            version=kwargs.get("version", "0.1.0"),
            capabilities=kwargs.get("capabilities", ["test"]),
        )
        self.init_calls = 0
        self.exec_calls = 0
        self.shutdown_calls = 0

    def _initialize(self) -> None:
        self.init_calls += 1

    def _execute(self, request: WorkerRequest) -> WorkerResponse:
        self.exec_calls += 1
        return WorkerResponse(
            request_id=request.request_id,
            success=True,
            result=f"processed:{request.payload}",
        )

    def _shutdown(self) -> None:
        self.shutdown_calls += 1


class FailingInitWorker(BaseWorker):
    """Worker whose _initialize() always raises."""

    def __init__(self) -> None:
        super().__init__(
            worker_id="fail-init",
            name="Fail Init",
            description="Fails at init.",
            version="0.0.0",
            capabilities=[],
        )

    def _initialize(self) -> None:
        raise RuntimeError("init boom")

    def _execute(self, request: WorkerRequest) -> WorkerResponse:  # pragma: no cover
        return WorkerResponse(request_id=request.request_id, success=True)

    def _shutdown(self) -> None:  # pragma: no cover
        pass


class FailingExecWorker(BaseWorker):
    """Worker whose _execute() always raises."""

    def __init__(self) -> None:
        super().__init__(
            worker_id="fail-exec",
            name="Fail Exec",
            description="Fails at exec.",
            version="0.0.0",
            capabilities=[],
        )

    def _initialize(self) -> None:
        pass

    def _execute(self, request: WorkerRequest) -> WorkerResponse:
        raise RuntimeError("exec boom")

    def _shutdown(self) -> None:
        pass


class FailingShutdownWorker(BaseWorker):
    """Worker whose _shutdown() always raises."""

    def __init__(self) -> None:
        super().__init__(
            worker_id="fail-shutdown",
            name="Fail Shutdown",
            description="Fails at shutdown.",
            version="0.0.0",
            capabilities=[],
        )

    def _initialize(self) -> None:
        pass

    def _execute(self, request: WorkerRequest) -> WorkerResponse:  # pragma: no cover
        return WorkerResponse(request_id=request.request_id, success=True)

    def _shutdown(self) -> None:
        raise RuntimeError("shutdown boom")


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def dummy_worker() -> DummyWorker:
    """Return a fresh DummyWorker in CREATED state."""
    return DummyWorker()


@pytest.fixture()
def idle_worker() -> DummyWorker:
    """Return a DummyWorker that has already been initialized (IDLE state)."""
    worker = DummyWorker()
    worker.initialize()
    return worker


@pytest.fixture()
def make_request():
    """Factory fixture: returns a callable that builds a WorkerRequest."""

    def _make(payload: object = "test-payload", worker_id: str = "dummy-01") -> WorkerRequest:
        return WorkerRequest(worker_id=worker_id, payload=payload)

    return _make

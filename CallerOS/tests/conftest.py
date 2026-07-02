"""
pytest conftest — shared fixtures for CallerOS tests.
"""

import os
import pytest


# Environment variables that Settings reads from.
_CALLER_OS_ENV_KEYS = (
    "CALLER_OS_APP_NAME",
    "CALLER_OS_VERSION",
    "CALLER_OS_LOG_LEVEL",
    "CALLER_OS_LOG_DIR",
    "CALLER_OS_ENVIRONMENT",
)


@pytest.fixture()
def clean_env(monkeypatch):
    """
    Remove all CALLER_OS_* environment variables for the duration of a test.

    This ensures tests start from a known baseline and do not accidentally
    inherit values from the developer's shell environment.
    """
    for key in _CALLER_OS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


# ===========================================================================
# Stage 2 — Worker Framework fixtures
# ===========================================================================

from workers.base_worker import BaseWorker
from workers.models import WorkerRequest, WorkerResponse


class DummyWorker(BaseWorker):
    """
    Minimal concrete worker for testing happy paths.

    Tracks call counts so tests can assert lifecycle methods ran.
    """

    def __init__(self, worker_id: str = "dummy-01", **kwargs) -> None:
        super().__init__(
            worker_id=worker_id,
            name=kwargs.get("name", "Dummy Worker"),
            description=kwargs.get("description", "A test worker."),
            version=kwargs.get("version", "0.1.0"),
            capabilities=kwargs.get("capabilities", ["test"]),
        )
        self.init_calls: int = 0
        self.exec_calls: int = 0
        self.shutdown_calls: int = 0

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


@pytest.fixture()
def dummy_worker() -> DummyWorker:
    """Fresh DummyWorker in CREATED state."""
    return DummyWorker()


@pytest.fixture()
def idle_worker() -> DummyWorker:
    """DummyWorker that has been initialized (IDLE state)."""
    w = DummyWorker()
    w.initialize()
    return w


@pytest.fixture()
def make_request():
    """Factory: builds a WorkerRequest with sensible defaults."""

    def _make(
        payload: object = "test-payload",
        worker_id: str = "dummy-01",
    ) -> WorkerRequest:
        return WorkerRequest(worker_id=worker_id, payload=payload)

    return _make

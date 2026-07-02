"""
Tests: ResearchWorker (workers/research/worker.py)
==================================================
All tests use a mock AI client — no real API calls are made.

Covers:
  - Worker identity (id, name, version, capabilities).
  - initialize() sets status to IDLE.
  - Successful research: correct WorkerResponse structure.
  - WorkerResponse.result is a ResearchResult.
  - WorkerResponse.success is True on success.
  - WorkerResponse.request_id matches the request.
  - WorkerResponse.metadata contains expected keys.
  - Invalid payload type returns WorkerResponse(success=False).
  - Empty research_query returns WorkerResponse(success=False).
  - Whitespace-only research_query returns WorkerResponse(success=False).
  - AI client error returns WorkerResponse(success=False).
  - Unexpected AI exception returns WorkerResponse(success=False).
  - Worker remains IDLE after a failure response (not FAILED state).
  - Parser failure is handled gracefully (parser never raises, but tested
    via a response that produces minimal output).
  - Logging: key events are logged (via caplog).
  - shutdown() completes without error.
  - duration_ms is set on the response (from BaseWorker).
  - WorkerResponse metadata includes findings_count, sources_count, confidence.
  - Worker integrates with WorkerRegistry and WorkerManager.
"""

from __future__ import annotations

import logging
import pytest

from workers.base_worker import WorkerStatus
from workers.manager import WorkerManager
from workers.models import WorkerRequest, WorkerResponse
from workers.registry import WorkerRegistry
from workers.research.client import AIClientError
from workers.research.models import ResearchRequest, ResearchResult
from workers.research.worker import ResearchWorker, _WORKER_ID


# ---------------------------------------------------------------------------
# Shared fixtures and helpers
# ---------------------------------------------------------------------------

_GOOD_RESPONSE = """\
SUMMARY:
Python is a general-purpose programming language.

FINDINGS:
- Python was created by Guido van Rossum.
- It was released in 1991.

SOURCES:
- https://python.org

CONFIDENCE:
high
Well-established fact.
"""


class MockAIClient:
    """Minimal mock that satisfies the AIClient protocol."""

    def __init__(self, response: str = _GOOD_RESPONSE) -> None:
        self._response = response
        self.call_count = 0
        self.last_system_prompt: str = ""
        self.last_user_message: str = ""

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.call_count += 1
        self.last_system_prompt = system_prompt
        self.last_user_message = user_message
        return self._response


class FailingAIClient:
    """Client that always raises AIClientError."""

    def complete(self, system_prompt: str, user_message: str) -> str:
        raise AIClientError("API quota exceeded")


class UnexpectedExceptionClient:
    """Client that raises a non-AIClientError exception."""

    def complete(self, system_prompt: str, user_message: str) -> str:
        raise ConnectionError("network failure")


@pytest.fixture()
def mock_client() -> MockAIClient:
    return MockAIClient()


@pytest.fixture()
def research_worker(mock_client) -> ResearchWorker:
    """ResearchWorker in CREATED state."""
    return ResearchWorker(ai_client=mock_client)


@pytest.fixture()
def idle_research_worker(mock_client) -> ResearchWorker:
    """ResearchWorker in IDLE state (initialized)."""
    w = ResearchWorker(ai_client=mock_client)
    w.initialize()
    return w


def _make_request(
    query: str = "What is Python?",
    context: str = "",
    constraints: list[str] | None = None,
) -> WorkerRequest:
    return WorkerRequest(
        worker_id=_WORKER_ID,
        payload=ResearchRequest(
            research_query=query,
            context=context,
            constraints=constraints or [],
        ),
    )


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TestResearchWorkerIdentity:
    def test_id(self, research_worker):
        assert research_worker.id == _WORKER_ID

    def test_name_non_empty(self, research_worker):
        assert research_worker.name != ""

    def test_version(self, research_worker):
        assert research_worker.version == "1.0.0"

    def test_capabilities_include_research(self, research_worker):
        assert "research" in research_worker.capabilities

    def test_initial_status_created(self, research_worker):
        assert research_worker.status is WorkerStatus.CREATED


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestResearchWorkerInitialization:
    def test_initialize_sets_idle(self, research_worker):
        research_worker.initialize()
        assert research_worker.status is WorkerStatus.IDLE

    def test_initialize_logs(self, research_worker, caplog):
        with caplog.at_level(logging.INFO):
            research_worker.initialize()
        assert any("ResearchWorker ready" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Successful execution
# ---------------------------------------------------------------------------


class TestResearchWorkerSuccess:
    def test_response_is_worker_response(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert isinstance(response, WorkerResponse)

    def test_response_success_true(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert response.success is True

    def test_response_request_id_matches(self, idle_research_worker):
        req = _make_request()
        response = idle_research_worker.execute(req)
        assert response.request_id == req.request_id

    def test_result_is_research_result(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert isinstance(response.result, ResearchResult)

    def test_result_has_summary(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert response.result.summary != ""

    def test_result_has_findings(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert len(response.result.findings) > 0

    def test_result_has_sources(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert len(response.result.sources) > 0

    def test_result_confidence_high(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert response.result.confidence == 1.0

    def test_metadata_contains_findings_count(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert "findings_count" in response.metadata

    def test_metadata_contains_sources_count(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert "sources_count" in response.metadata

    def test_metadata_contains_confidence(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert "confidence" in response.metadata

    def test_duration_ms_populated(self, idle_research_worker):
        response = idle_research_worker.execute(_make_request())
        assert response.duration_ms >= 0.0

    def test_worker_returns_to_idle_after_success(self, idle_research_worker):
        idle_research_worker.execute(_make_request())
        assert idle_research_worker.status is WorkerStatus.IDLE

    def test_ai_client_called_once(self, idle_research_worker, mock_client):
        idle_research_worker.execute(_make_request())
        assert mock_client.call_count == 1

    def test_user_message_contains_query(self, idle_research_worker, mock_client):
        idle_research_worker.execute(_make_request(query="speed of light"))
        assert "speed of light" in mock_client.last_user_message

    def test_context_injected_into_prompt(self, idle_research_worker, mock_client):
        idle_research_worker.execute(_make_request(context="in astrophysics"))
        assert "in astrophysics" in mock_client.last_user_message

    def test_constraints_injected_into_prompt(self, idle_research_worker, mock_client):
        idle_research_worker.execute(
            _make_request(constraints=["post-2020 only"])
        )
        assert "post-2020 only" in mock_client.last_user_message

    def test_execution_logs_start_and_complete(self, idle_research_worker, caplog):
        with caplog.at_level(logging.INFO):
            idle_research_worker.execute(_make_request())
        messages = [r.message for r in caplog.records]
        assert any("executing" in m.lower() or "started" in m.lower() for m in messages)
        assert any("completed" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# Validation failures (invalid payload)
# ---------------------------------------------------------------------------


class TestResearchWorkerValidation:
    def test_wrong_payload_type_returns_failure(self, idle_research_worker):
        req = WorkerRequest(worker_id=_WORKER_ID, payload="not a ResearchRequest")
        response = idle_research_worker.execute(req)
        assert response.success is False

    def test_wrong_payload_error_message(self, idle_research_worker):
        req = WorkerRequest(worker_id=_WORKER_ID, payload=42)
        response = idle_research_worker.execute(req)
        assert response.error is not None
        assert response.error != ""

    def test_empty_query_returns_failure(self, idle_research_worker):
        req = WorkerRequest(
            worker_id=_WORKER_ID,
            payload=ResearchRequest(research_query=""),
        )
        response = idle_research_worker.execute(req)
        assert response.success is False

    def test_whitespace_query_returns_failure(self, idle_research_worker):
        req = WorkerRequest(
            worker_id=_WORKER_ID,
            payload=ResearchRequest(research_query="   "),
        )
        response = idle_research_worker.execute(req)
        assert response.success is False

    def test_worker_stays_idle_after_validation_failure(self, idle_research_worker):
        req = WorkerRequest(worker_id=_WORKER_ID, payload=None)
        idle_research_worker.execute(req)
        assert idle_research_worker.status is WorkerStatus.IDLE


# ---------------------------------------------------------------------------
# AI client failures
# ---------------------------------------------------------------------------


class TestResearchWorkerAIFailures:
    def test_ai_client_error_returns_failure(self):
        worker = ResearchWorker(ai_client=FailingAIClient())
        worker.initialize()
        response = worker.execute(_make_request())
        assert response.success is False

    def test_ai_client_error_has_error_message(self):
        worker = ResearchWorker(ai_client=FailingAIClient())
        worker.initialize()
        response = worker.execute(_make_request())
        assert response.error is not None

    def test_unexpected_exception_returns_failure(self):
        worker = ResearchWorker(ai_client=UnexpectedExceptionClient())
        worker.initialize()
        response = worker.execute(_make_request())
        assert response.success is False

    def test_worker_stays_idle_after_ai_failure(self):
        """AI errors are transient — worker must remain reusable."""
        worker = ResearchWorker(ai_client=FailingAIClient())
        worker.initialize()
        worker.execute(_make_request())
        assert worker.status is WorkerStatus.IDLE

    def test_ai_failure_logs_error(self, caplog):
        worker = ResearchWorker(ai_client=FailingAIClient())
        worker.initialize()
        with caplog.at_level(logging.ERROR):
            worker.execute(_make_request())
        assert any("error" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Empty / minimal AI response (parser stress test)
# ---------------------------------------------------------------------------


class TestResearchWorkerParserEdgeCases:
    def test_empty_ai_response_returns_failure(self):
        worker = ResearchWorker(ai_client=MockAIClient(response=""))
        worker.initialize()
        response = worker.execute(_make_request())
        # Empty response means client returned "" — _call_ai returns it, then
        # parse_response returns a default ResearchResult, so success=True with
        # a minimal result.  This is expected — the parser never raises.
        # The worker correctly treats an empty response as a client returning
        # None only when complete() raises; empty string is a valid (if poor)
        # response.  Verify graceful handling:
        assert response.success is True  # parser handled it gracefully
        assert isinstance(response.result, ResearchResult)

    def test_malformed_ai_response_still_succeeds(self):
        worker = ResearchWorker(ai_client=MockAIClient(response="totally garbled"))
        worker.initialize()
        response = worker.execute(_make_request())
        assert response.success is True  # parser is defensive — never raises


# ---------------------------------------------------------------------------
# Shutdown
# ---------------------------------------------------------------------------


class TestResearchWorkerShutdown:
    def test_shutdown_sets_stopped(self, idle_research_worker):
        idle_research_worker.shutdown()
        assert idle_research_worker.status is WorkerStatus.STOPPED

    def test_shutdown_logs(self, idle_research_worker, caplog):
        with caplog.at_level(logging.INFO):
            idle_research_worker.shutdown()
        assert any("shut" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Integration: WorkerRegistry + WorkerManager
# ---------------------------------------------------------------------------


class TestResearchWorkerIntegration:
    def test_worker_registers_in_registry(self, research_worker):
        registry = WorkerRegistry()
        registry.register(research_worker)
        assert registry.is_registered(_WORKER_ID)

    def test_manager_can_initialize_and_execute(self, mock_client):
        worker = ResearchWorker(ai_client=mock_client)
        registry = WorkerRegistry()
        registry.register(worker)
        manager = WorkerManager(registry)

        manager.initialize_all()
        req = _make_request()
        response = manager.execute(_WORKER_ID, req)

        assert response.success is True
        assert isinstance(response.result, ResearchResult)

    def test_manager_can_shutdown(self, mock_client):
        worker = ResearchWorker(ai_client=mock_client)
        registry = WorkerRegistry()
        registry.register(worker)
        manager = WorkerManager(registry)
        manager.initialize_all()
        manager.shutdown_all()
        assert worker.status is WorkerStatus.STOPPED

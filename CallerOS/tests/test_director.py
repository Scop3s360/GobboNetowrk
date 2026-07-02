"""
Tests: Director Agent (Stage 6)
===============================
Covers:
  - Routing decisions in HeuristicRouter (Research vs Developer).
  - WorkerDispatcher invocation of WorkerManager.
  - Director coordination loop (success, logging, and memory storage).
  - Director error handling (worker failures, dispatcher exceptions, memory failures).
"""

from __future__ import annotations

import logging
import pytest
from unittest.mock import MagicMock, patch

from director.director import Director
from director.dispatcher import WorkerDispatcher
from director.models import DirectorDecision, DirectorRequest, DirectorResponse
from director.router import HeuristicRouter
from memory.exceptions import DatabaseError, MemoryError
from memory.manager import MemoryManager
from memory.models import MemoryRecord, MemoryType
from workers.exceptions import WorkerExecutionError, WorkerNotFoundError
from workers.manager import WorkerManager
from workers.models import WorkerRequest, WorkerResponse


# ---------------------------------------------------------------------------
# Router Tests
# ---------------------------------------------------------------------------

class TestRouter:
    def test_routes_programming_query_to_developer(self) -> None:
        router = HeuristicRouter()
        
        req1 = DirectorRequest(query="Write some Python code to parse JSON")
        dec1 = router.route(req1)
        assert dec1.worker_id == "developer-worker-v1"
        assert "programming" in dec1.reason.lower()

        req2 = DirectorRequest(query="Help me debug this program bug")
        dec2 = router.route(req2)
        assert dec2.worker_id == "developer-worker-v1"

    def test_routes_general_query_to_research(self) -> None:
        router = HeuristicRouter()
        
        req = DirectorRequest(query="What is the capital of France?")
        dec = router.route(req)
        assert dec.worker_id == "research-worker-v1"
        assert "defaulting to research worker" in dec.reason.lower()

    def test_routes_unknown_to_research(self) -> None:
        router = HeuristicRouter()
        
        req = DirectorRequest(query="Hello world context")
        dec = router.route(req)
        assert dec.worker_id == "research-worker-v1"


# ---------------------------------------------------------------------------
# Dispatcher Tests
# ---------------------------------------------------------------------------

class TestDispatcher:
    def test_dispatcher_invokes_worker_manager_for_research(self) -> None:
        mock_manager = MagicMock(spec=WorkerManager)
        mock_response = WorkerResponse(request_id="req-123", success=True, result="Research findings")
        mock_manager.execute.return_value = mock_response

        dispatcher = WorkerDispatcher(mock_manager)
        decision = DirectorDecision(worker_id="research-worker-v1", reason="Test")
        request = DirectorRequest(query="Research Python history")

        response = dispatcher.dispatch(decision, request)
        
        # Verify research payload is wrapped in ResearchRequest
        assert mock_manager.execute.call_count == 1
        args, kwargs = mock_manager.execute.call_args
        assert args[0] == "research-worker-v1"
        worker_req: WorkerRequest = args[1]
        assert worker_req.worker_id == "research-worker-v1"
        
        from workers.research.models import ResearchRequest
        assert isinstance(worker_req.payload, ResearchRequest)
        assert worker_req.payload.research_query == "Research Python history"
        assert response is mock_response

    def test_dispatcher_invokes_worker_manager_fallback(self) -> None:
        mock_manager = MagicMock(spec=WorkerManager)
        mock_response = WorkerResponse(request_id="req-123", success=True, result="Code output")
        mock_manager.execute.return_value = mock_response

        dispatcher = WorkerDispatcher(mock_manager)
        decision = DirectorDecision(worker_id="developer-worker-v1", reason="Test")
        request = DirectorRequest(query="Write code")

        response = dispatcher.dispatch(decision, request)
        
        assert mock_manager.execute.call_count == 1
        args, kwargs = mock_manager.execute.call_args
        assert args[0] == "developer-worker-v1"
        worker_req: WorkerRequest = args[1]
        assert worker_req.payload == "Write code"


# ---------------------------------------------------------------------------
# Director Core Loop Tests
# ---------------------------------------------------------------------------

class TestDirector:
    def test_director_happy_path(self, caplog: pytest.LogCaptureFixture) -> None:
        mock_router = MagicMock()
        mock_router.route.return_value = DirectorDecision(worker_id="research-worker-v1", reason="RouteToResearch")

        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = WorkerResponse(
            request_id="req-1", success=True, result="Final findings content"
        )

        mock_memory = MagicMock(spec=MemoryManager)

        director = Director(mock_router, mock_dispatcher, mock_memory)
        request = DirectorRequest(query="Info query", metadata={"project": "GoblinProject"})

        with caplog.at_level(logging.INFO):
            response = director.execute(request)

        # 1. Assert response
        assert response.success is True
        assert response.result == "Final findings content"
        assert response.duration_ms >= 0.0

        # 2. Assert routing and dispatch calls
        mock_router.route.assert_called_once_with(request)
        mock_dispatcher.dispatch.assert_called_once()

        # 3. Assert MemoryManager storing conversation
        mock_memory.create_memory.assert_called_once()
        args, kwargs = mock_memory.create_memory.call_args
        mem_rec: MemoryRecord = args[0]
        assert mem_rec.type == MemoryType.CONVERSATION
        assert "Info query" in mem_rec.content
        assert "Final findings content" in mem_rec.content
        assert "research-worker-v1" in mem_rec.tags
        assert mem_rec.project == "GoblinProject"

        # 4. Assert Logging events occurred
        messages = [record.message for record in caplog.records]
        assert any("user request received" in msg for msg in messages)
        assert any("worker selected=research-worker-v1" in msg for msg in messages)
        assert any("dispatch started" in msg for msg in messages)
        assert any("dispatch completed" in msg for msg in messages)
        assert any("storing conversation to memory" in msg for msg in messages)

    def test_director_handles_worker_execution_failure(self) -> None:
        mock_router = MagicMock()
        mock_router.route.return_value = DirectorDecision(worker_id="research-worker-v1", reason="FailedExec")

        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = WorkerResponse(
            request_id="req-1", success=False, error="AI service timeout"
        )

        mock_memory = MagicMock()

        director = Director(mock_router, mock_dispatcher, mock_memory)
        request = DirectorRequest(query="Trigger timeout")
        response = director.execute(request)

        assert response.success is False
        assert "Worker failure" in response.error
        assert "AI service timeout" in response.error
        # Memory should not be saved on execution failure
        mock_memory.create_memory.assert_not_called()

    def test_director_handles_dispatcher_exception(self) -> None:
        mock_router = MagicMock()
        mock_router.route.return_value = DirectorDecision(worker_id="research-worker-v1", reason="Boom")

        mock_dispatcher = MagicMock()
        # Raise WorkerError subclass
        mock_dispatcher.dispatch.side_effect = WorkerExecutionError("Dispatcher crashed")

        director = Director(mock_router, mock_dispatcher)
        request = DirectorRequest(query="Boom query")
        response = director.execute(request)

        assert response.success is False
        assert "Worker dispatcher exception" in response.error

    def test_director_handles_memory_failure_gracefully(self) -> None:
        mock_router = MagicMock()
        mock_router.route.return_value = DirectorDecision(worker_id="research-worker-v1", reason="RouteOk")

        mock_dispatcher = MagicMock()
        mock_dispatcher.dispatch.return_value = WorkerResponse(
            request_id="req-1", success=True, result="Result is fine"
        )

        mock_memory = MagicMock(spec=MemoryManager)
        # Simulate memory lock error
        mock_memory.create_memory.side_effect = MemoryError("Database is locked")

        director = Director(mock_router, mock_dispatcher, mock_memory)
        request = DirectorRequest(query="Query with DB lock")
        
        # Execution should succeed even if memory storage raises an error
        response = director.execute(request)
        
        assert response.success is True
        assert response.result == "Result is fine"
        mock_memory.create_memory.assert_called_once()

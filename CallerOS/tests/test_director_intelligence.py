"""
Tests: Director Intelligence (Stage 12)
========================================
Covers:
  - Intent classification (Heuristic and LLM modes).
  - Execution planning & metadata-driven worker selection.
  - Context integration (ContextEngine invocation and context attachment to plan).
  - Multi-step sequential execution & placeholder resolution.
  - Result validation & Response assembly (Heuristic and LLM modes).
  - Pipeline logs capturing all stages.
"""

from __future__ import annotations
import logging
import pytest
from unittest.mock import MagicMock

from director.director import Director
from director.intent import IntentAnalyzer
from director.planner import ExecutionPlanner
from director.assembler import ResultAssembler
from director.models import DirectorRequest, DirectorResponse, ExecutionPlan, ExecutionStep
from context.engine import ContextEngine
from context.models import ContextPackage
from context.providers import ContextProvider
from memory.manager import MemoryManager
from memory.models import MemoryRecord, MemoryType
from workers.base_worker import BaseWorker
from workers.manager import WorkerManager
from workers.models import WorkerRequest, WorkerResponse
from workers.registry import WorkerRegistry
from workers.research.models import ResearchResult
from workers.developer.models import DeveloperResult
from workflow.state import WorkflowState


# ---------------------------------------------------------------------------
# Test Doubles
# ---------------------------------------------------------------------------

class MockAIClient:
    """Mock AI client that returns predefined responses."""
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.calls.append((system_prompt, user_message))
        if self.responses:
            return self.responses.pop(0)
        return "Default Mock Completion"


class IntelligenceDummyWorker(BaseWorker):
    """Worker that handles research or development payloads and returns mock structures."""
    def __init__(self, worker_id: str, capabilities: list[str], response_result: object) -> None:
        super().__init__(
            worker_id=worker_id,
            name=f"Dummy {worker_id}",
            description="Test worker.",
            version="1.0.0",
            capabilities=capabilities,
        )
        self.response_result = response_result
        self.executed_requests: list[WorkerRequest] = []

    def _initialize(self) -> None:
        pass

    def _execute(self, request: WorkerRequest) -> WorkerResponse:
        self.executed_requests.append(request)
        return WorkerResponse(
            request_id=request.request_id,
            success=True,
            result=self.response_result
        )

    def _shutdown(self) -> None:
        pass


class MockContextProvider(ContextProvider):
    def retrieve_context(self, project_name: str, query: str) -> ContextPackage | None:
        return ContextPackage(
            project_name=project_name,
            summary="Gravehold summary context",
            facts=["Fact A", "Fact B"]
        )


# ---------------------------------------------------------------------------
# Stage 12 Unit Tests
# ---------------------------------------------------------------------------

class TestIntentAnalyzer:
    def test_heuristic_classification(self) -> None:
        analyzer = IntentAnalyzer()
        
        # Test programming keywords
        intent, task = analyzer.analyze("Write a python script to parse logs")
        assert intent == "Programming"
        assert task == "Programming Task"
        
        # Test debugging keywords
        intent, task = analyzer.analyze("Help me debug this stacktrace error")
        assert intent == "Debugging"
        
        # Test review keywords
        intent, task = analyzer.analyze("Audit this PR")
        assert intent == "Review"
        
        # Test research keywords
        intent, task = analyzer.analyze("Explain how memory caching works")
        assert intent == "Research"
        
        # Test fallback
        intent, task = analyzer.analyze("Hello there, how are you?")
        assert intent == "General Conversation"

    def test_llm_classification_success(self) -> None:
        mock_client = MockAIClient(["Programming"])
        analyzer = IntentAnalyzer(mock_client)
        intent, task = analyzer.analyze("Query text")
        
        assert intent == "Programming"
        assert len(mock_client.calls) == 1
        assert "Classify the user's query" in mock_client.calls[0][0]

    def test_llm_classification_fallback_on_failure(self) -> None:
        mock_client = MockAIClient([]) # Empty list causes pop error, raising exception
        analyzer = IntentAnalyzer(mock_client)
        
        # Should fallback to heuristic on LLM exception
        intent, task = analyzer.analyze("Write code")
        assert intent == "Programming"


class TestExecutionPlanner:
    def test_heuristic_planning_programming_multi_step(self) -> None:
        registry = WorkerRegistry()
        registry.register(IntelligenceDummyWorker("research-worker-v1", ["research"], "findings"))
        registry.register(IntelligenceDummyWorker("developer-worker-v1", ["programming"], "code"))
        
        planner = ExecutionPlanner()
        # Query triggers programming intent with research keywords
        plan = planner.plan(
            query="Research save systems and write a parser class",
            intent="Programming",
            task_classification="Programming Task",
            registry=registry
        )
        
        assert len(plan.steps) == 2
        assert plan.steps[0].id == "step1"
        assert plan.steps[0].worker_id == "research-worker-v1"
        assert plan.steps[1].id == "step2"
        assert plan.steps[1].worker_id == "developer-worker-v1"
        assert "{step1}" in plan.steps[1].input_data

    def test_heuristic_planning_single_step_research(self) -> None:
        registry = WorkerRegistry()
        registry.register(IntelligenceDummyWorker("research-worker-v1", ["research"], "findings"))
        
        planner = ExecutionPlanner()
        plan = planner.plan(
            query="Explain recursion",
            intent="Research",
            task_classification="Research Task",
            registry=registry
        )
        
        assert len(plan.steps) == 1
        assert plan.steps[0].worker_id == "research-worker-v1"
        assert plan.steps[0].input_data == "Explain recursion"

    def test_llm_planning_success(self) -> None:
        registry = WorkerRegistry()
        registry.register(IntelligenceDummyWorker("research-worker-v1", ["research"], "findings"))
        registry.register(IntelligenceDummyWorker("developer-worker-v1", ["programming"], "code"))
        
        response_json = """
        {
          "intent": "Programming",
          "task_classification": "Custom Programming Task",
          "steps": [
            {
              "id": "s1",
              "worker_id": "research-worker-v1",
              "input_data": "research query",
              "description": "step 1 desc"
            },
            {
              "id": "s2",
              "worker_id": "developer-worker-v1",
              "input_data": "implement query with s1 output: {s1}",
              "description": "step 2 desc"
            }
          ]
        }
        """
        mock_client = MockAIClient([response_json])
        planner = ExecutionPlanner(mock_client)
        plan = planner.plan("Query", "Programming", "Programming Task", registry)
        
        assert plan.intent == "Programming"
        assert plan.task_classification == "Custom Programming Task"
        assert len(plan.steps) == 2
        assert plan.steps[0].id == "s1"
        assert plan.steps[0].worker_id == "research-worker-v1"
        assert plan.steps[1].id == "s2"
        assert plan.steps[1].worker_id == "developer-worker-v1"
        assert "{s1}" in plan.steps[1].input_data


class TestResultAssembler:
    def test_heuristic_single_result_formatting(self) -> None:
        assembler = ResultAssembler()
        
        # Test ResearchResult formatting
        res = ResearchResult(summary="A sum", findings=["F1", "F2"], sources=["S1"], confidence=0.9)
        output = assembler.assemble("Query", {"step1": res})
        
        assert "A sum" in output
        assert "Key Findings" in output
        assert "- F1" in output
        assert "Sources" in output
        assert "- S1" in output

        # Test DeveloperResult formatting
        dev_res = DeveloperResult(explanation="An explanation", code="public class Resource {}", notes="Best practices")
        output = assembler.assemble("Query", {"step1": dev_res})
        
        assert "An explanation" in output
        assert "public class Resource {}" in output
        assert "Implementation Notes" in output
        assert "Best practices" in output

    def test_llm_assembly_success(self) -> None:
        mock_client = MockAIClient(["Merged Output Response"])
        assembler = ResultAssembler(mock_client)
        
        output = assembler.assemble("Original Query", {"step1": "findings", "step2": "code"})
        assert output == "Merged Output Response"
        assert len(mock_client.calls) == 1
        assert "Combine the outputs" in mock_client.calls[0][0]
        assert "step1" in mock_client.calls[0][1]
        assert "step2" in mock_client.calls[0][1]


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------

class TestDirectorIntelligenceIntegration:
    def test_e2e_single_step_research_workflow(self, caplog: pytest.LogCaptureFixture) -> None:
        registry = WorkerRegistry()
        research_worker = IntelligenceDummyWorker(
            "research-worker-v1",
            ["research", "question-answering"],
            ResearchResult(summary="Summary of data", findings=["Finding A", "Finding B"], sources=["URL"], confidence=0.95)
        )
        registry.register(research_worker)
        
        manager = WorkerManager(registry)
        manager.initialize_all()
        
        # Mock Router & Dispatcher (unused by intelligent pipeline but required by constructor signature)
        mock_router = MagicMock()
        mock_dispatcher = MagicMock()
        mock_memory = MagicMock(spec=MemoryManager)
        
        director = Director(
            router=mock_router,
            dispatcher=mock_dispatcher,
            memory_manager=mock_memory,
            worker_manager=manager
        )
        
        request = DirectorRequest(query="Research the history of space flight")
        
        with caplog.at_level(logging.INFO):
            response = director.execute(request)
            
        assert response.success is True
        assert "Summary of data" in response.result
        assert "Key Findings" in response.result
        assert response.plan is not None
        assert response.plan.intent == "Research"
        assert len(response.plan.steps) == 1
        assert response.plan.steps[0].worker_id == "research-worker-v1"
        
        # Assert memory was saved
        mock_memory.create_memory.assert_called_once()
        saved_rec: MemoryRecord = mock_memory.create_memory.call_args[0][0]
        assert saved_rec.type == MemoryType.CONVERSATION
        assert "Director Response" in saved_rec.content
        assert "research-worker-v1" in saved_rec.tags

        # Verify pipeline logs
        log_messages = [record.message for record in caplog.records]
        assert any("Director: Intent detected: Research" in msg for msg in log_messages)
        assert any("Director: Task classification: Research Task" in msg for msg in log_messages)
        assert any("Director: Execution plan created" in msg for msg in log_messages)
        assert any("Director: Workers selected: ['research-worker-v1']" in msg for msg in log_messages)
        assert any("Director: Workers completed: ['step1']" in msg for msg in log_messages)
        assert any("Director: Result validation completed successfully." in msg for msg in log_messages)
        assert any("Director: Response assembly completed." in msg for msg in log_messages)
        assert any("Director: Execution duration:" in msg for msg in log_messages)

    def test_e2e_multi_step_programming_workflow(self) -> None:
        registry = WorkerRegistry()
        research_worker = IntelligenceDummyWorker("research-worker-v1", ["research"], "Research findings content")
        dev_worker = IntelligenceDummyWorker(
            "developer-worker-v1",
            ["programming"],
            DeveloperResult(explanation="Code explanation", code="class SaveSystem {}", notes="Notes")
        )
        registry.register(research_worker)
        registry.register(dev_worker)
        
        manager = WorkerManager(registry)
        manager.initialize_all()
        
        director = Director(
            router=MagicMock(),
            dispatcher=MagicMock(),
            worker_manager=manager
        )
        
        # Query triggers multi-step programming with research
        request = DirectorRequest(query="Research save systems and write code to implement one")
        response = director.execute(request)
        
        assert response.success is True
        assert "Code explanation" in response.result
        assert "class SaveSystem {}" in response.result
        
        assert response.plan is not None
        assert len(response.plan.steps) == 2
        assert response.plan.steps[0].worker_id == "research-worker-v1"
        assert response.plan.steps[1].worker_id == "developer-worker-v1"
        
        # Verify inputs and variable resolution
        assert dev_worker.executed_requests[0].payload == "Research findings content"

    def test_e2e_context_integration(self, caplog: pytest.LogCaptureFixture) -> None:
        registry = WorkerRegistry()
        research_worker = IntelligenceDummyWorker("research-worker-v1", ["research"], "Research response")
        registry.register(research_worker)
        
        manager = WorkerManager(registry)
        manager.initialize_all()
        
        # Context engine setup
        context_engine = ContextEngine()
        context_engine.register_provider(MockContextProvider())
        
        director = Director(
            router=MagicMock(),
            dispatcher=MagicMock(),
            worker_manager=manager,
            context_engine=context_engine
        )
        
        # Gravehold keywords triggers active project context retrieval
        request = DirectorRequest(query="Let's build Gravehold resource manager rules")
        
        with caplog.at_level(logging.INFO):
            response = director.execute(request)
            
        assert response.success is True
        assert response.plan.context_block != ""
        assert "ACTIVE PROJECT CONTEXT: GRAVEHOLD" in response.plan.context_block
        assert "Gravehold summary context" in response.plan.context_block
        
        # Verify first step query had context prepended
        assert research_worker.executed_requests[0].payload.research_query.startswith(response.plan.context_block)
        
        log_messages = [record.message for record in caplog.records]
        assert any("Director: Detected project 'Gravehold'" in msg for msg in log_messages)
        assert any("Director: Context attached to execution plan." in msg for msg in log_messages)

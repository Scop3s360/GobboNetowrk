from __future__ import annotations

import pytest
from datetime import datetime, timezone
from context.models import ContextPackage
from context.providers import MemoryContextProvider
from context.engine import ContextEngine
from memory.manager import MemoryManager
from memory.models import MemoryRecord, MemoryType
from memory.search import MemorySearchQuery
from workers.models import WorkerRequest, WorkerResponse
from director.dispatcher import WorkerDispatcher
from director.models import DirectorDecision, DirectorRequest
from workers.manager import WorkerManager
from workers.registry import WorkerRegistry
from tests.conftest import DummyWorker

class MockMemoryRepo:
    def __init__(self) -> None:
        self.memories: list[MemoryRecord] = []

    def create_memory(self, record: MemoryRecord) -> None:
        self.memories.append(record)

    def search_memory(self, query: MemorySearchQuery) -> list[MemoryRecord]:
        results = self.memories
        if query.project:
            results = [r for r in results if r.project == query.project]
        return results

    def list_memories(self) -> list[MemoryRecord]:
        return self.memories

@pytest.fixture
def memory_manager() -> MemoryManager:
    repo = MockMemoryRepo()
    mgr = MemoryManager(repo)
    # Seed mock records
    mgr.create_memory(MemoryRecord(
        type=MemoryType.PROJECT,
        project="Gravehold",
        source="test",
        importance=10,
        tags=["summary", "overview"],
        content="Gravehold overview context."
    ))
    mgr.create_memory(MemoryRecord(
        type=MemoryType.PROJECT,
        project="Gravehold",
        source="test",
        importance=8,
        tags=["rules", "design"],
        content="Gravehold uses base class GraveholdResource."
    ))
    return mgr

class TestContextEngine:
    def test_project_detection(self):
        engine = ContextEngine()
        assert engine.detect_project("Let's build a resource for Gravehold") == "Gravehold"
        assert engine.detect_project("How is CallerOS doing?") == "CallerOS"
        assert engine.detect_project("What about GoblinOS?") == "GoblinOS"
        assert engine.detect_project("Some generic query") is None

    def test_project_detection_from_history(self):
        engine = ContextEngine()
        assert engine.detect_project("What are the resource system rules?", ["We are working on Gravehold"]) == "Gravehold"

    def test_memory_context_retrieval_and_ranking(self, memory_manager):
        provider = MemoryContextProvider(memory_manager)
        pkg = provider.retrieve_context("Gravehold", "resource rules")
        
        assert pkg is not None
        assert pkg.project_name == "Gravehold"
        assert pkg.summary == "Gravehold overview context."
        assert any("GraveholdResource" in f for f in pkg.facts)

    def test_context_engine_build_context(self, memory_manager):
        engine = ContextEngine()
        engine.register_provider(MemoryContextProvider(memory_manager))
        context_str = engine.build_context("Gravehold", "resource rules")
        
        assert "ACTIVE PROJECT CONTEXT: GRAVEHOLD" in context_str
        assert "Gravehold overview" in context_str
        assert "GraveholdResource" in context_str

    def test_dispatcher_context_injection(self, memory_manager):
        # Set up registry & manager with dummy worker
        registry = WorkerRegistry()
        dummy = DummyWorker("research-worker-v1")
        registry.register(dummy)
        worker_manager = WorkerManager(registry)
        worker_manager.initialize_all()

        # Set up ContextEngine
        engine = ContextEngine()
        engine.register_provider(MemoryContextProvider(memory_manager))

        # Set up Dispatcher with context engine
        dispatcher = WorkerDispatcher(worker_manager, context_engine=engine)
        
        decision = DirectorDecision(worker_id="research-worker-v1", reason="test")
        req = DirectorRequest(query="Design a new resource for Gravehold.")
        
        # Verify that during dispatching, context was injected before executing worker
        res = dispatcher.dispatch(decision, req)
        assert res.success is True
        # Since DummyWorker returns processed:<payload>, we can check the payload!
        processed_payload = res.result
        assert "ACTIVE PROJECT CONTEXT: GRAVEHOLD" in processed_payload
        assert "Gravehold overview" in processed_payload
        assert "GraveholdResource" in processed_payload
        assert "Design a new resource for Gravehold." in processed_payload

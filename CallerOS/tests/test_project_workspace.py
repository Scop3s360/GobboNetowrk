import os
import shutil
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from database.manager import DatabaseManager
from project.models import Project
from project.workspace import ProjectWorkspace
from project.manager import ProjectManager
from context.engine import ContextEngine
from director.director import Director
from director.models import DirectorRequest
from director.router import HeuristicRouter
from director.dispatcher import WorkerDispatcher
from workers.manager import WorkerManager
from workers.registry import WorkerRegistry
from workers.base_worker import BaseWorker, WorkerRequest, WorkerResponse

class WorkspaceDummyWorker(BaseWorker):
    def __init__(self, id: str, capabilities: list[str], reply: str) -> None:
        super().__init__(id, name=f"Dummy {id}", description="Dummy worker", version="1.0.0", capabilities=capabilities)
        self.reply = reply
        self.executed_requests = []

    def _initialize(self) -> None:
        pass

    def _shutdown(self) -> None:
        pass

    def _execute(self, request: WorkerRequest) -> WorkerResponse:
        self.executed_requests.append(request)
        if self.id == "research-worker-v1":
            from workers.research.models import ResearchResult
            res = ResearchResult(summary=self.reply, findings=["Finding 1"], sources=["Source 1"], confidence=0.9, raw_response="raw")
        else:
            from workers.developer.models import DeveloperResult
            res = DeveloperResult(explanation=self.reply, code="class Dummy {}", notes="notes")
        return WorkerResponse(request_id=request.request_id, success=True, result=res)

@pytest.fixture
def temp_workspaces_base(tmp_path: Path) -> Path:
    base = tmp_path / "workspaces"
    base.mkdir()
    return base

@pytest.fixture
def central_db() -> DatabaseManager:
    # Use in-memory or temporary sqlite database
    db = DatabaseManager(":memory:")
    return db

class TestProjectWorkspaceSystem:
    def test_project_crud_and_persistence(self, central_db, temp_workspaces_base):
        manager = ProjectManager(central_db, temp_workspaces_base)
        
        # Create
        proj = manager.create_project("Alpha", "First project", "Game", ["u5", "dots"])
        assert proj.name == "Alpha"
        assert proj.description == "First project"
        assert proj.type == "Game"
        assert "dots" in proj.tags
        
        # List
        projects = manager.list_projects()
        assert len(projects) == 1
        assert projects[0].id == proj.id
        
        # Get
        retrieved = manager.get_project(proj.id)
        assert retrieved is not None
        assert retrieved.name == "Alpha"
        
        # Switch / Open
        manager.open_project(proj.id)
        assert manager.active_project is not None
        assert manager.active_project.id == proj.id
        assert manager.active_workspace is not None
        
        # Check folders created
        ws_dir = temp_workspaces_base / proj.id
        assert ws_dir.is_dir()
        assert (ws_dir / "documents").is_dir()
        assert (ws_dir / "notes").is_dir()
        assert (ws_dir / "workspace.db").is_file()
        
        # Delete
        manager.delete_project(proj.id)
        assert manager.active_project is None
        assert not ws_dir.is_dir()
        assert len(manager.list_projects()) == 0

    def test_document_import_and_indexing(self, central_db, temp_workspaces_base, tmp_path):
        manager = ProjectManager(central_db, temp_workspaces_base)
        proj = manager.create_project("Beta", "Test import", "Software")
        manager.open_project(proj.id)
        
        workspace = manager.active_workspace
        
        # Create a test markdown file
        doc_file = tmp_path / "spec.md"
        doc_file.write_text(
            "# Architecture\n"
            "This is the core architecture specification.\n"
            "## Constraints\n"
            "Keep the memory usage below 256MB.\n",
            encoding="utf-8"
        )
        
        res = workspace.import_document(doc_file)
        assert res["name"] == "spec.md"
        assert res["chunks_count"] == 2
        
        # Verify file copied
        imported_path = workspace.docs_dir / "spec.md"
        assert imported_path.is_file()
        
        # Verify indexed in local workspace DB documents
        cursor = workspace.db.execute("SELECT name, content FROM documents")
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "spec.md"
        assert "# Architecture" in row["content"]
        
        # Verify FTS / keyword search index
        search_res = workspace.search_knowledge_index("memory")
        assert len(search_res) > 0
        assert search_res[0]["title"] == "Constraints"
        assert "256MB" in search_res[0]["content"]

    def test_context_engine_search_and_ranking(self, central_db, temp_workspaces_base, tmp_path):
        manager = ProjectManager(central_db, temp_workspaces_base)
        proj = manager.create_project("Gravehold", "Save Gravehold", "Game")
        manager.open_project(proj.id)
        
        workspace = manager.active_workspace
        
        # Seed memory
        from memory.models import MemoryRecord, MemoryType
        mem = MemoryRecord(
            type=MemoryType.PROJECT,
            content="Gravehold rules the skies.",
            source="seeder",
            project=proj.id,
            tags=["rules", "skies"],
            importance=8
        )
        workspace.memory_repo.create_memory(mem)
        
        # Seed doc
        doc_file = tmp_path / "disaster.txt"
        doc_file.write_text("Instability disasters strike when shield drops.", encoding="utf-8")
        workspace.import_document(doc_file)
        
        # Context Engine setup
        context_engine = ContextEngine(project_manager=manager)
        
        # Build context
        context_block = context_engine.build_context(proj.name, "disaster rules")
        
        assert "ACTIVE PROJECT CONTEXT: Gravehold" in context_block
        assert "Gravehold rules the skies" in context_block
        assert "disasters strike" in context_block

    def test_director_context_integration(self, central_db, temp_workspaces_base, tmp_path):
        # 1. Setup workers & manager
        registry = WorkerRegistry()
        research_worker = WorkspaceDummyWorker("research-worker-v1", ["research"], "Research findings")
        registry.register(research_worker)
        
        dev_worker = WorkspaceDummyWorker("developer-worker-v1", ["programming"], "Developer explanation")
        registry.register(dev_worker)
        
        worker_manager = WorkerManager(registry)
        worker_manager.initialize_all()
        
        # 2. Setup project manager
        project_manager = ProjectManager(central_db, temp_workspaces_base)
        proj = project_manager.create_project("Unity ECS", "DOTS coding", "Software")
        project_manager.open_project(proj.id)
        
        # Seed doc in project workspace
        doc_file = tmp_path / "ecs.md"
        doc_file.write_text("# DOTS Rules\nAlways use IComponentData for structs.\n", encoding="utf-8")
        project_manager.active_workspace.import_document(doc_file)
        
        # 3. Setup Context Engine & Director
        context_engine = ContextEngine(project_manager=project_manager)
        router = HeuristicRouter()
        dispatcher = WorkerDispatcher(worker_manager, context_engine=context_engine)
        director = Director(router, dispatcher, project_manager=project_manager)
        
        # Execute query
        request = DirectorRequest(query="Explain how to implement IComponentData")
        res = director.execute(request)
        
        assert res.success is True
        assert res.plan is not None
        assert res.plan.context_block != ""
        assert "Always use IComponentData" in res.plan.context_block
        
        # Verify first step received query with context prepended
        assert len(research_worker.executed_requests) == 1
        query_sent = research_worker.executed_requests[0].payload.research_query
        assert query_sent.startswith(res.plan.context_block)
        assert "Explain how to implement" in query_sent

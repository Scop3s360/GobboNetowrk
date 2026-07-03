import os
import shutil
import subprocess
import pytest
from pathlib import Path

from database.manager import DatabaseManager
from project.workspace import ProjectWorkspace
from project.index_service import CodeIndexService
from project.patch_system import PatchManager, FilePatch
from project.git_service import GitService
from context.engine import ContextEngine
from project.manager import ProjectManager

@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws_base = tmp_path / "workspaces"
    ws_base.mkdir()
    return ws_base

@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    return src

class TestCodeIndexService:
    def test_python_and_csharp_parsing(self, temp_workspace, source_dir):
        # Create ProjectWorkspace
        ws = ProjectWorkspace("proj_123", temp_workspace)
        indexer = CodeIndexService(ws)
        
        # 1. Create a dummy python file
        py_file = source_dir / "calculator.py"
        py_file.write_text(
            "import math\n"
            "from decimal import Decimal\n\n"
            "class ScientificCalculator:\n"
            "    def add(self, a, b):\n"
            "        return a + b\n\n"
            "    async def power(self, base, exp):\n"
            "        return math.pow(base, exp)\n",
            encoding="utf-8"
        )
        
        # 2. Create a dummy C# file
        cs_file = source_dir / "Manager.cs"
        cs_file.write_text(
            "using System;\n"
            "using System.Collections.Generic;\n\n"
            "namespace Game\n"
            "{\n"
            "    public class PlayerManager\n"
            "    { \n"
            "        public void Initialize()\n"
            "        {\n"
            "            Console.WriteLine(\"Init\");\n"
            "        }\n"
            "    }\n"
            "}\n",
            encoding="utf-8"
        )
        
        # Run scan
        res = indexer.index_project(source_dir)
        assert res["total_files"] == 2
        assert res["total_symbols"] > 0
        
        # Search Python symbols
        py_symbols = indexer.search_symbols("ScientificCalculator")
        assert len(py_symbols) == 1
        assert py_symbols[0]["symbol_type"] == "Class"
        assert py_symbols[0]["file_path"] == "calculator.py"
        
        # Search Python methods
        add_symbols = indexer.search_symbols("add")
        assert len(add_symbols) == 1
        assert add_symbols[0]["symbol_type"] == "Method"
        assert add_symbols[0]["parent_class"] == "ScientificCalculator"
        
        # Search C# symbols
        cs_symbols = indexer.search_symbols("PlayerManager")
        assert len(cs_symbols) == 1
        assert cs_symbols[0]["symbol_type"] == "Class"
        assert cs_symbols[0]["file_path"] == "Manager.cs"

class TestPatchManagerAndBackups:
    def test_create_apply_and_undo_patches(self, temp_workspace, source_dir):
        # Create dummy file to modify
        file_to_patch = source_dir / "config.txt"
        file_to_patch.write_text("DEBUG=False\nPORT=8080", encoding="utf-8")
        
        patch_m = PatchManager(temp_workspace / "proj_123", source_dir)
        
        # Staged patch
        patch = patch_m.create_patch("config.txt", "DEBUG=True\nPORT=8080", "Enable debug logging")
        assert patch.target_file == "config.txt"
        assert patch.original_content == "DEBUG=False\nPORT=8080"
        assert patch.patched_content == "DEBUG=True\nPORT=8080"
        
        # Apply patch (should create backup)
        patch_m.apply_patch("config.txt")
        assert file_to_patch.read_text(encoding="utf-8") == "DEBUG=True\nPORT=8080"
        
        # Check backups exist
        assert len(patch_m._backup_history) == 1
        backup = patch_m._backup_history[0]
        assert backup["operation"] == "modify"
        assert Path(backup["backup_path"]).is_file()
        
        # Undo operation
        undo_res = patch_m.undo_last_operation()
        assert undo_res["success"] is True
        # Content restored
        assert file_to_patch.read_text(encoding="utf-8") == "DEBUG=False\nPORT=8080"
        # Backup file cleaned up
        assert not Path(backup["backup_path"]).exists()

    def test_file_create_and_delete_undo(self, temp_workspace, source_dir):
        patch_m = PatchManager(temp_workspace / "proj_123", source_dir)
        
        # 1. Create a file
        new_file = source_dir / "new.txt"
        patch_m.backup_file("new.txt", "create")
        new_file.write_text("Fresh content", encoding="utf-8")
        
        # Undo creation (deletes file)
        patch_m.undo_last_operation()
        assert not new_file.exists()
        
        # 2. Delete an existing file
        del_file = source_dir / "del.txt"
        del_file.write_text("Good bye", encoding="utf-8")
        
        patch_m.backup_file("del.txt", "delete")
        del_file.unlink()
        
        # Undo deletion (restores file)
        patch_m.undo_last_operation()
        assert del_file.is_file()
        assert del_file.read_text(encoding="utf-8") == "Good bye"

class TestGitService:
    def test_git_operations(self, tmp_path):
        # Initialize a temporary git repository
        git_dir = tmp_path / "repo"
        git_dir.mkdir()
        
        git_s = GitService(git_dir)
        
        # Should not be a git repo initially
        assert git_s.is_git_repository() is False
        
        # Run git init
        subprocess.run(["git", "init"], cwd=str(git_dir), check=True, capture_output=True)
        assert git_s.is_git_repository() is True
        
        # Create a test file
        test_file = git_dir / "test.txt"
        test_file.write_text("Hello Git", encoding="utf-8")
        
        # Get status (should be untracked)
        status = git_s.get_status()
        assert "test.txt" in status["untracked"]
        
        # Stage the file
        git_s.stage_file("test.txt")
        status = git_s.get_status()
        assert "test.txt" in status["staged"]
        assert "test.txt" not in status["untracked"]
        
        # Commit staged files
        commit_out = git_s.commit("Initial commit")
        assert "Initial commit" in commit_out
        
        # Verify clean status
        status = git_s.get_status()
        assert len(status["staged"]) == 0
        assert len(status["unstaged"]) == 0
        assert len(status["untracked"]) == 0

class TestContextEngineSymbolRanking:
    def test_engine_scores_code_symbols(self, temp_workspace, source_dir):
        # Create managers and register project
        central_db = DatabaseManager(":memory:")
        central_db.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                type TEXT NOT NULL,
                tags TEXT NOT NULL,
                source_dir TEXT,
                created_at TEXT NOT NULL,
                last_opened_at TEXT NOT NULL
            );
            """
        )
        
        manager = ProjectManager(central_db, temp_workspace)
        proj = manager.create_project("AlphaGame", "Unity dots project", "Game", ["unity"], source_dir)
        manager.open_project(proj.id)
        
        # Index a class in workspace
        ws = manager.active_workspace
        indexer = CodeIndexService(ws)
        
        cs_file = source_dir / "Player.cs"
        cs_file.write_text(
            "public class PlayerController\n"
            "{\n"
            "    public void Respawn()\n"
            "    {\n"
            "    }\n"
            "}",
            encoding="utf-8"
        )
        indexer.index_project(source_dir)
        
        # Context Engine build context
        engine = ContextEngine(project_manager=manager)
        ctx = engine.build_context("AlphaGame", "Respawn PlayerController")
        
        assert "PlayerController" in ctx
        assert "Respawn" in ctx
        assert "Code Symbol" in ctx


def test_user_data_migration_and_persistent_paths(tmp_path):
    from config.settings import get_user_data_dir, migrate_user_data
    
    # 1. Verify get_user_data_dir returns a path
    data_dir = get_user_data_dir()
    assert data_dir is not None
    assert isinstance(data_dir, Path)
    
    # 2. Mock old directory layout
    old_base = tmp_path / "old_release"
    new_base = tmp_path / "new_userdata"
    
    config_dir = old_base / "config"
    config_dir.mkdir(parents=True)
    old_env = config_dir / ".env"
    old_env.write_text("OPENAI_API_KEY=sk-test-key-1234", encoding="utf-8")
    
    logs_dir = old_base / "logs"
    logs_dir.mkdir(parents=True)
    old_db = logs_dir / "caller_os_memory.db"
    old_db.write_text("dummy database content", encoding="utf-8")
    
    ws_dir = old_base / "workspaces"
    ws_dir.mkdir(parents=True)
    some_doc = ws_dir / "Gravehold" / "colony_notes.txt"
    some_doc.parent.mkdir(parents=True, exist_ok=True)
    some_doc.write_text("instability rules summary", encoding="utf-8")
    
    # Run migration
    migrate_user_data(old_base, new_base)
    
    # Verify new layout contains copies
    assert (new_base / ".env").is_file()
    assert (new_base / ".env").read_text(encoding="utf-8") == "OPENAI_API_KEY=sk-test-key-1234"
    assert (new_base / "logs" / "caller_os_memory.db").is_file()
    assert (new_base / "workspaces" / "Gravehold" / "colony_notes.txt").is_file()
    assert (new_base / "workspaces" / "Gravehold" / "colony_notes.txt").read_text(encoding="utf-8") == "instability rules summary"

"""
UI API Backend Server
====================
Exposes a lightweight, dependency-free HTTP API server to communicate with the
React + Electron frontend. Handles chat queries, logs, and settings configuration.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Adjust path to find core packages
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Settings, get_settings, reload_settings
from core.application import Application
from director.director import Director
from director.dispatcher import WorkerDispatcher
from director.models import DirectorRequest
from director.router import HeuristicRouter
from database.manager import DatabaseManager
from memory.manager import MemoryManager
from memory.repository import SQLiteMemoryRepository
from workers.manager import WorkerManager
from workers.registry import WorkerRegistry
from workers.research.client import AIClient, AIClientError, OpenAIClient
from workers.research.worker import ResearchWorker

log = logging.getLogger(__name__)

def get_exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

def get_assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent

def get_env_path() -> Path:
    exe_dir = get_exe_dir()
    if (exe_dir / "config").is_dir():
        return exe_dir / "config" / ".env"
    return exe_dir / ".env"

# Global UI state monitored via logging interceptor
_ui_status = {
    "active_agent": "Director",
    "workflow_status": "IDLE",
    "current_model": "gpt-4o-mini",
    "memory_status": "CONNECTED",
    "tool_activity": "NONE",
}


class UIStatusLogHandler(logging.Handler):
    """
    Custom log handler that intercepts logs to extract workflow state updates
    for the status bar, avoiding any modification of existing backend codes.
    """

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "user request received" in msg:
            _ui_status["workflow_status"] = "RUNNING"
            _ui_status["active_agent"] = "Director"
        elif "worker selected=" in msg:
            if "research-worker" in msg:
                _ui_status["active_agent"] = "Research Worker"
            elif "developer-worker" in msg:
                _ui_status["active_agent"] = "Developer Worker"
        elif "Tool execution started" in msg:
            # Extract tool name from e.g. "tool=read_file"
            if "tool=" in msg:
                tool_name = msg.split("tool=")[1].split(",")[0].strip()
                _ui_status["tool_activity"] = tool_name
        elif "Tool execution finished" in msg:
            _ui_status["tool_activity"] = "NONE"
        elif "dispatch completed" in msg or "finished" in msg:
            _ui_status["workflow_status"] = "COMPLETED"
            _ui_status["active_agent"] = "Director"
        elif "failed" in msg or "failure" in msg:
            _ui_status["workflow_status"] = "FAILED"
            _ui_status["active_agent"] = "Director"


# Setup backend services
app = Application()
app.startup()

# Sync UI model status with loaded settings
_ui_status["current_model"] = app.settings.openai_model

# Add log interceptor
logging.getLogger().addHandler(UIStatusLogHandler())

# Build registry & manager
registry = WorkerRegistry()
ai_client = OpenAIClient()
research_worker = ResearchWorker(ai_client=ai_client)
registry.register(research_worker)

# In Stage 6, HeuristicRouter targets "developer-worker-v1" for code requests.
from workers.developer.worker import DeveloperWorker
dev_worker = DeveloperWorker(ai_client=ai_client)
registry.register(dev_worker)

# Initialize all workers
worker_manager = WorkerManager(registry)
worker_manager.initialize_all()

# --- Startup Instrument Logs ---
try:
    from config.settings import get_base_dir, get_settings
    env_path = (get_base_dir() / ".env").resolve()
    env_exists = env_path.is_file()
    
    # Check if dotenv loaded successfully by inspecting some environment variables
    # (dotenv loads them into os.environ)
    dotenv_loaded = "OPENAI_API_KEY" in os.environ
    
    raw_env_key = os.environ.get("OPENAI_API_KEY", "")
    masked_env_key = f"{raw_env_key[:6]}...{raw_env_key[-4:]}" if len(raw_env_key) > 10 else ("***" if raw_env_key else "EMPTY")
    
    settings = get_settings()
    raw_settings_key = settings.openai_api_key
    masked_settings_key = f"{raw_settings_key[:6]}...{raw_settings_key[-4:]}" if len(raw_settings_key) > 10 else ("***" if raw_settings_key else "EMPTY")
    
    # Check if OpenAIClient gets a populated key at runtime (or if we can get its resolved key)
    # Since OpenAIClient resolves settings at runtime from get_settings(), let's check settings key
    client_has_key = bool(settings.openai_api_key)
    
    # Whether ResearchWorker uses the shared OpenAIClient instance
    worker_using_shared_client = (research_worker._ai_client is ai_client)

    log.info("=== STARTUP INSTRUMENTATION ===")
    log.info("1. Absolute path of .env file: %s", env_path)
    log.info("2. File exists: %s", env_exists)
    log.info("3. Dotenv loaded successfully (key in env): %s", dotenv_loaded)
    log.info("4. os.environ OPENAI_API_KEY: %s", masked_env_key)
    log.info("5. Settings.openai_api_key: %s", masked_settings_key)
    log.info("6. OpenAIClient receives populated key: %s", client_has_key)
    log.info("7. Research Worker using shared client: %s", worker_using_shared_client)
    log.info("=================================")
except Exception as e:
    log.error("Failed to log startup instrumentation: %s", e)

# Memory manager
db_mgr = DatabaseManager(get_exe_dir() / "logs" / "caller_os_memory.db")
repo = SQLiteMemoryRepository(db_mgr)
memory_mgr = MemoryManager(repo)

def seed_project_memories(mgr: MemoryManager) -> None:
    from memory.search import MemorySearchQuery
    from memory.models import MemoryRecord, MemoryType
    q = MemorySearchQuery(project="Gravehold")
    try:
        existing = mgr.search_memory(q)
        if existing:
            log.info("Database already seeded with Gravehold memories.")
            return
        
        log.info("Seeding database with Gravehold project memories...")
        memories = [
            MemoryRecord(
                type=MemoryType.PROJECT,
                project="Gravehold",
                source="seeder",
                importance=10,
                tags=["summary", "overview", "design"],
                content="Gravehold is a dark fantasy turn-based tactical strategy game. It features a unique resource management system where players manage instability, aether, and scrap to build and defend their underground colony."
            ),
            MemoryRecord(
                type=MemoryType.PROJECT,
                project="Gravehold",
                source="seeder",
                importance=9,
                tags=["rules", "resource", "design", "architecture"],
                content="The Gravehold Resource System is governed by the following rules:\n"
                        "1. All resources derive from a base class 'GraveholdResource'.\n"
                        "2. The player's main resources are 'Aether' (magic/energy) and 'Scrap' (material for construction).\n"
                        "3. Resources are registered with and managed by the 'ResourceManager' facade class.\n"
                        "4. Instability acts as a negative resource that triggers colony disasters if it exceeds 100%."
            ),
            MemoryRecord(
                type=MemoryType.PROJECT,
                project="Gravehold",
                source="seeder",
                importance=8,
                tags=["rules", "instability", "design"],
                content="Instability is generated by taking damage or building unstable structures. When instability rises, it triggers anomalies and reduces overall minion productivity."
            )
        ]
        for mem in memories:
            mgr.create_memory(mem)
    except Exception as exc:
        log.error("Failed to seed project memories: %s", exc)

seed_project_memories(memory_mgr)

# Project Manager setup
from project.manager import ProjectManager
workspaces_dir = get_exe_dir() / "workspaces"
project_manager = ProjectManager(db_mgr, workspaces_dir)

# Context Engine setup
from context.engine import ContextEngine
from context.providers import MemoryContextProvider

context_engine = ContextEngine(project_manager=project_manager)
context_engine.register_provider(MemoryContextProvider(memory_mgr))

# Plugins
from plugins.manager import PluginManager
plugins_dir = get_exe_dir() / "plugins"
plugin_mgr = PluginManager(plugins_dir)
try:
    plugin_mgr.discover_and_load()
except Exception as exc:
    log.error("Failed to discover and load plugins: %s", exc)

# Director
router = HeuristicRouter()
dispatcher = WorkerDispatcher(worker_manager, context_engine=context_engine)
director = Director(router, dispatcher, memory_mgr, project_manager=project_manager)
# Global IDE active services state
_active_git_service = None
_active_patch_manager = None
_active_index_service = None

def get_ide_services():
    global _active_git_service, _active_patch_manager, _active_index_service
    active_proj = project_manager.active_project
    if not active_proj:
        _active_git_service = None
        _active_patch_manager = None
        _active_index_service = None
        return None, None, None
        
    workspace = project_manager.active_workspace
    if not workspace:
        return None, None, None
        
    # Determine source directory (default to workspace_dir if none set)
    source_dir = active_proj.source_dir
    if not source_dir:
        source_dir = workspace.workspace_dir
    else:
        source_dir = Path(source_dir)
        
    # Re-instantiate if project ID has changed or if None
    if not _active_patch_manager or _active_patch_manager.workspace_dir != workspace.workspace_dir:
        from project.patch_system import PatchManager
        from project.git_service import GitService
        from project.index_service import CodeIndexService
        
        _active_patch_manager = PatchManager(workspace.workspace_dir, Path(source_dir))
        _active_git_service = GitService(Path(source_dir))
        _active_index_service = CodeIndexService(workspace)
        
    return _active_git_service, _active_patch_manager, _active_index_service

class GoblinUIHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        # Mute standard request logs in stdout
        pass

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(self.path)
        path_route = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        log.info(f"Incoming GET request: {path_route}")
        
        # Route static files
        if path_route == "/" or path_route == "/index.html":
            self.send_html_file(get_assets_dir() / "frontend" / "index.html")
        elif path_route == "/app.js":
            self.send_js_file(get_assets_dir() / "frontend" / "app.js")
        elif path_route == "/api/status":
            status_data = dict(_ui_status)
            status_data["active_project"] = project_manager.active_project.name if project_manager.active_project else "None"
            status_data["source_dir"] = project_manager.active_project.source_dir if project_manager.active_project else None
            self.send_json(status_data)
        elif path_route == "/api/projects":
            try:
                projects_list = project_manager.list_projects()
                data = []
                for p in projects_list:
                    data.append({
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "type": p.type,
                        "tags": p.tags,
                        "source_dir": p.source_dir,
                        "created_at": p.created_at,
                        "last_opened_at": p.last_opened_at
                    })
                self.send_json(data)
            except Exception as e:
                self.send_json({"error": f"Failed to list projects: {e}"})
        elif path_route == "/api/projects/documents":
            try:
                if project_manager.active_workspace:
                    docs = project_manager.active_workspace.list_documents()
                    self.send_json(docs)
                else:
                    self.send_json([])
            except Exception as e:
                self.send_json({"error": f"Failed to list documents: {e}"})
        elif path_route == "/api/logs":
            self.send_logs()
        elif path_route == "/api/settings":
            self.send_settings()
            
        # --- STAGE 14 GET ROUTES ---
        elif path_route == "/api/workspace/files":
            try:
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json([])
                    return
                
                # Recursively list files under active source directory
                def list_files_recursive(directory: Path, base_dir: Path) -> list[dict]:
                    items = []
                    if not directory.exists():
                        return items
                    for entry in directory.iterdir():
                        if entry.name.startswith(".") or entry.name in ("venv", ".venv", "node_modules", "__pycache__"):
                            continue
                        rel = str(entry.relative_to(base_dir)).replace("\\", "/")
                        is_dir = entry.is_dir()
                        items.append({
                            "name": entry.name,
                            "path": rel,
                            "isDir": is_dir,
                            "size": entry.stat().st_size if not is_dir else 0
                        })
                        if is_dir:
                            items.extend(list_files_recursive(entry, base_dir))
                    return items

                files = list_files_recursive(patch_m.source_dir, patch_m.source_dir)
                self.send_json(files)
            except Exception as e:
                self.send_json({"error": str(e)})
                
        elif path_route == "/api/workspace/file":
            try:
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"error": "No active project workspace"})
                    return
                rel_path = query_params.get("path", [""])[0]
                if not rel_path:
                    self.send_json({"error": "Path parameter is required"})
                    return
                
                full_path = (patch_m.source_dir / rel_path).resolve()
                if not full_path.is_file():
                    self.send_json({"error": f"File not found: {rel_path}"})
                    return
                    
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                self.send_json({"content": content})
            except Exception as e:
                self.send_json({"error": str(e)})
                
        elif path_route == "/api/git/status":
            try:
                git_s, patch_m, index_s = get_ide_services()
                if not git_s or not git_s.is_git_repository():
                    self.send_json({
                        "success": False, 
                        "error": "Not a Git Repository", 
                        "branch": "None", 
                        "status": {"staged": [], "unstaged": [], "untracked": []}
                    })
                    return
                
                branch = git_s.get_current_branch()
                status = git_s.get_status()
                self.send_json({
                    "success": True,
                    "branch": branch,
                    "status": status
                })
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})
                
        elif path_route == "/api/patches":
            try:
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"patches": []})
                    return
                
                patches = patch_m.list_patches()
                data = []
                for p in patches:
                    data.append({
                        "target_file": p.target_file,
                        "original_content": p.original_content,
                        "patched_content": p.patched_content,
                        "reason": p.reason
                    })
                self.send_json({"patches": data})
            except Exception as e:
                self.send_json({"error": str(e)})
        else:
            self.send_error(404, "File not found")

    def do_POST(self) -> None:
        log.info(f"Incoming POST request: {self.path}")
        if self.path == "/api/chat":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                query = data.get("query", "")
                
                # Run Director
                req = DirectorRequest(query=query)
                res = director.execute(req)
                 
                result_data = None
                if res.result is not None:
                    if res.result.__class__.__name__ == "ResearchResult":
                        result_data = {
                            "type": "research",
                            "summary": res.result.summary,
                            "findings": res.result.findings,
                            "sources": res.result.sources,
                            "confidence": res.result.confidence,
                            "raw_response": res.result.raw_response
                        }
                    elif hasattr(res.result, "__dict__"):
                        result_data = {k: v for k, v in res.result.__dict__.items() if not k.startswith("_")}
                        result_data["type"] = "object"
                        result_data["class_name"] = res.result.__class__.__name__
                    else:
                        result_data = str(res.result)
                        
                self.send_json({
                    "success": res.success,
                    "result": result_data,
                    "error": res.error,
                    "duration_ms": res.duration_ms
                })
            except Exception as exc:
                self.send_json({
                    "success": False,
                    "error": f"Failed to execute query: {exc}"
                })
        elif self.path == "/api/settings":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                api_key = data.get("api_key", "").strip()
                model = data.get("model", "gpt-4o-mini").strip()
                log_level = data.get("log_level", "INFO").strip()
                
                def is_masked(k: str) -> bool:
                    k = k.strip()
                    if not k:
                        return True
                    if "..." in k:
                        return True
                    if set(k) == {"*"}:
                        return True
                    if len(k) < 10:
                        return True
                    return False

                # Save API key and model if they are not masked
                if api_key and not is_masked(api_key):
                    os.environ["OPENAI_API_KEY"] = api_key
                os.environ["OPENAI_MODEL"] = model
                
                _ui_status["current_model"] = model
                
                # Write to .env file
                env_path = get_env_path()
                env_lines = []
                if env_path.is_file():
                    env_lines = env_path.read_text(encoding="utf-8").splitlines()
                
                new_lines = []
                has_key = False
                has_model = False
                for line in env_lines:
                    if line.startswith("OPENAI_API_KEY="):
                        if api_key and not is_masked(api_key):
                            new_lines.append(f"OPENAI_API_KEY={api_key}")
                        else:
                            new_lines.append(line)
                        has_key = True
                    elif line.startswith("OPENAI_MODEL="):
                        new_lines.append(f"OPENAI_MODEL={model}")
                        has_model = True
                    else:
                        new_lines.append(line)
                
                if not has_key and api_key and not is_masked(api_key):
                    new_lines.append(f"OPENAI_API_KEY={api_key}")
                if not has_model:
                    new_lines.append(f"OPENAI_MODEL={model}")
                    
                env_path.write_text("\n".join(new_lines), encoding="utf-8")
                
                # Reload settings in the global source of truth and the application
                reload_settings()
                app._settings = get_settings()
                _ui_status["current_model"] = app.settings.openai_model
                
                self.send_json({"success": True})
            except Exception as exc:
                self.send_json({"success": False, "error": str(exc)})
        elif self.path == "/api/projects":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                name = data.get("name", "").strip()
                description = data.get("description", "").strip()
                p_type = data.get("type", "Other").strip()
                tags = data.get("tags", [])
                
                if not name:
                    self.send_json({"success": False, "error": "Project name is required"})
                    return
                    
                project = project_manager.create_project(name, description, p_type, tags)
                
                # Q1 Migration: Auto-seed Gravehold memories if name matches
                if name.lower() == "gravehold":
                    try:
                        log.info("API: Auto-seeding Gravehold project memories from global DB.")
                        # Search global project memories
                        from memory.search import MemorySearchQuery
                        from database.models import Memory
                        search_query = MemorySearchQuery(project="Gravehold")
                        global_memories = memory_mgr.search_memory(search_query)
                        
                        ws_db = ProjectWorkspace(project.id, project_manager.base_workspaces_dir)
                        for mem in global_memories:
                            # Create workspace memory
                            ws_mem = Memory(
                                type=mem.type,
                                content=mem.content,
                                source=mem.source,
                                project=project.id,
                                tags=mem.tags,
                                importance=mem.importance
                            )
                            ws_db.memory_repo.create_memory(ws_mem)
                        ws_db.close()
                    except Exception as seed_err:
                        log.error(f"API: Failed to seed Gravehold memories: {seed_err}")
                
                self.send_json({"success": True, "project_id": project.id})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})
                
        elif self.path == "/api/projects/switch":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                project_id = data.get("project_id", "")
                project_manager.open_project(project_id)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})
                
        elif self.path == "/api/projects/close":
            try:
                project_manager.close_active_project()
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})
                
        elif self.path == "/api/projects/delete":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                project_id = data.get("project_id", "")
                project_manager.delete_project(project_id)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})
                
        elif self.path == "/api/projects/import":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                name = data.get("name", "").strip()
                content = data.get("content", "")
                
                if not project_manager.active_workspace:
                    self.send_json({"success": False, "error": "No active project workspace to import documents into"})
                    return
                    
                if not name:
                    self.send_json({"success": False, "error": "Document name is required"})
                    return
                    
                # Create temporary file inside workspace directory to parse/import
                temp_path = project_manager.active_workspace.workspace_dir / f"temp_{name}"
                temp_path.write_text(content, encoding="utf-8")
                
                try:
                    res = project_manager.active_workspace.import_document(temp_path)
                    self.send_json({"success": True, "document": res})
                finally:
                    if temp_path.exists():
                        os.remove(temp_path)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})
                
        # --- STAGE 14 POST ROUTES ---
        elif self.path == "/api/workspace/set_source":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                source_dir = data.get("source_dir", "").strip()
                if not project_manager.active_project:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                if not source_dir:
                    self.send_json({"success": False, "error": "Source directory is required"})
                    return
                if not Path(source_dir).is_dir():
                    self.send_json({"success": False, "error": f"Not a valid directory: {source_dir}"})
                    return
                
                project_manager.set_project_source_dir(project_manager.active_project.id, source_dir)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/workspace/file":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                rel_path = data.get("path", "").strip()
                content = data.get("content", "")
                is_dir = data.get("isDir", False)
                
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                if not rel_path:
                    self.send_json({"success": False, "error": "File path is required"})
                    return
                
                full_path = (patch_m.source_dir / rel_path).resolve()
                if is_dir:
                    patch_m.backup_file(rel_path, "create")
                    full_path.mkdir(parents=True, exist_ok=True)
                else:
                    if full_path.is_file():
                        patch_m.backup_file(rel_path, "modify")
                    else:
                        patch_m.backup_file(rel_path, "create")
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content, encoding="utf-8")
                
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/workspace/file/rename":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                old_rel = data.get("old_path", "").strip()
                new_rel = data.get("new_path", "").strip()
                
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                if not old_rel or not new_rel:
                    self.send_json({"success": False, "error": "Both old_path and new_path are required"})
                    return
                
                old_path = (patch_m.source_dir / old_rel).resolve()
                new_path = (patch_m.source_dir / new_rel).resolve()
                
                if not old_path.exists():
                    self.send_json({"success": False, "error": f"Path not found: {old_rel}"})
                    return
                    
                new_path.parent.mkdir(parents=True, exist_ok=True)
                
                patch_m._backup_history.append({
                    "original_path": str(new_path),
                    "backup_path": str(old_path),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "operation": "rename"
                })
                
                import shutil
                shutil.move(str(old_path), str(new_path))
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/workspace/file/delete":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                rel_path = data.get("path", "").strip()
                
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                if not rel_path:
                    self.send_json({"success": False, "error": "Path is required"})
                    return
                
                full_path = (patch_m.source_dir / rel_path).resolve()
                if not full_path.exists():
                    self.send_json({"success": False, "error": f"Path not found: {rel_path}"})
                    return
                
                patch_m.backup_file(rel_path, "delete")
                
                import shutil
                if full_path.is_file():
                    full_path.unlink()
                elif full_path.is_dir():
                    shutil.rmtree(full_path)
                
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/workspace/file/undo":
            try:
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                res = patch_m.undo_last_operation()
                if res:
                    self.send_json({"success": True, "undo": res})
                else:
                    self.send_json({"success": False, "error": "No actions to undo"})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/workspace/index":
            try:
                git_s, patch_m, index_s = get_ide_services()
                if not index_s or not patch_m:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                res = index_s.index_project(patch_m.source_dir)
                self.send_json({"success": True, "indexed": res})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/git/stage":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                rel_path = data.get("path", "").strip()
                git_s, patch_m, index_s = get_ide_services()
                if not git_s:
                    self.send_json({"success": False, "error": "No active git repo"})
                    return
                git_s.stage_file(rel_path)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/git/unstage":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                rel_path = data.get("path", "").strip()
                git_s, patch_m, index_s = get_ide_services()
                if not git_s:
                    self.send_json({"success": False, "error": "No active git repo"})
                    return
                git_s.unstage_file(rel_path)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/git/commit":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                message = data.get("message", "").strip()
                git_s, patch_m, index_s = get_ide_services()
                if not git_s:
                    self.send_json({"success": False, "error": "No active git repo"})
                    return
                out = git_s.commit(message)
                self.send_json({"success": True, "output": out})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/patches/create":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                rel_path = data.get("target_file", "").strip()
                patched = data.get("patched_content", "")
                reason = data.get("reason", "").strip()
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                patch_m.create_patch(rel_path, patched, reason)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/patches/apply":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                rel_path = data.get("target_file", "").strip()
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                patch_m.apply_patch(rel_path)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})

        elif self.path == "/api/patches/reject":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode("utf-8"))
                rel_path = data.get("target_file", "").strip()
                git_s, patch_m, index_s = get_ide_services()
                if not patch_m:
                    self.send_json({"success": False, "error": "No active project workspace"})
                    return
                patch_m.reject_patch(rel_path)
                self.send_json({"success": True})
            except Exception as e:
                self.send_json({"success": False, "error": str(e)})
        else:
            self.send_error(404, "API not found")

    def send_html_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404, "HTML file missing")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def send_js_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(404, "Javascript file missing")
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def send_json(self, data: dict | list) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def send_logs(self) -> None:
        log_file = get_exe_dir() / "logs" / "caller_os.log"
        if not log_file.is_file():
            self.send_json([])
            return
            
        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
            parsed_logs = []
            for line in lines[-200:]:  # Keep last 200 lines to avoid blowing memory
                parts = line.split("  ", 2)
                if len(parts) == 3:
                    parsed_logs.append({
                        "timestamp": parts[0],
                        "level": parts[1].strip(),
                        "message": parts[2]
                    })
                else:
                    parsed_logs.append({
                        "timestamp": "",
                        "level": "INFO",
                        "message": line
                    })
            self.send_json(parsed_logs)
        except Exception as exc:
            self.send_json([{"timestamp": "", "level": "ERROR", "message": f"Failed to read logs: {exc}"}])

    def send_settings(self) -> None:
        settings = get_settings()
        api_key = settings.openai_api_key
        masked_key = ""
        if api_key:
            masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
            
        self.send_json({
            "api_key": masked_key,
            "model": settings.openai_model,
            "log_level": "INFO"
        })


def run_server(port: int = 8080) -> None:
    try:
        server = HTTPServer(("127.0.0.1", port), GoblinUIHandler)
        log.info(f"API Server started at http://127.0.0.1:{port}")
        server.serve_forever()
    except Exception as exc:
        log.critical(f"API Server failed to start on port {port}: {exc}")
        raise
    finally:
        try:
            server.server_close()
        except Exception:
            pass
        app.shutdown()


if __name__ == "__main__":
    run_server()

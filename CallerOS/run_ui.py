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

from config.settings import Settings
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
from workers.research.client import AIClient, AIClientError
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
    if (exe_dir / "config" / ".env").is_file():
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


# Dynamic AI Client to support setting credentials at runtime without app crash
class DynamicAIClient:
    def complete(self, system_prompt: str, user_message: str) -> str:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        _ui_status["current_model"] = model
        
        if not api_key:
            raise AIClientError("OpenAI API key is missing. Please set it in the Settings screen.")

        try:
            import openai
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )
            return response.choices[0].message.content or ""
        except ImportError:
            raise AIClientError("The 'openai' package is not installed.")
        except Exception as exc:
            raise AIClientError(str(exc))


# Setup backend services
app = Application()
app.startup()

# Add log interceptor
logging.getLogger().addHandler(UIStatusLogHandler())

# Build registry & manager
registry = WorkerRegistry()
ai_client = DynamicAIClient()
research_worker = ResearchWorker(ai_client=ai_client)
registry.register(research_worker)

# In Stage 6, HeuristicRouter targets "developer-worker-v1" for code requests.
# Let's register a dummy developer worker so routing works without crashes!
from tests.conftest import DummyWorker
dev_worker = DummyWorker("developer-worker-v1", name="Developer Worker", capabilities=["programming"])
registry.register(dev_worker)

# Initialize all workers
worker_manager = WorkerManager(registry)
worker_manager.initialize_all()

# Memory manager
db_mgr = DatabaseManager(get_exe_dir() / "logs" / "caller_os_memory.db")
repo = SQLiteMemoryRepository(db_mgr)
memory_mgr = MemoryManager(repo)

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
dispatcher = WorkerDispatcher(worker_manager)
director = Director(router, dispatcher, memory_mgr)


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
        log.info(f"Incoming GET request: {self.path}")
        # Route static files
        if self.path == "/" or self.path == "/index.html":
            self.send_html_file(get_assets_dir() / "frontend" / "index.html")
        elif self.path == "/app.js":
            self.send_js_file(get_assets_dir() / "frontend" / "app.js")
        elif self.path == "/api/status":
            self.send_json(_ui_status)
        elif self.path == "/api/logs":
            self.send_logs()
        elif self.path == "/api/settings":
            self.send_settings()
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
                
                self.send_json({
                    "success": res.success,
                    "result": str(res.result) if res.result is not None else None,
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
                
                self.send_json({"success": True})
            except Exception as exc:
                self.send_json({"success": False, "error": str(exc)})
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
        api_key = os.environ.get("OPENAI_API_KEY", "")
        masked_key = ""
        if api_key:
            masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
            
        self.send_json({
            "api_key": masked_key,
            "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
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

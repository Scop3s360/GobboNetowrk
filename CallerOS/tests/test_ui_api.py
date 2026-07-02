"""
Tests: UI API Backend (run_ui.py)
=================================
Covers:
  - GET / and GET /app.js route matching.
  - GET /api/status retrieval.
  - GET /api/settings masking key details.
  - POST /api/settings updating settings successfully.
  - POST /api/chat invoking the Director.
  - Invalid route handling (404 errors).
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from run_ui import GoblinUIHandler, _ui_status


class MockHTTPHandler(GoblinUIHandler):
    """Testable subclass of GoblinUIHandler to isolate requests without socket binding."""

    def __init__(self, path: str, method: str = "GET", body: bytes = b"", headers: dict | None = None) -> None:
        self.path = path
        self.command = method
        self.rfile = BytesIO(body)
        self.wfile = BytesIO()
        self.headers = headers or {}
        if body:
            self.headers["Content-Length"] = str(len(body))
        
        self.response_code: int | None = None
        self.response_headers: list[tuple[str, str]] = []

    def send_response(self, code: int, message: str | None = None) -> None:
        self.response_code = code

    def send_header(self, keyword: str, value: str) -> None:
        self.response_headers.append((keyword, value))

    def end_headers(self) -> None:
        pass

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        self.response_code = code


# ---------------------------------------------------------------------------
# API Handler Tests
# ---------------------------------------------------------------------------

class TestUIAPI:
    def test_get_status_endpoint(self) -> None:
        handler = MockHTTPHandler(path="/api/status", method="GET")
        handler.do_GET()
        
        assert handler.response_code == 200
        response_body = json.loads(handler.wfile.getvalue().decode("utf-8"))
        assert "active_agent" in response_body
        assert "workflow_status" in response_body
        assert "current_model" in response_body

    def test_get_settings_endpoint(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-1234567890abcdef", "OPENAI_MODEL": "gpt-4o"}):
            handler = MockHTTPHandler(path="/api/settings", method="GET")
            handler.do_GET()
            
            assert handler.response_code == 200
            response_body = json.loads(handler.wfile.getvalue().decode("utf-8"))
            # Must return masked key, not the raw one
            assert response_body["api_key"] == "sk-123...cdef"
            assert response_body["model"] == "gpt-4o"

    def test_post_settings_endpoint(self) -> None:
        # Mock .env file write operation
        with patch.object(Path, "write_text") as mock_write, \
             patch.dict("os.environ", {}):
             
            settings_payload = {
                "api_key": "sk-new-api-key-test",
                "model": "gpt-4o-mini",
                "log_level": "DEBUG"
            }
            body_bytes = json.dumps(settings_payload).encode("utf-8")
            handler = MockHTTPHandler(path="/api/settings", method="POST", body=body_bytes)
            handler.do_POST()
            
            assert handler.response_code == 200
            response_body = json.loads(handler.wfile.getvalue().decode("utf-8"))
            assert response_body["success"] is True
            # Verifies state changed in environment
            import os
            assert os.environ["OPENAI_API_KEY"] == "sk-new-api-key-test"
            assert os.environ["OPENAI_MODEL"] == "gpt-4o-mini"
            assert mock_write.call_count == 1

    def test_post_settings_masked_key_ignored(self) -> None:
        # Verify that sending a masked API key does not overwrite the existing key
        with patch.object(Path, "write_text") as mock_write, \
             patch.dict("os.environ", {"OPENAI_API_KEY": "original-secret-key-12345"}):
             
            for masked_key in ["***", "sk-123...cdef", "short", ""]:
                settings_payload = {
                    "api_key": masked_key,
                    "model": "gpt-4o-mini",
                    "log_level": "INFO"
                }
                body_bytes = json.dumps(settings_payload).encode("utf-8")
                handler = MockHTTPHandler(path="/api/settings", method="POST", body=body_bytes)
                handler.do_POST()
                
                assert handler.response_code == 200
                import os
                # Key must remain unchanged
                assert os.environ["OPENAI_API_KEY"] == "original-secret-key-12345"

    def test_post_chat_endpoint_success(self) -> None:
        # Mock the Director execute method to isolate UI from AI API calls
        from director.director import DirectorResponse
        mock_response = DirectorResponse(success=True, result="GoblinOS answer content")
        
        with patch("run_ui.director.execute", return_value=mock_response) as mock_exec:
            chat_payload = {"query": "Tell me a python concept"}
            body_bytes = json.dumps(chat_payload).encode("utf-8")
            
            handler = MockHTTPHandler(path="/api/chat", method="POST", body=body_bytes)
            handler.do_POST()
            
            assert handler.response_code == 200
            response_body = json.loads(handler.wfile.getvalue().decode("utf-8"))
            assert response_body["success"] is True
            assert response_body["result"] == "GoblinOS answer content"
            assert mock_exec.call_count == 1

    def test_invalid_path_returns_404(self) -> None:
        handler = MockHTTPHandler(path="/api/unsupported", method="GET")
        handler.do_GET()
        assert handler.response_code == 404

"""
Tests: Tool Framework (Stage 4)
===============================
Covers:
  - Tool models immutability and default factories.
  - ToolRegistry registration, lookups, duplicate detection, listing, iteration.
  - ToolExecutor logic (lookup, permissions validation, error capturing, logging).
  - Concrete built-in tools (ReadFileTool, WriteFileTool, ListDirectoryTool, ReadFolderTool, RunCommandTool, SearchWebTool stub).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import pytest

from tools.base import Tool
from tools.builtin import (
    ListDirectoryTool,
    ReadFileTool,
    ReadFolderTool,
    RunCommandTool,
    SearchWebTool,
    WriteFileTool,
)
from tools.exceptions import (
    DuplicateToolError,
    PermissionDeniedError,
    ToolExecutionError,
    ToolNotFoundError,
)
from tools.executor import ToolExecutor
from tools.models import ToolRequest, ToolResponse
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Mocks & Dummies
# ---------------------------------------------------------------------------

class DummyTool(Tool):
    """A simple mock tool for registration and permission testing."""

    def __init__(self, name: str = "dummy_tool", permission_level: PermissionLevel = PermissionLevel.READ) -> None:
        self._name = name
        self._permission_level = permission_level

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Dummy tool {self._name}."

    @property
    def permission_level(self) -> PermissionLevel:
        return self._permission_level

    def execute(self, **kwargs: object) -> object:
        if kwargs.get("raise_error"):
            raise ValueError("Deliberate dummy error")
        return kwargs.get("return_val", "dummy_success")


# ---------------------------------------------------------------------------
# Tests: Tool Models
# ---------------------------------------------------------------------------

class TestToolModels:
    def test_tool_request_immutability(self) -> None:
        req = ToolRequest(tool_name="test_tool", arguments={"a": 1})
        with pytest.raises(AttributeError):
            # dataclass is frozen
            req.tool_name = "other"  # type: ignore

    def test_tool_request_defaults(self) -> None:
        req = ToolRequest(tool_name="test_tool", arguments={"a": 1})
        assert req.correlation_id is not None
        assert len(req.correlation_id) > 0
        assert req.timestamp is not None

    def test_tool_response_immutability(self) -> None:
        res = ToolResponse(success=True, output="output")
        with pytest.raises(AttributeError):
            res.success = False  # type: ignore


# ---------------------------------------------------------------------------
# Tests: Tool Registry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_register_and_get(self) -> None:
        registry = ToolRegistry()
        tool = DummyTool("my_tool")
        registry.register(tool)
        
        assert registry.is_registered("my_tool") is True
        assert registry.get("my_tool") is tool
        assert len(registry) == 1

    def test_duplicate_registration_raises(self) -> None:
        registry = ToolRegistry()
        tool1 = DummyTool("my_tool")
        tool2 = DummyTool("my_tool")
        registry.register(tool1)
        
        with pytest.raises(DuplicateToolError, match="already registered"):
            registry.register(tool2)

    def test_lookup_missing_tool_raises(self) -> None:
        registry = ToolRegistry()
        with pytest.raises(ToolNotFoundError, match="not found"):
            registry.get("ghost")

    def test_list_tools(self) -> None:
        registry = ToolRegistry()
        tool1 = DummyTool("b_tool")
        tool2 = DummyTool("a_tool")
        registry.register(tool1)
        registry.register(tool2)
        
        tools_list = registry.list_tools()
        # Should be sorted by name
        assert tools_list == [tool2, tool1]

    def test_iteration(self) -> None:
        registry = ToolRegistry()
        tool1 = DummyTool("b_tool")
        tool2 = DummyTool("a_tool")
        registry.register(tool1)
        registry.register(tool2)
        
        names = [t.name for t in registry]
        assert names == ["a_tool", "b_tool"]

    def test_clear(self) -> None:
        registry = ToolRegistry()
        registry.register(DummyTool("my_tool"))
        registry.clear()
        assert len(registry) == 0


# ---------------------------------------------------------------------------
# Tests: Tool Executor
# ---------------------------------------------------------------------------

class TestToolExecutor:
    def test_executor_success(self) -> None:
        registry = ToolRegistry()
        registry.register(DummyTool("read_tool", PermissionLevel.READ))
        executor = ToolExecutor(registry, PermissionLevel.READ)
        
        req = ToolRequest(tool_name="read_tool", arguments={"return_val": "hello"})
        res = executor.execute(req)
        
        assert res.success is True
        assert res.output == "hello"
        assert res.error is None
        assert res.execution_time_ms >= 0.0

    def test_executor_missing_tool(self) -> None:
        registry = ToolRegistry()
        executor = ToolExecutor(registry, PermissionLevel.READ)
        
        req = ToolRequest(tool_name="ghost_tool", arguments={})
        res = executor.execute(req)
        
        assert res.success is False
        assert "ghost_tool" in res.error

    def test_executor_permission_validation(self) -> None:
        registry = ToolRegistry()
        registry.register(DummyTool("execute_tool", PermissionLevel.EXECUTE))
        
        # 1. Allowed level too low (READ trying to run EXECUTE)
        executor = ToolExecutor(registry, PermissionLevel.READ)
        req = ToolRequest(tool_name="execute_tool", arguments={})
        res = executor.execute(req)
        
        assert res.success is False
        assert "Permission denied" in res.error

        # 2. Allowed level matches (EXECUTE trying to run EXECUTE)
        executor_high = ToolExecutor(registry, PermissionLevel.EXECUTE)
        res_high = executor_high.execute(req)
        assert res_high.success is True

    def test_executor_tool_failure(self) -> None:
        registry = ToolRegistry()
        registry.register(DummyTool("fail_tool", PermissionLevel.READ))
        executor = ToolExecutor(registry, PermissionLevel.READ)
        
        req = ToolRequest(tool_name="fail_tool", arguments={"raise_error": True})
        res = executor.execute(req)
        
        assert res.success is False
        assert "Deliberate dummy error" in res.error

    def test_executor_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        registry = ToolRegistry()
        registry.register(DummyTool("log_tool", PermissionLevel.READ))
        executor = ToolExecutor(registry, PermissionLevel.READ)
        
        req = ToolRequest(tool_name="log_tool", arguments={})
        
        with caplog.at_level(logging.INFO):
            executor.execute(req)
            
        # Verify log statements exist
        messages = [record.message for record in caplog.records]
        assert any("Tool execution started: tool=log_tool" in msg for msg in messages)
        assert any("Tool execution finished: tool=log_tool" in msg and "success=True" in msg for msg in messages)


# ---------------------------------------------------------------------------
# Tests: Built-in Tools
# ---------------------------------------------------------------------------

class TestBuiltinTools:
    def test_read_and_write_file_tools(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_file.txt"
        
        # Write file tool
        write_tool = WriteFileTool()
        assert write_tool.permission_level == PermissionLevel.WRITE
        
        write_res = write_tool.execute(path=str(test_file), content="hello world")
        assert "Successfully wrote" in str(write_res)
        assert test_file.read_text(encoding="utf-8") == "hello world"
        
        # Read file tool
        read_tool = ReadFileTool()
        assert read_tool.permission_level == PermissionLevel.READ
        
        read_res = read_tool.execute(path=str(test_file))
        assert read_res == "hello world"

    def test_read_file_missing_raises(self) -> None:
        read_tool = ReadFileTool()
        with pytest.raises(FileNotFoundError):
            read_tool.execute(path="this_file_definitely_does_not_exist.txt")

    def test_read_file_invalid_arguments_raises(self) -> None:
        read_tool = ReadFileTool()
        with pytest.raises(ValueError):
            read_tool.execute(path=123)  # type: ignore

    def test_list_directory_tool(self, tmp_path: Path) -> None:
        # Create structure
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()
        (tmp_path / "subdir").mkdir()
        
        list_tool = ListDirectoryTool()
        assert list_tool.permission_level == PermissionLevel.READ
        
        res = list_tool.execute(path=str(tmp_path))
        assert isinstance(res, list)
        assert res == ["file1.txt", "file2.txt", "subdir"]

    def test_read_folder_tool(self, tmp_path: Path) -> None:
        # Create nested files
        (tmp_path / "root.txt").write_text("root_content", encoding="utf-8")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.txt").write_text("nested_content", encoding="utf-8")
        
        folder_tool = ReadFolderTool()
        assert folder_tool.permission_level == PermissionLevel.READ
        
        res = folder_tool.execute(path=str(tmp_path))
        assert isinstance(res, dict)
        assert res.get("root.txt") == "root_content"
        assert res.get("subdir/nested.txt") == "nested_content"

    def test_run_command_tool(self, tmp_path: Path) -> None:
        cmd_tool = RunCommandTool()
        assert cmd_tool.permission_level == PermissionLevel.EXECUTE
        
        # Run a simple python print command (shell-free executable process)
        res = cmd_tool.execute(command="python -c \"print('hello from GoblinOS')\"")
        assert isinstance(res, dict)
        assert "stdout" in res
        assert "stderr" in res
        assert "returncode" in res
        assert "hello from GoblinOS" in res["stdout"].strip()
        assert res["returncode"] == 0

        # Verify working directory validation
        res_cwd = cmd_tool.execute(
            command="python -c \"import os; print(os.getcwd())\"",
            cwd=str(tmp_path)
        )
        assert Path(res_cwd["stdout"].strip()).resolve() == tmp_path.resolve()

        # Invalid directory raises FileNotFoundError
        with pytest.raises(FileNotFoundError):
            cmd_tool.execute(command="python -c \"print('ok')\"", cwd="nonexistent-directory-xyz")

    def test_search_web_tool_stub(self) -> None:
        search_tool = SearchWebTool()
        assert search_tool.permission_level == PermissionLevel.READ
        
        res = search_tool.execute(query="test query")
        assert "not yet integrated" in str(res)
        assert "test query" in str(res)

"""
Tool Framework
==============
A generic, extensible tool system for GoblinOS.
"""

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
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
)
from tools.executor import ToolExecutor
from tools.models import ToolRequest, ToolResponse
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry

__all__ = [
    "Tool",
    "PermissionLevel",
    "ToolRequest",
    "ToolResponse",
    "ToolRegistry",
    "ToolExecutor",
    "ToolError",
    "ToolNotFoundError",
    "DuplicateToolError",
    "PermissionDeniedError",
    "ToolExecutionError",
    "ReadFileTool",
    "WriteFileTool",
    "ListDirectoryTool",
    "ReadFolderTool",
    "RunCommandTool",
    "SearchWebTool",
]

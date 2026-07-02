"""
Tool Exceptions
===============
Exception hierarchy for the Tool Framework.

All tool exceptions derive from ToolError, which itself derives from
CallerOSError (Stage 1).
"""

from core.exceptions import CallerOSError


class ToolError(CallerOSError):
    """Base exception for all tool framework errors."""


class ToolNotFoundError(ToolError):
    """Raised when a requested tool name is not found in the registry."""


class DuplicateToolError(ToolError):
    """Raised when attempting to register a tool name that already exists."""


class PermissionDeniedError(ToolError):
    """Raised when the execution of a tool is rejected due to insufficient permission."""


class ToolExecutionError(ToolError):
    """Raised when a tool's execute() raises an unexpected exception."""

"""
Tool Executor
=============
Receives and executes tool requests, performing permission validation,
timing, error handling, and structured logging.
"""

import logging
import time
from datetime import datetime, timezone

from tools.base import Tool
from tools.exceptions import (
    PermissionDeniedError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
)
from tools.models import ToolRequest, ToolResponse
from tools.permissions import PermissionLevel
from tools.registry import ToolRegistry

log = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes tool requests through a controlled interface.
    
    Responsible for checking permissions, locating tools in the registry,
    timing execution, capturing any errors, and logging details.
    """

    # Define a hierarchy for checking permissions.
    # READ allows only READ.
    # WRITE allows READ and WRITE.
    # EXECUTE allows READ, WRITE, and EXECUTE.
    _PERMISSION_HIERARCHY = {
        PermissionLevel.READ: 1,
        PermissionLevel.WRITE: 2,
        PermissionLevel.EXECUTE: 3,
    }

    def __init__(
        self,
        registry: ToolRegistry,
        max_permission_level: PermissionLevel = PermissionLevel.READ,
    ) -> None:
        """
        Initialize the ToolExecutor.
        
        Args:
            registry: The registry containing all registered tools.
            max_permission_level: The maximum permission level allowed for execution.
        """
        self._registry = registry
        self._max_permission_level = max_permission_level

    def execute(self, request: ToolRequest) -> ToolResponse:
        """
        Execute the requested tool.
        
        Args:
            request: The ToolRequest object.
            
        Returns:
            A ToolResponse containing success status, output/error, and duration.
        """
        tool_name = request.tool_name
        start_time_dt = datetime.now(timezone.utc)
        start_time_str = start_time_dt.isoformat()
        
        log.info(
            "Tool execution started: tool=%s, correlation_id=%s, start_time=%s",
            tool_name,
            request.correlation_id,
            start_time_str,
        )
        
        start_perf = time.perf_counter()
        success = False
        error_msg = None
        output = None
        
        try:
            # 1. Lookup the tool
            # (get() raises ToolNotFoundError if missing)
            tool = self._registry.get(tool_name)
            
            # 2. Validate permissions
            # (raises PermissionDeniedError if insufficient)
            self._validate_permissions(tool)
            
            # 3. Execute the tool
            try:
                output = tool.execute(**request.arguments)
                success = True
            except Exception as exc:
                # Wrap any execution exception in a ToolExecutionError
                raise ToolExecutionError(
                    f"Error executing tool '{tool_name}': {exc}"
                ) from exc
                
        except ToolNotFoundError as exc:
            error_msg = str(exc)
        except PermissionDeniedError as exc:
            error_msg = str(exc)
        except ToolExecutionError as exc:
            error_msg = str(exc)
        except Exception as exc:
            # Catch-all for any other unanticipated errors
            error_msg = f"Unexpected error during tool execution: {exc}"
            
        finish_perf = time.perf_counter()
        duration_ms = (finish_perf - start_perf) * 1000.0
        finish_time_dt = datetime.now(timezone.utc)
        finish_time_str = finish_time_dt.isoformat()
        
        # Log the completion with the required fields:
        # Tool name, Start time, Finish time, Duration, Success, Failure reason
        if success:
            log.info(
                "Tool execution finished: tool=%s, start_time=%s, finish_time=%s, "
                "duration_ms=%.2f, success=True, failure_reason=None",
                tool_name,
                start_time_str,
                finish_time_str,
                duration_ms,
            )
        else:
            log.error(
                "Tool execution finished: tool=%s, start_time=%s, finish_time=%s, "
                "duration_ms=%.2f, success=False, failure_reason='%s'",
                tool_name,
                start_time_str,
                finish_time_str,
                duration_ms,
                error_msg,
            )
            
        return ToolResponse(
            success=success,
            output=output,
            error=error_msg,
            execution_time_ms=duration_ms,
        )

    def _validate_permissions(self, tool: Tool) -> None:
        """
        Check if the tool's required permission level is allowed by the executor.
        
        Raises:
            PermissionDeniedError: If the tool level exceeds the allowed level.
        """
        required_val = self._PERMISSION_HIERARCHY.get(tool.permission_level, 999)
        allowed_val = self._PERMISSION_HIERARCHY.get(self._max_permission_level, 0)
        
        if required_val > allowed_val:
            raise PermissionDeniedError(
                f"Permission denied for tool '{tool.name}'. "
                f"Required: {tool.permission_level.name}, Allowed: {self._max_permission_level.name}"
            )

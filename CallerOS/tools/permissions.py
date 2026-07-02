"""
Tool Permissions
================
Defines permission levels for validating tool executions.
"""

from enum import Enum, auto


class PermissionLevel(Enum):
    """
    Enum representing access/authorization levels for tool execution.
    
    Levels:
        READ    - Permission to read files, directories, etc.
        WRITE   - Permission to write or modify files, directories, etc.
        EXECUTE - Permission to run commands/subprocesses on the host system.
    """
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()

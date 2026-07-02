"""
GoblinOS Database System (Stage 9)
==================================
Manages connection lifetimes, transactions, incremental schema migrations,
and repositories for persistent storage.
"""

from database.connection import ConnectionManager
from database.exceptions import DatabaseError, MigrationError, RepositoryError
from database.manager import DatabaseManager
from database.models import (
    Conversation,
    LogEntry,
    Memory,
    Message,
    Setting,
    WorkflowHistory,
)

__all__ = [
    "ConnectionManager",
    "DatabaseError",
    "MigrationError",
    "RepositoryError",
    "DatabaseManager",
    "Conversation",
    "Message",
    "Memory",
    "WorkflowHistory",
    "Setting",
    "LogEntry",
]

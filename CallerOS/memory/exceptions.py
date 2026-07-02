"""
Memory Exceptions
=================
Exception hierarchy for the Memory System.

All memory exceptions derive from MemoryError, which itself derives from
CallerOSError (Stage 1).
"""

from core.exceptions import CallerOSError


class MemoryError(CallerOSError):
    """Base exception for all memory system errors."""


class MemoryNotFoundError(MemoryError):
    """Raised when a requested memory ID does not exist."""


class DatabaseError(MemoryError):
    """Raised when a database transaction or operation fails."""

"""
Database Exceptions
===================
Exception hierarchy for the Database Layer.

All database exceptions derive from DatabaseError, which itself derives from
CallerOSError (Stage 1).
"""

from core.exceptions import CallerOSError


class DatabaseError(CallerOSError):
    """Base exception for all database layer errors."""


class MigrationError(DatabaseError):
    """Raised when a schema migration fails or cannot be executed."""


class RepositoryError(DatabaseError):
    """Raised when repository operations (CRUD, mapping) fail."""

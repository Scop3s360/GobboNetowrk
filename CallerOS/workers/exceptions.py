"""
Worker Exceptions
=================
Exception hierarchy for the Worker Framework.

All worker exceptions derive from WorkerError, which itself derives from
CallerOSError (Stage 1), so callers can choose to catch at any level:

    except CallerOSError   — catches everything in the whole application
    except WorkerError     — catches anything from the worker layer
    except WorkerNotFoundError — catches only this specific condition

Architectural decision:
    Worker exceptions live in ``workers/`` rather than ``core/exceptions.py``
    because they are a domain concern of the worker framework, not a core
    infrastructure concern.  Keeping them here means Stage 1 has zero
    awareness of Stage 2 (dependency flows one way: workers → core).
"""

from core.exceptions import CallerOSError


class WorkerError(CallerOSError):
    """Base exception for all worker framework errors."""


class WorkerNotFoundError(WorkerError):
    """Raised when a worker id is not present in the registry."""


class WorkerAlreadyRegisteredError(WorkerError):
    """Raised when attempting to register a worker id that already exists."""


class WorkerExecutionError(WorkerError):
    """Raised when a worker raises during execute()."""


class WorkerInitializationError(WorkerError):
    """Raised when a worker raises during initialize()."""


class WorkerShutdownError(WorkerError):
    """Raised when a worker raises during shutdown()."""

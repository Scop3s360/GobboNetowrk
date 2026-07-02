"""
CallerOS Core Exceptions
========================
Custom exception hierarchy for the CallerOS application.

Every exception derives from CallerOSError so callers can choose to
catch the entire family (CallerOSError) or individual sub-types.

Architectural decision:
    Using a dedicated exception module keeps error semantics clear and
    prevents leaking low-level Python exceptions (KeyError, ValueError, etc.)
    across module boundaries.
"""


class CallerOSError(Exception):
    """Base exception for all CallerOS errors."""


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


class ConfigurationError(CallerOSError):
    """Raised when configuration is missing, invalid, or cannot be loaded."""


# ---------------------------------------------------------------------------
# Service registry errors
# ---------------------------------------------------------------------------


class ServiceRegistrationError(CallerOSError):
    """Raised when a service cannot be registered (e.g. duplicate name)."""


class ServiceNotFoundError(CallerOSError):
    """Raised when a requested service has not been registered."""


# ---------------------------------------------------------------------------
# Lifecycle errors
# ---------------------------------------------------------------------------


class StartupError(CallerOSError):
    """Raised when the application fails to start."""


class ShutdownError(CallerOSError):
    """Raised when a service fails to stop cleanly."""


# ---------------------------------------------------------------------------
# Health check errors
# ---------------------------------------------------------------------------


class HealthCheckError(CallerOSError):
    """Raised when a startup health validation fails."""

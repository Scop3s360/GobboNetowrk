"""
CallerOS Service Registry
=========================
A lightweight, dictionary-backed dependency registry.

Services are registered by name and resolved by name.  The registry
enforces uniqueness — attempting to register a service under a name that
is already taken raises ServiceRegistrationError immediately, making
mis-wiring obvious at startup rather than at call time.

Architectural decision:
    No IoC framework (e.g. dependency-injector, injector) is used because
    the guide explicitly forbids it and the application does not yet have
    enough services to warrant one.  A plain dict is sufficient.

    Services are stored as ``object`` so any Python value can be registered
    (class instance, function, plain value).  Type narrowing is the caller's
    responsibility — see get().

    Thread-safety is NOT guaranteed in this implementation.  CallerOS is
    single-threaded in Stage 1, so this is acceptable.  A threading.Lock
    can be added later without changing the public interface.
"""

import logging
from typing import Any

from core.exceptions import ServiceNotFoundError, ServiceRegistrationError

log = logging.getLogger(__name__)


class ServiceRegistry:
    """
    Maps string names to service instances.

    Usage::

        registry = ServiceRegistry()
        registry.register("my_service", MyService())
        svc = registry.get("my_service", MyService)
    """

    def __init__(self) -> None:
        self._services: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, name: str, service: Any) -> None:
        """
        Register a service under the given name.

        Args:
            name:    Unique identifier for the service.
            service: The service instance (any object).

        Raises:
            ServiceRegistrationError: If ``name`` is already registered.
        """
        if name in self._services:
            raise ServiceRegistrationError(
                f"Service '{name}' is already registered. "
                "Use a unique name or deregister the existing service first."
            )
        self._services[name] = service
        log.info("Service registered: %s (%s)", name, type(service).__name__)

    def get(self, name: str) -> Any:
        """
        Resolve and return the service registered under ``name``.

        Args:
            name: The service identifier.

        Returns:
            The registered service instance.

        Raises:
            ServiceNotFoundError: If no service is registered under ``name``.
        """
        service = self._services.get(name)
        if service is None:
            raise ServiceNotFoundError(
                f"Service '{name}' is not registered. "
                f"Registered services: {self._registered_names()}"
            )
        return service

    def is_registered(self, name: str) -> bool:
        """Return True if a service is registered under ``name``."""
        return name in self._services

    def deregister(self, name: str) -> None:
        """
        Remove a service from the registry.

        Silently does nothing if the name was not registered.  This avoids
        forcing callers to check is_registered() before cleanup.

        Args:
            name: The service identifier to remove.
        """
        removed = self._services.pop(name, None)
        if removed is not None:
            log.debug("Service deregistered: %s", name)

    def registered_names(self) -> list[str]:
        """Return a sorted list of all registered service names."""
        return sorted(self._services.keys())

    def clear(self) -> None:
        """Remove all registered services.  Intended for test teardown."""
        self._services.clear()
        log.debug("Service registry cleared.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _registered_names(self) -> str:
        """Return a comma-separated list of registered names for error messages."""
        names = self.registered_names()
        return ", ".join(names) if names else "(none)"

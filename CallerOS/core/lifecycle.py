"""
CallerOS Lifecycle Manager
==========================
Manages the ordered startup and shutdown of registered services.

Services are started in registration order and stopped in reverse order
(LIFO), which is the conventional pattern for service teardown: the last
service to come up is the first to go down.

Architectural decision:
    The lifecycle manager is deliberately decoupled from the ServiceRegistry.
    Services are passed in explicitly rather than discovered from the registry.
    This makes the startup order explicit in application.py, which is easier
    to reason about than implicit ordering.

    Each service must implement the LifecycleService protocol (start / stop
    methods).  Plain services (e.g. the registry itself) that do not need
    lifecycle hooks are not added to the lifecycle manager.

Protocol:
    Any object with `start()` and `stop()` methods qualifies as a
    LifecycleService.  No formal ABC is enforced — duck typing keeps this
    lightweight.
"""

import logging
from typing import Protocol, runtime_checkable

from core.exceptions import ShutdownError, StartupError

log = logging.getLogger(__name__)


@runtime_checkable
class LifecycleService(Protocol):
    """
    Protocol that lifecycle-managed services must satisfy.

    Both methods should be idempotent — calling start() on an already-started
    service or stop() on an already-stopped service should not raise.
    """

    def start(self) -> None:
        """Start the service.  Called during application startup."""
        ...

    def stop(self) -> None:
        """Stop the service.  Called during application shutdown."""
        ...


class LifecycleManager:
    """
    Orchestrates ordered startup and LIFO shutdown of services.

    Usage::

        manager = LifecycleManager()
        manager.add(service_a)
        manager.add(service_b)
        manager.startup()   # starts a then b
        manager.shutdown()  # stops b then a
    """

    def __init__(self) -> None:
        # Ordered list of services — insertion order is startup order.
        self._services: list[LifecycleService] = []
        self._started: list[LifecycleService] = []

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def add(self, service: LifecycleService) -> None:
        """
        Add a service to the managed set.

        Args:
            service: Any object that satisfies the LifecycleService protocol.

        Raises:
            StartupError: If the service does not satisfy the protocol.
        """
        if not isinstance(service, LifecycleService):
            raise StartupError(
                f"Object of type '{type(service).__name__}' does not implement "
                "the LifecycleService protocol (requires start() and stop())."
            )
        self._services.append(service)
        log.debug("Lifecycle service added: %s", type(service).__name__)

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    def startup(self) -> None:
        """
        Start all registered services in registration order.

        If any service fails to start, a StartupError is raised immediately.
        Services that started successfully before the failure are NOT
        automatically stopped here — that is the caller's responsibility so
        that partial-startup can be logged and diagnosed.

        Raises:
            StartupError: If any service raises during start().
        """
        log.info("Lifecycle startup: %d service(s) to start.", len(self._services))
        for service in self._services:
            name = type(service).__name__
            try:
                log.info("Starting service: %s", name)
                service.start()
                self._started.append(service)
                log.info("Service started:  %s", name)
            except Exception as exc:
                raise StartupError(
                    f"Service '{name}' failed to start: {exc}"
                ) from exc

        log.info("Lifecycle startup complete.")

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """
        Stop all successfully-started services in reverse order (LIFO).

        All services are given a chance to stop even if earlier stops raise.
        All errors are collected and re-raised together as a ShutdownError
        after all services have been attempted.

        Raises:
            ShutdownError: If one or more services raised during stop().
        """
        log.info("Lifecycle shutdown: %d service(s) to stop.", len(self._started))
        errors: list[str] = []

        for service in reversed(self._started):
            name = type(service).__name__
            try:
                log.info("Stopping service: %s", name)
                service.stop()
                log.info("Service stopped:  %s", name)
            except Exception as exc:  # noqa: BLE001
                # Collect and continue — never abandon remaining services.
                msg = f"Service '{name}' failed to stop cleanly: {exc}"
                log.error(msg)
                errors.append(msg)

        self._started.clear()
        log.info("Lifecycle shutdown complete.")

        if errors:
            raise ShutdownError(
                "One or more services did not shut down cleanly:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

"""
CallerOS Health Validator
=========================
Startup health checks that confirm the application is in a valid state
before it begins accepting work.

Checks are lightweight and fast — they validate presence and correctness
of collaborators, not real I/O.

Architectural decision:
    Health checks are separated from the Application class to keep
    Application focused on the startup/shutdown lifecycle.  The validator
    simply inspects the state of provided objects and reports problems
    as a list of human-readable strings, which makes unit testing trivial
    without mocking the entire application.

Health states:
    READY   — all checks passed; the application may proceed.
    FAILED  — one or more checks did not pass; startup should be aborted.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum

from config.settings import Settings
from core.service_registry import ServiceRegistry

log = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Possible outcomes of a health validation run."""

    READY = "READY"
    FAILED = "FAILED"


@dataclass
class HealthReport:
    """
    The result of a health validation run.

    Attributes:
        status:  Overall outcome (READY or FAILED).
        issues:  Human-readable descriptions of any problems found.
    """

    status: HealthStatus
    issues: list[str] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        """True when status is READY and there are no reported issues."""
        return self.status is HealthStatus.READY and not self.issues


class HealthValidator:
    """
    Validates the application's startup health.

    Checks performed:
        1. Configuration is present and has required fields.
        2. Logging is active (the root logger has handlers).
        3. The service registry is operational.
    """

    def validate(
        self,
        settings: Settings | None,
        registry: ServiceRegistry | None,
    ) -> HealthReport:
        """
        Run all startup health checks and return a HealthReport.

        Args:
            settings: The loaded application settings (may be None if
                      configuration loading failed).
            registry: The service registry (may be None if not yet created).

        Returns:
            HealthReport with status READY or FAILED.
        """
        issues: list[str] = []

        self._check_configuration(settings, issues)
        self._check_logging(issues)
        self._check_registry(registry, issues)

        if issues:
            status = HealthStatus.FAILED
            for issue in issues:
                log.error("Health check FAILED: %s", issue)
        else:
            status = HealthStatus.READY
            log.info("Health check PASSED — status: %s", status.value)

        return HealthReport(status=status, issues=issues)

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    @staticmethod
    def _check_configuration(settings: Settings | None, issues: list[str]) -> None:
        """Confirm that a Settings object was loaded and has required fields."""
        if settings is None:
            issues.append("Configuration has not been loaded (settings is None).")
            return

        # Spot-check the most critical fields.
        if not settings.app_name:
            issues.append("Configuration: 'app_name' is empty.")
        if not settings.version:
            issues.append("Configuration: 'version' is empty.")
        if not settings.log_level:
            issues.append("Configuration: 'log_level' is empty.")

    @staticmethod
    def _check_logging(issues: list[str]) -> None:
        """Confirm the root logger has at least one active handler."""
        import logging as _logging

        root = _logging.getLogger()
        if not root.handlers:
            issues.append(
                "Logging has not been initialised (root logger has no handlers)."
            )

    @staticmethod
    def _check_registry(registry: ServiceRegistry | None, issues: list[str]) -> None:
        """Confirm the service registry exists and is responsive."""
        if registry is None:
            issues.append("Service registry has not been created.")
            return

        # Probe the registry with a round-trip that should never raise.
        try:
            registry.is_registered("__health_probe__")
        except Exception as exc:  # noqa: BLE001
            issues.append(f"Service registry is not operational: {exc}")

"""
CallerOS Application
====================
Top-level application class that owns the startup and shutdown sequences.

Application is the single authoritative owner of:
    - Settings  (loaded once, shared read-only)
    - ServiceRegistry  (populated during startup)
    - LifecycleManager  (started and stopped as a unit)

It does NOT contain any business, AI, or domain logic.

Architectural decision:
    Application state is tracked via the ApplicationState enum rather than
    boolean flags.  This makes illegal state transitions (e.g. calling
    shutdown() before startup()) detectable and produces clear log messages.

    Signal handling (SIGINT / SIGTERM) is wired up during startup so that
    Ctrl-C and OS shutdown signals trigger a graceful shutdown rather than
    an abrupt exit.
"""

import logging
import signal
import sys
from enum import Enum, auto

from config.settings import Settings, get_settings
from core.exceptions import HealthCheckError, StartupError
from core.health import HealthStatus, HealthValidator
from core.lifecycle import LifecycleManager
from core.service_registry import ServiceRegistry
from app_logging.logger import setup_logging

log = logging.getLogger(__name__)


class ApplicationState(Enum):
    """Lifecycle state of the application."""

    CREATED = auto()    # Instance constructed, startup not yet called.
    STARTING = auto()   # Startup sequence in progress.
    RUNNING = auto()    # Startup completed successfully.
    STOPPING = auto()   # Shutdown sequence in progress.
    STOPPED = auto()    # Shutdown completed.
    FAILED = auto()     # Startup or shutdown encountered a fatal error.


class Application:
    """
    Bootstraps and manages the CallerOS application lifecycle.

    Typical usage::

        app = Application()
        app.startup()
        # ... application runs ...
        app.shutdown()

    Or via context manager::

        with Application() as app:
            ...  # application is running inside this block
    """

    def __init__(self) -> None:
        self._state = ApplicationState.CREATED
        self._settings: Settings | None = None
        self._registry: ServiceRegistry | None = None
        self._lifecycle: LifecycleManager | None = None
        self._health_validator = HealthValidator()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> ApplicationState:
        """Current lifecycle state."""
        return self._state

    @property
    def settings(self) -> Settings:
        """
        The loaded application settings.

        Raises:
            RuntimeError: If accessed before startup() completes.
        """
        if self._settings is None:
            raise RuntimeError("Settings not available before startup.")
        return self._settings

    @property
    def registry(self) -> ServiceRegistry:
        """
        The service registry.

        Raises:
            RuntimeError: If accessed before startup() completes.
        """
        if self._registry is None:
            raise RuntimeError("Registry not available before startup.")
        return self._registry

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def startup(self) -> None:
        """
        Execute the full application startup sequence.

        Sequence:
            1. Load configuration.
            2. Initialise logging.
            3. Create service registry.
            4. Run health validation.
            5. Start lifecycle services.

        Raises:
            StartupError: If any step fails.
        """
        if self._state is not ApplicationState.CREATED:
            raise StartupError(
                f"Cannot start application in state '{self._state.name}'."
            )

        self._state = ApplicationState.STARTING

        try:
            self._load_configuration()
            self._initialise_logging()
            self._create_registry()
            self._validate_health()
            self._start_lifecycle()
            self._register_signal_handlers()
        except Exception as exc:
            self._state = ApplicationState.FAILED
            # Log if logging was initialised before the failure.
            if logging.getLogger().handlers:
                log.critical("Startup failed: %s", exc, exc_info=True)
            raise StartupError(f"Application startup failed: {exc}") from exc

        self._state = ApplicationState.RUNNING
        log.info(
            "%s v%s is running  [environment: %s]",
            self._settings.app_name,  # type: ignore[union-attr]
            self._settings.version,   # type: ignore[union-attr]
            self._settings.environment,  # type: ignore[union-attr]
        )

    def shutdown(self) -> None:
        """
        Execute a graceful shutdown sequence.

        Can be called from RUNNING or FAILED state.  Subsequent calls after
        reaching STOPPED are silently ignored.
        """
        if self._state is ApplicationState.STOPPED:
            return
        if self._state is ApplicationState.STOPPING:
            return

        self._state = ApplicationState.STOPPING
        log.info("Application shutdown initiated.")

        try:
            if self._lifecycle is not None:
                self._lifecycle.shutdown()
        except Exception as exc:  # noqa: BLE001
            log.error("Error during lifecycle shutdown: %s", exc, exc_info=True)
        finally:
            self._state = ApplicationState.STOPPED
            log.info("Application stopped.")

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "Application":
        self.startup()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> bool:
        self.shutdown()
        # Return False so exceptions propagate normally.
        return False

    # ------------------------------------------------------------------
    # Private startup steps
    # ------------------------------------------------------------------

    def _load_configuration(self) -> None:
        log.debug("Loading configuration...")
        self._settings = get_settings()
        # Logging not yet active — cannot log settings here.

    def _initialise_logging(self) -> None:
        # Settings must be loaded first.
        assert self._settings is not None
        setup_logging(self._settings)
        log.info("Logging ready.")

    def _create_registry(self) -> None:
        log.info("Creating service registry...")
        self._registry = ServiceRegistry()
        self._lifecycle = LifecycleManager()
        log.info("Service registry ready.")

    def _validate_health(self) -> None:
        log.info("Running startup health checks...")
        report = self._health_validator.validate(
            settings=self._settings,
            registry=self._registry,
        )
        if not report.is_ready:
            raise HealthCheckError(
                "Startup health checks failed:\n"
                + "\n".join(f"  - {issue}" for issue in report.issues)
            )
        log.info("Health checks passed — status: %s", report.status.value)

    def _start_lifecycle(self) -> None:
        assert self._lifecycle is not None
        self._lifecycle.startup()

    def _register_signal_handlers(self) -> None:
        """
        Wire SIGINT and SIGTERM to a graceful shutdown.

        On Windows, SIGTERM is not reliably delivered by the OS, but we
        still register it so it works in test environments that send it
        programmatically.
        """
        def _handle_signal(signum: int, frame: object) -> None:
            sig_name = signal.Signals(signum).name
            log.info("Signal received: %s — initiating graceful shutdown.", sig_name)
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, _handle_signal)
        try:
            signal.signal(signal.SIGTERM, _handle_signal)
        except (OSError, ValueError):
            # SIGTERM may not be available in all environments (e.g. some CI).
            log.debug("SIGTERM handler could not be registered — skipping.")

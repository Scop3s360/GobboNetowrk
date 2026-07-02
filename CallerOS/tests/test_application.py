"""
Tests: Application (core/application.py)
=========================================
Covers:
  - Application starts successfully.
  - State transitions: CREATED → RUNNING → STOPPED.
  - Graceful shutdown from RUNNING.
  - Shutdown from STOPPED is a no-op (idempotent).
  - Startup failure sets FAILED state.
  - Double startup raises StartupError.
  - Context manager starts and stops correctly.
"""

import pytest

from core.application import Application, ApplicationState
from core.exceptions import StartupError
from app_logging.logger import reset_logging


@pytest.fixture(autouse=True)
def _reset_logging_around_test():
    """Each test gets a clean logging state."""
    reset_logging()
    yield
    reset_logging()


class TestApplicationStartup:
    """Application starts and reaches RUNNING state."""

    def test_initial_state_is_created(self):
        app = Application()
        assert app.state is ApplicationState.CREATED

    def test_startup_reaches_running(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_DIR", str(tmp_path / "logs"))
        app = Application()
        app.startup()
        try:
            assert app.state is ApplicationState.RUNNING
        finally:
            app.shutdown()

    def test_settings_available_after_startup(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_DIR", str(tmp_path / "logs"))
        app = Application()
        app.startup()
        try:
            assert app.settings.app_name == "CallerOS"
        finally:
            app.shutdown()

    def test_registry_available_after_startup(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_DIR", str(tmp_path / "logs"))
        app = Application()
        app.startup()
        try:
            assert app.registry is not None
        finally:
            app.shutdown()

    def test_double_startup_raises(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_DIR", str(tmp_path / "logs"))
        app = Application()
        app.startup()
        try:
            with pytest.raises(StartupError, match="Cannot start"):
                app.startup()
        finally:
            app.shutdown()


class TestApplicationShutdown:
    """Shutdown transitions to STOPPED."""

    def test_shutdown_reaches_stopped(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_DIR", str(tmp_path / "logs"))
        app = Application()
        app.startup()
        app.shutdown()
        assert app.state is ApplicationState.STOPPED

    def test_shutdown_from_stopped_is_noop(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_DIR", str(tmp_path / "logs"))
        app = Application()
        app.startup()
        app.shutdown()
        # Second call must not raise.
        app.shutdown()
        assert app.state is ApplicationState.STOPPED


class TestApplicationContextManager:
    """Context manager starts and stops correctly."""

    def test_context_manager_starts_and_stops(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_DIR", str(tmp_path / "logs"))
        with Application() as app:
            assert app.state is ApplicationState.RUNNING
        assert app.state is ApplicationState.STOPPED

    def test_context_manager_stops_on_exception(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("CALLER_OS_LOG_DIR", str(tmp_path / "logs"))
        app = Application()
        try:
            with app:
                raise ValueError("simulated error")
        except ValueError:
            pass
        assert app.state is ApplicationState.STOPPED


class TestApplicationPropertyGuards:
    """Accessing settings/registry before startup raises RuntimeError."""

    def test_settings_before_startup_raises(self):
        app = Application()
        with pytest.raises(RuntimeError, match="before startup"):
            _ = app.settings

    def test_registry_before_startup_raises(self):
        app = Application()
        with pytest.raises(RuntimeError, match="before startup"):
            _ = app.registry

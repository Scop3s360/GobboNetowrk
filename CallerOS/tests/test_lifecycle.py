"""
Tests: Lifecycle Manager (core/lifecycle.py)
============================================
Covers:
  - Services start in registration order.
  - Services stop in reverse (LIFO) order.
  - Failed start raises StartupError.
  - Failed stop raises ShutdownError (but all services still get stop()).
  - Non-protocol objects are rejected.
"""

import pytest

from core.exceptions import ShutdownError, StartupError
from core.lifecycle import LifecycleManager


class _RecordingService:
    """Records start/stop calls for order verification."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.events: list[str] = []

    def start(self) -> None:
        self.events.append(f"{self.name}.start")

    def stop(self) -> None:
        self.events.append(f"{self.name}.stop")


class _FailingStartService:
    def start(self) -> None:
        raise RuntimeError("start failed")

    def stop(self) -> None:
        pass


class _FailingStopService:
    def start(self) -> None:
        pass

    def stop(self) -> None:
        raise RuntimeError("stop failed")


class TestStartupOrder:
    """Services start in the order they were added."""

    def test_single_service_starts(self):
        manager = LifecycleManager()
        svc = _RecordingService("a")
        manager.add(svc)
        manager.startup()
        assert "a.start" in svc.events

    def test_two_services_start_in_order(self):
        order: list[str] = []

        class _Ordered:
            def __init__(self, tag: str) -> None:
                self._tag = tag

            def start(self) -> None:
                order.append(self._tag)

            def stop(self) -> None:
                pass

        manager = LifecycleManager()
        manager.add(_Ordered("first"))
        manager.add(_Ordered("second"))
        manager.startup()
        assert order == ["first", "second"]


class TestShutdownOrder:
    """Services stop in LIFO order."""

    def test_lifo_shutdown(self):
        order: list[str] = []

        class _Ordered:
            def __init__(self, tag: str) -> None:
                self._tag = tag

            def start(self) -> None:
                pass

            def stop(self) -> None:
                order.append(self._tag)

        manager = LifecycleManager()
        manager.add(_Ordered("first"))
        manager.add(_Ordered("second"))
        manager.startup()
        manager.shutdown()
        assert order == ["second", "first"]


class TestFailedStartup:
    """Failing start raises StartupError."""

    def test_failed_service_raises_startup_error(self):
        manager = LifecycleManager()
        manager.add(_FailingStartService())
        with pytest.raises(StartupError, match="failed to start"):
            manager.startup()


class TestFailedShutdown:
    """Failing stop raises ShutdownError; all services still get stop()."""

    def test_failed_stop_raises_shutdown_error(self):
        manager = LifecycleManager()
        manager.add(_FailingStopService())
        manager.startup()
        with pytest.raises(ShutdownError, match="did not shut down cleanly"):
            manager.shutdown()

    def test_all_services_stopped_even_on_partial_failure(self):
        stopped: list[str] = []

        class _GoodStop:
            def start(self) -> None:
                pass

            def stop(self) -> None:
                stopped.append("good")

        manager = LifecycleManager()
        manager.add(_FailingStopService())
        manager.add(_GoodStop())
        manager.startup()

        with pytest.raises(ShutdownError):
            manager.shutdown()

        # The good service must still have been stopped.
        assert "good" in stopped


class TestProtocolEnforcement:
    """Non-protocol objects are rejected at add() time."""

    def test_non_protocol_raises(self):
        manager = LifecycleManager()
        with pytest.raises(StartupError, match="does not implement"):
            manager.add("not a service")  # type: ignore[arg-type]

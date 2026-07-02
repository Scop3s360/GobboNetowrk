"""
Tests: Service Registry (core/service_registry.py)
===================================================
Covers:
  - Register a service and resolve it.
  - Duplicate registration raises ServiceRegistrationError.
  - Resolving an unregistered service raises ServiceNotFoundError.
  - is_registered() returns correct boolean.
  - registered_names() returns sorted list.
  - deregister() removes a service.
  - clear() empties the registry.
"""

import pytest

from core.exceptions import ServiceNotFoundError, ServiceRegistrationError
from core.service_registry import ServiceRegistry


class _FakeService:
    """Minimal stand-in service for testing."""

    def __init__(self, value: str = "ok") -> None:
        self.value = value


class TestServiceRegistration:
    """Happy-path registration and resolution."""

    def test_register_and_get(self):
        registry = ServiceRegistry()
        svc = _FakeService("hello")
        registry.register("svc", svc)
        assert registry.get("svc") is svc

    def test_get_returns_correct_instance(self):
        registry = ServiceRegistry()
        a = _FakeService("a")
        b = _FakeService("b")
        registry.register("a", a)
        registry.register("b", b)
        assert registry.get("a") is a
        assert registry.get("b") is b

    def test_is_registered_true(self):
        registry = ServiceRegistry()
        registry.register("x", _FakeService())
        assert registry.is_registered("x") is True

    def test_is_registered_false(self):
        registry = ServiceRegistry()
        assert registry.is_registered("missing") is False

    def test_registered_names_sorted(self):
        registry = ServiceRegistry()
        registry.register("beta", _FakeService())
        registry.register("alpha", _FakeService())
        assert registry.registered_names() == ["alpha", "beta"]

    def test_register_non_object_value(self):
        """Registry should accept any Python value, including primitives."""
        registry = ServiceRegistry()
        registry.register("answer", 42)
        assert registry.get("answer") == 42


class TestDuplicateRegistration:
    """Duplicate names are rejected."""

    def test_duplicate_raises(self):
        registry = ServiceRegistry()
        registry.register("svc", _FakeService())
        with pytest.raises(ServiceRegistrationError, match="already registered"):
            registry.register("svc", _FakeService())

    def test_duplicate_does_not_overwrite(self):
        registry = ServiceRegistry()
        original = _FakeService("original")
        registry.register("svc", original)
        with pytest.raises(ServiceRegistrationError):
            registry.register("svc", _FakeService("replacement"))
        # Original is still in place.
        assert registry.get("svc") is original


class TestMissingService:
    """Resolving an absent service raises ServiceNotFoundError."""

    def test_get_missing_raises(self):
        registry = ServiceRegistry()
        with pytest.raises(ServiceNotFoundError, match="not registered"):
            registry.get("ghost")

    def test_error_message_includes_registered_names(self):
        registry = ServiceRegistry()
        registry.register("real_service", _FakeService())
        with pytest.raises(ServiceNotFoundError, match="real_service"):
            registry.get("ghost")


class TestDeregister:
    """Deregistration removes services without errors."""

    def test_deregister_removes_service(self):
        registry = ServiceRegistry()
        registry.register("svc", _FakeService())
        registry.deregister("svc")
        assert not registry.is_registered("svc")

    def test_deregister_missing_is_silent(self):
        registry = ServiceRegistry()
        # Should not raise.
        registry.deregister("does_not_exist")


class TestClear:
    """clear() empties the registry."""

    def test_clear_removes_all(self):
        registry = ServiceRegistry()
        registry.register("a", _FakeService())
        registry.register("b", _FakeService())
        registry.clear()
        assert registry.registered_names() == []

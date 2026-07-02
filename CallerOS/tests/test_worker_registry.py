"""
Tests: WorkerRegistry (workers/registry.py)
============================================
Covers:
  - Register a worker and retrieve it by id.
  - Duplicate registration raises WorkerAlreadyRegisteredError.
  - get() for an unknown id raises WorkerNotFoundError.
  - Error message for missing worker includes registered ids.
  - unregister() removes a worker.
  - unregister() of an unknown id is silent (no exception).
  - list_workers() returns sorted list of all workers.
  - is_registered() returns correct boolean.
  - len() reflects the count of registered workers.
  - clear() empties the registry.
  - Iteration yields workers in id order.
"""

from __future__ import annotations

import pytest

from workers.exceptions import WorkerAlreadyRegisteredError, WorkerNotFoundError
from workers.registry import WorkerRegistry


class TestWorkerRegistration:
    def test_register_and_get(self, dummy_worker):
        registry = WorkerRegistry()
        registry.register(dummy_worker)
        retrieved = registry.get(dummy_worker.id)
        assert retrieved is dummy_worker

    def test_is_registered_true(self, dummy_worker):
        registry = WorkerRegistry()
        registry.register(dummy_worker)
        assert registry.is_registered(dummy_worker.id) is True

    def test_is_registered_false_for_unknown(self):
        registry = WorkerRegistry()
        assert registry.is_registered("nonexistent") is False

    def test_len_reflects_count(self, dummy_worker):
        registry = WorkerRegistry()
        assert len(registry) == 0
        registry.register(dummy_worker)
        assert len(registry) == 1

    def test_register_multiple_workers(self):
        from tests.conftest import DummyWorker

        registry = WorkerRegistry()
        a = DummyWorker(worker_id="a")
        b = DummyWorker(worker_id="b")
        registry.register(a)
        registry.register(b)
        assert len(registry) == 2
        assert registry.get("a") is a
        assert registry.get("b") is b


class TestDuplicateRegistration:
    def test_duplicate_raises(self, dummy_worker):
        registry = WorkerRegistry()
        registry.register(dummy_worker)
        with pytest.raises(WorkerAlreadyRegisteredError, match="already registered"):
            registry.register(dummy_worker)

    def test_duplicate_does_not_overwrite(self):
        from tests.conftest import DummyWorker

        registry = WorkerRegistry()
        original = DummyWorker(worker_id="same-id")
        registry.register(original)

        replacement = DummyWorker(worker_id="same-id")
        with pytest.raises(WorkerAlreadyRegisteredError):
            registry.register(replacement)

        # Original must still be in place.
        assert registry.get("same-id") is original


class TestWorkerNotFound:
    def test_get_unknown_raises(self):
        registry = WorkerRegistry()
        with pytest.raises(WorkerNotFoundError, match="No worker registered"):
            registry.get("ghost")

    def test_error_message_includes_registered_ids(self, dummy_worker):
        registry = WorkerRegistry()
        registry.register(dummy_worker)
        with pytest.raises(WorkerNotFoundError, match="dummy-01"):
            registry.get("ghost")


class TestUnregister:
    def test_unregister_removes_worker(self, dummy_worker):
        registry = WorkerRegistry()
        registry.register(dummy_worker)
        registry.unregister(dummy_worker.id)
        assert not registry.is_registered(dummy_worker.id)

    def test_unregister_unknown_is_silent(self):
        registry = WorkerRegistry()
        # Must not raise.
        registry.unregister("does-not-exist")

    def test_len_after_unregister(self, dummy_worker):
        registry = WorkerRegistry()
        registry.register(dummy_worker)
        registry.unregister(dummy_worker.id)
        assert len(registry) == 0


class TestListWorkers:
    def test_empty_registry_returns_empty_list(self):
        registry = WorkerRegistry()
        assert registry.list_workers() == []

    def test_list_workers_sorted_by_id(self):
        from tests.conftest import DummyWorker

        registry = WorkerRegistry()
        registry.register(DummyWorker(worker_id="charlie"))
        registry.register(DummyWorker(worker_id="alpha"))
        registry.register(DummyWorker(worker_id="bravo"))

        ids = [w.id for w in registry.list_workers()]
        assert ids == ["alpha", "bravo", "charlie"]

    def test_list_workers_returns_copy(self, dummy_worker):
        """Mutating the returned list must not affect the registry."""
        registry = WorkerRegistry()
        registry.register(dummy_worker)
        workers = registry.list_workers()
        workers.clear()
        assert len(registry) == 1


class TestClear:
    def test_clear_empties_registry(self):
        from tests.conftest import DummyWorker

        registry = WorkerRegistry()
        registry.register(DummyWorker(worker_id="a"))
        registry.register(DummyWorker(worker_id="b"))
        registry.clear()
        assert len(registry) == 0

    def test_clear_then_register_works(self, dummy_worker):
        registry = WorkerRegistry()
        registry.register(dummy_worker)
        registry.clear()
        # Should be able to register the same id again after clearing.
        registry.register(dummy_worker)
        assert len(registry) == 1


class TestIteration:
    def test_iterate_yields_workers_in_id_order(self):
        from tests.conftest import DummyWorker

        registry = WorkerRegistry()
        registry.register(DummyWorker(worker_id="z-last"))
        registry.register(DummyWorker(worker_id="a-first"))

        ids = [w.id for w in registry]
        assert ids == ["a-first", "z-last"]

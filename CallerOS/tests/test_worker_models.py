"""
Tests: Worker Models (workers/models.py)
=========================================
Covers:
  - WorkerRequest auto-generates request_id and created_at.
  - WorkerRequest stores worker_id, payload, metadata correctly.
  - WorkerRequest is immutable.
  - WorkerResponse stores all fields.
  - WorkerResponse is immutable.
  - Default field values on WorkerResponse.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from workers.models import WorkerRequest, WorkerResponse


class TestWorkerRequest:
    """WorkerRequest construction and immutability."""

    def test_required_fields_stored(self):
        req = WorkerRequest(worker_id="w1", payload="hello")
        assert req.worker_id == "w1"
        assert req.payload == "hello"

    def test_auto_request_id_is_valid_uuid(self):
        req = WorkerRequest(worker_id="w1", payload=None)
        # Should not raise.
        parsed = uuid.UUID(req.request_id)
        assert str(parsed) == req.request_id

    def test_two_requests_have_different_ids(self):
        a = WorkerRequest(worker_id="w1", payload=None)
        b = WorkerRequest(worker_id="w1", payload=None)
        assert a.request_id != b.request_id

    def test_explicit_request_id_preserved(self):
        req = WorkerRequest(worker_id="w1", payload=None, request_id="my-id")
        assert req.request_id == "my-id"

    def test_created_at_is_utc_iso8601(self):
        req = WorkerRequest(worker_id="w1", payload=None)
        # datetime.fromisoformat() will raise if the string is malformed.
        dt = datetime.fromisoformat(req.created_at)
        assert dt.tzinfo is not None  # must be timezone-aware

    def test_default_metadata_is_empty_dict(self):
        req = WorkerRequest(worker_id="w1", payload=None)
        assert req.metadata == {}

    def test_custom_metadata_stored(self):
        req = WorkerRequest(worker_id="w1", payload=None, metadata={"tag": "test"})
        assert req.metadata["tag"] == "test"

    def test_immutable(self):
        req = WorkerRequest(worker_id="w1", payload=None)
        with pytest.raises((AttributeError, TypeError)):
            req.worker_id = "changed"  # type: ignore[misc]

    def test_payload_can_be_any_type(self):
        for payload in [None, 42, {"key": "val"}, [1, 2, 3]]:
            req = WorkerRequest(worker_id="w1", payload=payload)
            assert req.payload == payload


class TestWorkerResponse:
    """WorkerResponse construction and immutability."""

    def test_minimum_fields(self):
        resp = WorkerResponse(request_id="req-1", success=True)
        assert resp.request_id == "req-1"
        assert resp.success is True

    def test_success_false(self):
        resp = WorkerResponse(request_id="req-1", success=False, error="oops")
        assert resp.success is False
        assert resp.error == "oops"

    def test_default_result_is_none(self):
        resp = WorkerResponse(request_id="req-1", success=True)
        assert resp.result is None

    def test_default_error_is_none(self):
        resp = WorkerResponse(request_id="req-1", success=True)
        assert resp.error is None

    def test_default_duration_ms_is_zero(self):
        resp = WorkerResponse(request_id="req-1", success=True)
        assert resp.duration_ms == 0.0

    def test_default_metadata_is_empty(self):
        resp = WorkerResponse(request_id="req-1", success=True)
        assert resp.metadata == {}

    def test_explicit_fields(self):
        resp = WorkerResponse(
            request_id="r1",
            success=True,
            result="done",
            error=None,
            metadata={"source": "test"},
            duration_ms=12.5,
        )
        assert resp.result == "done"
        assert resp.metadata["source"] == "test"
        assert resp.duration_ms == 12.5

    def test_immutable(self):
        resp = WorkerResponse(request_id="r1", success=True)
        with pytest.raises((AttributeError, TypeError)):
            resp.success = False  # type: ignore[misc]

from __future__ import annotations

import logging
import pytest

from workers.base_worker import WorkerStatus
from workers.manager import WorkerManager
from workers.models import WorkerRequest, WorkerResponse
from workers.registry import WorkerRegistry
from workers.developer.models import DeveloperRequest, DeveloperResult
from workers.developer.worker import DeveloperWorker

_GOOD_DEVELOPER_RESPONSE = """\
EXPLANATION:
This is a simple player controller that moves gameobjects.

CODE:
```csharp
using UnityEngine;
public class Player : MonoBehaviour {}
```

NOTES:
- Attach to a Unity GameObject.
"""

class MockDeveloperAIClient:
    def __init__(self, response: str = _GOOD_DEVELOPER_RESPONSE) -> None:
        self._response = response
        self.call_count = 0
        self.last_system_prompt: str = ""
        self.last_user_message: str = ""

    def complete(self, system_prompt: str, user_message: str) -> str:
        self.call_count += 1
        self.last_system_prompt = system_prompt
        self.last_user_message = user_message
        return self._response

@pytest.fixture()
def mock_client() -> MockDeveloperAIClient:
    return MockDeveloperAIClient()

@pytest.fixture()
def developer_worker(mock_client) -> DeveloperWorker:
    return DeveloperWorker(ai_client=mock_client)

@pytest.fixture()
def idle_developer_worker(mock_client) -> DeveloperWorker:
    w = DeveloperWorker(ai_client=mock_client)
    w.initialize()
    return w

def _make_request(prompt: str = "Create a player movement script") -> WorkerRequest:
    return WorkerRequest(
        worker_id="developer-worker-v1",
        payload=DeveloperRequest(prompt=prompt)
    )

class TestDeveloperWorkerIdentity:
    def test_id(self, developer_worker):
        assert developer_worker.id == "developer-worker-v1"

    def test_name(self, developer_worker):
        assert developer_worker.name == "Developer Worker"

    def test_capabilities(self, developer_worker):
        assert "programming" in developer_worker.capabilities

class TestDeveloperWorkerExecution:
    def test_execute_success(self, idle_developer_worker):
        response = idle_developer_worker.execute(_make_request())
        assert response.success is True
        assert isinstance(response.result, DeveloperResult)
        assert response.result.explanation != ""
        assert "UnityEngine" in response.result.code
        assert response.result.notes != ""

class TestDeveloperWorkerIntegration:
    def test_registry_and_manager(self, mock_client):
        worker = DeveloperWorker(ai_client=mock_client)
        registry = WorkerRegistry()
        registry.register(worker)
        manager = WorkerManager(registry)

        manager.initialize_all()
        req = _make_request()
        response = manager.execute("developer-worker-v1", req)

        assert response.success is True
        assert isinstance(response.result, DeveloperResult)
        
        manager.shutdown_all()
        assert worker.status is WorkerStatus.STOPPED

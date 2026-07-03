from __future__ import annotations

import logging
from workers.base_worker import BaseWorker
from workers.models import WorkerRequest, WorkerResponse
from workers.research.client import AIClient, AIClientError
from workers.developer.models import DeveloperRequest, DeveloperResult
from workers.developer.parser import parse_developer_response

log = logging.getLogger(__name__)

_WORKER_ID = "developer-worker-v1"
_WORKER_NAME = "Developer Worker"
_WORKER_DESCRIPTION = (
    "Accepts a coding request and returns structured code, explanation, and notes."
)
_WORKER_VERSION = "1.0.0"
_WORKER_CAPABILITIES = ["programming", "code-generation", "refactoring"]

SYSTEM_PROMPT = """You are CallerOS Developer Assistant. Your goal is to write clean, correct, and well-commented code that implements the requested programming task.

You must respond in exactly this format, using the section headers in uppercase:

EXPLANATION:
<A concise explanation of the implementation details, how the code works, and any key concepts.>

CODE:
```csharp
<The code implementation block. Ensure it is complete, correct, and does not use placeholders.>
```

NOTES:
<Any additional implementation notes, setup instructions, best practices, or prerequisites.>
"""

class DeveloperWorker(BaseWorker):
    """
    Answers coding queries using an injected AI client.
    """
    def __init__(self, ai_client: AIClient) -> None:
        super().__init__(
            worker_id=_WORKER_ID,
            name=_WORKER_NAME,
            description=_WORKER_DESCRIPTION,
            version=_WORKER_VERSION,
            capabilities=_WORKER_CAPABILITIES,
        )
        self._ai_client = ai_client

    def _initialize(self) -> None:
        log.info("DeveloperWorker initialized: id=%s", self.id)

    def _execute(self, request: WorkerRequest) -> WorkerResponse:
        log.info("DeveloperWorker executing request_id=%s", request.request_id)
        
        payload = request.payload
        prompt = ""
        if isinstance(payload, DeveloperRequest):
            prompt = payload.prompt
        elif isinstance(payload, str):
            prompt = payload
        else:
            prompt = str(payload)

        system_prompt = SYSTEM_PROMPT
        user_message = f"Programming Task:\n{prompt}"

        try:
            log.info("DeveloperWorker: Calling AI client...")
            response = self._ai_client.complete(system_prompt, user_message)
            log.info("DeveloperWorker: AI client returned response of length=%d chars", len(response))
            
            result = parse_developer_response(response)
            
            return WorkerResponse(
                request_id=request.request_id,
                success=True,
                result=result
            )
        except Exception as exc:
            log.error("DeveloperWorker: Request execution failed: %s", exc)
            return WorkerResponse(
                request_id=request.request_id,
                success=False,
                error=str(exc)
            )

    def _shutdown(self) -> None:
        log.info("DeveloperWorker stopped: id=%s", self.id)

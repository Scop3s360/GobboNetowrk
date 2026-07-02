"""
Research Worker
===============
Concrete implementation of BaseWorker that answers research queries.

Responsibilities (exactly these, nothing more):
    1. Validate the incoming payload as a ResearchRequest.
    2. Build the system and user prompts.
    3. Call the AI client.
    4. Parse the raw response into a ResearchResult.
    5. Wrap the result in a WorkerResponse.
    6. Handle errors using the existing exception hierarchy.

What this worker does NOT do:
    - Remember previous conversations (no memory).
    - Call other workers or the Director.
    - Write files or execute shell commands.
    - Make decisions about routing.
    - Perform software development tasks.

Architectural decisions:

    Dependency injection for the AI client:
        The AI client is injected at construction time rather than created
        internally.  This keeps the worker testable in isolation — tests pass
        a mock client, production code passes an OpenAIClient.

    Validation returns a WorkerResponse on failure:
        Rather than raising on invalid input (which would trigger the
        BaseWorker's FAILED state), the worker catches validation problems
        early in _execute() and returns a WorkerResponse(success=False).
        This lets the caller inspect the error without the worker becoming
        permanently unavailable.

    AI errors also return WorkerResponse(success=False):
        API failures (timeouts, auth errors, rate limits) are transient.
        Returning a failure response rather than raising keeps the worker
        in IDLE state, ready to retry.  A permanent crash is reserved for
        truly fatal conditions (e.g. missing dependencies detected during
        initialize()).

    Parser is always called:
        Even if the AI returns an empty or malformed response, the parser
        is called.  The parser's defensive design ensures a ResearchResult
        is always produced, which is then wrapped in WorkerResponse.
"""

from __future__ import annotations

import logging

from workers.base_worker import BaseWorker
from workers.models import WorkerRequest, WorkerResponse
from workers.research.client import AIClient, AIClientError
from workers.research.models import ResearchRequest, ResearchResult
from workers.research.parser import parse_response
from workers.research.prompts import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)

_WORKER_ID = "research-worker-v1"
_WORKER_NAME = "Research Worker"
_WORKER_DESCRIPTION = (
    "Accepts a research query and returns structured findings from an AI model."
)
_WORKER_VERSION = "1.0.0"
_WORKER_CAPABILITIES = ["research", "question-answering", "summarisation"]


class ResearchWorker(BaseWorker):
    """
    Answers research queries using an injected AI client.

    Args:
        ai_client: Any object satisfying the AIClient protocol.
                   Pass an OpenAIClient for production; pass a mock for tests.

    Example::

        from workers.research.client import OpenAIClient
        from workers.research.worker import ResearchWorker
        from workers.research.models import ResearchRequest
        from workers.models import WorkerRequest

        client = OpenAIClient()
        worker = ResearchWorker(ai_client=client)
        worker.initialize()

        request = WorkerRequest(
            worker_id=worker.id,
            payload=ResearchRequest(research_query="What is Python?"),
        )
        response = worker.execute(request)
        result: ResearchResult = response.result
    """

    def __init__(self, ai_client: AIClient) -> None:
        super().__init__(
            worker_id=_WORKER_ID,
            name=_WORKER_NAME,
            description=_WORKER_DESCRIPTION,
            version=_WORKER_VERSION,
            capabilities=_WORKER_CAPABILITIES,
        )
        # Stored as-is — no validation needed here because the AIClient
        # Protocol is @runtime_checkable only for debugging convenience.
        self._ai_client = ai_client

    # ------------------------------------------------------------------
    # BaseWorker hooks
    # ------------------------------------------------------------------

    def _initialize(self) -> None:
        """
        Verify that the AI client is present.

        The worker has no resources of its own to open (no DB, no file handles).
        We log readiness and nothing more.
        """
        log.info(
            "ResearchWorker ready: id=%s  client=%s",
            self.id, type(self._ai_client).__name__,
        )

    def _execute(self, request: WorkerRequest) -> WorkerResponse:
        """
        Process a research request end-to-end.

        Sequence:
            1. Validate payload → ResearchRequest.
            2. Build prompts.
            3. Call AI client.
            4. Parse response.
            5. Return WorkerResponse with ResearchResult.

        On validation or AI errors, returns WorkerResponse(success=False)
        rather than raising, so the worker remains IDLE and reusable.
        """
        log.info(
            "ResearchWorker executing: request_id=%s", request.request_id
        )

        # 1. Validate payload.
        research_request = self._validate_payload(request)
        if research_request is None:
            return WorkerResponse(
                request_id=request.request_id,
                success=False,
                error=(
                    "Invalid payload: expected a ResearchRequest with a "
                    "non-empty research_query."
                ),
            )

        log.info(
            "ResearchWorker: query=%r  request_id=%s",
            research_request.research_query, request.request_id,
        )

        # 2. Build prompts.
        user_message = build_user_prompt(research_request)

        # 3. Call AI client.
        raw_response, error_msg = self._call_ai(request.request_id, user_message)
        if raw_response is None:
            return WorkerResponse(
                request_id=request.request_id,
                success=False,
                error=error_msg or "AI client returned no response.",
            )

        # 4. Parse the response.
        result = parse_response(raw_response)

        log.info(
            "ResearchWorker: findings=%d  confidence=%.2f  request_id=%s",
            len(result.findings), result.confidence, request.request_id,
        )

        # 5. Return success.
        return WorkerResponse(
            request_id=request.request_id,
            success=True,
            result=result,
            metadata={
                "findings_count": len(result.findings),
                "sources_count": len(result.sources),
                "confidence": result.confidence,
            },
        )

    def _shutdown(self) -> None:
        """
        Release any resources held by the worker.

        The AI client is stateless (HTTP connections are managed by the SDK),
        so there is nothing to close.  We log the shutdown for observability.
        """
        log.info("ResearchWorker shutting down: id=%s", self.id)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _validate_payload(self, request: WorkerRequest) -> ResearchRequest | None:
        """
        Cast and validate the request payload.

        Returns:
            A validated ResearchRequest, or None if the payload is invalid.
        """
        payload = request.payload
        if not isinstance(payload, ResearchRequest):
            log.warning(
                "ResearchWorker: payload is %s, expected ResearchRequest  "
                "request_id=%s",
                type(payload).__name__, request.request_id,
            )
            return None

        if not payload.research_query or not payload.research_query.strip():
            log.warning(
                "ResearchWorker: empty research_query  request_id=%s",
                request.request_id,
            )
            return None

        return payload

    def _call_ai(self, request_id: str, user_message: str) -> tuple[str | None, str | None]:
        """
        Call the AI client and return (response_text, error_message).
        """
        try:
            res = self._ai_client.complete(
                system_prompt=SYSTEM_PROMPT,
                user_message=user_message,
            )
            return res, None
        except AIClientError as exc:
            log.error(
                "ResearchWorker: AI client error  request_id=%s  error=%s",
                request_id, exc,
            )
            return None, str(exc)
        except Exception as exc:  # noqa: BLE001
            # Catch unexpected errors (e.g. network issues not wrapped by SDK).
            log.error(
                "ResearchWorker: unexpected AI error  request_id=%s  error=%s",
                request_id, exc, exc_info=True,
            )
            return None, f"Unexpected AI error: {exc}"

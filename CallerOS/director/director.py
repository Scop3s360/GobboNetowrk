"""
Director Agent
==============
The orchestrator coordinating worker selection, execution, and memory storage.
"""

import logging
import time

from director.interfaces import Dispatcher, Router
from director.models import DirectorRequest, DirectorResponse
from memory.exceptions import MemoryError
from memory.manager import MemoryManager
from memory.models import MemoryRecord, MemoryType
from workers.exceptions import WorkerError

log = logging.getLogger(__name__)


class Director:
    """
    Main orchestrator agent that manages the workflow.
    """

    def __init__(
        self,
        router: Router,
        dispatcher: Dispatcher,
        memory_manager: MemoryManager | None = None,
    ) -> None:
        """
        Initialize the Director.

        Args:
            router:         The Router implementation.
            dispatcher:     The Dispatcher implementation.
            memory_manager: Optional MemoryManager to persist conversation history.
        """
        self._router = router
        self._dispatcher = dispatcher
        self._memory_manager = memory_manager

    def execute(self, request: DirectorRequest) -> DirectorResponse:
        """
        Coordinate the request end-to-end.

        Args:
            request: The user's DirectorRequest.

        Returns:
            A DirectorResponse with results or error.
        """
        log.info("Director: user request received. query=%r", request.query)
        start_time = time.perf_counter()
        
        try:
            # 1. Analyze request & Select worker
            decision = self._router.route(request)
            log.info("Director: worker selected=%s (reason: %s)", decision.worker_id, decision.reason)
            
            # 2. Dispatch worker
            log.info("Director: dispatch started to worker=%s", decision.worker_id)
            worker_response = self._dispatcher.dispatch(decision, request)
            log.info("Director: dispatch completed. success=%s", worker_response.success)
            
            if not worker_response.success:
                error_msg = worker_response.error or "Worker execution failed without error details."
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                log.error("Director: worker failed. error=%s", error_msg)
                return DirectorResponse(
                    success=False,
                    error=f"Worker failure ({decision.worker_id}): {error_msg}",
                    duration_ms=elapsed_ms,
                )
            
            # 3. Store conversation memory if MemoryManager is configured
            if self._memory_manager is not None:
                log.info("Director: storing conversation to memory.")
                content = (
                    f"User Query: {request.query}\n"
                    f"Worker Response ({decision.worker_id}): {worker_response.result}"
                )
                memory_rec = MemoryRecord(
                    type=MemoryType.CONVERSATION,
                    content=content,
                    source="Director",
                    tags=[decision.worker_id, "conversation"],
                    project=str(request.metadata.get("project", "default")),
                    agent="Director",
                )
                try:
                    self._memory_manager.create_memory(memory_rec)
                    log.info("Director: memory stored. id=%s", memory_rec.id)
                except MemoryError as exc:
                    log.error("Director: memory storage failed. error=%s", exc)
                    # Handle memory failure gracefully without crashing the response
                    # (since worker execution itself was successful)
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return DirectorResponse(
                success=True,
                result=worker_response.result,
                duration_ms=elapsed_ms,
            )
            
        except WorkerError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            log.error("Director: worker exception caught: %s", exc, exc_info=True)
            return DirectorResponse(
                success=False,
                error=f"Worker dispatcher exception: {exc}",
                duration_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            log.error("Director: unexpected exception: %s", exc, exc_info=True)
            return DirectorResponse(
                success=False,
                error=f"Director orchestration error: {exc}",
                duration_ms=elapsed_ms,
            )

"""
Worker Dispatcher
=================
Dispatches queries to the Worker Framework using the WorkerManager.
"""

from __future__ import annotations
import logging

from context.engine import ContextEngine
from director.interfaces import Dispatcher
from director.models import DirectorDecision, DirectorRequest
from workers.manager import WorkerManager
from workers.models import WorkerRequest, WorkerResponse

log = logging.getLogger(__name__)


class WorkerDispatcher(Dispatcher):
    """
    Concrete Dispatcher that executes specialist workers using WorkerManager.
    """

    def __init__(self, worker_manager: WorkerManager, context_engine: ContextEngine | None = None) -> None:
        """
        Initialize the WorkerDispatcher.

        Args:
            worker_manager: The active WorkerManager service.
            context_engine: Optional ContextEngine to inject relevant project context.
        """
        self._worker_manager = worker_manager
        self._context_engine = context_engine

    def dispatch(
        self, decision: DirectorDecision, request: DirectorRequest
    ) -> WorkerResponse:
        log.info(
            "WorkerDispatcher: dispatching query to worker=%s",
            decision.worker_id,
        )

        query = request.query
        
        # Inject project context before calling the worker
        if self._context_engine is not None:
            project_name = self._context_engine.detect_project(query)
            if project_name:
                log.info("WorkerDispatcher: detected project '%s' for request", project_name)
                context_block = self._context_engine.build_context(project_name, query)
                if context_block:
                    query = f"{context_block}\n{query}"
                    log.info("WorkerDispatcher: injected project context. Final query length=%d chars", len(query))

        # Build appropriate payload for the target worker type.
        if decision.worker_id == "research-worker-v1":
            from workers.research.models import ResearchRequest
            payload = ResearchRequest(research_query=query)
        else:
            # Fallback for other workers (e.g. developer-worker-v1 or test dummies)
            payload = query

        # Construct standard WorkerRequest.
        worker_req = WorkerRequest(
            worker_id=decision.worker_id,
            payload=payload,
        )

        # Execute using WorkerManager (propagates WorkerNotFoundError / WorkerExecutionError)
        return self._worker_manager.execute(decision.worker_id, worker_req)

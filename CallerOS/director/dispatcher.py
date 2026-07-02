"""
Worker Dispatcher
=================
Dispatches queries to the Worker Framework using the WorkerManager.
"""

import logging

from director.interfaces import Dispatcher
from director.models import DirectorDecision, DirectorRequest
from workers.manager import WorkerManager
from workers.models import WorkerRequest, WorkerResponse

log = logging.getLogger(__name__)


class WorkerDispatcher(Dispatcher):
    """
    Concrete Dispatcher that executes specialist workers using WorkerManager.
    """

    def __init__(self, worker_manager: WorkerManager) -> None:
        """
        Initialize the WorkerDispatcher.

        Args:
            worker_manager: The active WorkerManager service.
        """
        self._worker_manager = worker_manager

    def dispatch(
        self, decision: DirectorDecision, request: DirectorRequest
    ) -> WorkerResponse:
        log.info(
            "WorkerDispatcher: dispatching query to worker=%s",
            decision.worker_id,
        )

        # Build appropriate payload for the target worker type.
        if decision.worker_id == "research-worker-v1":
            from workers.research.models import ResearchRequest
            payload = ResearchRequest(research_query=request.query)
        else:
            # Fallback for other workers (e.g. developer-worker-v1 or test dummies)
            payload = request.query

        # Construct standard WorkerRequest.
        worker_req = WorkerRequest(
            worker_id=decision.worker_id,
            payload=payload,
        )

        # Execute using WorkerManager (propagates WorkerNotFoundError / WorkerExecutionError)
        return self._worker_manager.execute(decision.worker_id, worker_req)

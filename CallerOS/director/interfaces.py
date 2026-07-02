"""
Director Interfaces
===================
Abstract base classes defining boundaries for Router and Dispatcher services.
"""

from abc import ABC, abstractmethod

from director.models import DirectorDecision, DirectorRequest
from workers.models import WorkerResponse


class Router(ABC):
    """Responsible for analyzing requests and determining which worker to select."""

    @abstractmethod
    def route(self, request: DirectorRequest) -> DirectorDecision:
        """
        Analyze the request and return a routing decision.

        Args:
            request: The incoming DirectorRequest.

        Returns:
            A DirectorDecision specifying the target worker_id and rationale.
        """
        pass


class Dispatcher(ABC):
    """Responsible for executing a worker request based on a routing decision."""

    @abstractmethod
    def dispatch(
        self, decision: DirectorDecision, request: DirectorRequest
    ) -> WorkerResponse:
        """
        Invoke the designated worker via the Worker Framework.

        Args:
            decision: The decision containing the selected worker_id.
            request:  The original DirectorRequest containing the query payload.

        Returns:
            A WorkerResponse from the executed worker.
        """
        pass

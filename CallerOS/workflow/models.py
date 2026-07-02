"""
Workflow Models
===============
Immutable data transfer models representing Workflows and WorkflowSteps.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkflowStep:
    """
    An immutable configuration for a single step within a workflow.

    Attributes:
        id:              Unique identifier for this step.
        worker_name:     The identifier/id of the worker to execute (e.g. 'research-worker-v1').
        input_data:      The inputs passed to this worker.
        timeout_seconds: Maximum time in seconds this step is allowed to run.
        retry_count:     Number of retries allowed on failure.
    """

    id: str
    worker_name: str
    input_data: object
    timeout_seconds: float = 30.0
    retry_count: int = 0


@dataclass(frozen=True)
class Workflow:
    """
    An immutable definition of a sequential workflow.

    Attributes:
        id:    Unique workflow configuration identifier.
        name:  Human-readable description.
        steps: List of WorkflowSteps to run sequentially.
    """

    id: str
    name: str
    steps: list[WorkflowStep] = field(default_factory=list)

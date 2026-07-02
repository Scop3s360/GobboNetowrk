"""
Workflow Result
===============
Immutable model carrying the final outcome of a workflow execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from workflow.state import WorkflowState


@dataclass(frozen=True)
class WorkflowResult:
    """
    Final output and telemetry of a completed or failed workflow.

    Attributes:
        workflow_id:     The configuration identifier of the executed Workflow.
        status:          Final lifecycle state of the workflow (COMPLETED or FAILED).
        completed_steps: List of step IDs that finished successfully.
        failed_step:     The step ID where execution halted on failure, or None.
        execution_time:  Duration of the workflow run in seconds.
        final_output:    Output returned by the final step, or None on failure.
        errors:          List of error strings encountered.
    """

    workflow_id: str
    status: WorkflowState
    completed_steps: list[str] = field(default_factory=list)
    failed_step: str | None = None
    execution_time: float = 0.0
    final_output: object = None
    errors: list[str] = field(default_factory=list)

"""
Workflow Engine
===============
Coordinates workflow validation, context creation, and runner invocation.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from workers.registry import WorkerRegistry
from workflow.context import WorkflowContext
from workflow.exceptions import WorkflowValidationError
from workflow.models import Workflow
from workflow.result import WorkflowResult
from workflow.runner import WorkflowRunner

if TYPE_CHECKING:
    from workflow.executor import StepExecutor

log = logging.getLogger(__name__)


class WorkflowEngine:
    """
    Primary interface for validating and executing sequential workflows.
    """

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        step_executor: StepExecutor,
    ) -> None:
        """
        Initialize the WorkflowEngine.

        Args:
            worker_registry: Registry containing valid, executable workers.
            step_executor:   Executor to run individual steps.
        """
        self._worker_registry = worker_registry
        self._step_executor = step_executor
        self._runner = WorkflowRunner(self._step_executor)

    def start_workflow(
        self, workflow: Workflow, original_request: object
    ) -> WorkflowResult:
        """
        Validate and execute the workflow.

        Args:
            workflow:         The Workflow configuration to execute.
            original_request: Triggering request metadata/input.

        Returns:
            A WorkflowResult summarizing the outcome.

        Raises:
            WorkflowValidationError: If workflow validation fails.
        """
        log.info("WorkflowEngine: starting workflow validation for workflow_id=%s", workflow.id)
        self.validate_workflow(workflow)
        
        # Create execution context
        context = WorkflowContext(original_request=original_request)
        log.info("WorkflowEngine: context created. execution_id=%s", context.execution_id)
        
        # Invoke the runner
        return self._runner.run(workflow, context)

    def validate_workflow(self, workflow: Workflow) -> None:
        """
        Perform checks on a workflow definition.

        Args:
            workflow: The Workflow configuration to check.

        Raises:
            WorkflowValidationError: If any validation rule is violated.
        """
        if not workflow.id or not workflow.id.strip():
            raise WorkflowValidationError("Workflow ID must not be empty.")

        if not workflow.name or not workflow.name.strip():
            raise WorkflowValidationError("Workflow Name must not be empty.")

        if not workflow.steps:
            raise WorkflowValidationError("Workflow must contain at least one step.")

        step_ids = set()
        for idx, step in enumerate(workflow.steps):
            if not step.id or not step.id.strip():
                raise WorkflowValidationError(f"Step at index {idx} has an empty ID.")
            
            if step.id in step_ids:
                raise WorkflowValidationError(f"Duplicate step ID found: '{step.id}'.")
            step_ids.add(step.id)

            if not step.worker_name or not step.worker_name.strip():
                raise WorkflowValidationError(f"Step '{step.id}' has an empty worker_name.")

            # Validate that the worker is registered
            if not self._worker_registry.is_registered(step.worker_name):
                raise WorkflowValidationError(
                    f"Step '{step.id}' requests unregistered worker '{step.worker_name}'."
                )

            if step.retry_count < 0:
                raise WorkflowValidationError(
                    f"Step '{step.id}' has invalid retry_count '{step.retry_count}'. Must be >= 0."
                )

            if step.timeout_seconds <= 0:
                raise WorkflowValidationError(
                    f"Step '{step.id}' has invalid timeout_seconds '{step.timeout_seconds}'. Must be > 0."
                )
        
        log.info("WorkflowEngine: workflow validation succeeded.")

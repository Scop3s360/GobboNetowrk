"""
Workflow Runner
===============
Executes workflow steps sequentially, implementing retries, timeouts, and state transitions.
"""

from __future__ import annotations

import logging
import time

from workflow.context import WorkflowContext
from workflow.executor import StepExecutor
from workflow.models import Workflow, WorkflowStep
from workflow.result import WorkflowResult
from workflow.state import WorkflowState

log = logging.getLogger(__name__)


class WorkflowRunner:
    """
    Executes a workflow's steps sequentially. Handles retries and state updates.
    """

    def __init__(self, step_executor: StepExecutor) -> None:
        """
        Initialize the WorkflowRunner.

        Args:
            step_executor: The StepExecutor to run individual steps.
        """
        self._step_executor = step_executor

    def run(self, workflow: Workflow, context: WorkflowContext) -> WorkflowResult:
        """
        Execute the workflow sequentially.

        Args:
            workflow: The Workflow definition.
            context:  The active WorkflowContext.

        Returns:
            A WorkflowResult indicating final state, duration, and output.
        """
        log.info("WorkflowRunner: starting execution of workflow_id=%s", workflow.id)
        start_perf = time.perf_counter()
        
        completed_steps: list[str] = []
        failed_step: str | None = None
        errors: list[str] = []
        final_output: object = None
        status = WorkflowState.RUNNING

        for step in workflow.steps:
            log.info("WorkflowRunner: starting step_id=%s", step.id)
            
            # Execute step with retries
            retries_remaining = step.retry_count
            step_success = False
            step_error = None
            step_output = None
            
            while True:
                step_res = self._step_executor.execute(step, context)
                if step_res.success:
                    step_success = True
                    step_output = step_res.result
                    break
                else:
                    step_error = step_res.error or "Unknown step execution error"
                    log.warning(
                        "WorkflowRunner: step_id=%s failed. retries_remaining=%d. error=%s",
                        step.id,
                        retries_remaining,
                        step_error,
                    )
                    if retries_remaining <= 0:
                        break
                    retries_remaining -= 1
                    errors.append(f"Step {step.id} retry failed: {step_error}")
            
            if not step_success:
                log.error("WorkflowRunner: step_id=%s failed ultimately. Halting workflow.", step.id)
                failed_step = step.id
                errors.append(f"Step {step.id} failed: {step_error}")
                status = WorkflowState.FAILED
                break
            
            # Record successful step result in context
            context.step_results[step.id] = step_output
            # Propagate to shared data as well
            context.shared_data[step.id] = step_output
            completed_steps.append(step.id)
            final_output = step_output
            log.info("WorkflowRunner: step_id=%s completed successfully.", step.id)

        # Calculate final execution time
        execution_time_s = time.perf_counter() - start_perf
        
        if status == WorkflowState.RUNNING:
            status = WorkflowState.COMPLETED
            log.info(
                "WorkflowRunner: workflow completed successfully. workflow_id=%s duration=%.2fs",
                workflow.id,
                execution_time_s,
            )
        else:
            log.error(
                "WorkflowRunner: workflow failed. workflow_id=%s duration=%.2fs",
                workflow.id,
                execution_time_s,
            )

        return WorkflowResult(
            workflow_id=workflow.id,
            status=status,
            completed_steps=completed_steps,
            failed_step=failed_step,
            execution_time=execution_time_s,
            final_output=final_output,
            errors=errors,
        )

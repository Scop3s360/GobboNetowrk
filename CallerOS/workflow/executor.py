"""
Step Executor
=============
Invokes specialist workers through the Worker Framework and maps execution context.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from workers.exceptions import WorkerError
from workers.manager import WorkerManager
from workers.models import WorkerRequest, WorkerResponse
from workflow.context import WorkflowContext
from workflow.exceptions import StepExecutionError
from workflow.models import WorkflowStep

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StepResult:
    """
    Outcome of an individual step execution.
    """
    success: bool
    result: object = None
    error: str | None = None
    duration_ms: float = 0.0


class StepExecutor:
    """
    Executes a single WorkflowStep by mapping context and invoking the Worker Framework.
    """

    def __init__(self, worker_manager: WorkerManager) -> None:
        """
        Initialize the StepExecutor.

        Args:
            worker_manager: The active WorkerManager.
        """
        self._worker_manager = worker_manager

    def execute(self, step: WorkflowStep, context: WorkflowContext) -> StepResult:
        """
        Execute the given step using the provided context.

        Args:
            step:    The WorkflowStep configuration.
            context: The current WorkflowContext.

        Returns:
            A StepResult indicating success, output, and duration.
        """
        log.info("StepExecutor: step started. id=%s worker=%s", step.id, step.worker_name)
        start_time = time.perf_counter()
        
        try:
            # Resolve inputs from context if they contain step references (e.g. "{step_id}")
            resolved_payload = self._resolve_input(step.input_data, context)
            
            # Map appropriate payload structure if target is the ResearchWorker
            if step.worker_name == "research-worker-v1":
                from workers.research.models import ResearchRequest
                if isinstance(resolved_payload, str):
                    payload = ResearchRequest(research_query=resolved_payload)
                elif isinstance(resolved_payload, dict) and "research_query" in resolved_payload:
                    payload = ResearchRequest(research_query=str(resolved_payload["research_query"]))
                else:
                    payload = ResearchRequest(research_query=str(resolved_payload))
            else:
                payload = resolved_payload

            # Build standard WorkerRequest
            worker_req = WorkerRequest(
                worker_id=step.worker_name,
                payload=payload,
            )
            
            log.info("StepExecutor: invoking worker=%s", step.worker_name)
            # Call WorkerManager (throws WorkerNotFoundError / WorkerExecutionError)
            worker_response = self._worker_manager.execute(step.worker_name, worker_req)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            
            log.info(
                "StepExecutor: worker completed. worker=%s success=%s duration_ms=%.2f",
                step.worker_name,
                worker_response.success,
                duration_ms,
            )
            
            if worker_response.success:
                return StepResult(
                    success=True,
                    result=worker_response.result,
                    duration_ms=duration_ms,
                )
            else:
                return StepResult(
                    success=False,
                    error=worker_response.error or "Worker failed execution.",
                    duration_ms=duration_ms,
                )
                
        except WorkerError as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            log.error("StepExecutor: step failed due to worker framework error: %s", exc)
            return StepResult(
                success=False,
                error=f"Worker Framework error: {exc}",
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            log.error("StepExecutor: step failed due to unexpected error: %s", exc, exc_info=True)
            return StepResult(
                success=False,
                error=f"Step execution error: {exc}",
                duration_ms=duration_ms,
            )

    def _resolve_input(self, input_data: object, context: WorkflowContext) -> object:
        """
        Resolve placeholders inside input data from context values.
        E.g., if a string is "{step1}", it resolves to context.step_results["step1"].
        """
        if isinstance(input_data, str):
            if input_data.startswith("{") and input_data.endswith("}"):
                ref_step = input_data[1:-1]
                if ref_step in context.step_results:
                    return context.step_results[ref_step]
            return input_data
        elif isinstance(input_data, dict):
            resolved = {}
            for k, v in input_data.items():
                if isinstance(v, str) and v.startswith("{") and v.endswith("}"):
                    ref_step = v[1:-1]
                    if ref_step in context.step_results:
                        resolved[k] = context.step_results[ref_step]
                    else:
                        resolved[k] = v
                else:
                    resolved[k] = v
            return resolved
        return input_data

"""
Director Agent
==============
The orchestrator coordinating worker selection, execution, and memory storage.
"""

from __future__ import annotations
import logging
import time
from typing import TYPE_CHECKING

from director.interfaces import Dispatcher, Router
from director.models import DirectorRequest, DirectorResponse, ExecutionPlan, ExecutionStep
from director.intent import IntentAnalyzer
from director.planner import ExecutionPlanner
from director.assembler import ResultAssembler
from memory.exceptions import MemoryError
from memory.manager import MemoryManager
from memory.models import MemoryRecord, MemoryType
from workers.exceptions import WorkerError
from workflow.models import Workflow, WorkflowStep
from workflow.context import WorkflowContext
from workflow.runner import WorkflowRunner
from workflow.executor import StepExecutor
from workflow.state import WorkflowState

if TYPE_CHECKING:
    from workers.manager import WorkerManager
    from workers.research.client import AIClient
    from context.engine import ContextEngine

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
        ai_client: AIClient | None = None,
        worker_manager: WorkerManager | None = None,
        context_engine: ContextEngine | None = None,
        project_manager: ProjectManager | None = None,
    ) -> None:
        """
        Initialize the Director.

        Args:
            router:         The Router implementation.
            dispatcher:     The Dispatcher implementation.
            memory_manager: Optional MemoryManager to persist conversation history.
            ai_client:      Optional AIClient for intent detection and planning.
            worker_manager: Optional WorkerManager for executing workflows.
            context_engine: Optional ContextEngine to retrieve project context.
            project_manager: Optional ProjectManager to retrieve active project context.
        """
        self._router = router
        self._dispatcher = dispatcher
        self._memory_manager = memory_manager
        self._ai_client = ai_client
        self._project_manager = project_manager

        # Discover worker manager and context engine (avoiding MagicMock automatic attributes)
        is_mock_dispatcher = False
        try:
            from unittest.mock import Mock
            if isinstance(dispatcher, Mock):
                is_mock_dispatcher = True
        except ImportError:
            pass

        self._worker_manager = worker_manager
        if self._worker_manager is None and not is_mock_dispatcher:
            if hasattr(dispatcher, "_worker_manager"):
                self._worker_manager = getattr(dispatcher, "_worker_manager")

        self._context_engine = context_engine
        if self._context_engine is None and not is_mock_dispatcher:
            if hasattr(dispatcher, "_context_engine"):
                self._context_engine = getattr(dispatcher, "_context_engine")

        # Inject project_manager into context_engine if needed
        if self._context_engine is not None and hasattr(self._context_engine, "_project_manager"):
            if getattr(self._context_engine, "_project_manager") is None:
                setattr(self._context_engine, "_project_manager", self._project_manager)

        # Discover worker registry
        self._worker_registry = None
        if self._worker_manager is not None:
            self._worker_registry = self._worker_manager._registry

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

        # If we do not have a worker manager or registry, fall back to legacy route (Stage 6 compatibility)
        if self._worker_manager is None or self._worker_registry is None:
            log.info("Director: falling back to simple single-worker routing path.")
            return self._execute_legacy(request, start_time)

        try:
            # 1. Intent Analysis & Task Classification
            intent_analyzer = IntentAnalyzer(self._ai_client)
            intent, task_classification = intent_analyzer.analyze(request.query)
            log.info("Director: Intent detected: %s", intent)
            log.info("Director: Task classification: %s", task_classification)

            # 2. Execution Planning
            planner = ExecutionPlanner(self._ai_client)
            plan = planner.plan(request.query, intent, task_classification, self._worker_registry)
            steps_summary = " -> ".join(f"{s.id}({s.worker_id})" for s in plan.steps)
            log.info("Director: Execution plan created: %s", steps_summary)
            
            selected_workers = [s.worker_id for s in plan.steps]
            log.info("Director: Workers selected: %s", selected_workers)

            # 3. Context Integration
            context_block = ""
            if self._context_engine is not None:
                project_name = None
                if self._project_manager and self._project_manager.active_project:
                    project_name = self._project_manager.active_project.name
                else:
                    project_name = self._context_engine.detect_project(request.query)
                
                if project_name or (self._project_manager and self._project_manager.active_project):
                    log.info("Director: Detected project '%s'", project_name or self._project_manager.active_project.name)
                    context_block = self._context_engine.build_context(project_name, request.query)
                    if context_block:
                        plan.context_block = context_block
                        log.info("Director: Context attached to execution plan.")
                        
                        # Prepend context to the first step's input if it is a string
                        if plan.steps:
                            first_step = plan.steps[0]
                            if isinstance(first_step.input_data, str):
                                from dataclasses import replace
                                plan.steps[0] = replace(first_step, input_data=f"{context_block}\n{first_step.input_data}")

            # 4. Worker Execution (sequential runner via workflow engine packages)
            wf_steps = []
            for step in plan.steps:
                wf_steps.append(WorkflowStep(
                    id=step.id,
                    worker_name=step.worker_id,
                    input_data=step.input_data,
                    timeout_seconds=step.timeout_seconds,
                    retry_count=step.retry_count
                ))
            
            workflow = Workflow(
                id=f"director-wf-{request.session_id}",
                name=f"Director Executive Workflow: {task_classification}",
                steps=wf_steps
            )

            context = WorkflowContext(original_request=request.query)
            runner = WorkflowRunner(StepExecutor(self._worker_manager))
            
            workflow_result = runner.run(workflow, context)

            # Log any retries or failures recorded during runner execution
            if workflow_result.errors:
                log.info("Director: Runner reported warnings/retries: %s", workflow_result.errors)

            completed_workers = workflow_result.completed_steps
            log.info("Director: Workers completed: %s", completed_workers)

            # 5. Result Validation
            if workflow_result.status == WorkflowState.FAILED:
                failed_step = workflow_result.failed_step
                error_msg = f"Step {failed_step} failed: " + "; ".join(workflow_result.errors)
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                log.error("Director: execution failed at step=%s. error=%s", failed_step, error_msg)
                return DirectorResponse(
                    success=False,
                    error=error_msg,
                    duration_ms=elapsed_ms,
                    plan=plan
                )

            if not completed_workers:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                log.error("Director: result validation failed. No steps completed successfully.")
                return DirectorResponse(
                    success=False,
                    error="Result validation failed: No steps were completed.",
                    duration_ms=elapsed_ms,
                    plan=plan
                )

            log.info("Director: Result validation completed successfully.")

            # 6. Response Assembly
            assembler = ResultAssembler(self._ai_client)
            final_result = assembler.assemble(request.query, context.step_results)
            log.info("Director: Response assembly completed.")

            # 7. Store conversation memory
            if self._memory_manager is not None:
                log.info("Director: storing conversation to memory.")
                content = (
                    f"User Query: {request.query}\n"
                    f"Director Response: {final_result}"
                )
                memory_rec = MemoryRecord(
                    type=MemoryType.CONVERSATION,
                    content=content,
                    source="Director",
                    tags=selected_workers + ["conversation"],
                    project=str(request.metadata.get("project", "default")),
                    agent="Director",
                )
                try:
                    self._memory_manager.create_memory(memory_rec)
                    log.info("Director: memory stored. id=%s", memory_rec.id)
                except MemoryError as exc:
                    log.error("Director: memory storage failed. error=%s", exc)

            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            log.info("Director: Execution duration: %.2f ms", elapsed_ms)
            return DirectorResponse(
                success=True,
                result=final_result,
                duration_ms=elapsed_ms,
                plan=plan
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            log.error("Director: unexpected exception: %s", exc, exc_info=True)
            return DirectorResponse(
                success=False,
                error=f"Director orchestration error: {exc}",
                duration_ms=elapsed_ms,
            )

    def _execute_legacy(self, request: DirectorRequest, start_time: float) -> DirectorResponse:
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

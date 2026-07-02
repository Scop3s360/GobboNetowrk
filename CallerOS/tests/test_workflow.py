"""
Tests: Workflow Engine (Stage 7)
================================
Covers:
  - WorkflowEngine validation of metadata, steps, worker registration, retries, and timeouts.
  - Sequential execution of single-step and multi-step workflows.
  - Failures halting execution cleanly.
  - Context passing between steps (resolving "{step_id}" placeholder inputs).
  - Retry behavior on transient errors.
  - Timing metrics and execution state transitions.
  - Logging events.
"""

from __future__ import annotations

import logging
import pytest
from unittest.mock import MagicMock

from tests.conftest import DummyWorker
from workers.manager import WorkerManager
from workers.registry import WorkerRegistry
from workflow.context import WorkflowContext
from workflow.engine import WorkflowEngine
from workflow.exceptions import WorkflowValidationError
from workflow.executor import StepExecutor, StepResult
from workflow.models import Workflow, WorkflowStep
from workflow.result import WorkflowResult
from workflow.state import WorkflowState


# ---------------------------------------------------------------------------
# Setup Helpers
# ---------------------------------------------------------------------------

class FailingDummyWorker(DummyWorker):
    """A dummy worker that fails N times before succeeding or fails permanently."""

    def __init__(self, worker_id: str, fail_count: int = 1) -> None:
        super().__init__(worker_id=worker_id)
        self.fail_count = fail_count
        self.attempts = 0

    def _execute(self, request: object) -> object:
        self.attempts += 1
        from workers.models import WorkerResponse
        if self.attempts <= self.fail_count:
            return WorkerResponse(request_id="err", success=False, error="Transient error")
        return WorkerResponse(request_id="ok", success=True, result=f"success:{self.attempts}")


# ---------------------------------------------------------------------------
# Tests: Workflow Validation
# ---------------------------------------------------------------------------

class TestWorkflowValidation:
    def test_valid_workflow_passes(self) -> None:
        registry = WorkerRegistry()
        registry.register(DummyWorker("w1"))
        
        step = WorkflowStep(id="step1", worker_name="w1", input_data="input")
        wf = Workflow(id="wf1", name="Valid Workflow", steps=[step])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        # Should not raise any validation exceptions
        engine.validate_workflow(wf)

    def test_empty_workflow_raises_validation_error(self) -> None:
        registry = WorkerRegistry()
        wf = Workflow(id="wf1", name="Empty Workflow", steps=[])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        with pytest.raises(WorkflowValidationError, match="at least one step"):
            engine.validate_workflow(wf)

    def test_unregistered_worker_raises_validation_error(self) -> None:
        registry = WorkerRegistry()
        step = WorkflowStep(id="step1", worker_name="ghost-worker", input_data="input")
        wf = Workflow(id="wf1", name="Invalid Worker Workflow", steps=[step])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        with pytest.raises(WorkflowValidationError, match="unregistered worker"):
            engine.validate_workflow(wf)

    def test_duplicate_step_ids_raises_validation_error(self) -> None:
        registry = WorkerRegistry()
        registry.register(DummyWorker("w1"))
        
        step1 = WorkflowStep(id="step-dup", worker_name="w1", input_data="i1")
        step2 = WorkflowStep(id="step-dup", worker_name="w1", input_data="i2")
        wf = Workflow(id="wf1", name="Dup ID Workflow", steps=[step1, step2])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        with pytest.raises(WorkflowValidationError, match="Duplicate step ID"):
            engine.validate_workflow(wf)

    def test_invalid_retry_or_timeout_raises_validation_error(self) -> None:
        registry = WorkerRegistry()
        registry.register(DummyWorker("w1"))
        
        step_neg_retry = WorkflowStep(id="step1", worker_name="w1", input_data="i", retry_count=-1)
        wf_neg = Workflow(id="wf1", name="Neg Retry", steps=[step_neg_retry])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        with pytest.raises(WorkflowValidationError, match="retry_count"):
            engine.validate_workflow(wf_neg)
            
        step_zero_timeout = WorkflowStep(id="step1", worker_name="w1", input_data="i", timeout_seconds=0)
        wf_zero = Workflow(id="wf1", name="Zero Timeout", steps=[step_zero_timeout])
        with pytest.raises(WorkflowValidationError, match="timeout_seconds"):
            engine.validate_workflow(wf_zero)


# ---------------------------------------------------------------------------
# Tests: Sequential Execution & Context Passing
# ---------------------------------------------------------------------------

class TestWorkflowExecution:
    def test_single_step_execution_success(self) -> None:
        registry = WorkerRegistry()
        w = DummyWorker("w1")
        registry.register(w)
        w.initialize()
        
        step = WorkflowStep(id="step1", worker_name="w1", input_data="hello")
        wf = Workflow(id="wf1", name="Single Step Workflow", steps=[step])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        result = engine.start_workflow(wf, original_request="user-input")
        
        assert result.status == WorkflowState.COMPLETED
        assert result.completed_steps == ["step1"]
        assert result.failed_step is None
        assert result.final_output == "processed:hello"
        assert result.execution_time >= 0.0
        assert len(result.errors) == 0

    def test_multi_step_execution_and_context_passing(self) -> None:
        registry = WorkerRegistry()
        w1 = DummyWorker("worker-a")
        w2 = DummyWorker("worker-b")
        registry.register(w1)
        registry.register(w2)
        w1.initialize()
        w2.initialize()
        
        step1 = WorkflowStep(id="stepA", worker_name="worker-a", input_data="first")
        # Step B references output of Step A via "{stepA}"
        step2 = WorkflowStep(id="stepB", worker_name="worker-b", input_data="{stepA}")
        
        wf = Workflow(id="wf2", name="Multi Step Workflow", steps=[step1, step2])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        result = engine.start_workflow(wf, original_request="start")
        
        assert result.status == WorkflowState.COMPLETED
        assert result.completed_steps == ["stepA", "stepB"]
        # Step A output: "processed:first"
        # Step B input should resolve to "processed:first" -> Output: "processed:processed:first"
        assert result.final_output == "processed:processed:first"

    def test_workflow_halts_on_failure(self) -> None:
        registry = WorkerRegistry()
        w1 = FailingDummyWorker("failing-worker", fail_count=5)
        w2 = DummyWorker("worker-ok")
        registry.register(w1)
        registry.register(w2)
        w1.initialize()
        w2.initialize()
        
        # Step 1 fails permanently because it allows 0 retries but needs 5
        step1 = WorkflowStep(id="step1", worker_name="failing-worker", input_data="fail", retry_count=0)
        step2 = WorkflowStep(id="step2", worker_name="worker-ok", input_data="ok")
        
        wf = Workflow(id="wf_fail", name="Fail halt Workflow", steps=[step1, step2])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        result = engine.start_workflow(wf, original_request="start")
        
        assert result.status == WorkflowState.FAILED
        assert result.completed_steps == []
        assert result.failed_step == "step1"
        assert len(result.errors) > 0
        assert w2.exec_calls == 0  # Second step should never be executed

    def test_retry_behavior_success_after_failure(self) -> None:
        registry = WorkerRegistry()
        w = FailingDummyWorker("retry-worker", fail_count=2)
        registry.register(w)
        w.initialize()
        
        # Step fails twice, succeeds on third try. We allow 2 retries (3 attempts total)
        step = WorkflowStep(id="step1", worker_name="retry-worker", input_data="retry", retry_count=2)
        wf = Workflow(id="wf_retry", name="Retry success", steps=[step])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        result = engine.start_workflow(wf, original_request="start")
        
        assert result.status == WorkflowState.COMPLETED
        assert result.completed_steps == ["step1"]
        # Success returned from attempts=3
        assert result.final_output == "success:3"
        assert w.attempts == 3

    def test_retry_behavior_failure_when_exhausted(self) -> None:
        registry = WorkerRegistry()
        w = FailingDummyWorker("retry-fail-worker", fail_count=3)
        registry.register(w)
        w.initialize()
        
        # Fails 3 times. We allow only 1 retry (2 attempts total). Should fail.
        step = WorkflowStep(id="step1", worker_name="retry-fail-worker", input_data="retry", retry_count=1)
        wf = Workflow(id="wf_retry_fail", name="Retry exhausted", steps=[step])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        result = engine.start_workflow(wf, original_request="start")
        
        assert result.status == WorkflowState.FAILED
        assert result.failed_step == "step1"
        assert w.attempts == 2


# ---------------------------------------------------------------------------
# Tests: Logging Fixtures
# ---------------------------------------------------------------------------

class TestWorkflowLogging:
    def test_workflow_execution_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        registry = WorkerRegistry()
        w = DummyWorker("w1")
        registry.register(w)
        w.initialize()
        
        step = WorkflowStep(id="step1", worker_name="w1", input_data="log_test")
        wf = Workflow(id="wf_log", name="Logging Test", steps=[step])
        
        manager = WorkerManager(registry)
        executor = StepExecutor(manager)
        engine = WorkflowEngine(registry, executor)
        
        with caplog.at_level(logging.INFO):
            engine.start_workflow(wf, original_request="log")
            
        messages = [record.message for record in caplog.records]
        assert any("workflow validation for workflow_id=wf_log" in msg for msg in messages)
        assert any("starting execution of workflow_id=wf_log" in msg for msg in messages)
        assert any("step started. id=step1" in msg for msg in messages)
        assert any("invoking worker=w1" in msg for msg in messages)
        assert any("worker completed" in msg for msg in messages)
        assert any("workflow completed successfully" in msg for msg in messages)

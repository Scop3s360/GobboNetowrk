"""
Execution Planner
=================
Generates execution plans with single-worker or multi-worker steps.
"""

from __future__ import annotations
import json
import logging
from typing import TYPE_CHECKING

from director.models import ExecutionPlan, ExecutionStep

if TYPE_CHECKING:
    from workers.registry import WorkerRegistry
    from workers.research.client import AIClient

log = logging.getLogger(__name__)

class ExecutionPlanner:
    """
    Builds an ExecutionPlan using LLM or heuristic capability matching.
    """

    def __init__(self, ai_client: AIClient | None = None) -> None:
        self._ai_client = ai_client

    def plan(
        self,
        query: str,
        intent: str,
        task_classification: str,
        registry: WorkerRegistry,
    ) -> ExecutionPlan:
        """
        Build an ExecutionPlan.
        """
        plan = None
        
        if self._ai_client is not None:
            try:
                plan = self._plan_via_llm(query, intent, task_classification, registry)
                log.info("ExecutionPlanner: LLM created plan with %d step(s)", len(plan.steps))
            except Exception as exc:
                log.warning("ExecutionPlanner: LLM planning failed: %s. Falling back to heuristics.", exc)
        
        if plan is None:
            plan = self._plan_via_heuristics(query, intent, task_classification, registry)
            log.info("ExecutionPlanner: Heuristic created plan with %d step(s)", len(plan.steps))
            
        return plan

    def _plan_via_heuristics(
        self,
        query: str,
        intent: str,
        task_classification: str,
        registry: WorkerRegistry,
    ) -> ExecutionPlan:
        # Discover worker IDs from metadata
        dev_worker_id = None
        research_worker_id = None
        
        for worker in registry.list_workers():
            caps = [c.lower() for c in worker.capabilities]
            if any(c in caps for c in ("programming", "code-generation", "refactoring")):
                dev_worker_id = worker.id
            if any(c in caps for c in ("research", "question-answering", "summarisation")):
                research_worker_id = worker.id

        # Fallback if no matching workers registered
        if not dev_worker_id:
            dev_worker_id = "developer-worker-v1"
        if not research_worker_id:
            research_worker_id = "research-worker-v1"

        steps = []
        
        # Decide if single-step or multi-step sequential
        if intent in ("Programming", "Debugging", "Review"):
            # Check if it mentions research/understanding/explain
            query_lower = query.lower()
            needs_research = any(w in query_lower for w in ("research", "explain", "why", "background", "information", "find out"))
            
            if needs_research:
                # Step 1: Research the topic
                steps.append(ExecutionStep(
                    id="step1",
                    worker_id=research_worker_id,
                    input_data=f"Research context/rules and requirements for: {query}",
                    description="Research background information and requirements."
                ))
                # Step 2: Implement code based on research
                steps.append(ExecutionStep(
                    id="step2",
                    worker_id=dev_worker_id,
                    input_data="{step1}",
                    description="Generate clean, well-commented code implementing the requested task."
                ))
            else:
                # Single-step developer worker
                steps.append(ExecutionStep(
                    id="step1",
                    worker_id=dev_worker_id,
                    input_data=query,
                    description="Implement the programming request."
                ))
        else:
            # Single-step research worker
            steps.append(ExecutionStep(
                id="step1",
                worker_id=research_worker_id,
                input_data=query,
                description="Perform research and answer user query."
            ))
            
        return ExecutionPlan(
            intent=intent,
            task_classification=task_classification,
            steps=steps
        )

    def _plan_via_llm(
        self,
        query: str,
        intent: str,
        task_classification: str,
        registry: WorkerRegistry,
    ) -> ExecutionPlan | None:
        # Build workers info string for data-driven worker selection
        workers_list = []
        for w in registry.list_workers():
            workers_list.append(
                f"- ID: {w.id}\n"
                f"  Name: {w.name}\n"
                f"  Description: {w.description}\n"
                f"  Capabilities: {', '.join(w.capabilities)}"
            )
        workers_info = "\n".join(workers_list)

        system_prompt = (
            "You are the CallerOS Director Planner.\n"
            "Create a sequential execution plan using available workers to fulfill the user's request.\n\n"
            "Rules:\n"
            "- A step input_data can reference a previous step's output using the placeholder: {step_id}.\n"
            "- Only select registered workers listed below.\n"
            "- Output plan as a JSON object, with EXACTLY this structure:\n"
            "{\n"
            '  "intent": "<intent_category>",\n'
            '  "task_classification": "<classification>",\n'
            '  "steps": [\n'
            "    {\n"
            '      "id": "<step_id_e.g_step1>",\n'
            '      "worker_id": "<worker_id>",\n'
            '      "input_data": "<input_data_for_worker>",\n'
            '      "description": "<what_this_step_does>"\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"Available workers:\n{workers_info}"
        )

        user_message = (
            f"User Query: {query}\n"
            f"Intent: {intent}\n"
            f"Classification: {task_classification}"
        )

        raw_response = self._ai_client.complete(system_prompt, user_message)
        data = self._extract_json(raw_response)
        
        steps = []
        for s in data.get("steps", []):
            worker_id = s.get("worker_id")
            # Validate worker is in registry
            if registry.is_registered(worker_id):
                steps.append(ExecutionStep(
                    id=s.get("id"),
                    worker_id=worker_id,
                    input_data=s.get("input_data"),
                    description=s.get("description", ""),
                    timeout_seconds=float(s.get("timeout_seconds", 30.0)),
                    retry_count=int(s.get("retry_count", 0))
                ))
            else:
                log.warning("ExecutionPlanner: LLM selected unregistered worker '%s'. Ignoring step.", worker_id)

        if not steps:
            return None

        return ExecutionPlan(
            intent=data.get("intent", intent),
            task_classification=data.get("task_classification", task_classification),
            steps=steps
        )

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```json"):
            text = text[len("```json"):]
        elif text.startswith("```"):
            text = text[len("```"):]
        if text.endswith("```"):
            text = text[:-len("```")]
        return json.loads(text.strip())

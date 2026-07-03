"""
Result Assembler
================
Merges and formats multi-step worker outputs into a single coherent response.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workers.research.client import AIClient

log = logging.getLogger(__name__)

class ResultAssembler:
    """
    Combines step execution results into a unified, high-quality final response.
    """

    def __init__(self, ai_client: AIClient | None = None) -> None:
        self._ai_client = ai_client

    def assemble(self, query: str, step_results: dict[str, object]) -> str:
        """
        Merge all step results.
        """
        if not step_results:
            return "No execution results obtained."
            
        assembled = None
        if self._ai_client is not None:
            try:
                assembled = self._assemble_via_llm(query, step_results)
                log.info("ResultAssembler: LLM successfully merged responses.")
            except Exception as exc:
                log.warning("ResultAssembler: LLM merge failed: %s. Falling back to heuristic formatting.", exc)

        if assembled is None:
            assembled = self._assemble_heuristically(query, step_results)
            log.info("ResultAssembler: Heuristically formatted responses.")
            
        return assembled

    def _assemble_heuristically(self, query: str, step_results: dict[str, object]) -> str:
        if len(step_results) == 1:
            return self.format_result_value(next(iter(step_results.values())))

        parts = []
        for step_id, value in step_results.items():
            formatted = self.format_result_value(value)
            parts.append(f"## Step: {step_id}\n\n{formatted}")
            
        return "\n\n".join(parts)

    def _assemble_via_llm(self, query: str, step_results: dict[str, object]) -> str:
        # Build formatted inputs string
        inputs_list = []
        for step_id, val in step_results.items():
            formatted_val = self.format_result_value(val)
            inputs_list.append(f"--- Step: {step_id} ---\n{formatted_val}")
        step_outputs = "\n\n".join(inputs_list)

        system_prompt = (
            "You are the CallerOS Director Response Assembler.\n"
            "Combine the outputs of multiple specialist worker steps into a single, high-quality, coherent final response.\n"
            "Rules:\n"
            "- Remove any redundant or duplicate information.\n"
            "- Maintain a consistent and professional structure.\n"
            "- Present a single, unified answer to the user's original query.\n"
            "- Output in clean Markdown."
        )

        user_message = (
            f"Original User Query: {query}\n\n"
            f"Worker Outputs:\n{step_outputs}"
        )

        return self._ai_client.complete(system_prompt, user_message).strip()

    def format_result_value(self, value: object) -> str:
        """
        Formats a single result object (like ResearchResult or DeveloperResult) to clean string.
        """
        if value is None:
            return "No result."
            
        # Detect ResearchResult
        if hasattr(value, "summary") and hasattr(value, "findings") and hasattr(value, "sources"):
            summary = getattr(value, "summary")
            findings = getattr(value, "findings", [])
            sources = getattr(value, "sources", [])
            
            findings_str = "\n".join(f"- {f}" for f in findings)
            sources_str = "\n".join(f"- {s}" for s in sources) if sources else "None"
            
            return (
                f"{summary}\n\n"
                f"### Key Findings\n{findings_str}\n\n"
                f"### Sources\n{sources_str}"
            )
            
        # Detect DeveloperResult
        if hasattr(value, "explanation") and hasattr(value, "code") and hasattr(value, "notes"):
            explanation = getattr(value, "explanation")
            code = getattr(value, "code")
            notes = getattr(value, "notes")
            
            return (
                f"{explanation}\n\n"
                f"```csharp\n{code}\n```\n\n"
                f"### Implementation Notes\n{notes}"
            )
            
        return str(value)

from __future__ import annotations
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ContextPackage:
    project_name: str
    summary: str = ""
    facts: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    raw_content: str = ""

    def format_for_prompt(self) -> str:
        """
        Formats the context package as a Markdown instruction block for the AI model.
        """
        lines = [
            f"=== ACTIVE PROJECT CONTEXT: {self.project_name.upper()} ===",
            "Use the following project-specific information to inform your response. Do not contradict established system rules or active design decisions.",
        ]
        if self.summary:
            lines.append(f"\n[Project Summary]\n{self.summary}")
        if self.facts:
            lines.append("\n[Key Facts & Systems]")
            for fact in self.facts:
                lines.append(f"- {fact}")
        if self.constraints:
            lines.append("\n[Design Constraints]")
            for constraint in self.constraints:
                lines.append(f"- {constraint}")
        if self.raw_content:
            lines.append(f"\n[Additional Reference Material]\n{self.raw_content}")
        lines.append("=========================================\n")
        return "\n".join(lines)

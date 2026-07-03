from __future__ import annotations

import logging
from workers.developer.models import DeveloperResult

log = logging.getLogger(__name__)

def parse_developer_response(raw: str) -> DeveloperResult:
    """
    Parse the raw AI text response into a DeveloperResult.
    """
    if not raw or not raw.strip():
        return DeveloperResult(explanation="", code="", notes="", raw_response=raw)

    # Simple section splitting
    sections = {}
    current_section = None
    section_content = []

    lines = raw.splitlines()
    for line in lines:
        upper_line = line.strip().upper()
        if upper_line in ("EXPLANATION:", "CODE:", "NOTES:"):
            if current_section:
                sections[current_section] = "\n".join(section_content).strip()
            current_section = upper_line[:-1]  # Remove trailing colon
            section_content = []
        else:
            if current_section:
                section_content.append(line)

    if current_section:
        sections[current_section] = "\n".join(section_content).strip()

    explanation = sections.get("EXPLANATION", "")
    code_raw = sections.get("CODE", "")
    notes = sections.get("NOTES", "")

    # Clean code block formatting
    code = code_raw
    if "```" in code_raw:
        try:
            parts = code_raw.split("```")
            if len(parts) >= 3:
                code_lines = parts[1].splitlines()
                if code_lines:
                    first_line = code_lines[0].strip().lower()
                    # Skip the language tag line if present
                    if first_line in ("csharp", "cs", "python", "py", "javascript", "js", "typescript", "ts", "html", "css", "cpp", "c", "bash"):
                        code = "\n".join(code_lines[1:])
                    else:
                        code = "\n".join(code_lines)
        except Exception:
            pass

    return DeveloperResult(
        explanation=explanation,
        code=code,
        notes=notes,
        raw_response=raw
    )

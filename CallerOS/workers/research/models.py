"""
Research Worker Models
======================
Domain-specific data transfer objects for the Research Worker.

These models represent the *shape* of a research request and its result.
They are separate from the generic WorkerRequest/WorkerResponse so that
research-specific fields have explicit names and types rather than living
inside an opaque ``payload: object`` field.

Architectural decisions:

    Frozen dataclasses (again):
        Consistent with the rest of the project.  Research results should not
        be mutated after they are returned.

    ResearchRequest as payload:
        The WorkerRequest.payload is typed as ``object`` in Stage 2.  The
        ResearchWorker casts payload → ResearchRequest inside _execute().
        The cast is validated early so failures produce a clear error.

    confidence as float [0.0, 1.0]:
        A structured confidence score is more useful than a free-text
        qualifier.  The parser maps model output (e.g. "high/medium/low") to
        a float.  0.0 means the model expressed no confidence; 1.0 means
        full confidence.  The score is advisory — not a guarantee.

    sources as list[str]:
        Sources are plain URL strings or citation texts.  No URL validation
        is applied at this stage because the AI may return partial citations
        or named references rather than full URLs.

    raw_response optional:
        Keeping the raw model output allows debugging and manual review of
        the parser's work.  It is excluded from production summaries but
        available when needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResearchRequest:
    """
    Describes a research task.

    Attributes:
        research_query: The question or topic to research.  Must be non-empty.
        context:        Optional background information to help focus the
                        response (e.g. "in the context of Python packaging").
        constraints:    Optional list of constraints (e.g. "published after
                        2022", "no more than 3 findings").
    """

    research_query: str
    context: str = ""
    constraints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResearchResult:
    """
    Structured output from a completed research task.

    Attributes:
        summary:       A concise paragraph summarising the overall findings.
        findings:      An ordered list of discrete, factual findings.
        sources:       References cited by the model (URLs or citation texts).
        confidence:    Model's expressed confidence in its answer, normalised
                       to [0.0, 1.0].  Derived from the model's own words.
        raw_response:  The unmodified text returned by the AI.  Useful for
                       debugging parser behaviour.  None when not captured.
    """

    summary: str
    findings: list[str]
    sources: list[str]
    confidence: float
    raw_response: str | None = None

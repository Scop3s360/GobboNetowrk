"""
Research Response Parser
========================
Converts a raw AI text response into a structured ResearchResult.

Architectural decisions:

    Defensive by design:
        The parser never raises on malformed input.  Every section is
        optional-as-found: if a section is missing, empty, or garbled,
        the parser fills it with a sensible default and continues.  The
        caller receives a best-effort ResearchResult rather than an
        exception, which is far more useful for debugging.

    Section extraction via simple string search:
        No regex is used.  The format is defined in prompts.RESPONSE_SECTIONS
        and the parser scans for those literal section headers.  This is
        robust to minor whitespace variation and avoids hard-to-read patterns.

    Confidence normalisation:
        The model is instructed to output "high", "medium", or "low".
        The parser maps these to 1.0, 0.5, 0.3 respectively.  If the
        model outputs something else, confidence defaults to 0.0 and the
        raw text is preserved in the ResearchResult for inspection.

    Bullet-point extraction:
        Lines starting with "- " or "* " are treated as list items.
        Lines that are not list items within a FINDINGS or SOURCES block
        are ignored (the model sometimes adds blank lines or sub-headers).

    raw_response is always attached:
        The unmodified AI response is stored in ResearchResult.raw_response
        so callers can audit the parser's work without re-querying the model.
"""

from __future__ import annotations

import logging

from workers.research.models import ResearchResult
from workers.research.prompts import RESPONSE_SECTIONS

log = logging.getLogger(__name__)

# Mapping from model confidence words to float scores.
_CONFIDENCE_MAP: dict[str, float] = {
    "high": 1.0,
    "medium": 0.5,
    "low": 0.3,
}

_DEFAULT_CONFIDENCE = 0.0
_NO_SOURCES_MARKER = "no sources available"


def parse_response(raw: str) -> ResearchResult:
    """
    Parse the raw AI text response into a ResearchResult.

    This function is intentionally lenient: any section that cannot be
    parsed falls back to a safe default.

    Args:
        raw: The unmodified text returned by the AI model.

    Returns:
        A ResearchResult populated with whatever structure was recoverable.
        ``raw_response`` always contains the original text.
    """
    if not raw or not raw.strip():
        log.warning("Parser received empty response; returning empty ResearchResult.")
        return _empty_result(raw or "")

    sections = _split_sections(raw)

    summary = _extract_summary(sections)
    findings = _extract_list_items(sections.get("FINDINGS", ""))
    sources = _extract_sources(sections.get("SOURCES", ""))
    confidence = _extract_confidence(sections.get("CONFIDENCE", ""))

    return ResearchResult(
        summary=summary,
        findings=findings,
        sources=sources,
        confidence=confidence,
        raw_response=raw,
    )


# ---------------------------------------------------------------------------
# Private section extraction helpers
# ---------------------------------------------------------------------------

def _split_sections(raw: str) -> dict[str, str]:
    """
    Split the raw response into named sections.

    Scans for section headers from RESPONSE_SECTIONS.  Text between two
    consecutive headers is attributed to the first header.  Text before
    the first recognised header is discarded (model preamble).

    Returns a dict mapping section name → section body text.
    """
    # Normalise line endings.
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    # Locate the position of each known header in the text.
    positions: list[tuple[int, str]] = []
    for section in RESPONSE_SECTIONS:
        # Headers may appear as "SECTION:" or "SECTION :" with trailing text.
        needle = section + ":"
        idx = text.upper().find(needle)
        if idx != -1:
            positions.append((idx, section))

    if not positions:
        log.debug("Parser found no recognised section headers in response.")
        return {}

    # Sort by position in the document.
    positions.sort(key=lambda t: t[0])

    result: dict[str, str] = {}
    for i, (start_idx, name) in enumerate(positions):
        # Body starts after the header line ends.
        body_start = text.find("\n", start_idx)
        if body_start == -1:
            body_start = start_idx + len(name) + 1
        else:
            body_start += 1  # skip the newline itself

        # Body ends at the next section header (or EOF).
        if i + 1 < len(positions):
            body_end = positions[i + 1][0]
        else:
            body_end = len(text)

        result[name] = text[body_start:body_end].strip()

    return result


def _extract_summary(sections: dict[str, str]) -> str:
    """Return the SUMMARY body, or a placeholder if missing."""
    body = sections.get("SUMMARY", "").strip()
    if not body:
        log.debug("Parser: SUMMARY section missing or empty.")
        return "No summary available."
    return body


def _extract_list_items(body: str) -> list[str]:
    """
    Extract bullet-point items from a section body.

    Accepts lines starting with "- " or "* ".  Empty lines and
    non-bullet lines are ignored.
    """
    items: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            item = stripped[2:].strip()
            if item:
                items.append(item)
    return items


def _extract_sources(body: str) -> list[str]:
    """
    Extract source references from the SOURCES body.

    Filters out the "no sources available" marker that the model is
    instructed to use when it has no citations.
    """
    raw_items = _extract_list_items(body)
    return [
        item for item in raw_items
        if item.lower() != _NO_SOURCES_MARKER
    ]


def _extract_confidence(body: str) -> float:
    """
    Map the CONFIDENCE section text to a float score.

    Looks for "high", "medium", or "low" in the first line of the body.
    Defaults to 0.0 if none is found.
    """
    if not body:
        return _DEFAULT_CONFIDENCE

    first_line = body.splitlines()[0].strip().lower()
    for word, score in _CONFIDENCE_MAP.items():
        if word in first_line:
            return score

    log.debug(
        "Parser: unrecognised confidence value '%s'; defaulting to %.1f.",
        first_line, _DEFAULT_CONFIDENCE,
    )
    return _DEFAULT_CONFIDENCE


def _empty_result(raw: str) -> ResearchResult:
    """Return a ResearchResult with all fields at their safe defaults."""
    return ResearchResult(
        summary="No summary available.",
        findings=[],
        sources=[],
        confidence=_DEFAULT_CONFIDENCE,
        raw_response=raw,
    )

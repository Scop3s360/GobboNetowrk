"""
Tests: Research Response Parser (workers/research/parser.py)
=============================================================
Covers:
  - Well-formed response parses all four sections correctly.
  - Summary extracted correctly.
  - Findings extracted as list items.
  - Sources extracted as list items.
  - "No sources available" marker is filtered out of sources.
  - Confidence "high" maps to 1.0.
  - Confidence "medium" maps to 0.5.
  - Confidence "low" maps to 0.3.
  - Unrecognised confidence word maps to 0.0.
  - Empty response returns safe defaults (no exception).
  - Whitespace-only response returns safe defaults.
  - Response missing SUMMARY section uses placeholder.
  - Response missing FINDINGS section returns empty list.
  - Response missing SOURCES section returns empty list.
  - Response missing CONFIDENCE section returns 0.0.
  - raw_response is always the original input text.
  - Parser handles Windows line endings (\r\n).
  - Parser handles mixed bullet styles (- and *).
"""

from __future__ import annotations

import pytest

from workers.research.parser import parse_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WELL_FORMED = """\
SUMMARY:
Python is a high-level programming language.

FINDINGS:
- Python was created by Guido van Rossum.
- It was first released in 1991.
- Python emphasises code readability.

SOURCES:
- https://python.org
- https://en.wikipedia.org/wiki/Python_(programming_language)

CONFIDENCE:
high
This is well-established information from primary sources.
"""


class TestWellFormedResponse:
    def test_summary_extracted(self):
        result = parse_response(_WELL_FORMED)
        assert "Python is a high-level programming language." in result.summary

    def test_findings_extracted(self):
        result = parse_response(_WELL_FORMED)
        assert len(result.findings) == 3

    def test_findings_content(self):
        result = parse_response(_WELL_FORMED)
        assert any("Guido van Rossum" in f for f in result.findings)
        assert any("1991" in f for f in result.findings)

    def test_sources_extracted(self):
        result = parse_response(_WELL_FORMED)
        assert len(result.sources) == 2
        assert "https://python.org" in result.sources

    def test_confidence_high(self):
        result = parse_response(_WELL_FORMED)
        assert result.confidence == 1.0

    def test_raw_response_preserved(self):
        result = parse_response(_WELL_FORMED)
        assert result.raw_response == _WELL_FORMED


class TestConfidenceMapping:
    def _response_with_confidence(self, level: str) -> str:
        return (
            "SUMMARY:\nSome summary.\n\n"
            "FINDINGS:\n- A finding.\n\n"
            "SOURCES:\n- No sources available\n\n"
            f"CONFIDENCE:\n{level}\nExplanation.\n"
        )

    def test_high_maps_to_1_0(self):
        result = parse_response(self._response_with_confidence("high"))
        assert result.confidence == 1.0

    def test_medium_maps_to_0_5(self):
        result = parse_response(self._response_with_confidence("medium"))
        assert result.confidence == 0.5

    def test_low_maps_to_0_3(self):
        result = parse_response(self._response_with_confidence("low"))
        assert result.confidence == 0.3

    def test_unknown_maps_to_0_0(self):
        result = parse_response(self._response_with_confidence("uncertain"))
        assert result.confidence == 0.0


class TestNoSourcesMarker:
    def test_no_sources_marker_filtered(self):
        response = (
            "SUMMARY:\nSummary text.\n\n"
            "FINDINGS:\n- A finding.\n\n"
            "SOURCES:\n- No sources available\n\n"
            "CONFIDENCE:\nlow\nLimited sources.\n"
        )
        result = parse_response(response)
        assert result.sources == []

    def test_real_sources_not_filtered(self):
        response = (
            "SUMMARY:\nSummary.\n\n"
            "FINDINGS:\n- Finding.\n\n"
            "SOURCES:\n- https://example.com\n\n"
            "CONFIDENCE:\nhigh\nGood.\n"
        )
        result = parse_response(response)
        assert "https://example.com" in result.sources


class TestEmptyAndMalformedResponses:
    def test_empty_string_returns_defaults(self):
        result = parse_response("")
        assert result.summary == "No summary available."
        assert result.findings == []
        assert result.sources == []
        assert result.confidence == 0.0
        assert result.raw_response == ""

    def test_whitespace_only_returns_defaults(self):
        result = parse_response("   \n\t  ")
        assert result.summary == "No summary available."
        assert result.findings == []

    def test_missing_summary_uses_placeholder(self):
        response = (
            "FINDINGS:\n- A finding.\n\n"
            "SOURCES:\n- No sources available\n\n"
            "CONFIDENCE:\nmedium\n"
        )
        result = parse_response(response)
        assert result.summary == "No summary available."

    def test_missing_findings_returns_empty_list(self):
        response = (
            "SUMMARY:\nA summary.\n\n"
            "SOURCES:\n- No sources available\n\n"
            "CONFIDENCE:\nhigh\n"
        )
        result = parse_response(response)
        assert result.findings == []

    def test_missing_sources_returns_empty_list(self):
        response = (
            "SUMMARY:\nA summary.\n\n"
            "FINDINGS:\n- Finding.\n\n"
            "CONFIDENCE:\nhigh\n"
        )
        result = parse_response(response)
        assert result.sources == []

    def test_missing_confidence_returns_zero(self):
        response = (
            "SUMMARY:\nA summary.\n\n"
            "FINDINGS:\n- Finding.\n\n"
            "SOURCES:\n- No sources available\n"
        )
        result = parse_response(response)
        assert result.confidence == 0.0

    def test_no_sections_at_all(self):
        """Garbage input should not raise; return safe defaults."""
        result = parse_response("This is just random text with no sections.")
        assert result.summary == "No summary available."
        assert result.findings == []
        assert result.sources == []

    def test_raw_response_always_set(self):
        raw = "SUMMARY:\nSomething.\n\nFINDINGS:\n- X.\n\nSOURCES:\n- Y.\n\nCONFIDENCE:\nhigh\n"
        result = parse_response(raw)
        assert result.raw_response == raw


class TestLineEndingHandling:
    def test_windows_line_endings(self):
        response = (
            "SUMMARY:\r\nA summary.\r\n\r\n"
            "FINDINGS:\r\n- A finding.\r\n\r\n"
            "SOURCES:\r\n- No sources available\r\n\r\n"
            "CONFIDENCE:\r\nhigh\r\n"
        )
        result = parse_response(response)
        assert "A summary." in result.summary
        assert len(result.findings) == 1
        assert result.confidence == 1.0


class TestBulletStyles:
    def test_asterisk_bullets_in_findings(self):
        response = (
            "SUMMARY:\nSummary.\n\n"
            "FINDINGS:\n* Finding one.\n* Finding two.\n\n"
            "SOURCES:\n- No sources available\n\n"
            "CONFIDENCE:\nhigh\n"
        )
        result = parse_response(response)
        assert len(result.findings) == 2

    def test_mixed_bullets_in_sources(self):
        response = (
            "SUMMARY:\nSummary.\n\n"
            "FINDINGS:\n- Finding.\n\n"
            "SOURCES:\n- https://a.com\n* https://b.com\n\n"
            "CONFIDENCE:\nhigh\n"
        )
        result = parse_response(response)
        assert len(result.sources) == 2

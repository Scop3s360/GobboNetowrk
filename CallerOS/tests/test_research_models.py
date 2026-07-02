"""
Tests: Research Worker Models (workers/research/models.py)
===========================================================
Covers:
  - ResearchRequest required field (research_query).
  - ResearchRequest optional fields default correctly.
  - ResearchRequest is immutable.
  - ResearchResult all fields.
  - ResearchResult is immutable.
  - ResearchResult default for raw_response is None.
"""

from __future__ import annotations

import pytest

from workers.research.models import ResearchRequest, ResearchResult


class TestResearchRequest:
    def test_required_field_stored(self):
        req = ResearchRequest(research_query="What is Python?")
        assert req.research_query == "What is Python?"

    def test_context_defaults_to_empty_string(self):
        req = ResearchRequest(research_query="query")
        assert req.context == ""

    def test_constraints_defaults_to_empty_list(self):
        req = ResearchRequest(research_query="query")
        assert req.constraints == []

    def test_context_stored(self):
        req = ResearchRequest(research_query="query", context="background info")
        assert req.context == "background info"

    def test_constraints_stored(self):
        req = ResearchRequest(research_query="query", constraints=["after 2022"])
        assert req.constraints == ["after 2022"]

    def test_immutable(self):
        req = ResearchRequest(research_query="query")
        with pytest.raises((AttributeError, TypeError)):
            req.research_query = "changed"  # type: ignore[misc]


class TestResearchResult:
    def test_all_fields_stored(self):
        result = ResearchResult(
            summary="A summary.",
            findings=["Finding 1", "Finding 2"],
            sources=["https://example.com"],
            confidence=0.9,
            raw_response="raw text",
        )
        assert result.summary == "A summary."
        assert result.findings == ["Finding 1", "Finding 2"]
        assert result.sources == ["https://example.com"]
        assert result.confidence == 0.9
        assert result.raw_response == "raw text"

    def test_raw_response_defaults_to_none(self):
        result = ResearchResult(
            summary="s", findings=[], sources=[], confidence=0.5
        )
        assert result.raw_response is None

    def test_immutable(self):
        result = ResearchResult(
            summary="s", findings=[], sources=[], confidence=0.5
        )
        with pytest.raises((AttributeError, TypeError)):
            result.summary = "changed"  # type: ignore[misc]

    def test_confidence_zero(self):
        result = ResearchResult(
            summary="s", findings=[], sources=[], confidence=0.0
        )
        assert result.confidence == 0.0

    def test_empty_findings_and_sources(self):
        result = ResearchResult(
            summary="s", findings=[], sources=[], confidence=1.0
        )
        assert result.findings == []
        assert result.sources == []

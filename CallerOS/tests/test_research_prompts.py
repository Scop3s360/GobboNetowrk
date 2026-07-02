"""
Tests: Research Prompt Builder (workers/research/prompts.py)
============================================================
Covers:
  - SYSTEM_PROMPT contains key behavioural instructions.
  - SYSTEM_PROMPT references all four expected response sections.
  - build_user_prompt() includes the research query.
  - build_user_prompt() includes context when provided.
  - build_user_prompt() omits context section when context is empty.
  - build_user_prompt() includes constraints when provided.
  - build_user_prompt() omits constraints section when list is empty.
  - build_user_prompt() includes format reminder.
  - Multiple constraints are each on their own bullet line.
"""

from __future__ import annotations

import pytest

from workers.research.models import ResearchRequest
from workers.research.prompts import (
    RESPONSE_SECTIONS,
    SYSTEM_PROMPT,
    build_user_prompt,
)


class TestSystemPrompt:
    def test_system_prompt_is_non_empty(self):
        assert SYSTEM_PROMPT.strip() != ""

    def test_system_prompt_forbids_hallucination(self):
        # Must instruct the model not to invent facts.
        assert "uncertain" in SYSTEM_PROMPT.lower() or "never invent" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_sources(self):
        assert "source" in SYSTEM_PROMPT.lower()

    def test_system_prompt_mentions_all_sections(self):
        for section in RESPONSE_SECTIONS:
            assert section in SYSTEM_PROMPT, f"SYSTEM_PROMPT missing section: {section}"

    def test_response_sections_tuple_has_four_entries(self):
        assert len(RESPONSE_SECTIONS) == 4

    def test_response_sections_correct_names(self):
        assert RESPONSE_SECTIONS == ("SUMMARY", "FINDINGS", "SOURCES", "CONFIDENCE")


class TestBuildUserPrompt:
    def test_includes_research_query(self):
        req = ResearchRequest(research_query="What is the speed of light?")
        prompt = build_user_prompt(req)
        assert "What is the speed of light?" in prompt

    def test_includes_context_when_present(self):
        req = ResearchRequest(
            research_query="What is Python?",
            context="in the context of programming languages",
        )
        prompt = build_user_prompt(req)
        assert "in the context of programming languages" in prompt

    def test_omits_context_section_when_empty(self):
        req = ResearchRequest(research_query="What is Python?")
        prompt = build_user_prompt(req)
        assert "Context:" not in prompt

    def test_includes_constraints_when_present(self):
        req = ResearchRequest(
            research_query="query",
            constraints=["published after 2022", "peer-reviewed only"],
        )
        prompt = build_user_prompt(req)
        assert "published after 2022" in prompt
        assert "peer-reviewed only" in prompt

    def test_omits_constraints_section_when_empty(self):
        req = ResearchRequest(research_query="query")
        prompt = build_user_prompt(req)
        assert "Constraints:" not in prompt

    def test_includes_format_reminder(self):
        req = ResearchRequest(research_query="query")
        prompt = build_user_prompt(req)
        assert "SUMMARY" in prompt or "format" in prompt.lower()

    def test_multiple_constraints_each_on_own_line(self):
        req = ResearchRequest(
            research_query="query",
            constraints=["constraint A", "constraint B"],
        )
        prompt = build_user_prompt(req)
        lines = prompt.splitlines()
        constraint_lines = [l for l in lines if "constraint A" in l or "constraint B" in l]
        # Each constraint should appear on its own line (bullet).
        assert len(constraint_lines) == 2

    def test_returns_string(self):
        req = ResearchRequest(research_query="query")
        result = build_user_prompt(req)
        assert isinstance(result, str)

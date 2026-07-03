"""
Intent Analyzer
===============
Detects user intent and task classification using heuristic rules or LLM.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from workers.research.client import AIClient

log = logging.getLogger(__name__)

INTENT_CATEGORIES = [
    "Research",
    "Programming",
    "Debugging",
    "Design",
    "Architecture",
    "Planning",
    "Documentation",
    "Review",
    "General Conversation"
]

# Keywords mapping for heuristic classification
HEURISTIC_RULES = {
    "Programming": {"code", "program", "develop", "compile", "script", "software", "write function", "implement", "programming", "csharp", "python", "javascript", "class"},
    "Debugging": {"bug", "debug", "fix", "error", "exception", "crash", "fail", "nullreference", "stacktrace"},
    "Review": {"review", "audit", "check code", "inspect", "refactor advice"},
    "Research": {"research", "find", "search", "explain", "what is", "how does", "learn", "info", "background", "concept"},
    "Design": {"design", "ui", "ux", "interface", "layout", "color", "aesthetic", "mockup", "wireframe"},
    "Architecture": {"architecture", "system design", "modular", "structure", "component layout", "pattern", "facade"},
    "Planning": {"plan", "roadmap", "schedule", "milestone", "todo", "task list", "sprint"},
    "Documentation": {"documentation", "doc", "readme", "write-up", "guide", "tutorial", "instruction"},
}

class IntentAnalyzer:
    """
    Analyzes user queries to detect their intent category and task classification.
    """

    def __init__(self, ai_client: AIClient | None = None) -> None:
        self._ai_client = ai_client

    def analyze(self, query: str) -> tuple[str, str]:
        """
        Analyze the query.
        Returns a tuple of (intent_category, task_classification).
        """
        intent = None
        
        if self._ai_client is not None:
            try:
                intent = self._analyze_via_llm(query)
                log.info("IntentAnalyzer: LLM detected intent '%s'", intent)
            except Exception as exc:
                log.warning("IntentAnalyzer: LLM intent detection failed: %s. Falling back to heuristics.", exc)
        
        if not intent:
            intent = self._analyze_via_heuristics(query)
            log.info("IntentAnalyzer: Heuristics detected intent '%s'", intent)
            
        task_classification = f"{intent} Task"
        return intent, task_classification

    def _analyze_via_heuristics(self, query: str) -> str:
        query_lower = query.lower()
        
        # Check matching score for each intent category
        best_intent = "General Conversation"
        max_matches = 0
        
        for category, keywords in HEURISTIC_RULES.items():
            matches = sum(1 for keyword in keywords if keyword in query_lower)
            if matches > max_matches:
                max_matches = matches
                best_intent = category
                
        return best_intent

    def _analyze_via_llm(self, query: str) -> str | None:
        system_prompt = (
            "You are the CallerOS Intent Analyzer.\n"
            f"Classify the user's query into exactly one of these categories: {', '.join(INTENT_CATEGORIES)}.\n"
            "Respond with only the category name, nothing else."
        )
        response = self._ai_client.complete(system_prompt, query).strip()
        
        # Normalize and find matching category
        for cat in INTENT_CATEGORIES:
            if cat.lower() == response.lower() or response.lower() in cat.lower():
                return cat
                
        return None

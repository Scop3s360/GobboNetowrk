"""
Heuristic Router
================
Analyzes requests based on key terms to select appropriate specialist workers.
"""

from director.interfaces import Router
from director.models import DirectorDecision, DirectorRequest


class HeuristicRouter(Router):
    """
    Deterministic Router that selects workers based on query keyword patterns.
    """

    # Keyword lists for classification.
    # Checks are case-insensitive.
    _DEVELOPER_KEYWORDS = {
        "code",
        "program",
        "develop",
        "compile",
        "script",
        "bug",
        "software",
        "write function",
        "implement",
        "programming",
    }

    def route(self, request: DirectorRequest) -> DirectorDecision:
        query_lower = request.query.lower()

        # Check if any programming-related keywords are in the query
        is_programming = any(keyword in query_lower for keyword in self._DEVELOPER_KEYWORDS)

        if is_programming:
            return DirectorDecision(
                worker_id="developer-worker-v1",
                reason="Query contains programming-related keywords. Routed to Developer Worker.",
            )
        else:
            return DirectorDecision(
                worker_id="research-worker-v1",
                reason="Query does not contain programming keywords. Defaulting to Research Worker.",
            )

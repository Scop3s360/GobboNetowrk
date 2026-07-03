from __future__ import annotations
import abc
import logging
from datetime import datetime
from context.models import ContextPackage
from memory.manager import MemoryManager
from memory.search import MemorySearchQuery
from memory.models import MemoryType, MemoryRecord

log = logging.getLogger(__name__)

class ContextProvider(abc.ABC):
    """
    Abstract base class for modular context providers.
    """
    @abc.abstractmethod
    def retrieve_context(self, project_name: str, query: str) -> ContextPackage | None:
        """
        Retrieves context for the given project and query.
        """
        pass

class MemoryContextProvider(ContextProvider):
    """
    Retrieves and ranks context memories from the MemoryManager.
    """
    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    def retrieve_context(self, project_name: str, query: str) -> ContextPackage | None:
        log.info("MemoryContextProvider: retrieving context for project=%s", project_name)
        
        try:
            # Query all memories matching the project name
            search_query = MemorySearchQuery(project=project_name)
            memories = self._memory_manager.search_memory(search_query)
        except Exception as exc:
            log.error("MemoryContextProvider: search failed: %s", exc)
            return None

        if not memories:
            log.info("MemoryContextProvider: no memories found for project=%s", project_name)
            return None

        # Scoring & Ranking Algorithm
        scored_memories: list[tuple[float, MemoryRecord]] = []
        for mem in memories:
            score = 0.0
            
            # 1. Base importance
            score += float(mem.importance)
            
            # 2. Type boost
            if mem.type == MemoryType.PROJECT:
                score += 10.0
            
            # 3. Tag boosts
            for tag in mem.tags:
                tag_lower = tag.lower()
                if tag_lower in ("architecture", "design", "rules", "system", "specification"):
                    score += 5.0
                elif tag_lower in ("constraint", "limit"):
                    score += 4.0
                elif tag_lower in ("summary", "overview"):
                    score += 3.0

            # 4. Keyword relevance boost
            # Check if any terms in user query overlap with the memory content
            query_words = set(query.lower().split())
            content_words = set(mem.content.lower().split())
            overlap = query_words.intersection(content_words)
            score += len(overlap) * 1.5

            # 5. Recency calculation
            try:
                # Parse created_at timestamp
                created_dt = datetime.fromisoformat(mem.created_at.replace("Z", "+00:00"))
                # Use age in hours to scale down score slightly for older memories
                age_hours = (datetime.now(created_dt.tzinfo) - created_dt).total_seconds() / 3600.0
                # Subtract small penalty for age (e.g. 0.01 per hour, capped at 5.0 max penalty)
                score -= min(5.0, age_hours * 0.01)
            except Exception:
                pass

            scored_memories.append((score, mem))

        # Sort descending by score
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        # Select top records and organize into ContextPackage
        top_memories = [mem for _, mem in scored_memories[:5]]
        
        summary = ""
        facts = []
        constraints = []
        additional = []

        for mem in top_memories:
            tags_lower = [t.lower() for t in mem.tags]
            
            # Identify summary
            if "summary" in tags_lower or "overview" in tags_lower:
                if not summary:
                    summary = mem.content
                    continue
            
            # Identify constraints
            if "constraint" in tags_lower or "limit" in tags_lower:
                constraints.append(mem.content)
            # Identify key systems/facts
            elif any(t in tags_lower for t in ("rules", "design", "system", "architecture")):
                facts.append(mem.content)
            else:
                additional.append(mem.content)

        # Fallback summary: use the first project level memory if no summary tag was found
        if not summary and top_memories:
            for mem in top_memories:
                if mem.type == MemoryType.PROJECT:
                    summary = mem.content
                    break
            if not summary:
                summary = top_memories[0].content

        return ContextPackage(
            project_name=project_name,
            summary=summary,
            facts=facts,
            constraints=constraints,
            raw_content="\n\n".join(additional) if additional else ""
        )

from __future__ import annotations
import logging
from context.models import ContextPackage
from context.providers import ContextProvider
from project.manager import ProjectManager
from project.workspace import ProjectWorkspace

log = logging.getLogger(__name__)

class ContextEngine:
    """
    Orchestrator that detects active projects and builds concise context packages
    from the global database or the active project workspace.
    """
    def __init__(self, providers: list[ContextProvider] | None = None, project_manager: ProjectManager | None = None) -> None:
        self._providers = providers or []
        self._project_manager = project_manager

    def register_provider(self, provider: ContextProvider) -> None:
        """
        Registers a new ContextProvider dynamically.
        """
        self._providers.append(provider)

    def detect_project(self, query: str, history: list[str] | None = None) -> str | None:
        """
        Determines the active project using explicit name matches.
        """
        # If project_manager is active, use the currently active project
        if self._project_manager and self._project_manager.active_project:
            return self._project_manager.active_project.name

        search_str = query.lower()
        if history:
            search_str += " " + " ".join(history).lower()

        if "gravehold" in search_str:
            return "Gravehold"
        if "calleros" in search_str:
            return "CallerOS"
        if "goblinos" in search_str:
            return "GoblinOS"
            
        return None

    def build_context(self, project_name: str | None, query: str) -> str:
        """
        Orchestrates all active providers or the project workspace to gather context.
        """
        # Check if project manager and active workspace are present
        active_project = None
        workspace = None
        if self._project_manager:
            active_project = self._project_manager.active_project
            workspace = self._project_manager.active_workspace

        if active_project and workspace:
            log.info("ContextEngine: active project detected. Retrieving context from workspace database.")
            context_block = self._rank_and_format_workspace_context(active_project, workspace, query)
            if context_block:
                log.info(
                    "ContextEngine: context package completed. project=%s, size=%d chars",
                    active_project.name,
                    len(context_block)
                )
                # Format to wrap in standard active project headers
                header = (
                    f"=== ACTIVE PROJECT CONTEXT: {active_project.name} ===\n"
                    f"Type: {active_project.type}\n"
                    f"Description: {active_project.description}\n"
                    f"Tags: {', '.join(active_project.tags)}\n\n"
                )
                return header + context_block
            return ""

        # Legacy fallback
        if not project_name:
            return ""

        log.info("ContextEngine: building context package for project=%s (legacy mode)", project_name)
        
        packages = []
        for provider in self._providers:
            try:
                pkg = provider.retrieve_context(project_name, query)
                if pkg:
                    packages.append(pkg)
            except Exception as exc:
                log.error("ContextEngine: provider error: %s", exc)

        if not packages:
            log.info("ContextEngine: no context retrieved by any provider.")
            return ""

        # Format context package
        formatted_context = packages[0].format_for_prompt()
        log.info(
            "ContextEngine: context package completed. project=%s, size=%d chars",
            project_name,
            len(formatted_context)
        )
        return formatted_context

    def _rank_and_format_workspace_context(self, project, workspace: ProjectWorkspace, query: str) -> str:
        """
        Query project-isolated memories, document chunks, notes, and past messages,
        ranking them by importance, base type, and keyword relevance overlap.
        """
        # 1. Fetch memories
        try:
            memories = workspace.memory_repo.list_memories()
        except Exception as e:
            log.error(f"ContextEngine: failed to list workspace memories: {e}")
            memories = []
            
        # 2. Fetch document chunks using knowledge index
        try:
            doc_chunks = workspace.search_knowledge_index(query, limit=10)
        except Exception as e:
            log.error(f"ContextEngine: failed to query knowledge index: {e}")
            doc_chunks = []
            
        # 3. Fetch notes
        notes = []
        try:
            notes_cursor = workspace.db.execute("SELECT id, title, content, created_at FROM notes")
            notes = [dict(row) for row in notes_cursor.fetchall()]
        except Exception as e:
            log.error(f"ContextEngine: failed to fetch workspace notes: {e}")
            
        # 4. Fetch past messages
        conversations = []
        try:
            msg_cursor = workspace.db.execute(
                """
                SELECT c.title as conv_title, m.content, m.timestamp 
                FROM conversations c 
                JOIN messages m ON c.id = m.conversation_id
                WHERE m.role != 'assistant'
                """
            )
            conversations = [dict(row) for row in msg_cursor.fetchall()]
        except Exception as e:
            log.error(f"ContextEngine: failed to fetch workspace conversations: {e}")
            
        # 4b. Fetch code symbols matching query keywords
        code_symbols = []
        try:
            query_cleaned = query.strip().replace("'", "").replace('"', "")
            if query_cleaned:
                words = [w.strip() for w in query_cleaned.split() if len(w.strip()) > 2]
                if words:
                    clauses = []
                    params = []
                    for w in words:
                        clauses.append("(symbol_name LIKE ? OR content LIKE ?)")
                        params.extend([f"%{w}%", f"%{w}%"])
                    
                    sql = f"""
                        SELECT file_path, symbol_name, symbol_type, line_number, parent_class, content
                        FROM code_symbols
                        WHERE {" OR ".join(clauses)}
                        LIMIT 10
                    """
                    cursor = workspace.db.execute(sql, params)
                    code_symbols = [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            log.error(f"ContextEngine: failed to query workspace code symbols: {e}")

        # 5. Score candidates
        query_words = set(w.lower() for w in query.split() if len(w) > 2)
        candidates = []
        
        # Memories
        for mem in memories:
            score = float(mem.importance)
            if mem.type == "PROJECT":
                score += 10.0
            for tag in mem.tags:
                if tag.lower() in ("architecture", "design", "rules", "system", "specification"):
                    score += 5.0
                    
            content_words = set(w.lower() for w in mem.content.split())
            overlap = query_words.intersection(content_words)
            score += len(overlap) * 2.0
            
            candidates.append({
                "title": f"Memory (Tags: {', '.join(mem.tags)})",
                "content": mem.content,
                "score": score
            })
            
        # Document chunks
        for chunk in doc_chunks:
            score = 8.0 # Base score for documents
            content_words = set(w.lower() for w in chunk["content"].split())
            overlap = query_words.intersection(content_words)
            score += len(overlap) * 2.0
            
            candidates.append({
                "title": f"Document: {chunk['title']}",
                "content": chunk["content"],
                "score": score
            })
            
        # Notes
        for note in notes:
            score = 6.0 # Base score for notes
            content_words = set(w.lower() for w in note["content"].split())
            overlap = query_words.intersection(content_words)
            score += len(overlap) * 2.0
            
            candidates.append({
                "title": f"Note: {note['title']}",
                "content": note["content"],
                "score": score
            })
            
        # Conversations
        for conv in conversations:
            score = 4.0 # Base score for conversation messages
            content_words = set(w.lower() for w in conv["content"].split())
            overlap = query_words.intersection(content_words)
            score += len(overlap) * 2.0
            
            candidates.append({
                "title": f"Past Chat in: {conv['conv_title']}",
                "content": conv["content"],
                "score": score
            })

        # Code Symbols
        for sym in code_symbols:
            score = 7.0 # Base score for code symbols
            name_words = set(w.lower() for w in sym["symbol_name"].split())
            overlap = query_words.intersection(name_words)
            score += len(overlap) * 3.0 # Heavy boost for exact symbol name overlap
            
            symbol_description = (
                f"File: {sym['file_path']}\n"
                f"Type: {sym['symbol_type']}\n"
                f"Line: {sym['line_number']}\n"
            )
            if sym["parent_class"]:
                symbol_description += f"Parent Class: {sym['parent_class']}\n"
            symbol_description += f"Signature/Code: {sym['content']}"

            candidates.append({
                "title": f"Code Symbol ({sym['symbol_type']}): {sym['symbol_name']}",
                "content": symbol_description,
                "score": score
            })
            
        # Sort descending by score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Take top 5
        top_candidates = candidates[:5]
        if not top_candidates:
            return ""
            
        # Build block
        blocks = []
        for cand in top_candidates:
            blocks.append(f"[{cand['title']}] (Relevance Score: {cand['score']:.1f})\n{cand['content']}")
            
        return "\n\n---\n\n".join(blocks)

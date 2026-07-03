"""
Project Workspace
=================
Manages isolated project files, SQLite database, full-text knowledge indexing,
and document parsing heuristics.
"""

from __future__ import annotations
import os
import re
import shutil
import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone

from database.manager import DatabaseManager
from memory.repository import SQLiteMemoryRepository
from database.repositories import ConversationRepository
from memory.models import MemoryRecord, MemoryType

log = logging.getLogger(__name__)

class ProjectWorkspace:
    """
    Manages filesystem layout and isolated database operations for a specific project.
    """

    def __init__(self, project_id: str, base_workspaces_dir: Path) -> None:
        self.project_id = project_id
        self.workspace_dir = (base_workspaces_dir / project_id).resolve()
        
        # Ensure directories exist
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir = self.workspace_dir / "documents"
        self.docs_dir.mkdir(exist_ok=True)
        self.notes_dir = self.workspace_dir / "notes"
        self.notes_dir.mkdir(exist_ok=True)
        
        # Database setup
        self.db_path = self.workspace_dir / "workspace.db"
        self.db = DatabaseManager(self.db_path)
        
        # Determine FTS5 availability and setup index schema
        self.has_fts5 = self._check_fts5_support()
        self._initialize_workspace_schema()
        
        # Standard repository reuse
        self.memory_repo = SQLiteMemoryRepository(self.db)
        self.conversation_repo = ConversationRepository(self.db.connection_manager)

    def _check_fts5_support(self) -> bool:
        """Check if FTS5 SQLite module is available."""
        conn = None
        try:
            conn = sqlite3.connect(":memory:")
            conn.execute("CREATE VIRTUAL TABLE fts_test USING fts5(content);")
            conn.execute("DROP TABLE fts_test;")
            return True
        except sqlite3.OperationalError:
            log.warning("ProjectWorkspace: FTS5 module not available. Falling back to keyword search.")
            return False
        finally:
            if conn:
                conn.close()

    def _initialize_workspace_schema(self) -> None:
        """Create project-isolated schema tables in workspace.db."""
        # Create standard tables if they don't exist
        tables = [
            # Conversations
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """,
            # Messages
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            );
            """,
            # Project memories
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                project TEXT,
                agent TEXT,
                content TEXT NOT NULL,
                tags TEXT NOT NULL,
                importance INTEGER NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """,
            # Documents
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                content TEXT NOT NULL,
                imported_at TEXT NOT NULL
            );
            """,
            # Notes
            """
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        ]
        
        for sql in tables:
            self.db.execute(sql)
            
        # Setup Knowledge Index virtual tables
        if self.has_fts5:
            self.db.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_index USING fts5(
                    title,
                    content,
                    doc_id,
                    doc_type UNINDEXED
                );
                """
            )
        else:
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_index_fallback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    doc_type TEXT NOT NULL
                );
                """
            )

    def import_document(self, file_path: Path) -> dict:
        """
        Import a Markdown (.md) or Text (.txt) file into the workspace.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
            
        ext = file_path.suffix.lower()
        if ext not in (".md", ".txt"):
            raise ValueError("Only Markdown (.md) and plain Text (.txt) files are supported.")
            
        doc_name = file_path.name
        content = file_path.read_text(encoding="utf-8")
        
        # Copy original file to workspace documents folder
        dest_path = self.docs_dir / doc_name
        shutil.copy2(file_path, dest_path)
        
        doc_id = str(Path(doc_name).stem).lower().replace(" ", "_")
        imported_at = datetime.now(timezone.utc).isoformat()
        
        # Insert document record into isolated database
        self.db.execute(
            """
            INSERT OR REPLACE INTO documents (id, name, path, content, imported_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (doc_id, doc_name, str(dest_path), content, imported_at)
        )
        
        # Parse and index chunks
        chunks = []
        if ext == ".md":
            chunks = self._chunk_markdown(content)
        else:
            chunks = self._chunk_plain_text(content)
            
        for heading, chunk_text in chunks:
            # 1. Update knowledge index
            if self.has_fts5:
                self.db.execute(
                    """
                    INSERT INTO knowledge_index (title, content, doc_id, doc_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (heading or doc_name, chunk_text, doc_id, "document")
                )
            else:
                self.db.execute(
                    """
                    INSERT INTO knowledge_index_fallback (title, content, doc_id, doc_type)
                    VALUES (?, ?, ?, ?)
                    """,
                    (heading or doc_name, chunk_text, doc_id, "document")
                )
                
            # 2. Generate project memory entries
            tags_list = ["imported", doc_name.lower().replace(".", "_")]
            if heading:
                tags_list.append(heading.lower().replace(" ", "_"))
                
            memory_content = f"Document: {doc_name}\n"
            if heading:
                memory_content += f"Section: {heading}\n"
            memory_content += f"\n{chunk_text}"
            
            memory = MemoryRecord(
                type=MemoryType.PROJECT,
                content=memory_content,
                source="document_import",
                project=self.project_id,
                tags=tags_list,
                importance=5
            )
            self.memory_repo.create_memory(memory)
            
        log.info(f"ProjectWorkspace: document '{doc_name}' imported and indexed successfully into {len(chunks)} chunks.")
        
        return {
            "id": doc_id,
            "name": doc_name,
            "path": str(dest_path),
            "chunks_count": len(chunks)
        }

    def _chunk_markdown(self, markdown_text: str) -> list[tuple[str, str]]:
        """
        Chunk markdown file by headings (#, ##, ###).
        """
        chunks = []
        lines = markdown_text.splitlines()
        
        current_heading = ""
        current_block = []
        
        for line in lines:
            # Match Markdown headers: e.g. "# Heading Name" or "## Section Title"
            header_match = re.match(r"^(#{1,6})\s+(.*)$", line)
            if header_match:
                # Save previous chunk if not empty
                if current_block:
                    block_content = "\n".join(current_block).strip()
                    if block_content:
                        chunks.append((current_heading, block_content))
                # Start new chunk
                current_heading = header_match.group(2).strip()
                current_block = []
            else:
                current_block.append(line)
                
        # Save last chunk
        if current_block:
            block_content = "\n".join(current_block).strip()
            if block_content:
                chunks.append((current_heading, block_content))
                
        # If no headings found, fall back to plain chunking
        if not chunks:
            chunks = self._chunk_plain_text(markdown_text)
            
        return chunks

    def _chunk_plain_text(self, text: str, max_chars: int = 1000) -> list[tuple[str, str]]:
        """
        Chunk plain text into paragraphs or character limits.
        """
        chunks = []
        # Split by double newlines for paragraph boundary
        paragraphs = text.split("\n\n")
        
        current_chunk = []
        current_len = 0
        
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                continue
                
            if current_len + len(para) > max_chars and current_chunk:
                # Flush current chunk
                chunk_content = "\n\n".join(current_chunk)
                chunks.append((f"Section {len(chunks) + 1}", chunk_content))
                current_chunk = [para]
                current_len = len(para)
            else:
                current_chunk.append(para)
                current_len += len(para)
                
        if current_chunk:
            chunk_content = "\n\n".join(current_chunk)
            chunks.append((f"Section {len(chunks) + 1}", chunk_content))
            
        return chunks

    def search_knowledge_index(self, query: str, limit: int = 5) -> list[dict]:
        """
        Search the knowledge index using FTS5 match query or LIKE fallback.
        """
        results = []
        query_cleaned = query.strip().replace("'", "").replace('"', "")
        if not query_cleaned:
            return results
            
        if self.has_fts5:
            # FTS5 matches using token matching
            sql = """
                SELECT doc_id, doc_type, title, content
                FROM knowledge_index
                WHERE knowledge_index MATCH ?
                LIMIT ?
            """
            cursor = self.db.execute(sql, (query_cleaned, limit))
        else:
            # LIKE fallback
            sql = """
                SELECT doc_id, doc_type, title, content
                FROM knowledge_index_fallback
                WHERE content LIKE ? OR title LIKE ?
                LIMIT ?
            """
            pattern = f"%{query_cleaned}%"
            cursor = self.db.execute(sql, (pattern, pattern, limit))
            
        for row in cursor.fetchall():
            results.append({
                "doc_id": row["doc_id"],
                "doc_type": row["doc_type"],
                "title": row["title"],
                "content": row["content"]
            })
            
        return results

    def list_documents(self) -> list[dict]:
        """List all imported documents in the workspace database."""
        cursor = self.db.execute("SELECT id, name, path, imported_at FROM documents ORDER BY name")
        return [dict(row) for row in cursor.fetchall()]

    def close(self) -> None:
        """Close the local database connection."""
        self.db.close()

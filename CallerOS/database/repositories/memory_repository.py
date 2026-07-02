"""
Memory Repository
=================
Handles CRUD and parameterized searches on the Memories table.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any

from database.connection import ConnectionManager
from database.exceptions import RepositoryError
from database.models import Memory

log = logging.getLogger(__name__)


class MemoryRepository:
    """
    Repository providing CRUD and filtering capability for memories.
    """

    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def create_memory(self, mem: Memory) -> None:
        sql = """
            INSERT INTO memories (id, type, project, agent, content, tags, importance, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            tags_serialized = json.dumps(mem.tags)
            self._db.execute(
                sql,
                (
                    mem.id,
                    mem.type,
                    mem.project,
                    mem.agent,
                    mem.content,
                    tags_serialized,
                    mem.importance,
                    mem.source,
                    mem.created_at,
                    mem.updated_at,
                ),
            )
        except Exception as exc:
            log.error("Failed to create memory ID %s: %s", mem.id, exc)
            raise RepositoryError(f"Error creating memory: {exc}") from exc

    def get_memory(self, memory_id: str) -> Memory:
        sql = "SELECT * FROM memories WHERE id = ?"
        try:
            cursor = self._db.execute(sql, (memory_id,))
            row = cursor.fetchone()
            if not row:
                raise RepositoryError(f"Memory with ID '{memory_id}' not found.")
            return self._map_row(row)
        except RepositoryError:
            raise
        except Exception as exc:
            log.error("Failed to get memory ID %s: %s", memory_id, exc)
            raise RepositoryError(f"Error getting memory: {exc}") from exc

    def update_memory(self, mem: Memory) -> None:
        sql = """
            UPDATE memories
            SET type = ?, project = ?, agent = ?, content = ?, tags = ?, importance = ?, source = ?, created_at = ?, updated_at = ?
            WHERE id = ?
        """
        try:
            tags_serialized = json.dumps(mem.tags)
            cursor = self._db.execute(
                sql,
                (
                    mem.type,
                    mem.project,
                    mem.agent,
                    mem.content,
                    tags_serialized,
                    mem.importance,
                    mem.source,
                    mem.created_at,
                    mem.updated_at,
                    mem.id,
                ),
            )
            if cursor.rowcount == 0:
                raise RepositoryError(f"Memory with ID '{mem.id}' not found.")
        except RepositoryError:
            raise
        except Exception as exc:
            log.error("Failed to update memory ID %s: %s", mem.id, exc)
            raise RepositoryError(f"Error updating memory: {exc}") from exc

    def delete_memory(self, memory_id: str) -> None:
        sql = "DELETE FROM memories WHERE id = ?"
        try:
            cursor = self._db.execute(sql, (memory_id,))
            if cursor.rowcount == 0:
                raise RepositoryError(f"Memory with ID '{memory_id}' not found.")
        except RepositoryError:
            raise
        except Exception as exc:
            log.error("Failed to delete memory ID %s: %s", memory_id, exc)
            raise RepositoryError(f"Error deleting memory: {exc}") from exc

    def list_memories(self) -> list[Memory]:
        sql = "SELECT * FROM memories ORDER BY created_at DESC"
        try:
            cursor = self._db.execute(sql)
            rows = cursor.fetchall()
            return [self._map_row(row) for row in rows]
        except Exception as exc:
            log.error("Failed to list memories: %s", exc)
            raise RepositoryError(f"Error listing memories: {exc}") from exc

    def search_memories(
        self,
        keyword: str | None = None,
        tags: list[str] | None = None,
        project: str | None = None,
        agent: str | None = None,
        memory_type: str | None = None,
        importance: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Memory]:
        sql_parts = ["SELECT * FROM memories WHERE 1=1"]
        params: list[Any] = []

        if keyword:
            sql_parts.append("AND content LIKE ?")
            params.append(f"%{keyword}%")
        if project is not None:
            sql_parts.append("AND project = ?")
            params.append(project)
        if agent is not None:
            sql_parts.append("AND agent = ?")
            params.append(agent)
        if memory_type is not None:
            sql_parts.append("AND type = ?")
            params.append(memory_type)
        if importance is not None:
            sql_parts.append("AND importance = ?")
            params.append(importance)
        if start_date is not None:
            sql_parts.append("AND created_at >= ?")
            params.append(start_date)
        if end_date is not None:
            sql_parts.append("AND created_at <= ?")
            params.append(end_date)
            
        # Apply LIKE constraints for tags first pass
        if tags:
            for tag in tags:
                sql_parts.append("AND tags LIKE ?")
                params.append(f'%"{tag}"%')

        sql = " ".join(sql_parts) + " ORDER BY created_at DESC"

        try:
            cursor = self._db.execute(sql, params)
            rows = cursor.fetchall()
            candidates = [self._map_row(row) for row in rows]
        except Exception as exc:
            log.error("Failed to search memories: %s", exc)
            raise RepositoryError(f"Error searching memories: {exc}") from exc

        # Strict tags subset check
        if tags:
            query_tag_set = set(tags)
            return [c for c in candidates if query_tag_set.issubset(set(c.tags))]

        return candidates

    def _map_row(self, row: dict[str, Any]) -> Memory:
        try:
            tags_parsed = json.loads(row["tags"])
        except (TypeError, json.JSONDecodeError):
            tags_parsed = []

        return Memory(
            id=row["id"],
            type=row["type"],
            project=row["project"],
            agent=row["agent"],
            content=row["content"],
            tags=tags_parsed,
            importance=row["importance"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

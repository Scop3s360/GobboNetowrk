"""
Memory Repository Layer
=======================
Interface and SQLite implementation of the memory repository.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from database.manager import DatabaseManager
from memory.exceptions import MemoryNotFoundError
from memory.models import MemoryRecord, MemoryType
from memory.search import MemorySearchQuery

log = logging.getLogger(__name__)


class MemoryRepository(ABC):
    """Abstract base class defining repository operations for MemoryRecords."""

    @abstractmethod
    def create_memory(self, record: MemoryRecord) -> None:
        """Create a new memory record in storage."""
        pass

    @abstractmethod
    def get_memory(self, memory_id: str) -> MemoryRecord:
        """Retrieve a memory record by ID. Raises MemoryNotFoundError if not found."""
        pass

    @abstractmethod
    def update_memory(self, record: MemoryRecord) -> None:
        """Update an existing memory record. Raises MemoryNotFoundError if not found."""
        pass

    @abstractmethod
    def delete_memory(self, memory_id: str) -> None:
        """Delete a memory record by ID. Raises MemoryNotFoundError if not found."""
        pass

    @abstractmethod
    def search_memory(self, query: MemorySearchQuery) -> list[MemoryRecord]:
        """Search memory records matching the criteria."""
        pass

    @abstractmethod
    def list_memories(self) -> list[MemoryRecord]:
        """List all memories ordered by creation time descending."""
        pass


class SQLiteMemoryRepository(MemoryRepository):
    """Concrete SQLite implementation of MemoryRepository."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def create_memory(self, record: MemoryRecord) -> None:
        sql = """
            INSERT INTO memories (id, type, content, tags, project, agent, importance, source, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        tags_serialized = json.dumps(record.tags)
        with self.db_manager.transaction() as conn:
            conn.execute(
                sql,
                (
                    record.id,
                    record.type.value,
                    record.content,
                    tags_serialized,
                    record.project,
                    record.agent,
                    record.importance,
                    record.source,
                    record.created_at,
                    record.updated_at,
                ),
            )

    def get_memory(self, memory_id: str) -> MemoryRecord:
        sql = "SELECT * FROM memories WHERE id = ?"
        with self.db_manager.transaction() as conn:
            cursor = conn.execute(sql, (memory_id,))
            row = cursor.fetchone()
            if row is None:
                raise MemoryNotFoundError(f"Memory with ID '{memory_id}' not found.")
            return self._map_row(row)

    def update_memory(self, record: MemoryRecord) -> None:
        sql = """
            UPDATE memories
            SET type = ?, content = ?, tags = ?, project = ?, agent = ?, importance = ?, source = ?, created_at = ?, updated_at = ?
            WHERE id = ?
        """
        tags_serialized = json.dumps(record.tags)
        with self.db_manager.transaction() as conn:
            cursor = conn.execute(
                sql,
                (
                    record.type.value,
                    record.content,
                    tags_serialized,
                    record.project,
                    record.agent,
                    record.importance,
                    record.source,
                    record.created_at,
                    record.updated_at,
                    record.id,
                ),
            )
            if cursor.rowcount == 0:
                raise MemoryNotFoundError(f"Memory with ID '{record.id}' not found.")

    def delete_memory(self, memory_id: str) -> None:
        sql = "DELETE FROM memories WHERE id = ?"
        with self.db_manager.transaction() as conn:
            cursor = conn.execute(sql, (memory_id,))
            if cursor.rowcount == 0:
                raise MemoryNotFoundError(f"Memory with ID '{memory_id}' not found.")

    def list_memories(self) -> list[MemoryRecord]:
        sql = "SELECT * FROM memories ORDER BY created_at DESC"
        with self.db_manager.transaction() as conn:
            cursor = conn.execute(sql)
            rows = cursor.fetchall()
            return [self._map_row(row) for row in rows]

    def search_memory(self, query: MemorySearchQuery) -> list[MemoryRecord]:
        sql_parts = ["SELECT * FROM memories WHERE 1=1"]
        params: list[Any] = []

        if query.keyword:
            sql_parts.append("AND content LIKE ?")
            params.append(f"%{query.keyword}%")

        if query.project is not None:
            sql_parts.append("AND project = ?")
            params.append(query.project)

        if query.agent is not None:
            sql_parts.append("AND agent = ?")
            params.append(query.agent)

        if query.memory_type is not None:
            sql_parts.append("AND type = ?")
            params.append(query.memory_type.value)

        if query.importance is not None:
            sql_parts.append("AND importance = ?")
            params.append(query.importance)

        if query.start_date is not None:
            sql_parts.append("AND created_at >= ?")
            params.append(query.start_date)

        if query.end_date is not None:
            sql_parts.append("AND created_at <= ?")
            params.append(query.end_date)

        # Apply LIKE constraints for tags in SQL as a first pass filter
        if query.tags:
            for tag in query.tags:
                sql_parts.append("AND tags LIKE ?")
                params.append(f'%"{tag}"%')

        sql = " ".join(sql_parts) + " ORDER BY created_at DESC"

        with self.db_manager.transaction() as conn:
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            candidates = [self._map_row(row) for row in rows]

        # Double check tag membership in Python to eliminate false positives
        if query.tags:
            query_tag_set = set(query.tags)
            return [c for c in candidates if query_tag_set.issubset(set(c.tags))]
            
        return candidates

    def _map_row(self, row: dict[str, Any]) -> MemoryRecord:
        """Map database row to MemoryRecord dataclass."""
        try:
            tags_parsed = json.loads(row["tags"])
        except (TypeError, json.JSONDecodeError):
            tags_parsed = []

        return MemoryRecord(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            tags=tags_parsed,
            project=row["project"],
            agent=row["agent"],
            importance=row["importance"],
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

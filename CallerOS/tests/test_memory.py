"""
Tests: Memory System (Stage 5)
===============================
Covers:
  - MemoryRecord and MemoryType models.
  - SQLite DatabaseManager automatic creation and connection context.
  - CRUD operations in SQLiteMemoryRepository and MemoryManager.
  - Searching by keyword, tags, project, agent, importance, and date ranges.
  - Persistence across restarts using database files.
  - Error conditions (e.g., MemoryNotFoundError, DatabaseError).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from database.manager import DatabaseManager
from memory.exceptions import DatabaseError, MemoryNotFoundError
from memory.manager import MemoryManager
from memory.models import MemoryRecord, MemoryType
from memory.repository import SQLiteMemoryRepository
from memory.search import MemorySearchQuery


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def in_mem_db() -> DatabaseManager:
    """Fixture providing an in-memory DatabaseManager."""
    return DatabaseManager(":memory:")


@pytest.fixture
def memory_repo(in_mem_db: DatabaseManager) -> SQLiteMemoryRepository:
    """Fixture providing an SQLiteMemoryRepository connected to in-memory DB."""
    return SQLiteMemoryRepository(in_mem_db)


@pytest.fixture
def memory_manager(memory_repo: SQLiteMemoryRepository) -> MemoryManager:
    """Fixture providing a MemoryManager using the SQLiteMemoryRepository."""
    return MemoryManager(memory_repo)


# ---------------------------------------------------------------------------
# Tests: CRUD operations
# ---------------------------------------------------------------------------

class TestMemoryCRUD:
    def test_create_and_get_memory(self, memory_manager: MemoryManager) -> None:
        record = MemoryRecord(
            type=MemoryType.CONVERSATION,
            content="This is a conversation memory.",
            source="user",
            tags=["chat", "test"],
            project="GoblinOS",
            agent="Director",
            importance=5,
        )
        
        memory_manager.create_memory(record)
        
        retrieved = memory_manager.get_memory(record.id)
        assert retrieved.id == record.id
        assert retrieved.type == MemoryType.CONVERSATION
        assert retrieved.content == "This is a conversation memory."
        assert retrieved.source == "user"
        assert retrieved.tags == ["chat", "test"]
        assert retrieved.project == "GoblinOS"
        assert retrieved.agent == "Director"
        assert retrieved.importance == 5
        assert retrieved.created_at == record.created_at
        assert retrieved.updated_at == record.updated_at

    def test_get_nonexistent_memory_raises(self, memory_manager: MemoryManager) -> None:
        with pytest.raises(MemoryNotFoundError, match="not found"):
            memory_manager.get_memory("nonexistent-uuid")

    def test_update_memory(self, memory_manager: MemoryManager) -> None:
        record = MemoryRecord(
            type=MemoryType.PROJECT,
            content="Original content.",
            source="researcher",
            importance=2,
        )
        memory_manager.create_memory(record)
        
        # Modify and update
        updated_record = MemoryRecord(
            id=record.id,
            type=MemoryType.PROJECT,
            content="Updated content.",
            source="researcher",
            tags=["updated"],
            project="NewProj",
            agent="NewAgent",
            importance=8,
            created_at=record.created_at,
        )
        
        import time
        time.sleep(0.01)
        memory_manager.update_memory(updated_record)
        
        retrieved = memory_manager.get_memory(record.id)
        assert retrieved.content == "Updated content."
        assert retrieved.tags == ["updated"]
        assert retrieved.project == "NewProj"
        assert retrieved.agent == "NewAgent"
        assert retrieved.importance == 8
        # The updated_at timestamp should have been updated to a newer ISO timestamp
        assert retrieved.updated_at != record.updated_at

    def test_update_nonexistent_memory_raises(self, memory_manager: MemoryManager) -> None:
        record = MemoryRecord(
            id="nonexistent-uuid",
            type=MemoryType.AGENT,
            content="content",
            source="agent",
        )
        with pytest.raises(MemoryNotFoundError):
            memory_manager.update_memory(record)

    def test_delete_memory(self, memory_manager: MemoryManager) -> None:
        record = MemoryRecord(
            type=MemoryType.AGENT,
            content="ToDelete",
            source="system",
        )
        memory_manager.create_memory(record)
        
        # Verify it exists
        assert memory_manager.get_memory(record.id) is not None
        
        # Delete
        memory_manager.delete_memory(record.id)
        
        # Verify it is deleted
        with pytest.raises(MemoryNotFoundError):
            memory_manager.get_memory(record.id)

    def test_delete_nonexistent_memory_raises(self, memory_manager: MemoryManager) -> None:
        with pytest.raises(MemoryNotFoundError):
            memory_manager.delete_memory("nonexistent-uuid")

    def test_list_memories(self, memory_manager: MemoryManager) -> None:
        # Create multiple records
        r1 = MemoryRecord(type=MemoryType.CONVERSATION, content="M1", source="s1")
        r2 = MemoryRecord(type=MemoryType.PROJECT, content="M2", source="s2")
        
        memory_manager.create_memory(r1)
        memory_manager.create_memory(r2)
        
        all_memories = memory_manager.list_memories()
        assert len(all_memories) == 2
        # Ordered by created_at descending, or just check IDs present
        ids = [m.id for m in all_memories]
        assert r1.id in ids
        assert r2.id in ids


# ---------------------------------------------------------------------------
# Tests: Search / Filtering
# ---------------------------------------------------------------------------

class TestMemorySearch:
    @pytest.fixture(autouse=True)
    def setup_data(self, memory_manager: MemoryManager) -> None:
        # Insert test records for search filters
        self.r1 = MemoryRecord(
            id="uuid-1",
            type=MemoryType.CONVERSATION,
            content="Python programming is simple and fun.",
            source="user",
            tags=["python", "simple"],
            project="NGOS",
            agent="Director",
            importance=9,
            created_at="2026-07-02T00:00:00Z",
        )
        self.r2 = MemoryRecord(
            id="uuid-2",
            type=MemoryType.PROJECT,
            content="Writing SQLite database logic in memory.",
            source="developer",
            tags=["sqlite", "database"],
            project="NGOS",
            agent="DeveloperAgent",
            importance=5,
            created_at="2026-07-02T01:00:00Z",
        )
        self.r3 = MemoryRecord(
            id="uuid-3",
            type=MemoryType.AGENT,
            content="Web search stubs are implemented in CallerOS.",
            source="researcher",
            tags=["web", "stub", "simple"],
            project="CallerOS",
            agent="ResearchAgent",
            importance=3,
            created_at="2026-07-02T02:00:00Z",
        )
        
        memory_manager.create_memory(self.r1)
        memory_manager.create_memory(self.r2)
        memory_manager.create_memory(self.r3)

    def test_search_keyword(self, memory_manager: MemoryManager) -> None:
        # Match 'programming'
        q = MemorySearchQuery(keyword="programming")
        res = memory_manager.search_memory(q)
        assert len(res) == 1
        assert res[0].id == "uuid-1"

        # Match 'simple' in content or not? Keyword only filters 'content LIKE %keyword%'
        q2 = MemorySearchQuery(keyword="implemented")
        res2 = memory_manager.search_memory(q2)
        assert len(res2) == 1
        assert res2[0].id == "uuid-3"

    def test_search_tags(self, memory_manager: MemoryManager) -> None:
        # Search single tag 'simple'
        q = MemorySearchQuery(tags=["simple"])
        res = memory_manager.search_memory(q)
        # uuid-1 and uuid-3 have 'simple'
        assert len(res) == 2
        ids = [r.id for r in res]
        assert "uuid-1" in ids
        assert "uuid-3" in ids

        # Search multiple tags (must contain all of them)
        q2 = MemorySearchQuery(tags=["python", "simple"])
        res2 = memory_manager.search_memory(q2)
        assert len(res2) == 1
        assert res2[0].id == "uuid-1"

        # Search non-matching tag
        q3 = MemorySearchQuery(tags=["rust"])
        res3 = memory_manager.search_memory(q3)
        assert len(res3) == 0

    def test_search_project(self, memory_manager: MemoryManager) -> None:
        q = MemorySearchQuery(project="NGOS")
        res = memory_manager.search_memory(q)
        assert len(res) == 2
        ids = [r.id for r in res]
        assert "uuid-1" in ids
        assert "uuid-2" in ids

    def test_search_agent(self, memory_manager: MemoryManager) -> None:
        q = MemorySearchQuery(agent="ResearchAgent")
        res = memory_manager.search_memory(q)
        assert len(res) == 1
        assert res[0].id == "uuid-3"

    def test_search_memory_type(self, memory_manager: MemoryManager) -> None:
        q = MemorySearchQuery(memory_type=MemoryType.PROJECT)
        res = memory_manager.search_memory(q)
        assert len(res) == 1
        assert res[0].id == "uuid-2"

    def test_search_importance(self, memory_manager: MemoryManager) -> None:
        q = MemorySearchQuery(importance=5)
        res = memory_manager.search_memory(q)
        assert len(res) == 1
        assert res[0].id == "uuid-2"

    def test_search_date_range(self, memory_manager: MemoryManager) -> None:
        # Range covers uuid-1 and uuid-2
        q = MemorySearchQuery(start_date="2026-07-02T00:00:00Z", end_date="2026-07-02T01:30:00Z")
        res = memory_manager.search_memory(q)
        assert len(res) == 2
        ids = [r.id for r in res]
        assert "uuid-1" in ids
        assert "uuid-2" in ids


# ---------------------------------------------------------------------------
# Tests: Restart & Persistence
# ---------------------------------------------------------------------------

class TestMemoryPersistence:
    def test_persistence_across_restart(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test_persist.db"
        
        # 1. Setup DB manager and write a memory
        db_mgr_1 = DatabaseManager(db_file)
        repo_1 = SQLiteMemoryRepository(db_mgr_1)
        manager_1 = MemoryManager(repo_1)
        
        record = MemoryRecord(
            type=MemoryType.CONVERSATION,
            content="Should survive the restart.",
            source="user",
        )
        manager_1.create_memory(record)
        
        # Dispose of them to simulate shutdown/restart
        del manager_1, repo_1, db_mgr_1
        
        # 2. Reload from same file
        db_mgr_2 = DatabaseManager(db_file)
        repo_2 = SQLiteMemoryRepository(db_mgr_2)
        manager_2 = MemoryManager(repo_2)
        
        retrieved = manager_2.get_memory(record.id)
        assert retrieved.content == "Should survive the restart."


# ---------------------------------------------------------------------------
# Tests: Errors & Edge cases
# ---------------------------------------------------------------------------

class TestMemoryErrors:
    def test_database_error_propagation(self, in_mem_db: DatabaseManager) -> None:
        repo = SQLiteMemoryRepository(in_mem_db)
        manager = MemoryManager(repo)
        
        # Mock transaction on DatabaseManager to raise DatabaseError
        with patch.object(in_mem_db, "transaction", side_effect=DatabaseError("Database error: Mock SQL error")):
            record = MemoryRecord(type=MemoryType.AGENT, content="Fail", source="system")
            with pytest.raises(DatabaseError, match="Database error"):
                manager.create_memory(record)

    def test_invalid_uuid_retrieval_raises_not_found(self, memory_manager: MemoryManager) -> None:
        with pytest.raises(MemoryNotFoundError):
            memory_manager.get_memory("garbage-uuid-string")
            
    def test_update_mismatched_id_raises_not_found(self, memory_manager: MemoryManager) -> None:
        record = MemoryRecord(
            id="uuid-does-not-exist",
            type=MemoryType.CONVERSATION,
            content="Content",
            source="user",
        )
        with pytest.raises(MemoryNotFoundError):
            memory_manager.update_memory(record)
            
    def test_delete_mismatched_id_raises_not_found(self, memory_manager: MemoryManager) -> None:
        with pytest.raises(MemoryNotFoundError):
            memory_manager.delete_memory("uuid-does-not-exist")

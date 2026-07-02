"""
Tests: Database Layer (Stage 9)
===============================
Covers:
  - DatabaseManager initialization and ConnectionManager open/close.
  - MigrationEngine applying INITIAL_SCHEMA to get version 1.
  - CRUD operations across all repositories (Conversation, Memory, WorkflowHistory, Log, Settings).
  - Transaction rollbacks.
  - Proper exception wrapping (hiding raw sqlite3 exceptions).
"""

from __future__ import annotations

import sqlite3
import pytest

from database.exceptions import DatabaseError, MigrationError, RepositoryError
from database.manager import DatabaseManager
from database.models import (
    Conversation,
    LogEntry,
    Memory,
    Message,
    Setting,
    WorkflowHistory,
)
from database.repositories import (
    ConversationRepository,
    LogRepository,
    MemoryRepository,
    SettingsRepository,
    WorkflowHistoryRepository,
)


@pytest.fixture
def db_manager() -> DatabaseManager:
    """Provides a freshly migrated in-memory DatabaseManager."""
    mgr = DatabaseManager(":memory:")
    yield mgr
    mgr.close()


# ---------------------------------------------------------------------------
# Migration & Schema Tests
# ---------------------------------------------------------------------------

class TestDatabaseMigration:
    def test_schema_created_automatically(self, db_manager: DatabaseManager) -> None:
        # Check that tables exist by querying sqlite_master
        cursor = db_manager.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row["name"] for row in cursor.fetchall()]
        
        assert "conversations" in tables
        assert "messages" in tables
        assert "memories" in tables
        assert "workflow_history" in tables
        assert "settings" in tables
        assert "logs" in tables
        assert "schema_version" in tables

    def test_version_tracking(self, db_manager: DatabaseManager) -> None:
        cursor = db_manager.execute("SELECT version FROM schema_version")
        row = cursor.fetchone()
        assert row is not None
        assert row["version"] == 1


# ---------------------------------------------------------------------------
# Transaction & Rollback Tests
# ---------------------------------------------------------------------------

class TestTransactions:
    def test_rollback_on_failure(self, db_manager: DatabaseManager) -> None:
        # Insert a setting inside a transaction that fails
        repo = SettingsRepository(db_manager.connection_manager)
        repo.set_value("theme", "dark")
        
        # Verify initial value
        assert repo.get_value("theme") == "dark"
        
        # Start a failing transaction
        with pytest.raises(DatabaseError):
            with db_manager.transaction() as conn:
                conn.execute("UPDATE settings SET value = 'light' WHERE key = 'theme'")
                # Intentionally trigger an error (duplicate key insert)
                conn.execute("INSERT INTO settings (key, value) VALUES ('theme', 'duplicate')")
                
        # Value must not be modified due to rollback
        assert repo.get_value("theme") == "dark"


# ---------------------------------------------------------------------------
# Repository Tests
# ---------------------------------------------------------------------------

class TestRepositories:
    def test_conversation_and_messages_crud(self, db_manager: DatabaseManager) -> None:
        repo = ConversationRepository(db_manager.connection_manager)
        
        # 1. Create conversation
        conv = Conversation(title="Goblin Discussion")
        repo.create_conversation(conv)
        
        # 2. Get and list
        retrieved = repo.get_conversation(conv.id)
        assert retrieved.title == "Goblin Discussion"
        
        all_convs = repo.list_conversations()
        assert len(all_convs) == 1
        assert all_convs[0].id == conv.id
        
        # 3. Add and get messages
        msg1 = Message(conversation_id=conv.id, role="user", content="Hello Goblin")
        msg2 = Message(conversation_id=conv.id, role="assistant", content="Greetings User")
        repo.add_message(msg1)
        repo.add_message(msg2)
        
        messages = repo.get_messages(conv.id)
        assert len(messages) == 2
        assert messages[0].content == "Hello Goblin"
        assert messages[1].content == "Greetings User"
        
        # 4. Update
        updated_conv = Conversation(id=conv.id, title="Polished Goblin Discussion")
        repo.update_conversation(updated_conv)
        assert repo.get_conversation(conv.id).title == "Polished Goblin Discussion"
        
        # 5. Delete (cascades to messages due to foreign key constraints)
        repo.delete_conversation(conv.id)
        with pytest.raises(RepositoryError):
            repo.get_conversation(conv.id)
        assert len(repo.get_messages(conv.id)) == 0

    def test_memory_repository_crud_and_search(self, db_manager: DatabaseManager) -> None:
        repo = MemoryRepository(db_manager.connection_manager)
        
        mem1 = Memory(
            type="CONVERSATION",
            content="Python is simple.",
            tags=["python", "simple"],
            project="default",
            agent="Director",
            source="user",
        )
        mem2 = Memory(
            type="PROJECT",
            content="SQLite database backend logic.",
            tags=["sqlite", "database"],
            project="GoblinOS",
            agent="Developer",
            source="system",
        )
        
        repo.create_memory(mem1)
        repo.create_memory(mem2)
        
        # Verify lists
        assert len(repo.list_memories()) == 2
        
        # Retrieve by id
        assert repo.get_memory(mem1.id).content == "Python is simple."
        
        # Search by tag
        res = repo.search_memories(tags=["python"])
        assert len(res) == 1
        assert res[0].id == mem1.id
        
        # Search by project
        res2 = repo.search_memories(project="GoblinOS")
        assert len(res2) == 1
        assert res2[0].id == mem2.id
        
        # Update
        updated = Memory(
            id=mem1.id,
            type="CONVERSATION",
            content="Python is elegant and simple.",
            tags=["python", "elegant"],
            source="user",
        )
        repo.update_memory(updated)
        assert repo.get_memory(mem1.id).content == "Python is elegant and simple."
        
        # Delete
        repo.delete_memory(mem1.id)
        with pytest.raises(RepositoryError):
            repo.get_memory(mem1.id)

    def test_workflow_history_repository(self, db_manager: DatabaseManager) -> None:
        repo = WorkflowHistoryRepository(db_manager.connection_manager)
        
        hist = WorkflowHistory(
            workflow_id="wf-123",
            state="COMPLETED",
            request='{"query": "run"}',
            response='{"output": "ok"}',
        )
        repo.create_history(hist)
        
        retrieved = repo.get_history(hist.id)
        assert retrieved.workflow_id == "wf-123"
        assert retrieved.state == "COMPLETED"
        assert retrieved.request == '{"query": "run"}'
        
        all_hist = repo.list_histories()
        assert len(all_hist) == 1

    def test_settings_repository(self, db_manager: DatabaseManager) -> None:
        repo = SettingsRepository(db_manager.connection_manager)
        
        # Insert
        repo.set_value("env", "test")
        assert repo.get_value("env") == "test"
        
        # Update (Conflict check)
        repo.set_value("env", "production")
        assert repo.get_value("env") == "production"
        
        # Delete
        repo.delete_value("env")
        assert repo.get_value("env") is None
        
        with pytest.raises(RepositoryError):
            repo.delete_value("nonexistent")

    def test_log_repository(self, db_manager: DatabaseManager) -> None:
        repo = LogRepository(db_manager.connection_manager)
        
        log1 = LogEntry(timestamp="2026-07-02T06:00:00Z", level="INFO", message="Booting")
        log2 = LogEntry(timestamp="2026-07-02T06:01:00Z", level="ERROR", message="Failure")
        
        repo.create_log(log1)
        repo.create_log(log2)
        
        all_logs = repo.list_logs()
        assert len(all_logs) == 2
        assert all_logs[0].message == "Booting"
        assert all_logs[1].level == "ERROR"


# ---------------------------------------------------------------------------
# Exception Handling Tests
# ---------------------------------------------------------------------------

class TestExceptionWrapping:
    def test_sql_error_wrapped_in_database_error(self, db_manager: DatabaseManager) -> None:
        # Trigger an illegal insert statement to verify Exception wrapping (duplicate primary key)
        db_manager.execute("INSERT INTO settings (key, value) VALUES ('theme', 'dark')")
        with pytest.raises(DatabaseError):
            db_manager.execute("INSERT INTO settings (key, value) VALUES ('theme', 'light')")

    def test_missing_record_raises_repository_error(self, db_manager: DatabaseManager) -> None:
        repo = ConversationRepository(db_manager.connection_manager)
        with pytest.raises(RepositoryError, match="not found"):
            repo.get_conversation("missing-id")

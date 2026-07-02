"""
Conversation Repository
=======================
Handles SQL CRUD operations for Conversations and Messages tables.
"""

from __future__ import annotations

import logging
import sqlite3

from database.connection import ConnectionManager
from database.exceptions import RepositoryError
from database.models import Conversation, Message

log = logging.getLogger(__name__)


class ConversationRepository:
    """
    CRUD repository for Conversations and associated Messages.
    """

    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def create_conversation(self, conv: Conversation) -> None:
        sql = """
            INSERT INTO conversations (id, title, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """
        try:
            self._db.execute(sql, (conv.id, conv.title, conv.created_at, conv.updated_at))
        except Exception as exc:
            log.error("Failed to create conversation: %s", exc)
            raise RepositoryError(f"Error creating conversation: {exc}") from exc

    def get_conversation(self, conv_id: str) -> Conversation:
        sql = "SELECT * FROM conversations WHERE id = ?"
        try:
            cursor = self._db.execute(sql, (conv_id,))
            row = cursor.fetchone()
            if not row:
                raise RepositoryError(f"Conversation with ID '{conv_id}' not found.")
            return Conversation(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
        except RepositoryError:
            raise
        except Exception as exc:
            log.error("Failed to get conversation ID %s: %s", conv_id, exc)
            raise RepositoryError(f"Error getting conversation: {exc}") from exc

    def update_conversation(self, conv: Conversation) -> None:
        sql = """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ?
        """
        try:
            cursor = self._db.execute(sql, (conv.title, conv.updated_at, conv.id))
            if cursor.rowcount == 0:
                raise RepositoryError(f"Conversation with ID '{conv.id}' not found.")
        except RepositoryError:
            raise
        except Exception as exc:
            log.error("Failed to update conversation ID %s: %s", conv.id, exc)
            raise RepositoryError(f"Error updating conversation: {exc}") from exc

    def delete_conversation(self, conv_id: str) -> None:
        sql = "DELETE FROM conversations WHERE id = ?"
        try:
            cursor = self._db.execute(sql, (conv_id,))
            if cursor.rowcount == 0:
                raise RepositoryError(f"Conversation with ID '{conv_id}' not found.")
        except RepositoryError:
            raise
        except Exception as exc:
            log.error("Failed to delete conversation ID %s: %s", conv_id, exc)
            raise RepositoryError(f"Error deleting conversation: {exc}") from exc

    def list_conversations(self) -> list[Conversation]:
        sql = "SELECT * FROM conversations ORDER BY created_at DESC"
        try:
            cursor = self._db.execute(sql)
            rows = cursor.fetchall()
            return [
                Conversation(
                    id=row["id"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]
        except Exception as exc:
            log.error("Failed to list conversations: %s", exc)
            raise RepositoryError(f"Error listing conversations: {exc}") from exc

    def add_message(self, msg: Message) -> None:
        sql = """
            INSERT INTO messages (id, conversation_id, role, content, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """
        try:
            self._db.execute(sql, (msg.id, msg.conversation_id, msg.role, msg.content, msg.timestamp))
        except Exception as exc:
            log.error("Failed to add message to conversation ID %s: %s", msg.conversation_id, exc)
            raise RepositoryError(f"Error adding message: {exc}") from exc

    def get_messages(self, conv_id: str) -> list[Message]:
        sql = "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC"
        try:
            cursor = self._db.execute(sql, (conv_id,))
            rows = cursor.fetchall()
            return [
                Message(
                    id=row["id"],
                    conversation_id=row["conversation_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                )
                for row in rows
            ]
        except Exception as exc:
            log.error("Failed to get messages for conversation ID %s: %s", conv_id, exc)
            raise RepositoryError(f"Error retrieving messages: {exc}") from exc

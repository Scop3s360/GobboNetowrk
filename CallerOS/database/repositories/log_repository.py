"""
Log Repository
==============
Handles appending and querying log records in the SQLite database.
"""

from __future__ import annotations

import logging

from database.connection import ConnectionManager
from database.exceptions import RepositoryError
from database.models import LogEntry

log = logging.getLogger(__name__)


class LogRepository:
    """
    CRUD repository for LogEntry records.
    """

    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def create_log(self, entry: LogEntry) -> None:
        sql = """
            INSERT INTO logs (timestamp, level, message)
            VALUES (?, ?, ?)
        """
        try:
            self._db.execute(sql, (entry.timestamp, entry.level, entry.message))
        except Exception as exc:
            log.error("Failed to append DB log entry: %s", exc)
            raise RepositoryError(f"Error creating log entry: {exc}") from exc

    def list_logs(self) -> list[LogEntry]:
        sql = "SELECT * FROM logs ORDER BY id ASC"
        try:
            cursor = self._db.execute(sql)
            rows = cursor.fetchall()
            return [
                LogEntry(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    level=row["level"],
                    message=row["message"],
                )
                for row in rows
            ]
        except Exception as exc:
            log.error("Failed to list DB logs: %s", exc)
            raise RepositoryError(f"Error listing logs: {exc}") from exc

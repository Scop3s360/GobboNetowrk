"""
Connection Manager
==================
Handles SQLite connection states, transactions, rollbacks, and parameterised queries.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from database.exceptions import DatabaseError

log = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages SQLite connections, executing queries, and controlling transactions
    while wrapping sqlite3 exceptions in custom exceptions.
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize the ConnectionManager.

        Args:
            db_path: Path to database file, or ':memory:'.
        """
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def open(self) -> None:
        """
        Establish the database connection.
        Keeps a single open connection for the lifetime of this manager.
        """
        if self._conn is not None:
            return
            
        try:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys=ON;")
            if self.db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode=WAL;")
            log.info("SQLite connection opened: %s", self.db_path)
        except sqlite3.Error as exc:
            log.error("Failed to open database connection: %s", exc)
            raise DatabaseError(f"Failed to open database: {exc}") from exc

    def close(self) -> None:
        """Close any active database connections."""
        if self._conn is not None:
            try:
                self._conn.close()
                log.info("SQLite connection closed: %s", self.db_path)
            except sqlite3.Error as exc:
                log.error("Error closing SQLite connection: %s", exc)
            finally:
                self._conn = None

    @contextmanager
    def transaction(self):
        """
        Context manager to run queries inside a transaction block.
        Yields the connection object. Automatically commits on success
        and rolls back on any error.
        """
        self.open()
        
        try:
            yield self._conn
            self._conn.commit()
        except sqlite3.Error as exc:
            try:
                self._conn.rollback()
            except sqlite3.Error:
                pass
            raise DatabaseError(f"Database transaction error: {exc}") from exc
        except Exception:
            try:
                self._conn.rollback()
            except sqlite3.Error:
                pass
            raise

    def execute(self, sql: str, params: tuple | dict | None = None) -> sqlite3.Cursor:
        """
        Execute a single SQL query.

        Args:
            sql:    SQL query string.
            params: Parameters to bind to query.

        Returns:
            The cursor object.
        """
        params = params or ()
        with self.transaction() as conn:
            try:
                return conn.execute(sql, params)
            except sqlite3.Error as exc:
                log.error("SQL execution failed: %s (SQL: %s)", exc, sql)
                raise DatabaseError(f"SQL execution error: {exc}") from exc

    def execute_many(self, sql: str, seq_of_params: list[tuple] | list[dict]) -> sqlite3.Cursor:
        """
        Execute an SQL query against a sequence of parameters.

        Args:
            sql:           SQL query string.
            seq_of_params: List of bindings.

        Returns:
            The cursor object.
        """
        with self.transaction() as conn:
            try:
                return conn.executemany(sql, seq_of_params)
            except sqlite3.Error as exc:
                log.error("SQL executemany failed: %s (SQL: %s)", exc, sql)
                raise DatabaseError(f"SQL execution error: {exc}") from exc

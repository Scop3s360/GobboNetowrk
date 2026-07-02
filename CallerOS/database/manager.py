"""
Database Manager
================
Coordinative entrypoint managing connections, executing migrations,
and serving as the single registry-accessible database service.
"""

from __future__ import annotations

import logging
from pathlib import Path

from database.connection import ConnectionManager
from database.migrations import MigrationEngine

log = logging.getLogger(__name__)


class DatabaseManager:
    """
    Main database service coordinator.
    """

    def __init__(self, db_path: str | Path) -> None:
        """
        Initialize the DatabaseManager.

        Args:
            db_path: SQLite database path or ':memory:'.
        """
        self.db_path = db_path
        self._connection_manager = ConnectionManager(db_path)
        self._migration_engine = MigrationEngine(self._connection_manager)
        
        # Open connection and run migrations immediately
        self.open()
        self.initialize_schema()

    def open(self) -> None:
        """Open connections."""
        self._connection_manager.open()
        log.info("DatabaseManager: database connection opened.")

    def close(self) -> None:
        """Close connections."""
        self._connection_manager.close()
        log.info("DatabaseManager: database connection closed.")

    def initialize_schema(self) -> None:
        """Run the migration engine upgrade loop."""
        log.info("DatabaseManager: running migrations...")
        self._migration_engine.upgrade()

    @property
    def connection_manager(self) -> ConnectionManager:
        """Expose the connection manager directly for repositories."""
        return self._connection_manager

    def execute(self, sql: str, params: tuple | dict | None = None) -> object:
        """Shortcut to execute queries directly."""
        return self._connection_manager.execute(sql, params)

    def execute_many(self, sql: str, seq_of_params: list[tuple] | list[dict]) -> object:
        """Shortcut to execute bulk queries."""
        return self._connection_manager.execute_many(sql, seq_of_params)

    def transaction(self):
        """Shortcut to get transaction context manager."""
        return self._connection_manager.transaction()

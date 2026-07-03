"""
Database Migrations
===================
Handles automatic schema creation and incremental version upgrades on startup.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

from database.connection import ConnectionManager
from database.exceptions import MigrationError
from database.schema import INITIAL_SCHEMA

log = logging.getLogger(__name__)


# Migration scripts dictionary.
# Key: version (int), Value: list of SQL statements.
MIGRATIONS: dict[int, list[str]] = {
    1: INITIAL_SCHEMA,
    2: [
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            type TEXT NOT NULL,
            tags TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_opened_at TEXT NOT NULL
        );
        """
    ],
    3: [
        "ALTER TABLE projects ADD COLUMN source_dir TEXT;"
    ]
}

LATEST_VERSION = max(MIGRATIONS.keys())


class MigrationEngine:
    """
    Applies database migrations to keep the database schema up to date.
    """

    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._db = connection_manager

    def get_current_version(self) -> int:
        """
        Retrieve the current database schema version.
        Returns 0 if the schema_version table does not exist.
        """
        try:
            cursor = self._db.execute("SELECT max(version) FROM schema_version")
            row = cursor.fetchone()
            if row and row[0] is not None:
                return int(row[0])
            return 0
        except Exception:
            # Table doesn't exist yet, return version 0
            return 0

    def upgrade(self) -> None:
        """
        Upgrade the database schema to the latest version.
        Runs migrations sequentially inside a transaction block.
        """
        self._db.open()
        current_version = self.get_current_version()
        log.info("MigrationEngine: checking migrations. Current version: %d, Latest: %d", current_version, LATEST_VERSION)
        
        if current_version >= LATEST_VERSION:
            log.info("MigrationEngine: database is already up to date.")
            return

        for version in sorted(MIGRATIONS.keys()):
            if version > current_version:
                log.info("MigrationEngine: applying migration version %d...", version)
                start_time = datetime.now(timezone.utc).isoformat()
                
                try:
                    with self._db.transaction() as conn:
                        # Apply SQL statements for this version
                        for statement in MIGRATIONS[version]:
                            if statement.strip():
                                conn.execute(statement)
                                
                        # Update schema_version table
                        conn.execute(
                            "INSERT INTO schema_version (version, migrated_at) VALUES (?, ?)",
                            (version, start_time),
                        )
                    log.info("MigrationEngine: version %d applied successfully.", version)
                except Exception as exc:
                    log.critical("MigrationEngine: migration version %d failed: %s", version, exc)
                    raise MigrationError(f"Failed to apply migration version {version}: {exc}") from exc
                    
        log.info("MigrationEngine: database schema upgrade complete.")

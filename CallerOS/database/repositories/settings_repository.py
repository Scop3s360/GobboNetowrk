"""
Settings Repository
===================
Handles key/value configuration lookups and updates on the settings table.
"""

from __future__ import annotations

import logging

from database.connection import ConnectionManager
from database.exceptions import RepositoryError

log = logging.getLogger(__name__)


class SettingsRepository:
    """
    CRUD operations for settings key/value pairs.
    """

    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def set_value(self, key: str, value: str) -> None:
        sql = """
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """
        try:
            self._db.execute(sql, (key, value))
        except Exception as exc:
            log.error("Failed to set settings key '%s': %s", key, exc)
            raise RepositoryError(f"Error setting configuration value: {exc}") from exc

    def get_value(self, key: str) -> str | None:
        sql = "SELECT value FROM settings WHERE key = ?"
        try:
            cursor = self._db.execute(sql, (key,))
            row = cursor.fetchone()
            return row["value"] if row else None
        except Exception as exc:
            log.error("Failed to get settings key '%s': %s", key, exc)
            raise RepositoryError(f"Error getting configuration value: {exc}") from exc

    def delete_value(self, key: str) -> None:
        sql = "DELETE FROM settings WHERE key = ?"
        try:
            cursor = self._db.execute(sql, (key,))
            if cursor.rowcount == 0:
                raise RepositoryError(f"Settings key '{key}' not found.")
        except RepositoryError:
            raise
        except Exception as exc:
            log.error("Failed to delete settings key '%s': %s", key, exc)
            raise RepositoryError(f"Error deleting configuration value: {exc}") from exc

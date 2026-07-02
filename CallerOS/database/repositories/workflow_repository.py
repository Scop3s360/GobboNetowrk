"""
Workflow History Repository
===========================
Handles CRUD operations on the Workflow History table.
"""

from __future__ import annotations

import logging

from database.connection import ConnectionManager
from database.exceptions import RepositoryError
from database.models import WorkflowHistory

log = logging.getLogger(__name__)


class WorkflowHistoryRepository:
    """
    CRUD repository for WorkflowHistory records.
    """

    def __init__(self, db: ConnectionManager) -> None:
        self._db = db

    def create_history(self, history: WorkflowHistory) -> None:
        sql = """
            INSERT INTO workflow_history (id, workflow_id, state, request, response, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            self._db.execute(
                sql,
                (
                    history.id,
                    history.workflow_id,
                    history.state,
                    history.request,
                    history.response,
                    history.timestamp,
                ),
            )
        except Exception as exc:
            log.error("Failed to create workflow history: %s", exc)
            raise RepositoryError(f"Error creating workflow history: {exc}") from exc

    def get_history(self, history_id: str) -> WorkflowHistory:
        sql = "SELECT * FROM workflow_history WHERE id = ?"
        try:
            cursor = self._db.execute(sql, (history_id,))
            row = cursor.fetchone()
            if not row:
                raise RepositoryError(f"Workflow history with ID '{history_id}' not found.")
            return WorkflowHistory(
                id=row["id"],
                workflow_id=row["workflow_id"],
                state=row["state"],
                request=row["request"],
                response=row["response"],
                timestamp=row["timestamp"],
            )
        except RepositoryError:
            raise
        except Exception as exc:
            log.error("Failed to get workflow history ID %s: %s", history_id, exc)
            raise RepositoryError(f"Error getting workflow history: {exc}") from exc

    def list_histories(self) -> list[WorkflowHistory]:
        sql = "SELECT * FROM workflow_history ORDER BY timestamp DESC"
        try:
            cursor = self._db.execute(sql)
            rows = cursor.fetchall()
            return [
                WorkflowHistory(
                    id=row["id"],
                    workflow_id=row["workflow_id"],
                    state=row["state"],
                    request=row["request"],
                    response=row["response"],
                    timestamp=row["timestamp"],
                )
                for row in rows
            ]
        except Exception as exc:
            log.error("Failed to list workflow histories: %s", exc)
            raise RepositoryError(f"Error listing workflow histories: {exc}") from exc

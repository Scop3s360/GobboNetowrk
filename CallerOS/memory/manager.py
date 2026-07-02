"""
Memory Manager Service
======================
The primary facade/service interface for all memory operations in GoblinOS.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from dataclasses import replace

from memory.exceptions import MemoryError
from memory.models import MemoryRecord
from memory.repository import MemoryRepository
from memory.search import MemorySearchQuery

log = logging.getLogger(__name__)


class MemoryManager:
    """
    Main service coordinating access to memories.
    Handles logging, timing measurements, and CRUD operations.
    """

    def __init__(self, repository: MemoryRepository) -> None:
        """
        Initialize the MemoryManager.

        Args:
            repository: The storage repository implementation.
        """
        self._repository = repository

    def create_memory(self, record: MemoryRecord) -> None:
        """
        Save a new memory record.

        Args:
            record: The MemoryRecord to persist.
        """
        log.debug("Creating memory: id=%s type=%s", record.id, record.type.value)
        start = time.perf_counter()
        try:
            self._repository.create_memory(record)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            log.info(
                "Memory created: id=%s type=%s source=%s duration_ms=%.2f",
                record.id,
                record.type.name,
                record.source,
                elapsed_ms,
            )
        except MemoryError as exc:
            log.error("Failed to create memory: id=%s error=%s", record.id, exc)
            raise
        except Exception as exc:
            log.error("Unexpected failure creating memory: id=%s error=%s", record.id, exc)
            raise MemoryError(f"Failed to create memory: {exc}") from exc

    def get_memory(self, memory_id: str) -> MemoryRecord:
        """
        Retrieve a memory by ID.

        Args:
            memory_id: The unique UUID of the memory.

        Returns:
            The associated MemoryRecord.
        """
        log.debug("Retrieving memory: id=%s", memory_id)
        start = time.perf_counter()
        try:
            record = self._repository.get_memory(memory_id)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            log.debug("Memory retrieved: id=%s duration_ms=%.2f", memory_id, elapsed_ms)
            return record
        except MemoryError as exc:
            log.warning("Memory not found during retrieval: id=%s error=%s", memory_id, exc)
            raise
        except Exception as exc:
            log.error("Unexpected failure retrieving memory: id=%s error=%s", memory_id, exc)
            raise MemoryError(f"Failed to retrieve memory: {exc}") from exc

    def update_memory(self, record: MemoryRecord) -> None:
        """
        Update an existing memory record, bumping its updated_at timestamp.

        Args:
            record: The updated MemoryRecord to save.
        """
        log.debug("Updating memory: id=%s", record.id)
        start = time.perf_counter()
        
        # Bump the updated_at timestamp since this is an update operation
        updated_record = replace(record, updated_at=datetime.now(timezone.utc).isoformat())
        
        try:
            self._repository.update_memory(updated_record)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            log.info(
                "Memory updated: id=%s type=%s duration_ms=%.2f",
                updated_record.id,
                updated_record.type.name,
                elapsed_ms,
            )
        except MemoryError as exc:
            log.error("Failed to update memory: id=%s error=%s", record.id, exc)
            raise
        except Exception as exc:
            log.error("Unexpected failure updating memory: id=%s error=%s", record.id, exc)
            raise MemoryError(f"Failed to update memory: {exc}") from exc

    def delete_memory(self, memory_id: str) -> None:
        """
        Delete a memory record by ID.

        Args:
            memory_id: The unique ID to delete.
        """
        log.debug("Deleting memory: id=%s", memory_id)
        start = time.perf_counter()
        try:
            self._repository.delete_memory(memory_id)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            log.info("Memory deleted: id=%s duration_ms=%.2f", memory_id, elapsed_ms)
        except MemoryError as exc:
            log.error("Failed to delete memory: id=%s error=%s", memory_id, exc)
            raise
        except Exception as exc:
            log.error("Unexpected failure deleting memory: id=%s error=%s", memory_id, exc)
            raise MemoryError(f"Failed to delete memory: {exc}") from exc

    def search_memory(self, query: MemorySearchQuery) -> list[MemoryRecord]:
        """
        Search memory records matching query filters.

        Args:
            query: Search parameters.

        Returns:
            A list of matching MemoryRecords.
        """
        log.debug("Searching memory with query: %s", query)
        start = time.perf_counter()
        try:
            results = self._repository.search_memory(query)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            log.info(
                "Memory searched: found=%d matches, query_duration_ms=%.2f",
                len(results),
                elapsed_ms,
            )
            return results
        except MemoryError as exc:
            log.error("Memory search failed: query=%s error=%s", query, exc)
            raise
        except Exception as exc:
            log.error("Unexpected failure searching memory: query=%s error=%s", query, exc)
            raise MemoryError(f"Failed to search memory: {exc}") from exc

    def list_memories(self) -> list[MemoryRecord]:
        """
        List all memories.

        Returns:
            A list of all MemoryRecords.
        """
        log.debug("Listing all memories")
        start = time.perf_counter()
        try:
            results = self._repository.list_memories()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            log.debug("Memories listed: total=%d, duration_ms=%.2f", len(results), elapsed_ms)
            return results
        except MemoryError as exc:
            log.error("Listing memories failed: error=%s", exc)
            raise
        except Exception as exc:
            log.error("Unexpected failure listing memories: error=%s", exc)
            raise MemoryError(f"Failed to list memories: {exc}") from exc

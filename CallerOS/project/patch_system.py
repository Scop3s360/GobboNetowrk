"""
Patch System
============
Manages AI-suggested code patches and filesystem operations.
Forces safety by requiring user approval before editing, and maintains a
reversible backup history in a local .trash directory.
"""

from __future__ import annotations
import os
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass

log = logging.getLogger(__name__)

@dataclass
class FilePatch:
    target_file: str # Relative path from project source root
    original_content: str
    patched_content: str
    reason: str

class PatchManager:
    """
    Manages pending file changes and performs reversible file backups/operations.
    """

    def __init__(self, workspace_dir: Path, source_dir: Path) -> None:
        self.workspace_dir = Path(workspace_dir).resolve()
        self.source_dir = Path(source_dir).resolve()
        
        self.trash_dir = self.workspace_dir / ".trash"
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        
        # Pending patches: key is relative file path
        self._pending_patches: dict[str, FilePatch] = {}
        
        # Backup history stack: list of dicts (original_path, backup_path, timestamp, operation)
        self._backup_history: list[dict] = []

    def create_patch(self, rel_file_path: str, patched_content: str, reason: str) -> FilePatch:
        """
        Stage a proposed patch for a file.
        """
        rel_file_path = rel_file_path.replace("\\", "/")
        full_path = (self.source_dir / rel_file_path).resolve()
        
        original_content = ""
        if full_path.is_file():
            original_content = full_path.read_text(encoding="utf-8", errors="ignore")
            
        patch = FilePatch(
            target_file=rel_file_path,
            original_content=original_content,
            patched_content=patched_content,
            reason=reason
        )
        self._pending_patches[rel_file_path] = patch
        log.info(f"PatchManager: staged patch for '{rel_file_path}' (reason: {reason})")
        return patch

    def get_patch(self, rel_file_path: str) -> FilePatch | None:
        return self._pending_patches.get(rel_file_path.replace("\\", "/"))

    def list_patches(self) -> list[FilePatch]:
        return list(self._pending_patches.values())

    def reject_patch(self, rel_file_path: str) -> None:
        rel_file_path = rel_file_path.replace("\\", "/")
        if rel_file_path in self._pending_patches:
            del self._pending_patches[rel_file_path]
            log.info(f"PatchManager: rejected and removed patch for '{rel_file_path}'")

    def apply_patch(self, rel_file_path: str) -> None:
        """
        Apply a staged patch after backing up the original file state.
        """
        rel_file_path = rel_file_path.replace("\\", "/")
        patch = self.get_patch(rel_file_path)
        if not patch:
            raise ValueError(f"No pending patch found for file: {rel_file_path}")
            
        full_path = (self.source_dir / rel_file_path).resolve()
        
        # 1. Back up the target file if it exists
        self.backup_file(rel_file_path, operation="modify")
        
        # 2. Ensure parent directories exist
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 3. Write patched content
        full_path.write_text(patch.patched_content, encoding="utf-8")
        
        # 4. Remove patch from pending
        del self._pending_patches[rel_file_path]
        log.info(f"PatchManager: successfully applied patch to '{rel_file_path}'")

    def backup_file(self, rel_file_path: str, operation: str) -> Path | None:
        """
        Copy current file state into the .trash folder before modifications or deletions.
        """
        rel_file_path = rel_file_path.replace("\\", "/")
        full_path = (self.source_dir / rel_file_path).resolve()
        
        if not full_path.exists():
            # If it's a new file, we back up the absence (allows undoing creation by deleting)
            self._backup_history.append({
                "original_path": str(full_path),
                "backup_path": None,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": "create"
            })
            return None
            
        # Generate backup filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = rel_file_path.replace("/", "_")
        backup_name = f"{safe_name}.{timestamp}.bak"
        backup_path = self.trash_dir / backup_name
        
        # Copy to trash
        shutil.copy2(full_path, backup_path)
        
        self._backup_history.append({
            "original_path": str(full_path),
            "backup_path": str(backup_path),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation
        })
        
        log.info(f"PatchManager: backed up '{rel_file_path}' to '{backup_path.name}' before operation='{operation}'")
        return backup_path

    def undo_last_operation(self) -> dict | None:
        """
        Roll back the most recent file change from backup history.
        """
        if not self._backup_history:
            log.warning("PatchManager: no history to undo.")
            return None
            
        history = self._backup_history.pop()
        original_path = Path(history["original_path"])
        backup_path = Path(history["backup_path"]) if history["backup_path"] else None
        op = history["operation"]
        
        log.info(f"PatchManager: undoing last operation: {op} on {original_path.name}")
        
        if op == "create":
            # Undo creation: delete the created file
            if original_path.is_file():
                original_path.unlink()
            elif original_path.is_dir():
                shutil.rmtree(original_path)
        elif op == "modify" or op == "delete":
            # Undo modify/delete: restore backup file
            if backup_path and backup_path.is_file():
                original_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, original_path)
                backup_path.unlink()
        elif op == "rename" or op == "move":
            # Rename/move undo logic can be mapped here:
            # backup_path points to original path before rename
            if backup_path: # backup_path contains the original path location in this case
                shutil.move(original_path, backup_path)
                
        return {
            "original_path": str(original_path),
            "operation": op,
            "success": True
        }

"""
Project Manager
===============
Handles creation, listing, switching, opening, and deleting of projects.
Authoritative registry of the active project and active workspace.
"""

from __future__ import annotations
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone

from database.manager import DatabaseManager
from project.models import Project
from project.workspace import ProjectWorkspace

log = logging.getLogger(__name__)

class ProjectManager:
    """
    Manages project lifecycle, metadata storage, and project switching.
    """

    def __init__(self, central_db: DatabaseManager, base_workspaces_dir: Path) -> None:
        self.central_db = central_db
        self.base_workspaces_dir = Path(base_workspaces_dir).resolve()
        self.base_workspaces_dir.mkdir(parents=True, exist_ok=True)
        
        self._active_project: Project | None = None
        self._active_workspace: ProjectWorkspace | None = None
        
        # Load active project on startup
        self._load_active_project_on_startup()

    def _load_active_project_on_startup(self) -> None:
        """Read the active project ID from central settings and load it."""
        try:
            cursor = self.central_db.execute(
                "SELECT value FROM settings WHERE key = ?", ("active_project_id",)
            )
            row = cursor.fetchone()
            if row:
                project_id = row[0]
                project = self.get_project(project_id)
                if project:
                    self._active_project = project
                    self._active_workspace = ProjectWorkspace(project_id, self.base_workspaces_dir)
                    log.info(f"ProjectManager: loaded active project '{project.name}' on startup.")
                else:
                    # Clean stale reference
                    self.central_db.execute(
                        "DELETE FROM settings WHERE key = ?", ("active_project_id",)
                    )
        except Exception as e:
            log.error(f"ProjectManager: failed to load active project on startup: {e}")

    def create_project(self, name: str, description: str = "", type: str = "Other", tags: list[str] | None = None, source_dir: str | None = None) -> Project:
        """Create a new project and initialize its workspace."""
        tags = tags or []
        source_dir_str = str(Path(source_dir).resolve()) if source_dir else None
        project = Project(
            name=name,
            description=description,
            type=type,
            tags=tags,
            source_dir=source_dir_str
        )
        
        # Insert metadata in central db
        tags_json = json.dumps(project.tags)
        self.central_db.execute(
            """
            INSERT INTO projects (id, name, description, type, tags, source_dir, created_at, last_opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project.id, project.name, project.description, project.type, tags_json, project.source_dir, project.created_at, project.last_opened_at)
        )
        
        # Initialize workspace folder and db
        ws = ProjectWorkspace(project.id, self.base_workspaces_dir)
        ws.close() # Close connection for now
        
        log.info(f"ProjectManager: created project '{project.name}' with id '{project.id}'.")
        return project

    def get_project(self, project_id: str) -> Project | None:
        """Retrieve project metadata by ID."""
        cursor = self.central_db.execute(
            "SELECT id, name, description, type, tags, source_dir, created_at, last_opened_at FROM projects WHERE id = ?",
            (project_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
            
        tags = []
        try:
            tags = json.loads(row["tags"])
        except Exception:
            pass
            
        return Project(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            type=row["type"],
            tags=tags,
            source_dir=row["source_dir"],
            created_at=row["created_at"],
            last_opened_at=row["last_opened_at"]
        )

    def list_projects(self) -> list[Project]:
        """List all projects sorted by last opened date."""
        cursor = self.central_db.execute(
            "SELECT id, name, description, type, tags, source_dir, created_at, last_opened_at FROM projects ORDER BY last_opened_at DESC"
        )
        projects = []
        for row in cursor.fetchall():
            tags = []
            try:
                tags = json.loads(row["tags"])
            except Exception:
                pass
            projects.append(Project(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                type=row["type"],
                tags=tags,
                source_dir=row["source_dir"],
                created_at=row["created_at"],
                last_opened_at=row["last_opened_at"]
            ))
        return projects

    def set_project_source_dir(self, project_id: str, source_dir: str) -> None:
        """Update a project's source directory."""
        source_dir_cleaned = str(Path(source_dir).resolve())
        self.central_db.execute(
            "UPDATE projects SET source_dir = ? WHERE id = ?",
            (source_dir_cleaned, project_id)
        )
        # Reload active project metadata if currently active
        if self._active_project and self._active_project.id == project_id:
            self._active_project = self.get_project(project_id)
        log.info(f"ProjectManager: set source_dir to '{source_dir_cleaned}' for project '{project_id}'")


    def open_project(self, project_id: str) -> Project:
        """Switch the currently active project."""
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"Project with ID '{project_id}' does not exist.")
            
        # Close old active workspace
        if self._active_workspace:
            self._active_workspace.close()
            self._active_workspace = None
            
        # Update metadata
        opened_at = datetime.now(timezone.utc).isoformat()
        self.central_db.execute(
            "UPDATE projects SET last_opened_at = ? WHERE id = ?",
            (opened_at, project_id)
        )
        
        # Save active project in central settings
        self.central_db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("active_project_id", project_id)
        )
        
        # Load project
        self._active_project = self.get_project(project_id)
        self._active_workspace = ProjectWorkspace(project_id, self.base_workspaces_dir)
        
        log.info(f"ProjectManager: opened project '{self._active_project.name}' (id: {project_id})")
        return self._active_project

    def close_active_project(self) -> None:
        """Close current active project and reset state."""
        if self._active_workspace:
            self._active_workspace.close()
            self._active_workspace = None
        self._active_project = None
        self.central_db.execute("DELETE FROM settings WHERE key = ?", ("active_project_id",))

    def delete_project(self, project_id: str) -> None:
        """Delete a project metadata and its filesystem workspace."""
        # Reset active status if this project is active
        if self._active_project and self._active_project.id == project_id:
            self.close_active_project()
            
        # Delete central metadata
        self.central_db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        
        # Delete workspaces folder
        project_ws_dir = self.base_workspaces_dir / project_id
        if project_ws_dir.is_dir():
            try:
                shutil.rmtree(project_ws_dir)
            except Exception as e:
                log.error(f"ProjectManager: failed to delete workspace folder for {project_id}: {e}")
                
        log.info(f"ProjectManager: deleted project '{project_id}'.")

    @property
    def active_project(self) -> Project | None:
        """Get currently active Project model."""
        return self._active_project

    @property
    def active_workspace(self) -> ProjectWorkspace | None:
        """Get currently active ProjectWorkspace instance."""
        return self._active_workspace

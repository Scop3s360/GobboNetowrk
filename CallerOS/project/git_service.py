"""
Git Integration Service
=======================
Wrapper executing git commands via subprocess in the project directory.
"""

from __future__ import annotations
import subprocess
import logging
from pathlib import Path

log = logging.getLogger(__name__)

class GitService:
    """
    Safely executes Git commands in the project repository directory.
    """

    def __init__(self, repo_dir: str | Path) -> None:
        self.repo_dir = Path(repo_dir).resolve()

    def _run_git(self, args: list[str]) -> str:
        """Execute a git CLI command in repo_dir and return stdout."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
                errors="ignore"
            )
            return res.stdout.strip()
        except subprocess.CalledProcessError as exc:
            err_msg = exc.stderr.strip() or str(exc)
            log.warning(f"GitService: command failed git {' '.join(args)}: {err_msg}")
            raise RuntimeError(f"Git command failed: {err_msg}") from exc
        except FileNotFoundError:
            raise RuntimeError("Git executable not found in PATH")

    def is_git_repository(self) -> bool:
        """Check if target folder is a valid git repository."""
        # Fast path
        if not (self.repo_dir / ".git").is_dir():
            return False
        try:
            out = self._run_git(["rev-parse", "--is-inside-work-tree"])
            return out == "true"
        except Exception:
            return False

    def get_current_branch(self) -> str:
        """Get currently checked-out branch name."""
        if not self.is_git_repository():
            return "Not a Git Repository"
        try:
            return self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        except Exception:
            return "DETACHED HEAD"

    def get_status(self) -> dict[str, list[str]]:
        """
        Get classified status list of staged, unstaged and untracked files.
        """
        if not self.is_git_repository():
            return {"staged": [], "unstaged": [], "untracked": []}
            
        try:
            # 1. Staged files
            staged_out = self._run_git(["diff", "--name-only", "--cached"])
            staged = [line.strip() for line in staged_out.splitlines() if line.strip()]
            
            # 2. Unstaged (modified) files
            unstaged_out = self._run_git(["diff", "--name-only"])
            unstaged = [line.strip() for line in unstaged_out.splitlines() if line.strip()]
            
            # 3. Untracked files via porcelain status
            status_out = self._run_git(["status", "--porcelain"])
            untracked = []
            for line in status_out.splitlines():
                if line.startswith("?? "):
                    untracked.append(line[3:].strip())
                    
            return {
                "staged": staged,
                "unstaged": list(set(unstaged) - set(staged)), # Filter duplicate staged items
                "untracked": untracked
            }
        except Exception as e:
            log.error(f"GitService: failed to read status: {e}")
            return {"staged": [], "unstaged": [], "untracked": []}

    def stage_file(self, rel_path: str) -> None:
        """Stage a file (git add)."""
        self._run_git(["add", rel_path])
        log.info(f"GitService: staged '{rel_path}'")

    def unstage_file(self, rel_path: str) -> None:
        """Unstage a file (git reset)."""
        # Run reset HEAD to unstage
        try:
            self._run_git(["reset", "HEAD", rel_path])
            log.info(f"GitService: unstaged '{rel_path}'")
        except Exception:
            # Fallback if branch has no commits yet (HEAD does not exist)
            self._run_git(["rm", "--cached", rel_path])
            log.info(f"GitService: unstaged '{rel_path}' via cache removal")

    def commit(self, message: str) -> str:
        """Create a commit with staged changes."""
        if not message.strip():
            raise ValueError("Commit message cannot be empty")
        out = self._run_git(["commit", "-m", message])
        log.info(f"GitService: committed staged changes with message '{message}'")
        return out

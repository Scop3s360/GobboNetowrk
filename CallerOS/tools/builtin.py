"""
Built-in Tools
==============
Concrete implementations of initial tools for the GoblinOS Tool Framework:
- ReadFileTool
- WriteFileTool
- ListDirectoryTool
- ReadFolderTool
- RunCommandTool
- SearchWebTool (stub)
"""

import os
import subprocess
from pathlib import Path
from typing import Any

from tools.base import Tool
from tools.permissions import PermissionLevel


class ReadFileTool(Tool):
    """Tool that reads and returns the text content of a file."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Reads the text contents of a file at the specified path."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    def execute(self, **kwargs: object) -> str:
        path_arg = kwargs.get("path")
        if not isinstance(path_arg, str):
            raise ValueError("Argument 'path' must be a string.")

        path = Path(path_arg)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path_arg}")

        return path.read_text(encoding="utf-8")


class WriteFileTool(Tool):
    """Tool that writes text content to a file, creating directories if needed."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Writes text content to a file at the specified path."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.WRITE

    def execute(self, **kwargs: object) -> str:
        path_arg = kwargs.get("path")
        content_arg = kwargs.get("content")

        if not isinstance(path_arg, str):
            raise ValueError("Argument 'path' must be a string.")
        if not isinstance(content_arg, str):
            raise ValueError("Argument 'content' must be a string.")

        path = Path(path_arg)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content_arg, encoding="utf-8")
        return f"Successfully wrote to {path_arg}"


class ListDirectoryTool(Tool):
    """Tool that lists the contents of a directory."""

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "Lists the files and directories in the specified path (defaults to current directory)."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    def execute(self, **kwargs: object) -> list[str]:
        path_arg = kwargs.get("path", ".")
        if not isinstance(path_arg, str):
            raise ValueError("Argument 'path' must be a string.")

        path = Path(path_arg)
        if not path.is_dir():
            raise NotADirectoryError(f"Directory not found: {path_arg}")

        return sorted([entry.name for entry in path.iterdir()])


class ReadFolderTool(Tool):
    """Tool that reads all files in a folder and returns a dictionary of filename -> content."""

    @property
    def name(self) -> str:
        return "read_folder"

    @property
    def description(self) -> str:
        return "Reads all files in the specified folder and returns their contents as a dictionary."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    def execute(self, **kwargs: object) -> dict[str, str]:
        path_arg = kwargs.get("path")
        if not isinstance(path_arg, str):
            raise ValueError("Argument 'path' must be a string.")

        folder_path = Path(path_arg)
        if not folder_path.is_dir():
            raise NotADirectoryError(f"Folder not found: {path_arg}")

        results: dict[str, str] = {}
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = Path(root) / file
                relative_path = full_path.relative_to(folder_path).as_posix()
                try:
                    results[relative_path] = full_path.read_text(encoding="utf-8")
                except Exception as exc:
                    results[relative_path] = f"<Error reading file: {exc}>"
        return results


class RunCommandTool(Tool):
    """Tool that runs a command on the local system."""

    @property
    def name(self) -> str:
        return "run_command"

    @property
    def description(self) -> str:
        return "Runs a command on the host system and returns its stdout, stderr, and return code."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.EXECUTE

    def execute(self, **kwargs: object) -> dict[str, Any]:
        command_arg = kwargs.get("command")
        if not isinstance(command_arg, str):
            raise ValueError("Argument 'command' must be a string.")

        cwd_arg = kwargs.get("cwd")
        cwd = None
        if cwd_arg is not None:
            if not isinstance(cwd_arg, str):
                raise ValueError("Argument 'cwd' must be a string.")
            cwd_path = Path(cwd_arg)
            if not cwd_path.is_dir():
                raise FileNotFoundError(f"Directory not found: {cwd_arg}")
            cwd = str(cwd_path.resolve())

        import shlex
        args = shlex.split(command_arg)
        if not args:
            raise ValueError("Command must not be empty.")

        try:
            result = subprocess.run(
                args,
                shell=False,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,  # Safety timeout
            )
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Executable program not found: {args[0]}") from exc
        except Exception as exc:
            raise RuntimeError(f"Failed to execute command: {exc}") from exc

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }


class SearchWebTool(Tool):
    """Stub tool for searching the web."""

    @property
    def name(self) -> str:
        return "search_web"

    @property
    def description(self) -> str:
        return "Stub: Searches the web for the given query."

    @property
    def permission_level(self) -> PermissionLevel:
        return PermissionLevel.READ

    def execute(self, **kwargs: object) -> str:
        query_arg = kwargs.get("query")
        if not isinstance(query_arg, str):
            raise ValueError("Argument 'query' must be a string.")

        return f"Web search is not yet integrated. Query received: '{query_arg}'"

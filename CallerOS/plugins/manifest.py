"""
Plugin Manifest
===============
Dataclass and parsing logic representing a plugin's manifest.json file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from plugins.exceptions import PluginManifestError, PluginValidationError


@dataclass(frozen=True)
class PluginManifest:
    """
    Metadata representation of a plugin defined in manifest.json.
    """
    name: str
    version: str
    author: str
    description: str
    entry: str

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> PluginManifest:
        """
        Validate and instantiate a PluginManifest from a dictionary.
        """
        required_fields = ["name", "version", "author", "description", "entry"]
        for field_name in required_fields:
            if field_name not in data:
                raise PluginValidationError(f"Manifest missing required field: '{field_name}'")
            
            value = data[field_name]
            if not isinstance(value, str) or not value.strip():
                raise PluginValidationError(
                    f"Manifest field '{field_name}' must be a non-empty string."
                )

        return cls(
            name=str(data["name"]).strip(),
            version=str(data["version"]).strip(),
            author=str(data["author"]).strip(),
            description=str(data["description"]).strip(),
            entry=str(data["entry"]).strip(),
        )

    @classmethod
    def from_file(cls, path: Path) -> PluginManifest:
        """
        Load, parse, and validate manifest.json from a file path.
        """
        if not path.is_file():
            raise PluginManifestError(f"Manifest file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PluginManifestError(f"Manifest is invalid JSON: {exc}") from exc
        except Exception as exc:
            raise PluginManifestError(f"Failed to read manifest file: {exc}") from exc

        if not isinstance(data, dict):
            raise PluginValidationError("Manifest JSON must be a key-value dictionary object.")

        return cls.from_dict(data)

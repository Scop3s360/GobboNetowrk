"""
Plugin Validator
================
Validates plugin directory structures, manifest parameters, and entrypoint files.
"""

from __future__ import annotations

import logging
from pathlib import Path

from plugins.exceptions import PluginValidationError
from plugins.manifest import PluginManifest

log = logging.getLogger(__name__)


class PluginValidator:
    """
    Validates directories and entrypoint files for pluggable modules.
    """

    def validate_plugin_dir(self, plugin_dir: Path) -> PluginManifest:
        """
        Verify that a directory contains a valid manifest and matching entrypoint file.

        Args:
            plugin_dir: Absolute path to the plugin directory.

        Returns:
            The parsed and validated PluginManifest.

        Raises:
            PluginValidationError: If directories or files are invalid.
        """
        if not plugin_dir.is_dir():
            raise PluginValidationError(f"Plugin path is not a directory: {plugin_dir}")

        manifest_path = plugin_dir / "manifest.json"
        # Parse manifest (checks for missing file, invalid JSON, structure type mismatch)
        manifest = PluginManifest.from_file(manifest_path)

        # Validate that the entrypoint file exists relative to the plugin directory
        # Support both 'plugin.py' and 'subfolder/plugin.py' paths.
        entry_file_path = plugin_dir / manifest.entry
        if not entry_file_path.is_file():
            raise PluginValidationError(
                f"Plugin '{manifest.name}' specifies entrypoint '{manifest.entry}' "
                f"but file was not found: {entry_file_path}"
            )

        return manifest

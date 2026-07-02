"""
Plugin Loader
=============
Scans subdirectories, validates manifests, and dynamically loads Python
modules containing BasePlugin subclasses.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

from plugins.base_plugin import BasePlugin
from plugins.exceptions import PluginLoadError
from plugins.manifest import PluginManifest
from plugins.validator import PluginValidator

log = logging.getLogger(__name__)


class PluginLoader:
    """
    Scans a directory for plugins, validates them, and instantiates their subclasses dynamically.
    """

    def __init__(self, plugins_dir: Path | str) -> None:
        self.plugins_dir = Path(plugins_dir)
        self._validator = PluginValidator()

    def scan_and_load(self) -> list[BasePlugin]:
        """
        Scan the plugins directory and load all valid plugins.
        If a plugin fails validation or loading, log the error and continue.

        Returns:
            List of instantiated BasePlugin instances.
        """
        loaded_instances: list[BasePlugin] = []
        if not self.plugins_dir.is_dir():
            log.warning("PluginLoader: directory '%s' does not exist.", self.plugins_dir)
            return loaded_instances

        log.info("PluginLoader: scanning directory: %s", self.plugins_dir)
        
        # Iterate over immediate subdirectories
        for path in self.plugins_dir.iterdir():
            if not path.is_dir():
                continue
                
            # Skip hidden folders or caches
            if path.name.startswith(".") or path.name.startswith("__"):
                continue

            try:
                plugin_instance = self.load_plugin(path)
                loaded_instances.append(plugin_instance)
            except Exception as exc:
                log.error("PluginLoader: failed to load plugin from directory '%s': %s", path.name, exc)
                # Continue loading other plugins

        return loaded_instances

    def load_plugin(self, plugin_dir: Path) -> BasePlugin:
        """
        Validate and load a specific plugin directory.

        Args:
            plugin_dir: Path to directory.

        Returns:
            The loaded BasePlugin instance.
        """
        # Ensure plugin_dir is strictly within plugins_dir (prevent traversal)
        resolved_plugins_dir = self.plugins_dir.resolve()
        resolved_plugin_dir = plugin_dir.resolve()
        try:
            resolved_plugin_dir.relative_to(resolved_plugins_dir)
        except ValueError as exc:
            raise PluginLoadError(
                f"Plugin directory {plugin_dir} is outside the approved plugins root: {self.plugins_dir}"
            ) from exc

        # Validate manifest and entrypoint existence
        manifest = self._validator.validate_plugin_dir(plugin_dir)
        entry_file = plugin_dir / manifest.entry
        
        log.info("PluginLoader: loading plugin '%s' from %s", manifest.name, entry_file)
        
        # Create module name from plugin name
        module_name = f"plugins.dynamic.{manifest.name.replace('-', '_')}"
        
        try:
            # Setup dynamic import
            spec = importlib.util.spec_from_file_location(module_name, entry_file)
            if spec is None or spec.loader is None:
                raise PluginLoadError(f"Could not load spec for module {module_name} at {entry_file}")
                
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Find the BasePlugin subclass
            plugin_cls = self._find_plugin_class(module)
            if not plugin_cls:
                raise PluginLoadError(
                    f"No subclass of BasePlugin found in entry file '{manifest.entry}'"
                )
                
            # Instantiate
            instance = plugin_cls(manifest)
            log.info("PluginLoader: successfully loaded plugin class '%s'", plugin_cls.__name__)
            return instance
            
        except Exception as exc:
            if module_name in sys.modules:
                del sys.modules[module_name]
            raise PluginLoadError(f"Error executing entrypoint module: {exc}") from exc

    def _find_plugin_class(self, module: object) -> type[BasePlugin] | None:
        """Find subclasses of BasePlugin defined in the module."""
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BasePlugin)
                and attr is not BasePlugin
            ):
                return attr
        return None

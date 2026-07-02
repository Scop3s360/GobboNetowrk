"""
Plugin Manager
==============
Coordinates the plugin lifecycle: scanning, validation, loading, initialisation,
enable/disable control, and clean deactivation/shutdown hooks.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from plugins.base_plugin import BasePlugin
from plugins.exceptions import PluginError
from plugins.loader import PluginLoader
from plugins.registry import PluginRegistry

log = logging.getLogger(__name__)


class PluginManager:
    """
    Coordinating boundary exposing registry details and managing plugin lifetimes.
    """

    def __init__(self, plugins_dir: Path | str) -> None:
        """
        Initialize the PluginManager.

        Args:
            plugins_dir: Root directory where plugin folders live.
        """
        self.plugins_dir = Path(plugins_dir)
        self._registry = PluginRegistry()
        self._loader = PluginLoader(self.plugins_dir)
        
        # Future extension points (registered classes/hooks)
        self.registered_workers: list[Any] = []
        self.registered_tools: list[Any] = []
        self.registered_services: list[Any] = []

    @property
    def registry(self) -> PluginRegistry:
        """Get the internal registry."""
        return self._registry

    def discover_and_load(self) -> None:
        """
        Scan directory, load matching plugins, register, and initialise them.
        Exceptions inside a single plugin will be caught, logged, and bypassed
        to protect core system integrity.
        """
        log.info("PluginManager: starting discovery and load...")
        start_perf = time.perf_counter()
        
        loaded_plugins = self._loader.scan_and_load()
        
        for plugin in loaded_plugins:
            name = plugin.manifest.name
            try:
                # Register plugin
                self._registry.register(plugin)
                # Automatically enable/initialise it on load
                self.enable_plugin(name)
            except Exception as exc:
                log.error("PluginManager: failed during setup of plugin '%s': %s", name, exc)
                # Unregister if registered but failed during initialization
                if self._registry.is_registered(name):
                    self._registry.unregister(name)

        elapsed = time.perf_counter() - start_perf
        log.info(
            "PluginManager: completed discovery. Loaded %d plugin(s) in %.3fs",
            len(self._registry),
            elapsed,
        )

    def enable_plugin(self, name: str) -> None:
        """
        Enable a registered plugin, triggering its initialise() routine.

        Args:
            name: Plugin name.
        """
        plugin = self._registry.get(name)
        if self._registry.is_enabled(name):
            log.debug("PluginManager: plugin '%s' is already enabled.", name)
            return

        log.info("PluginManager: enabling plugin '%s'...", name)
        start_perf = time.perf_counter()
        try:
            plugin.initialise()
            self._registry.enable(name)
            elapsed = time.perf_counter() - start_perf
            log.info("PluginManager: plugin '%s' enabled successfully (initialised in %.3fs)", name, elapsed)
        except Exception as exc:
            log.error("PluginManager: initialise() failed for plugin '%s': %s", name, exc)
            raise PluginError(f"Failed to enable plugin '{name}': {exc}") from exc

    def disable_plugin(self, name: str) -> None:
        """
        Disable a plugin, triggering its shutdown() routine.

        Args:
            name: Plugin name.
        """
        plugin = self._registry.get(name)
        if not self._registry.is_enabled(name):
            log.debug("PluginManager: plugin '%s' is already disabled.", name)
            return

        log.info("PluginManager: disabling plugin '%s'...", name)
        start_perf = time.perf_counter()
        try:
            plugin.shutdown()
            self._registry.disable(name)
            elapsed = time.perf_counter() - start_perf
            log.info("PluginManager: plugin '%s' disabled successfully (shutdown in %.3fs)", name, elapsed)
        except Exception as exc:
            log.error("PluginManager: shutdown() failed for plugin '%s': %s", name, exc)
            raise PluginError(f"Failed to disable plugin '{name}': {exc}") from exc

    def shutdown_all(self) -> None:
        """
        Cleanly shutdown all enabled plugins.
        Continues execution even if some plugins raise errors.
        """
        log.info("PluginManager: shutting down all registered plugins...")
        for plugin in list(self._registry.list_plugins()):
            name = plugin.manifest.name
            if self._registry.is_enabled(name):
                try:
                    self.disable_plugin(name)
                except Exception as exc:
                    log.error("PluginManager: error deactivating plugin '%s' during shutdown: %s", name, exc)

    # -----------------------------------------------------------------------
    # Future integration extension registration endpoints
    # -----------------------------------------------------------------------
    def register_worker(self, worker_class: Any) -> None:
        """Extension point: register a pluggable worker class."""
        self.registered_workers.append(worker_class)
        log.info("PluginManager: registered extension worker class '%s'", worker_class.__name__)

    def register_tool(self, tool_class: Any) -> None:
        """Extension point: register a pluggable tool class."""
        self.registered_tools.append(tool_class)
        log.info("PluginManager: registered extension tool class '%s'", tool_class.__name__)

    def register_service(self, service_class: Any) -> None:
        """Extension point: register a pluggable service class."""
        self.registered_services.append(service_class)
        log.info("PluginManager: registered extension service class '%s'", service_class.__name__)

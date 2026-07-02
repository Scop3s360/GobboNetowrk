"""
Plugin Registry
===============
Holds active records of loaded, enabled, and disabled plugins.
Provides duplicate protection and search lookups.
"""

from __future__ import annotations

import logging
from typing import Iterator

from plugins.base_plugin import BasePlugin
from plugins.exceptions import PluginRegistrationError

log = logging.getLogger(__name__)


class PluginRegistry:
    """
    Registry for tracking all loaded plugins and their runtime states.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._enabled_plugins: set[str] = set()

    def register(self, plugin: BasePlugin) -> None:
        """
        Add a plugin instance to the registry.

        Args:
            plugin: BasePlugin subclass instance.

        Raises:
            PluginRegistrationError: If a plugin with the same name exists.
        """
        name = plugin.manifest.name
        if name in self._plugins:
            log.warning("PluginRegistry: duplicate registration attempted for '%s'", name)
            raise PluginRegistrationError(f"Plugin '{name}' is already registered.")
            
        self._plugins[name] = plugin
        log.info("PluginRegistry: plugin '%s' successfully registered.", name)

    def unregister(self, name: str) -> None:
        """
        Remove a plugin from the registry.

        Args:
            name: Name of the plugin.
        """
        if name in self._plugins:
            self._enabled_plugins.discard(name)
            del self._plugins[name]
            log.info("PluginRegistry: plugin '%s' unregistered.", name)

    def get(self, name: str) -> BasePlugin:
        """
        Get a plugin by name.

        Args:
            name: Plugin name.

        Returns:
            The registered BasePlugin instance.

        Raises:
            PluginRegistrationError: If plugin not found.
        """
        if name not in self._plugins:
            raise PluginRegistrationError(f"Plugin '{name}' not found in registry.")
        return self._plugins[name]

    def is_registered(self, name: str) -> bool:
        """Check if plugin is registered."""
        return name in self._plugins

    def enable(self, name: str) -> None:
        """Mark plugin as enabled."""
        if name not in self._plugins:
            raise PluginRegistrationError(f"Cannot enable unregistered plugin '{name}'.")
        self._enabled_plugins.add(name)
        self._plugins[name].enabled = True

    def disable(self, name: str) -> None:
        """Mark plugin as disabled."""
        if name not in self._plugins:
            raise PluginRegistrationError(f"Cannot disable unregistered plugin '{name}'.")
        self._enabled_plugins.discard(name)
        self._plugins[name].enabled = False

    def is_enabled(self, name: str) -> bool:
        """Check if plugin is enabled."""
        return name in self._enabled_plugins

    def list_plugins(self) -> list[BasePlugin]:
        """Return list of all registered plugin instances."""
        return list(self._plugins.values())

    def list_enabled(self) -> list[BasePlugin]:
        """Return list of enabled plugin instances."""
        return [self._plugins[name] for name in self._enabled_plugins]

    def __iter__(self) -> Iterator[BasePlugin]:
        return iter(self._plugins.values())

    def __len__(self) -> int:
        return len(self._plugins)

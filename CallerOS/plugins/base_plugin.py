"""
Base Plugin Class
=================
Abstract interface defining the lifecycle hooks and metadata for GoblinOS plugins.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from plugins.manifest import PluginManifest


class BasePlugin(ABC):
    """
    Abstract base class for all GoblinOS plugins.
    Plugins must inherit from this class and implement initialise() and shutdown().
    """

    def __init__(self, manifest: PluginManifest) -> None:
        """
        Initialize the plugin base.

        Args:
            manifest: The parsed metadata manifest.
        """
        self._manifest = manifest
        self._enabled = False

    @property
    def manifest(self) -> PluginManifest:
        """Get the plugin's manifest metadata."""
        return self._manifest

    @property
    def enabled(self) -> bool:
        """Indicate if the plugin is currently enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set the plugin's enabled status."""
        self._enabled = value

    @abstractmethod
    def initialise(self) -> None:
        """
        Perform plugin initialization.
        Called when the plugin is loaded and activated.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """
        Perform clean shutdown.
        Called when the plugin is deactivated or system closes.
        """
        pass

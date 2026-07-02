"""
GoblinOS Plugin System (Stage 10)
=================================
Allows discovering, validating, dynamically loading, and shutting down optional
plugin components without altering core application layers.
"""

from plugins.base_plugin import BasePlugin
from plugins.exceptions import (
    PluginError,
    PluginLoadError,
    PluginManifestError,
    PluginRegistrationError,
    PluginValidationError,
)
from plugins.loader import PluginLoader
from plugins.manager import PluginManager
from plugins.manifest import PluginManifest
from plugins.models import PluginState
from plugins.registry import PluginRegistry
from plugins.validator import PluginValidator

__all__ = [
    "BasePlugin",
    "PluginManifest",
    "PluginRegistry",
    "PluginLoader",
    "PluginManager",
    "PluginValidator",
    "PluginState",
    "PluginError",
    "PluginLoadError",
    "PluginManifestError",
    "PluginRegistrationError",
    "PluginValidationError",
]

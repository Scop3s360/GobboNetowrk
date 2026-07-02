"""
Plugin Exceptions
=================
Exception hierarchy for the Plugin System.

All plugin exceptions derive from PluginError, which itself derives from
CallerOSError (Stage 1).
"""

from core.exceptions import CallerOSError


class PluginError(CallerOSError):
    """Base exception for all plugin system errors."""


class PluginValidationError(PluginError):
    """Raised when validation of plugin code or manifest parameters fails."""


class PluginLoadError(PluginError):
    """Raised when dynamic loading or instantiating of a plugin fails."""


class PluginRegistrationError(PluginError):
    """Raised when duplicate plugins are registered or registry lookups fail."""


class PluginManifestError(PluginError):
    """Raised when a manifest.json file is missing, corrupt, or contains invalid JSON."""

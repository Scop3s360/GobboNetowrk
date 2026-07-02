"""
Plugin Models
=============
Data representations and lifecycle state models for plugins.
"""

from enum import Enum, auto


class PluginState(Enum):
    """
    Lifecycle status of an active plugin.
    """
    LOADED = auto()
    ENABLED = auto()
    DISABLED = auto()
    FAILED = auto()

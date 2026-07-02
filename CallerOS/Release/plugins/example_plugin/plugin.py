"""
Example Plugin
==============
A fully-functional demonstration plugin logging initialization and shutdown hooks.
"""

from __future__ import annotations

import logging

from plugins.base_plugin import BasePlugin

log = logging.getLogger(__name__)


class ExamplePlugin(BasePlugin):
    """
    Concrete example plugin demonstrating the standard lifecycle hooks.
    """

    def initialise(self) -> None:
        """Called when the plugin is enabled."""
        log.info("ExamplePlugin: initializing optional plugin components...")
        self.log_message = "initialized"

    def shutdown(self) -> None:
        """Called when the plugin is disabled or shut down."""
        log.info("ExamplePlugin: deactivating plugin components and cleaning up...")
        self.log_message = "shutdown"

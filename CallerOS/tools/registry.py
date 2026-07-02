"""
Tool Registry
=============
Manages registration and lookup of tools.
"""

import logging
from typing import Iterator

from tools.base import Tool
from tools.exceptions import DuplicateToolError, ToolNotFoundError

log = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for storing and retrieving tools by name.
    
    Ensures name uniqueness and provides lookup and listing functions.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        Register a tool.
        
        Args:
            tool: The tool instance to register.
            
        Raises:
            DuplicateToolError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            log.warning("Failed to register duplicate tool: name=%s", tool.name)
            raise DuplicateToolError(
                f"Tool with name '{tool.name}' is already registered."
            )
        self._tools[tool.name] = tool
        log.info("Tool registered: name=%s, permission_level=%s", tool.name, tool.permission_level.name)

    def get(self, name: str) -> Tool:
        """
        Look up a tool by name.
        
        Args:
            name: The name of the tool to retrieve.
            
        Returns:
            The registered Tool instance.
            
        Raises:
            ToolNotFoundError: If no tool is registered under the given name.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(
                f"Tool '{name}' not found. Registered tools: {self._registered_names()}"
            )
        return tool

    def is_registered(self, name: str) -> bool:
        """Return True if a tool with the given name is registered."""
        return name in self._tools

    def list_tools(self) -> list[Tool]:
        """
        Return a list of all registered tools, sorted by name.
        
        Returns:
            A new list containing all registered Tool instances.
        """
        return [self._tools[name] for name in sorted(self._tools.keys())]

    def clear(self) -> None:
        """Remove all tools from the registry. (Useful for tests)"""
        self._tools.clear()
        log.debug("Tool registry cleared.")

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def __iter__(self) -> Iterator[Tool]:
        """Iterate over registered tools in name order."""
        for name in sorted(self._tools.keys()):
            yield self._tools[name]

    def _registered_names(self) -> str:
        names = sorted(self._tools.keys())
        return ", ".join(names) if names else "(none)"

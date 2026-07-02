"""
Tool Base Interface
===================
Abstract base class representing a tool.
"""

from abc import ABC, abstractmethod
from tools.permissions import PermissionLevel


class Tool(ABC):
    """
    Abstract base class for all GoblinOS tools.
    
    All tools must inherit from this class and implement its properties
    and execute method.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A brief description of what the tool does."""
        pass

    @property
    @abstractmethod
    def permission_level(self) -> PermissionLevel:
        """The minimum permission level required to execute this tool."""
        pass

    @abstractmethod
    def execute(self, **kwargs: object) -> object:
        """
        Execute the tool's core logic with keyword arguments.
        
        Args:
            **kwargs: Arguments required by the specific tool implementation.
            
        Returns:
            The output of the tool execution.
            
        Raises:
            Exception: If execution fails.
        """
        pass

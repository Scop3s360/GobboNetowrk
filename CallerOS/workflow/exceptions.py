"""
Workflow Exceptions
===================
Exception hierarchy for the Workflow Engine.

All workflow exceptions derive from WorkflowError, which itself derives from
CallerOSError (Stage 1).
"""

from core.exceptions import CallerOSError


class WorkflowError(CallerOSError):
    """Base exception for all workflow engine errors."""


class WorkflowValidationError(WorkflowError):
    """Raised when validation of workflow metadata or steps fails."""


class WorkflowExecutionError(WorkflowError):
    """Raised when execution of the overall workflow fails."""


class StepExecutionError(WorkflowError):
    """Raised when an individual step execution fails."""

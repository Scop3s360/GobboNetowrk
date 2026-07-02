"""
Workflow States
===============
Defines the lifecycle states of a workflow execution.
"""

from enum import Enum


class WorkflowState(Enum):
    """
    Lifecycle states of a workflow.
    """
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

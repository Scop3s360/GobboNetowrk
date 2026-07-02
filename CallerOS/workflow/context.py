"""
Workflow Context
================
Maintains runtime state and shared variables during a workflow execution.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


def _new_execution_id() -> str:
    """Generate a new unique execution ID."""
    return str(uuid.uuid4())


@dataclass
class WorkflowContext:
    """
    Mutable context passed between steps during a workflow run.

    Attributes:
        original_request: The initial triggering request/payload.
        execution_id:     Unique identifier for this specific run.
        shared_data:      Key/value storage accessible and modifiable by steps.
        step_results:     Mapping of step ID to the output returned by that step.
        metadata:         Optional tagging or telemetry properties.
        start_time:       Unix epoch timestamp indicating when execution started.
    """

    original_request: object
    execution_id: str = field(default_factory=_new_execution_id)
    shared_data: dict[str, object] = field(default_factory=dict)
    step_results: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)

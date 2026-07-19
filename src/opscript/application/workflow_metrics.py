from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class WorkflowMetricsReport:
    """
    Application-level metrics produced by a Opscript workflow.
    """

    workflow_name: str
    duration_ms: int
    measurements: Mapping[str, int | float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "measurements",
            MappingProxyType(dict(self.measurements)),
        )

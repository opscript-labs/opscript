from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class WorkflowExecutionResult[T]:
    value: T
    duration_ms: int


class WorkflowExecution:
    """
    Measures execution duration for a workflow operation.
    """

    def run(
        self,
        operation: Callable[[], T],
    ) -> WorkflowExecutionResult[T]:
        started_at = perf_counter()

        value = operation()

        duration_ms = int((perf_counter() - started_at) * 1000)

        return WorkflowExecutionResult(
            value=value,
            duration_ms=duration_ms,
        )

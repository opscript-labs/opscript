from __future__ import annotations

from collections.abc import Mapping

from opscript.application.workflow_execution import WorkflowExecutionResult
from opscript.application.workflow_metrics import WorkflowMetricsReport


class WorkflowMetricsFactory:
    """
    Builds workflow metrics reports from workflow execution outcomes.
    """

    def create(
        self,
        workflow_name: str,
        execution: WorkflowExecutionResult,
        measurements: Mapping[str, int | float] | None = None,
    ) -> WorkflowMetricsReport:
        return WorkflowMetricsReport(
            workflow_name=workflow_name,
            duration_ms=execution.duration_ms,
            measurements=measurements or {},
        )

from __future__ import annotations

from dataclasses import dataclass

from platformiq.model import AnalysisResult

from opscript.application.workflow_execution import WorkflowExecutionResult
from opscript.application.workflow_metrics import WorkflowMetricsReport


@dataclass(frozen=True)
class WorkflowOutcome:
    """
    Represents the complete outcome of executing a workflow.

    It separates the application result from presentation concerns.
    """

    report: str
    execution: WorkflowExecutionResult
    metrics: WorkflowMetricsReport
    analysis_result: AnalysisResult | None = None

from opscript.application.workflow_execution import WorkflowExecutionResult
from opscript.application.workflow_metrics import WorkflowMetricsReport
from opscript.application.workflow_outcome import WorkflowOutcome


def test_workflow_outcome_contains_report_execution_and_metrics():
    execution = WorkflowExecutionResult(
        value="snapshot",
        duration_ms=25,
    )

    metrics = WorkflowMetricsReport(
        workflow_name="observation",
        duration_ms=25,
        measurements={
            "resources": 5,
            "observations": 2,
        },
    )

    outcome = WorkflowOutcome(
        report="Observations:\n- Resource created",
        execution=execution,
        metrics=metrics,
    )

    assert outcome.report.startswith("Observations:")
    assert outcome.execution is execution
    assert outcome.metrics is metrics
    assert outcome.analysis_result is None

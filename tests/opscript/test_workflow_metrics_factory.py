from opscript.application.workflow_execution import WorkflowExecutionResult
from opscript.application.workflow_metrics_factory import WorkflowMetricsFactory


def test_workflow_metrics_factory_uses_execution_duration():
    factory = WorkflowMetricsFactory()

    execution = WorkflowExecutionResult(
        value="completed",
        duration_ms=42,
    )

    report = factory.create(
        workflow_name="observation",
        execution=execution,
    )

    assert report.workflow_name == "observation"
    assert report.duration_ms == 42


def test_workflow_metrics_factory_includes_named_measurements():
    factory = WorkflowMetricsFactory()

    execution = WorkflowExecutionResult(
        value="completed",
        duration_ms=42,
    )

    report = factory.create(
        workflow_name="resource_evolution",
        execution=execution,
        measurements={
            "snapshots": 2,
            "comparisons": 1,
        },
    )

    assert report.measurements["snapshots"] == 2
    assert report.measurements["comparisons"] == 1

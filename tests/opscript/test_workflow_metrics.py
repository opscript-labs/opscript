import pytest

from opscript.application.workflow_metrics import WorkflowMetricsReport


def test_workflow_metrics_report_records_workflow_name_and_duration():
    report = WorkflowMetricsReport(
        workflow_name="observation",
        duration_ms=10,
    )

    assert report.workflow_name == "observation"
    assert report.duration_ms == 10
    assert report.measurements == {}


def test_workflow_metrics_report_records_named_measurements():
    report = WorkflowMetricsReport(
        workflow_name="resource_evolution",
        duration_ms=25,
        measurements={
            "snapshots": 2,
            "comparisons": 1,
            "matched_comparisons": 1,
        },
    )

    assert report.measurements["snapshots"] == 2
    assert report.measurements["comparisons"] == 1
    assert report.measurements["matched_comparisons"] == 1


def test_workflow_metrics_report_is_immutable():
    report = WorkflowMetricsReport(
        workflow_name="environment_evolution",
        duration_ms=30,
        measurements={
            "snapshots": 2,
        },
    )

    with pytest.raises(TypeError):
        report.measurements["snapshots"] = 3

from opscript.application.workflow_execution import WorkflowExecution


def test_workflow_execution_returns_operation_result():
    execution = WorkflowExecution()

    result = execution.run(lambda: "completed")

    assert result.value == "completed"


def test_workflow_execution_records_duration_in_milliseconds():
    execution = WorkflowExecution()

    result = execution.run(lambda: "completed")

    assert isinstance(result.duration_ms, int)
    assert result.duration_ms >= 0

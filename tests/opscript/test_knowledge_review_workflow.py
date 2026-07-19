import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from opscript import ReportingService
import opscript.commands as commands
import opscript.application.knowledge_review_workflow as knowledge_review_workflow
from opscript.command_registry import COMMANDS
from opscript.execution import activate_execution, create_execution
from opscript.application.engineering_knowledge_evolution_comparison_service import (
    EngineeringKnowledgeEvolutionComparison,
    EngineeringKnowledgeEvolutionUnchangedCondition,
)
from opscript.application.engineering_knowledge_report_projection import (
    EngineeringKnowledgeEvaluationContext,
    EngineeringKnowledgeReportEntry,
    EngineeringKnowledgeServiceResult,
)
from opscript.application.engineering_condition_evaluation import (
    EngineeringConditionComparisonEligibility,
)
from opscript.application.engineering_condition_support_comparison_projection import (
    EngineeringConditionSupportComparisonProjection,
)
from opscript.application.engineering_condition_support_comparison_workflow import (
    EngineeringConditionSupportComparisonWorkflowResult,
)
from opscript.application.engineering_knowledge_sequence_analysis_service import (
    ENGINEERING_KNOWLEDGE_SEQUENCE_ANALYSIS_UNAVAILABLE_MESSAGE,
    EngineeringKnowledgeSequenceAnalysis,
    EngineeringKnowledgeSequenceAnalysisResult,
)
from opscript.application.knowledge_review_workflow import (
    ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE,
    EngineeringConditionSupportComparisonSelection,
    compare_engineering_knowledge_evaluations,
    render_engineering_knowledge_report,
    run_knowledge_review_workflow_outcome,
)
from opscript.cli import build_parser
from opscript.formatter import format_output
from opscript.models import Success
from opscript.storage import SnapshotStorageError
from platformiq.core import Identifier
from platformiq.model import Finding, Resource, Snapshot
from platformiq.model.value_objects import DiscoveryScope, ResourceState

EC001_RECOGNITION_BASIS = (
    "Qualified historical evidence demonstrated repeated modification of the "
    "reported subject across the qualified observation window."
)
EC002_RECOGNITION_BASIS = (
    "Qualified historical evidence demonstrated recurring infrastructure removal "
    "activity across the qualified observation window for the Discovery Scope."
)
EC003_RECOGNITION_BASIS = (
    "Qualified historical evidence demonstrated recurring infrastructure "
    "introduction activity across the qualified observation window for the "
    "Discovery Scope."
)


class FakeReporter:
    def report(self, result):
        return "drift report"


class FakeSnapshotHistoryStorage:
    def __init__(self, snapshots: tuple[Snapshot, ...]):
        self.snapshots = snapshots

    def load_history(self) -> tuple[Snapshot, ...]:
        return self.snapshots


class FailingSnapshotHistoryStorage:
    def load_history(self) -> tuple[Snapshot, ...]:
        raise SnapshotStorageError("snapshot history is unavailable")


class FakeConditionSupportComparisonWorkflow:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, *, engineering_condition, discovery_scopes):
        self.calls.append((engineering_condition, discovery_scopes))
        return self.result


def test_cli_exposes_knowledge_review():
    args = build_parser().parse_args(["knowledge-review"])

    assert args.command == "knowledge-review"
    assert "knowledge-review" in COMMANDS


def test_cli_exposes_command_local_json_for_knowledge_review():
    args = build_parser().parse_args(["knowledge-review", "--json"])

    assert args.command == "knowledge-review"
    assert args.json is True


def test_cli_exposes_evolution_for_knowledge_review():
    args = build_parser().parse_args(["knowledge-review", "--evolution"])

    assert args.command == "knowledge-review"
    assert args.evolution is True


def test_cli_exposes_sequence_analysis_for_knowledge_review():
    args = build_parser().parse_args(["knowledge-review", "--sequence"])

    assert args.command == "knowledge-review"
    assert args.sequence is True


def test_cli_does_not_expose_condition_support_comparison_options():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["knowledge-review", "--condition-support"])


def test_existing_commands_remain_registered():
    for command in ("run", "change-review", "inventory", "health"):
        assert command in COMMANDS


def test_knowledge_review_dispatches_condition_support_comparison_selection():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    comparison_workflow = FakeConditionSupportComparisonWorkflow(
        _condition_support_comparison_result(
            classification="SUPPORTED_IN_SOME_SCOPES",
            compared_scopes=(scope_a, scope_b),
            supported_scopes=(scope_a,),
            not_supported_scopes=(scope_b,),
        )
    )

    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
        engineering_condition_support_comparison_selection=(
            EngineeringConditionSupportComparisonSelection(
                engineering_condition="recurring_infrastructure_removal_activity",
                discovery_scopes=(scope_a, scope_b),
            )
        ),
        engineering_condition_support_comparison_workflow=comparison_workflow,
    )

    assert not isinstance(outcome, str)
    assert comparison_workflow.calls == [
        (
            "recurring_infrastructure_removal_activity",
            (scope_a, scope_b),
        )
    ]
    assert "Support Distribution" in outcome.report
    assert "Supported in some compared Discovery Scopes" in outcome.report
    assert "- scope-a" in outcome.report
    assert "- scope-b" in outcome.report


def test_condition_support_comparison_unavailable_is_not_rendered():
    comparison_workflow = FakeConditionSupportComparisonWorkflow(
        _condition_support_comparison_result(
            status="comparison_unavailable",
            projection=None,
            reason="insufficient_eligible_evaluations",
        )
    )

    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
        engineering_condition_support_comparison_selection=(
            EngineeringConditionSupportComparisonSelection(
                engineering_condition="recurring_infrastructure_removal_activity",
                discovery_scopes=(DiscoveryScope("scope-a"), DiscoveryScope("scope-b")),
            )
        ),
        engineering_condition_support_comparison_workflow=comparison_workflow,
    )

    assert not isinstance(outcome, str)
    assert "Support Distribution" not in outcome.report
    assert "insufficient_eligible_evaluations" not in outcome.report


def test_default_knowledge_review_does_not_render_condition_support_comparison():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
    )

    assert not isinstance(outcome, str)
    assert "Support Distribution" not in outcome.report


def test_empty_engineering_knowledge_output():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history())
    )

    assert not isinstance(outcome, str)
    assert outcome.report == (
        "Engineering Knowledge\n"
        "\n"
        "No Engineering Conditions were supported by the qualified historical evidence."
    )


def test_human_readable_output_is_unchanged_with_structured_result():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )

    assert not isinstance(outcome, str)
    assert "Supported Engineering Condition:" in outcome.report
    assert "engineering_knowledge" not in outcome.report
    assert "qualified_observation_window" not in outcome.report


def test_empty_engineering_knowledge_json_output():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history())
    )

    data = _json_output(outcome)

    assert data == {
        "status": "success",
        "engineering_knowledge": {
            "supported_engineering_conditions": [],
        },
    }


def test_insufficient_history_renders_empty_engineering_knowledge_output():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_insufficient_history())
    )

    assert not isinstance(outcome, str)
    assert outcome.report == (
        "Engineering Knowledge\n"
        "\n"
        "No Engineering Conditions were supported by the qualified historical evidence."
    )


def test_invalid_cross_scope_history_is_rejected_by_history_validation():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_cross_scope_history())
    )

    assert outcome == (
        "Knowledge review failed: Snapshot history contains multiple discovery scopes."
    )


def test_duplicate_snapshot_history_is_rejected_by_history_validation():
    duplicate_id = Identifier.new()
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            (
                _snapshot(
                    _resource("resource-001", version=1), snapshot_id=duplicate_id
                ),
                _snapshot(
                    _resource("resource-001", version=2), snapshot_id=duplicate_id
                ),
            )
        )
    )

    assert isinstance(outcome, str)
    assert outcome.startswith("Knowledge review failed: Duplicate snapshot ID")


def test_storage_failure_is_controlled_workflow_failure():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FailingSnapshotHistoryStorage()
    )

    assert outcome == "Knowledge review failed: snapshot history is unavailable"


def test_storage_failure_has_terminal_lifecycle_event(caplog):
    with caplog.at_level("INFO", logger="opscript"):
        outcome = run_knowledge_review_workflow_outcome(
            snapshot_storage=FailingSnapshotHistoryStorage()
        )

    messages = [record.message for record in caplog.records]
    started = [
        message
        for message in messages
        if "event=workflow_started" in message
        and "workflow=knowledge_review" in message
    ]
    completed = [
        message
        for message in messages
        if "event=workflow_completed" in message
        and "workflow=knowledge_review" in message
    ]
    failed = [
        message
        for message in messages
        if "event=workflow_failed" in message and "workflow=knowledge_review" in message
    ]

    assert outcome == "Knowledge review failed: snapshot history is unavailable"
    assert len(started) == 1
    assert completed == []
    assert len(failed) == 1
    assert "duration_ms=" in failed[0]
    assert "reason=snapshot_storage_error" in failed[0]


def test_successful_knowledge_review_emits_phase_lifecycle_in_order(caplog):
    outcome, messages = _run_with_lifecycle_logs(
        caplog,
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history()),
    )

    assert not isinstance(outcome, str)
    assert _event_names(messages) == (
        "workflow_started",
        "workflow_phase_started",
        "workflow_phase_completed",
        "workflow_phase_started",
        "workflow_phase_completed",
        "workflow_phase_started",
        "workflow_phase_completed",
        "workflow_phase_started",
        "workflow_phase_completed",
        "workflow_completed",
    )
    assert _phase_names(messages) == (
        "history_loading",
        "history_loading",
        "history_validation",
        "history_validation",
        "engineering_knowledge_evaluation",
        "engineering_knowledge_evaluation",
        "report_projection",
        "report_projection",
    )
    assert _phase_events(messages, "workflow_phase_failed") == ()
    assert _all_phase_events_have_required_fields(messages)
    assert all(
        _has_non_negative_duration(message)
        for message in _phase_events(messages, "workflow_phase_completed")
    )
    assert not any("execution_id=" in message for message in messages)


def test_knowledge_review_workflow_lifecycle_uses_active_execution_identity(caplog):
    execution = create_execution()

    with activate_execution(execution):
        outcome, messages = _run_with_lifecycle_logs(
            caplog,
            snapshot_storage=FakeSnapshotHistoryStorage(_modification_history()),
        )

    assert not isinstance(outcome, str)
    workflow_events = [
        message for message in messages if "event=workflow_phase_" not in message
    ]
    phase_events = _phase_lifecycle_events(messages)

    assert len(workflow_events) == 2
    assert all(
        f"execution_id={execution.identity}" in message for message in workflow_events
    )
    assert phase_events
    assert all(
        f"execution_id={execution.identity}" in message for message in phase_events
    )


def test_knowledge_review_workflow_failure_uses_active_execution_identity(caplog):
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        outcome = run_knowledge_review_workflow_outcome(
            snapshot_storage=FailingSnapshotHistoryStorage()
        )

    messages = _knowledge_review_lifecycle_messages(caplog)
    workflow_events = [
        message for message in messages if "event=workflow_phase_" not in message
    ]

    assert outcome == "Knowledge review failed: snapshot history is unavailable"
    assert len(workflow_events) == 2
    assert any("event=workflow_started" in message for message in workflow_events)
    assert any("event=workflow_failed" in message for message in workflow_events)
    assert all(
        f"execution_id={execution.identity}" in message for message in workflow_events
    )


def test_knowledge_review_phase_lifecycle_failure_paths(caplog):
    outcome, messages = _run_with_lifecycle_logs(
        caplog,
        snapshot_storage=FailingSnapshotHistoryStorage(),
    )

    assert outcome == "Knowledge review failed: snapshot history is unavailable"
    assert _event_names(messages) == (
        "workflow_started",
        "workflow_phase_started",
        "workflow_phase_failed",
        "workflow_failed",
    )
    assert _phase_names(_phase_lifecycle_events(messages)) == (
        "history_loading",
        "history_loading",
    )
    assert _phase_pair_count(messages, "history_loading") == (1, 0, 1)
    assert _all_phase_events_have_required_fields(messages)
    assert (
        "reason=snapshot_storage_error"
        in _phase_events(
            messages,
            "workflow_phase_failed",
        )[0]
    )

    caplog.clear()
    comparison_service = FailingEngineeringKnowledgeEvolutionComparisonService()
    with caplog.at_level("INFO", logger="opscript"):
        with pytest.raises(RuntimeError, match="comparison unavailable"):
            run_knowledge_review_workflow_outcome(
                snapshot_storage=FakeSnapshotHistoryStorage(
                    _evolution_introduction_history()
                ),
                include_engineering_knowledge_evolution=True,
                comparison_service=comparison_service,
            )
    messages = _knowledge_review_lifecycle_messages(caplog)

    assert _phase_pair_count(
        messages,
        "engineering_knowledge_evolution",
    ) == (1, 0, 1)
    assert _all_phase_events_have_required_fields(messages)
    assert _event_names(messages)[-2:] == (
        "workflow_phase_failed",
        "workflow_failed",
    )
    assert (
        "reason=workflow_error"
        in _phase_events(
            messages,
            "workflow_phase_failed",
        )[0]
    )
    assert not any("phase=report_projection" in message for message in messages)
    assert _workflow_events(messages, "workflow_completed") == ()


def test_optional_phase_lifecycle_events_are_requested_and_distinct(caplog):
    _, default_messages = _run_with_lifecycle_logs(
        caplog,
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
    )
    assert not any(
        "phase=engineering_knowledge_evolution" in message
        for message in default_messages
    )
    assert not any(
        "phase=engineering_knowledge_sequence_analysis" in message
        for message in default_messages
    )

    caplog.clear()
    _, messages = _run_with_lifecycle_logs(
        caplog,
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert _phase_pair_count(messages, "engineering_knowledge_evolution") == (1, 1, 0)
    assert _phase_pair_count(
        messages,
        "engineering_knowledge_sequence_analysis",
    ) == (1, 1, 0)
    assert _all_phase_events_have_required_fields(messages)
    assert all(
        "workflow=knowledge_review" in message
        for message in _phase_lifecycle_events(messages)
        if "phase=engineering_knowledge_sequence_analysis" in message
    )
    assert _phase_names(messages).index("engineering_knowledge_evolution") < (
        _phase_names(messages).index("engineering_knowledge_sequence_analysis")
    )


def test_unavailable_optional_results_are_completed_phase_outcomes(caplog):
    outcome, messages = _run_with_lifecycle_logs(
        caplog,
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
        include_engineering_knowledge_evolution=True,
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(outcome, str)
    assert outcome.engineering_knowledge_evolution_unavailable_message == (
        ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE
    )
    assert outcome.engineering_knowledge_sequence_analysis is not None
    assert outcome.engineering_knowledge_sequence_analysis.availability == "unavailable"
    assert _phase_pair_count(messages, "engineering_knowledge_evolution") == (1, 1, 0)
    assert _phase_pair_count(
        messages,
        "engineering_knowledge_sequence_analysis",
    ) == (1, 1, 0)
    assert _all_phase_events_have_required_fields(messages)


def test_phase_logs_stay_out_of_product_output_and_hide_internal_details(caplog):
    outcome, messages = _run_with_lifecycle_logs(
        caplog,
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history()),
    )
    assert not isinstance(outcome, str)
    data = _json_output(outcome)

    for event_name in (
        "workflow_phase_started",
        "workflow_phase_completed",
        "workflow_phase_failed",
    ):
        assert event_name not in outcome.report
        assert event_name not in json.dumps(data)

    caplog.clear()
    with caplog.at_level("INFO", logger="opscript"):
        with pytest.raises(RuntimeError):
            run_knowledge_review_workflow_outcome(
                snapshot_storage=FakeSnapshotHistoryStorage(
                    _evolution_introduction_history()
                ),
                include_engineering_knowledge_evolution=True,
                comparison_service=FailingEngineeringKnowledgeEvolutionComparisonService(),
            )
    messages = "\n".join(_knowledge_review_lifecycle_messages(caplog))

    assert "comparison unavailable" not in messages
    assert "Snapshot(" not in messages
    assert "Resource(" not in messages
    assert "Observation(" not in messages
    assert "QualifiedHistoricalEvidence" not in messages
    assert "CompletedComparisonInterval" not in messages


def test_one_ec001_report():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )

    assert not isinstance(outcome, str)
    assert (
        "Supported Engineering Condition:\n    frequent_infrastructure_modification"
        in outcome.report
    )
    assert "Subject:\n    resource-001" in outcome.report
    assert f"Recognition Basis:\n    {EC001_RECOGNITION_BASIS}" in outcome.report
    assert "recurring_infrastructure_removal_activity" not in outcome.report


def test_one_ec001_json_output():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )

    condition = _supported_conditions(outcome)[0]

    assert condition["engineering_condition"] == "frequent_infrastructure_modification"
    assert condition["recognition_basis"] == EC001_RECOGNITION_BASIS
    assert condition["discovery_scope"] == "scope-001"
    assert condition["subject"] == "resource-001"
    assert set(condition["qualified_observation_window"]) == {
        "previous_snapshot",
        "current_snapshot",
    }


def test_one_ec002_report():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_removal_history())
    )

    assert not isinstance(outcome, str)
    assert (
        "Supported Engineering Condition:\n    recurring_infrastructure_removal_activity"
        in outcome.report
    )
    assert f"Recognition Basis:\n    {EC002_RECOGNITION_BASIS}" in outcome.report
    assert "frequent_infrastructure_modification" not in outcome.report


def test_one_ec002_json_output_omits_subject():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_removal_history())
    )

    condition = _supported_conditions(outcome)[0]

    assert (
        condition["engineering_condition"]
        == "recurring_infrastructure_removal_activity"
    )
    assert condition["recognition_basis"] == EC002_RECOGNITION_BASIS
    assert condition["discovery_scope"] == "scope-001"
    assert "subject" not in condition
    assert set(condition["qualified_observation_window"]) == {
        "previous_snapshot",
        "current_snapshot",
    }


def test_one_ec003_report_omits_subject():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_introduction_history())
    )

    assert not isinstance(outcome, str)
    assert (
        "Supported Engineering Condition:\n    "
        "recurring_infrastructure_introduction_activity"
    ) in outcome.report
    assert f"Recognition Basis:\n    {EC003_RECOGNITION_BASIS}" in outcome.report
    assert "Subject:" not in outcome.report
    assert "frequent_infrastructure_modification" not in outcome.report
    assert "recurring_infrastructure_removal_activity" not in outcome.report


def test_one_ec003_json_output_omits_subject():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_introduction_history())
    )

    condition = _supported_conditions(outcome)[0]

    assert (
        condition["engineering_condition"]
        == "recurring_infrastructure_introduction_activity"
    )
    assert condition["recognition_basis"] == EC003_RECOGNITION_BASIS
    assert condition["discovery_scope"] == "scope-001"
    assert "subject" not in condition
    assert set(condition["qualified_observation_window"]) == {
        "previous_snapshot",
        "current_snapshot",
    }


def test_two_supported_conditions_render_in_order():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_and_removal_history())
    )

    assert not isinstance(outcome, str)
    assert outcome.report.index("frequent_infrastructure_modification") < (
        outcome.report.index("recurring_infrastructure_removal_activity")
    )


def test_ec002_and_ec003_render_in_approved_order():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_removal_and_introduction_history())
    )

    assert not isinstance(outcome, str)
    assert outcome.report.index("recurring_infrastructure_removal_activity") < (
        outcome.report.index("recurring_infrastructure_introduction_activity")
    )
    assert "Subject:" not in outcome.report


def test_two_supported_conditions_json_order_is_deterministic():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_and_removal_history())
    )

    conditions = _supported_conditions(outcome)

    assert [condition["engineering_condition"] for condition in conditions] == [
        "frequent_infrastructure_modification",
        "recurring_infrastructure_removal_activity",
    ]


def test_all_three_conditions_render_in_approved_order():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_all_three_conditions_history())
    )

    assert not isinstance(outcome, str)
    assert outcome.report.index("frequent_infrastructure_modification") < (
        outcome.report.index("recurring_infrastructure_removal_activity")
    )
    assert outcome.report.index("recurring_infrastructure_removal_activity") < (
        outcome.report.index("recurring_infrastructure_introduction_activity")
    )


def test_all_three_conditions_json_order_is_deterministic():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_all_three_conditions_history())
    )

    conditions = _supported_conditions(outcome)

    assert [condition["engineering_condition"] for condition in conditions] == [
        "frequent_infrastructure_modification",
        "recurring_infrastructure_removal_activity",
        "recurring_infrastructure_introduction_activity",
    ]
    assert "subject" in conditions[0]
    assert "subject" not in conditions[1]
    assert "subject" not in conditions[2]


def test_human_and_structured_recognition_basis_are_semantically_equivalent():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_all_three_conditions_history())
    )

    conditions = _supported_conditions(outcome)

    for condition in conditions:
        assert condition["recognition_basis"] in outcome.report


def test_subject_is_omitted_for_scope_level_condition():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_removal_history())
    )

    assert not isinstance(outcome, str)
    assert "Subject:" not in outcome.report


def test_json_output_excludes_implementation_terminology():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_and_removal_history())
    )

    output = json.dumps(_json_output(outcome))

    assert "Recognition" not in output
    assert "RecognizedFinding" not in output
    assert "QualifiedHistoricalEvidence" not in output
    assert "CompletedComparisonInterval" not in output
    assert "Observation" not in output
    assert "Observations" not in output
    assert "threshold" not in output.lower()
    assert "interval" not in output.lower()
    assert "calibration" not in output.lower()
    assert "minimum completed intervals" not in output.lower()
    assert "qualifying interval count" not in output.lower()
    assert "qualified_historical_evidence" not in output
    assert "completed_intervals" not in output
    assert "severity" not in output.lower()
    assert "risk" not in output.lower()
    assert "recommendation" not in output.lower()
    assert "causality" not in output.lower()


def test_observation_window_formatting():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )

    assert not isinstance(outcome, str)
    assert "Observation Window:" in outcome.report
    assert "\n↓\n" in outcome.report


def test_no_unsupported_conditions_displayed():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history())
    )

    assert not isinstance(outcome, str)
    assert "Supported Engineering Condition:" not in outcome.report
    assert "RecognitionResult" not in outcome.report
    assert "RecognizedFinding" not in outcome.report
    assert "Recognition Basis:" not in outcome.report


def test_human_output_excludes_recognition_mechanics():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_all_three_conditions_history())
    )

    assert not isinstance(outcome, str)
    assert "Recognition Rule" not in outcome.report
    assert "threshold" not in outcome.report.lower()
    assert "calibration" not in outcome.report.lower()
    assert "minimum completed intervals" not in outcome.report.lower()
    assert "qualifying interval count" not in outcome.report.lower()
    assert "completed comparison interval" not in outcome.report.lower()
    assert "Qualified Historical Evidence" not in outcome.report
    assert "QualifiedHistoricalEvidence" not in outcome.report
    assert "Observations" not in outcome.report
    assert "RecognitionResult" not in outcome.report
    assert "RecognizedFinding" not in outcome.report
    assert "severity" not in outcome.report.lower()
    assert "risk" not in outcome.report.lower()
    assert "recommendation" not in outcome.report.lower()
    assert "causality" not in outcome.report.lower()


def test_unsupported_conditions_are_absent_from_json():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history())
    )

    output = json.dumps(_json_output(outcome))

    assert "frequent_infrastructure_modification" not in output
    assert "recurring_infrastructure_removal_activity" not in output
    assert "recurring_infrastructure_introduction_activity" not in output
    assert "unsupported" not in output
    assert "skipped" not in output


def test_knowledge_review_command_returns_structured_json(monkeypatch):
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )
    monkeypatch.setattr(
        commands,
        "run_knowledge_review_workflow_outcome",
        lambda config=None, **kwargs: outcome,
    )

    result, output = commands.knowledge_review_command(
        SimpleNamespace(fail=False, json=True)
    )
    data = json.loads(output)

    assert result.status == "success"
    assert data["status"] == "success"
    assert (
        data["engineering_knowledge"]["supported_engineering_conditions"][0][
            "engineering_condition"
        ]
        == "frequent_infrastructure_modification"
    )


def test_knowledge_review_command_plain_text_remains_report(monkeypatch):
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )
    monkeypatch.setattr(
        commands,
        "run_knowledge_review_workflow_outcome",
        lambda config=None, **kwargs: outcome,
    )

    _, output = commands.knowledge_review_command(
        SimpleNamespace(fail=False, json=False)
    )

    assert output == outcome.report
    assert "engineering_knowledge" not in output


def test_knowledge_review_command_requests_evolution_only_when_explicit(monkeypatch):
    calls = []
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )

    def fake_workflow(config=None, **kwargs):
        calls.append(kwargs)
        return outcome

    monkeypatch.setattr(
        commands, "run_knowledge_review_workflow_outcome", fake_workflow
    )

    commands.knowledge_review_command(SimpleNamespace(fail=False, json=False))
    commands.knowledge_review_command(
        SimpleNamespace(fail=False, json=False, evolution=True)
    )
    commands.knowledge_review_command(
        SimpleNamespace(fail=False, json=False, sequence=True)
    )

    assert calls == [
        {
            "include_engineering_knowledge_evolution": False,
            "include_engineering_knowledge_sequence_analysis": False,
        },
        {
            "include_engineering_knowledge_evolution": True,
            "include_engineering_knowledge_sequence_analysis": False,
        },
        {
            "include_engineering_knowledge_evolution": False,
            "include_engineering_knowledge_sequence_analysis": True,
        },
    ]


def test_existing_reporting_unaffected():
    service = ReportingService(FakeReporter())
    finding = Finding(
        subject="resource-001",
        type="infrastructure_changed",
        message="Infrastructure changed: resource-001",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_modified",
    )

    assert service.generate_finding_report((finding,)) == (
        "Findings:\n- Infrastructure changed: resource-001"
    )


def test_existing_change_review_handler_unchanged():
    assert COMMANDS["change-review"] is not COMMANDS["knowledge-review"]


def test_render_engineering_knowledge_report_does_not_expose_calibration_fields():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )

    assert not isinstance(outcome, str)
    assert "threshold" not in outcome.report.lower()
    assert "minimum" not in outcome.report.lower()
    assert "interval" not in outcome.report.lower()
    assert "risk" not in outcome.report.lower()
    assert "recommendation" not in outcome.report.lower()


def test_empty_report_renderer_is_deterministic():
    assert render_engineering_knowledge_report(()) == (
        "Engineering Knowledge\n"
        "\n"
        "No Engineering Conditions were supported by the qualified historical evidence."
    )


def test_human_output_is_unchanged_without_engineering_knowledge_evolution():
    entries = (
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        ),
    )

    assert render_engineering_knowledge_report(entries) == "\n".join(
        [
            "Engineering Knowledge",
            "",
            "Supported Engineering Condition:",
            "    frequent_infrastructure_modification",
            "",
            "Recognition Basis:",
            "    Recognition basis for frequent_infrastructure_modification",
            "",
            "Discovery Scope:",
            "    scope-001",
            "",
            "Subject:",
            "    resource-001",
            "",
            "Observation Window:",
            "",
            "window-start",
            "",
            "\u2193",
            "",
            "window-end",
        ]
    )


def test_json_output_is_unchanged_without_engineering_knowledge_evolution():
    outcome = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        )
    )

    data = _json_output(outcome)

    assert set(data["engineering_knowledge"]) == {
        "supported_engineering_conditions",
    }
    assert "engineering_knowledge_evolution" not in data["engineering_knowledge"]


def test_introduced_engineering_knowledge_section_renders():
    comparison = EngineeringKnowledgeEvolutionComparison(
        introduced=(
            _report_entry(
                "frequent_infrastructure_modification",
                subject="resource-001",
            ),
        )
    )

    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_evolution=comparison,
    )

    assert "Engineering Knowledge Evolution" in report
    assert "Introduced Supported Engineering Conditions" in report
    assert (
        "Supported Engineering Condition:\n    frequent_infrastructure_modification"
        in report
    )
    assert "Discovery Scope:\n    scope-001" in report
    assert "Subject:\n    resource-001" in report


def test_removed_engineering_knowledge_section_renders():
    comparison = EngineeringKnowledgeEvolutionComparison(
        removed=(_report_entry("recurring_infrastructure_removal_activity"),)
    )

    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_evolution=comparison,
    )

    assert "Removed Supported Engineering Conditions" in report
    assert "recurring_infrastructure_removal_activity" in report


def test_unchanged_engineering_knowledge_section_renders():
    comparison = EngineeringKnowledgeEvolutionComparison(
        unchanged=(
            EngineeringKnowledgeEvolutionUnchangedCondition(
                evaluation_a=_report_entry(
                    "frequent_infrastructure_modification",
                    subject="resource-001",
                    previous_snapshot="window-a-start",
                ),
                evaluation_b=_report_entry(
                    "frequent_infrastructure_modification",
                    subject="resource-001",
                    previous_snapshot="window-b-start",
                ),
            ),
        )
    )

    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_evolution=comparison,
    )

    assert "Unchanged Supported Engineering Conditions" in report
    assert "frequent_infrastructure_modification" in report
    assert "window-a-start" not in report
    assert "window-b-start" not in report


def test_empty_engineering_knowledge_evolution_renders_no_changes_message():
    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_evolution=EngineeringKnowledgeEvolutionComparison(),
    )

    assert "Engineering Knowledge Evolution" in report
    assert (
        "No change in supported Engineering Knowledge was identified between the compared qualified evaluations."
        in report
    )


def test_engineering_knowledge_evolution_sections_are_deterministic():
    comparison = EngineeringKnowledgeEvolutionComparison(
        introduced=(_report_entry("frequent_infrastructure_modification"),),
        removed=(_report_entry("recurring_infrastructure_removal_activity"),),
        unchanged=(
            EngineeringKnowledgeEvolutionUnchangedCondition(
                evaluation_a=_report_entry(
                    "recurring_infrastructure_introduction_activity"
                ),
                evaluation_b=_report_entry(
                    "recurring_infrastructure_introduction_activity"
                ),
            ),
        ),
    )

    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_evolution=comparison,
    )

    assert report.index("Introduced Supported Engineering Conditions") < report.index(
        "Removed Supported Engineering Conditions"
    )
    assert report.index("Removed Supported Engineering Conditions") < report.index(
        "Unchanged Supported Engineering Conditions"
    )


def test_engineering_knowledge_evolution_omits_subject_for_scope_level_conditions():
    comparison = EngineeringKnowledgeEvolutionComparison(
        introduced=(_report_entry("recurring_infrastructure_removal_activity"),)
    )

    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_evolution=comparison,
    )

    assert "Subject:" not in report


def test_engineering_knowledge_evolution_structured_output():
    comparison = EngineeringKnowledgeEvolutionComparison(
        introduced=(
            _report_entry(
                "frequent_infrastructure_modification",
                subject="resource-001",
            ),
        ),
        removed=(_report_entry("recurring_infrastructure_removal_activity"),),
        unchanged=(
            EngineeringKnowledgeEvolutionUnchangedCondition(
                evaluation_a=_report_entry(
                    "recurring_infrastructure_introduction_activity"
                ),
                evaluation_b=_report_entry(
                    "recurring_infrastructure_introduction_activity"
                ),
            ),
        ),
    )
    result = Success(
        value=EngineeringKnowledgeServiceResult(
            message=render_engineering_knowledge_report(
                (),
                engineering_knowledge_evolution=comparison,
            ),
            supported_engineering_conditions=(),
            engineering_knowledge_evolution=comparison,
        )
    )

    data = json.loads(format_output(result, json_mode=True))
    evolution = data["engineering_knowledge"]["engineering_knowledge_evolution"]

    assert evolution == {
        "introduced_supported_engineering_conditions": [
            {
                "engineering_condition": "frequent_infrastructure_modification",
                "discovery_scope": "scope-001",
                "subject": "resource-001",
            }
        ],
        "removed_supported_engineering_conditions": [
            {
                "engineering_condition": "recurring_infrastructure_removal_activity",
                "discovery_scope": "scope-001",
            }
        ],
        "unchanged_supported_engineering_conditions": [
            {
                "engineering_condition": (
                    "recurring_infrastructure_introduction_activity"
                ),
                "discovery_scope": "scope-001",
            }
        ],
    }


def test_engineering_knowledge_evolution_human_and_structured_outputs_match():
    comparison = EngineeringKnowledgeEvolutionComparison(
        introduced=(
            _report_entry(
                "frequent_infrastructure_modification",
                subject="resource-001",
            ),
        )
    )
    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_evolution=comparison,
    )
    result = Success(
        value=EngineeringKnowledgeServiceResult(
            message=report,
            supported_engineering_conditions=(),
            engineering_knowledge_evolution=comparison,
        )
    )

    data = json.loads(format_output(result, json_mode=True))
    condition = data["engineering_knowledge"]["engineering_knowledge_evolution"][
        "introduced_supported_engineering_conditions"
    ][0]

    assert condition["engineering_condition"] in report
    assert condition["discovery_scope"] in report
    assert condition["subject"] in report


def test_engineering_knowledge_evolution_output_excludes_implementation_terminology():
    comparison = EngineeringKnowledgeEvolutionComparison(
        introduced=(_report_entry("recurring_infrastructure_removal_activity"),)
    )
    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_evolution=comparison,
    )
    result = Success(
        value=EngineeringKnowledgeServiceResult(
            message=report,
            supported_engineering_conditions=(),
            engineering_knowledge_evolution=comparison,
        )
    )
    structured = json.dumps(json.loads(format_output(result, json_mode=True)))
    rendered_outputs = (report, structured)

    for output in rendered_outputs:
        assert "RecognitionResult" not in output
        assert "RecognizedFinding" not in output
        assert "identity" not in output.lower()
        assert "comparison algorithm" not in output.lower()
        assert "threshold" not in output.lower()
        assert "calibration" not in output.lower()
        assert "Qualified Historical Evidence" not in output
        assert "Completed Comparison Intervals" not in output
        assert "Observations" not in output
        assert "Introduced Engineering Knowledge" not in output
        assert "Removed Engineering Knowledge" not in output
        assert "Unchanged Engineering Knowledge" not in output
        assert "introduced_engineering_knowledge" not in output
        assert "removed_engineering_knowledge" not in output
        assert "unchanged_engineering_knowledge" not in output


def test_completed_engineering_knowledge_evaluations_can_be_compared():
    evaluation_a = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        )
    )
    evaluation_b = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        ),
        _report_entry("recurring_infrastructure_removal_activity"),
    )

    comparison = compare_engineering_knowledge_evaluations(evaluation_a, evaluation_b)

    assert _comparison_conditions(comparison.introduced) == (
        "recurring_infrastructure_removal_activity",
    )
    assert comparison.removed == ()
    assert len(comparison.unchanged) == 1


def test_engineering_knowledge_evolution_returns_removed_conditions():
    evaluation_a = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        ),
        _report_entry("recurring_infrastructure_removal_activity"),
    )
    evaluation_b = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        )
    )

    comparison = compare_engineering_knowledge_evaluations(evaluation_a, evaluation_b)

    assert _comparison_conditions(comparison.removed) == (
        "recurring_infrastructure_removal_activity",
    )
    assert comparison.introduced == ()


def test_unchanged_engineering_knowledge_preserves_both_evaluation_contexts():
    evaluation_a = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
            previous_snapshot="window-a-start",
            current_snapshot="window-a-end",
        ),
        previous_snapshot="window-a-start",
        current_snapshot="window-a-end",
    )
    evaluation_b = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
            previous_snapshot="window-b-start",
            current_snapshot="window-b-end",
        ),
        previous_snapshot="window-b-start",
        current_snapshot="window-b-end",
    )

    comparison = compare_engineering_knowledge_evaluations(evaluation_a, evaluation_b)

    unchanged = comparison.unchanged[0]
    assert unchanged.evaluation_a.observation_window_previous_snapshot_id == Identifier(
        "window-a-start"
    )
    assert unchanged.evaluation_b.observation_window_previous_snapshot_id == Identifier(
        "window-b-start"
    )


def test_engineering_knowledge_evolution_accepts_different_discovery_scopes():
    evaluation_a = _completed_evaluation(
        _report_entry(
            "recurring_infrastructure_removal_activity",
            scope="scope-a",
        ),
        scope="scope-a",
    )
    evaluation_b = _completed_evaluation(
        _report_entry(
            "recurring_infrastructure_removal_activity",
            scope="scope-b",
        ),
        scope="scope-b",
    )

    comparison = compare_engineering_knowledge_evaluations(evaluation_a, evaluation_b)

    assert _comparison_scopes(comparison.removed) == ("scope-a",)
    assert _comparison_scopes(comparison.introduced) == ("scope-b",)
    assert comparison.unchanged == ()


def test_internally_inconsistent_evaluation_a_is_rejected():
    evaluation_a = _completed_evaluation(
        _report_entry("recurring_infrastructure_removal_activity", scope="scope-b"),
        scope="scope-a",
    )
    evaluation_b = _completed_evaluation()

    with pytest.raises(ValueError, match="Discovery Scope"):
        compare_engineering_knowledge_evaluations(evaluation_a, evaluation_b)


def test_internally_inconsistent_evaluation_b_is_rejected():
    evaluation_a = _completed_evaluation()
    evaluation_b = _completed_evaluation(
        _report_entry(
            "recurring_infrastructure_removal_activity",
            previous_snapshot="other-start",
            current_snapshot="other-end",
        ),
        previous_snapshot="window-start",
        current_snapshot="window-end",
    )

    with pytest.raises(ValueError, match="observation window"):
        compare_engineering_knowledge_evaluations(evaluation_a, evaluation_b)


def test_engineering_knowledge_evolution_delegates_to_fi008a_service():
    comparison = EngineeringKnowledgeEvolutionComparison()
    comparison_service = SpyEngineeringKnowledgeEvolutionComparisonService(comparison)
    evaluation_a = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        )
    )
    evaluation_b = _completed_evaluation(
        _report_entry("recurring_infrastructure_removal_activity")
    )

    result = compare_engineering_knowledge_evaluations(
        evaluation_a,
        evaluation_b,
        comparison_service=comparison_service,
    )

    assert result is comparison
    assert comparison_service.calls == (
        (evaluation_a.report_entries, evaluation_b.report_entries),
    )


def test_engineering_knowledge_evolution_does_not_mutate_evaluations():
    evaluation_a = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        )
    )
    evaluation_b = _completed_evaluation(
        _report_entry("recurring_infrastructure_removal_activity")
    )
    original_a_entries = evaluation_a.report_entries
    original_b_entries = evaluation_b.report_entries
    original_a_scope = evaluation_a.discovery_scope
    original_b_scope = evaluation_b.discovery_scope
    original_a_window = (
        evaluation_a.observation_window_previous_snapshot_id,
        evaluation_a.observation_window_current_snapshot_id,
    )
    original_b_window = (
        evaluation_b.observation_window_previous_snapshot_id,
        evaluation_b.observation_window_current_snapshot_id,
    )

    compare_engineering_knowledge_evaluations(evaluation_a, evaluation_b)

    assert evaluation_a.report_entries == original_a_entries
    assert evaluation_b.report_entries == original_b_entries
    assert evaluation_a.discovery_scope == original_a_scope
    assert evaluation_b.discovery_scope == original_b_scope
    assert (
        evaluation_a.observation_window_previous_snapshot_id,
        evaluation_a.observation_window_current_snapshot_id,
    ) == original_a_window
    assert (
        evaluation_b.observation_window_previous_snapshot_id,
        evaluation_b.observation_window_current_snapshot_id,
    ) == original_b_window


def test_engineering_knowledge_evolution_repeated_execution_is_deterministic():
    evaluation_a = _completed_evaluation(
        _report_entry(
            "frequent_infrastructure_modification",
            subject="resource-001",
        )
    )
    evaluation_b = _completed_evaluation(
        _report_entry("recurring_infrastructure_removal_activity")
    )

    assert compare_engineering_knowledge_evaluations(
        evaluation_a,
        evaluation_b,
    ) == compare_engineering_knowledge_evaluations(evaluation_a, evaluation_b)


def test_existing_point_in_time_knowledge_review_behavior_remains_unchanged():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_modification_history())
    )

    assert not isinstance(outcome, str)
    assert "Supported Engineering Condition:" in outcome.report
    assert "Evolution" not in outcome.report
    assert "introduced" not in outcome.report
    assert "removed" not in outcome.report


def test_engineering_knowledge_evolution_executes_only_when_explicitly_requested():
    default_outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history())
    )
    evolution_outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(default_outcome, str)
    assert not isinstance(evolution_outcome, str)
    assert "Engineering Knowledge Evolution" not in default_outcome.report
    assert "Engineering Knowledge Evolution" in evolution_outcome.report


def test_engineering_knowledge_evolution_compares_immediately_preceding_evaluation():
    comparison_service = SpyEngineeringKnowledgeEvolutionComparisonService(
        EngineeringKnowledgeEvolutionComparison()
    )

    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
        comparison_service=comparison_service,
    )

    assert not isinstance(outcome, str)
    assert len(comparison_service.calls) == 1
    previous_entries, current_entries = comparison_service.calls[0]
    assert previous_entries == ()
    assert _comparison_conditions(current_entries) == (
        "frequent_infrastructure_modification",
    )


def test_engineering_knowledge_evolution_skips_unqualified_historical_windows():
    comparison_service = SpyEngineeringKnowledgeEvolutionComparisonService(
        EngineeringKnowledgeEvolutionComparison()
    )

    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
        comparison_service=comparison_service,
    )

    assert not isinstance(outcome, str)
    assert len(comparison_service.calls) == 1


def test_empty_qualified_engineering_knowledge_evaluation_participates_normally():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_six_snapshot_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    assert ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE not in outcome.report
    assert (
        "No change in supported Engineering Knowledge was identified between the compared qualified evaluations."
        in outcome.report
    )
    assert (
        outcome.engineering_knowledge_evolution
        == EngineeringKnowledgeEvolutionComparison()
    )


def test_engineering_knowledge_evolution_insufficient_history_message_is_exact():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    assert ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE not in outcome.report

    insufficient_outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(insufficient_outcome, str)
    assert ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE in (
        insufficient_outcome.report
    )


def test_engineering_knowledge_evolution_same_discovery_scope_is_enforced():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_cross_scope_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert outcome == (
        "Knowledge review failed: Snapshot history contains multiple discovery scopes."
    )


def test_engineering_knowledge_evolution_chronology_is_normalized_before_comparison():
    comparison_service = SpyEngineeringKnowledgeEvolutionComparisonService(
        EngineeringKnowledgeEvolutionComparison()
    )

    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            _six_snapshot_modification_history()
        ),
        include_engineering_knowledge_evolution=True,
        comparison_service=comparison_service,
    )

    assert not isinstance(outcome, str)
    previous_entries, current_entries = comparison_service.calls[0]
    assert _comparison_conditions(previous_entries) == (
        "frequent_infrastructure_modification",
    )
    assert _comparison_conditions(current_entries) == (
        "frequent_infrastructure_modification",
    )


def test_engineering_knowledge_evolution_json_uses_existing_comparison_contract():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    data = _json_output(outcome)

    evolution = data["engineering_knowledge"]["engineering_knowledge_evolution"]
    assert tuple(evolution) == (
        "earlier_qualified_evaluation",
        "later_qualified_evaluation",
        "introduced_supported_engineering_conditions",
        "removed_supported_engineering_conditions",
        "unchanged_supported_engineering_conditions",
    )
    assert evolution["introduced_supported_engineering_conditions"] == [
        {
            "engineering_condition": "frequent_infrastructure_modification",
            "discovery_scope": "scope-001",
            "subject": "resource-001",
        }
    ]


def test_successful_human_evolution_identifies_earlier_qualified_evaluation():
    history = _evolution_introduction_history()
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(history),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    assert "Earlier Qualified Evaluation" in outcome.report
    assert "Discovery Scope:\n    scope-001" in outcome.report
    assert "Qualified Observation Window:" in outcome.report
    assert _snapshot_id(history[0]) in outcome.report
    assert _snapshot_id(history[4]) in outcome.report


def test_successful_human_evolution_identifies_later_qualified_evaluation():
    history = _evolution_introduction_history()
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(history),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    assert "Later Qualified Evaluation" in outcome.report
    assert _snapshot_id(history[0]) in outcome.report
    assert _snapshot_id(history[5]) in outcome.report


def test_successful_structured_evolution_contains_compared_evaluation_contexts():
    history = _evolution_introduction_history()
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(history),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    evolution = _json_output(outcome)["engineering_knowledge"][
        "engineering_knowledge_evolution"
    ]

    assert evolution["earlier_qualified_evaluation"] == {
        "discovery_scope": "scope-001",
        "qualified_observation_window": {
            "previous_snapshot": _snapshot_id(history[0]),
            "current_snapshot": _snapshot_id(history[4]),
        },
    }
    assert evolution["later_qualified_evaluation"] == {
        "discovery_scope": "scope-001",
        "qualified_observation_window": {
            "previous_snapshot": _snapshot_id(history[0]),
            "current_snapshot": _snapshot_id(history[5]),
        },
    }


def test_empty_qualified_evolution_exposes_both_contexts():
    history = _unchanged_six_snapshot_history()
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(history),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    assert "Earlier Qualified Evaluation" in outcome.report
    assert "Later Qualified Evaluation" in outcome.report

    evolution = _json_output(outcome)["engineering_knowledge"][
        "engineering_knowledge_evolution"
    ]
    assert evolution["earlier_qualified_evaluation"]["qualified_observation_window"][
        "current_snapshot"
    ] == _snapshot_id(history[4])
    assert evolution["later_qualified_evaluation"]["qualified_observation_window"][
        "current_snapshot"
    ] == _snapshot_id(history[5])


def test_insufficient_history_is_not_structured_as_successful_comparison():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    evolution = _json_output(outcome)["engineering_knowledge"][
        "engineering_knowledge_evolution"
    ]

    assert evolution == {
        "availability": "unavailable",
        "message": ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE,
    }
    assert "unavailable" + "_reason" not in evolution
    assert "introduced_supported_engineering_conditions" not in evolution
    assert "removed_supported_engineering_conditions" not in evolution
    assert "unchanged_supported_engineering_conditions" not in evolution
    assert "earlier_qualified_evaluation" not in evolution
    assert "later_qualified_evaluation" not in evolution


def test_unavailable_engineering_knowledge_evolution_keeps_successful_execution():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
        include_engineering_knowledge_evolution=True,
    )

    data = _json_output(outcome)

    assert data["status"] == "success"
    assert data["engineering_knowledge"]["supported_engineering_conditions"] == []
    assert data["engineering_knowledge"]["engineering_knowledge_evolution"] == {
        "availability": "unavailable",
        "message": ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE,
    }


def test_successful_engineering_knowledge_evolution_has_no_unavailable_fields():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
    )

    evolution = _json_output(outcome)["engineering_knowledge"][
        "engineering_knowledge_evolution"
    ]

    assert "availability" not in evolution
    assert "message" not in evolution
    assert "unavailable" + "_reason" not in evolution


def test_engineering_knowledge_evolution_uses_existing_qualification_authority(
    monkeypatch,
):
    interval_counts = []
    original = knowledge_review_workflow.build_qualified_historical_evidence

    def spy_build_qualified_historical_evidence(analysis_history, **kwargs):
        evidence = original(analysis_history, **kwargs)
        interval_counts.append(len(evidence.completed_intervals))
        return evidence

    monkeypatch.setattr(
        knowledge_review_workflow,
        "build_qualified_historical_evidence",
        spy_build_qualified_historical_evidence,
    )

    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    assert interval_counts == [1, 2, 3, 4, 5]


def test_engineering_knowledge_evolution_output_exposes_no_selection_terminology():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
    )

    assert not isinstance(outcome, str)
    output = json.dumps(_json_output(outcome)) + outcome.report

    assert "checkpoint" not in output.lower()
    assert "version" not in output.lower()
    assert "evaluation identifier" not in output.lower()
    assert "comparison identifier" not in output.lower()
    assert "RecognitionResult" not in output
    assert "QualifiedHistoricalEvidence" not in output


def test_engineering_knowledge_sequence_analysis_executes_only_when_requested():
    default_outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            _six_snapshot_modification_history()
        )
    )
    sequence_outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            _six_snapshot_modification_history()
        ),
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(default_outcome, str)
    assert not isinstance(sequence_outcome, str)
    assert "Engineering Knowledge Sequence Analysis" not in default_outcome.report
    assert "Engineering Knowledge Sequence Analysis" in sequence_outcome.report


def test_engineering_knowledge_sequence_analysis_reports_continuous_support():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            _six_snapshot_modification_history()
        ),
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(outcome, str)
    assert "Supported Engineering Condition:" in outcome.report
    assert "    frequent_infrastructure_modification" in outcome.report
    assert "Discovery Scope:\n    scope-001" in outcome.report
    assert "Subject:\n    resource-001" in outcome.report
    assert "Qualified Evaluation Sequence" in outcome.report
    assert "Sequence Start Evaluation:" in outcome.report
    assert "Sequence End Evaluation:" in outcome.report
    assert "Qualified Evaluation Count:\n    2" in outcome.report
    assert "Support State at Sequence Start:\n    supported" in outcome.report
    assert "Support State at Sequence End:\n    supported" in outcome.report
    assert (
        "Continuously supported across the qualified evaluation sequence."
        in outcome.report
    )
    assert "Newly supported" not in outcome.report
    assert "No longer supported" not in outcome.report
    assert "Reappeared" not in outcome.report


def test_engineering_knowledge_sequence_analysis_reports_newly_supported():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(outcome, str)
    assert "Engineering Knowledge Sequence Analysis" in outcome.report
    assert "Support State at Sequence Start:\n    unsupported" in outcome.report
    assert "Support State at Sequence End:\n    supported" in outcome.report
    assert "Newly supported" in outcome.report


def test_engineering_knowledge_sequence_analysis_json_is_additive():
    history = _evolution_introduction_history()
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(history),
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(outcome, str)
    data = _json_output(outcome)

    sequence = data["engineering_knowledge"]["engineering_knowledge_sequence_analysis"]
    assert sequence == {
        "availability": "available",
        "supported_engineering_condition": {
            "engineering_condition": "frequent_infrastructure_modification",
            "discovery_scope": "scope-001",
            "subject": "resource-001",
        },
        "qualified_evaluation_sequence": {
            "start_evaluation": {
                "qualified_observation_window": {
                    "previous_snapshot": _snapshot_id(history[0]),
                    "current_snapshot": _snapshot_id(history[4]),
                },
            },
            "end_evaluation": {
                "qualified_observation_window": {
                    "previous_snapshot": _snapshot_id(history[0]),
                    "current_snapshot": _snapshot_id(history[5]),
                },
            },
            "qualified_evaluation_count": 2,
        },
        "support_state_at_sequence_start": "unsupported",
        "support_state_at_sequence_end": "supported",
        "continuous_support": "not_established",
        "new_support_within_sequence": "established",
        "support_end_within_sequence": "not_established",
        "reappearance_within_sequence": "not_established",
    }
    assert "discovery_scope" not in {
        key: value
        for key, value in sequence.items()
        if key != "supported_engineering_condition"
    }


def test_engineering_knowledge_sequence_analysis_json_absent_by_default():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            _six_snapshot_modification_history()
        )
    )

    assert not isinstance(outcome, str)
    data = _json_output(outcome)

    assert (
        "engineering_knowledge_sequence_analysis" not in data["engineering_knowledge"]
    )


def test_engineering_knowledge_sequence_analysis_renders_no_longer_and_reappeared():
    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_sequence_analysis=EngineeringKnowledgeSequenceAnalysisResult(
            availability="available",
            analysis=_sequence_analysis(
                no_longer_supported=True,
                reappeared=True,
            ),
        ),
    )

    assert "No longer supported" in report
    assert "Reappeared" in report


def test_engineering_knowledge_sequence_analysis_exposes_no_deferred_statistics():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            _six_snapshot_modification_history()
        ),
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(outcome, str)
    output = json.dumps(_json_output(outcome)) + outcome.report

    assert "transition count" not in output.lower()
    assert "support proportion" not in output.lower()
    assert "supported run length" not in output.lower()
    assert "unsupported run length" not in output.lower()
    assert "ranking" not in output.lower()


def test_engineering_knowledge_sequence_analysis_json_unavailable_contract():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(outcome, str)
    sequence = _json_output(outcome)["engineering_knowledge"][
        "engineering_knowledge_sequence_analysis"
    ]

    assert sequence == {
        "availability": "unavailable",
        "message": ENGINEERING_KNOWLEDGE_SEQUENCE_ANALYSIS_UNAVAILABLE_MESSAGE,
    }


def test_engineering_knowledge_sequence_analysis_human_unavailable_contract():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history()),
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(outcome, str)
    assert "Engineering Knowledge Sequence Analysis" in outcome.report
    assert ENGINEERING_KNOWLEDGE_SEQUENCE_ANALYSIS_UNAVAILABLE_MESSAGE in outcome.report


def test_engineering_knowledge_sequence_analysis_scope_condition_omits_subject():
    history = _removal_history() + (_snapshot(),)
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(history),
        include_engineering_knowledge_sequence_analysis=True,
    )

    assert not isinstance(outcome, str)
    sequence = _json_output(outcome)["engineering_knowledge"][
        "engineering_knowledge_sequence_analysis"
    ]

    assert sequence["availability"] == "available"
    assert sequence["supported_engineering_condition"] == {
        "engineering_condition": "recurring_infrastructure_removal_activity",
        "discovery_scope": "scope-001",
    }
    assert "subject" not in sequence["supported_engineering_condition"]


def test_engineering_knowledge_sequence_analysis_uses_analytical_state_values():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            _six_snapshot_modification_history()
        ),
        include_engineering_knowledge_sequence_analysis=True,
    )

    sequence = _json_output(outcome)["engineering_knowledge"][
        "engineering_knowledge_sequence_analysis"
    ]

    assert sequence["continuous_support"] == "established"
    assert sequence["new_support_within_sequence"] == "not_established"
    assert sequence["support_end_within_sequence"] == "not_established"
    assert sequence["reappearance_within_sequence"] == "not_established"
    assert True not in sequence.values()
    assert False not in sequence.values()
    assert "no_longer_supported_within_sequence" not in sequence


def test_engineering_knowledge_sequence_analysis_neutral_completed_wording():
    report = render_engineering_knowledge_report(
        (),
        engineering_knowledge_sequence_analysis=EngineeringKnowledgeSequenceAnalysisResult(
            availability="available",
            analysis=_sequence_analysis(),
        ),
    )

    assert (
        "No additional approved support-state pattern was established across the qualified evaluation sequence."
        in report
    )


def test_engineering_knowledge_sequence_analysis_has_no_explanation_field_or_array():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(
            _six_snapshot_modification_history()
        ),
        include_engineering_knowledge_sequence_analysis=True,
    )

    sequence = _json_output(outcome)["engineering_knowledge"][
        "engineering_knowledge_sequence_analysis"
    ]

    assert isinstance(sequence, dict)
    assert "analysis_basis" not in sequence
    assert "explanation" not in sequence
    assert "narrative" not in sequence


def test_engineering_knowledge_sequence_analysis_coexists_with_evolution():
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_evolution_introduction_history()),
        include_engineering_knowledge_evolution=True,
        include_engineering_knowledge_sequence_analysis=True,
    )

    data = _json_output(outcome)["engineering_knowledge"]

    assert "engineering_knowledge_evolution" in data
    assert "engineering_knowledge_sequence_analysis" in data
    assert (
        "engineering_knowledge_sequence_analysis"
        not in data["engineering_knowledge_evolution"]
    )


def _json_output(outcome):
    assert not isinstance(outcome, str)
    result = Success(
        value=EngineeringKnowledgeServiceResult(
            message=outcome.report,
            supported_engineering_conditions=outcome.report_entries,
            engineering_knowledge_evolution=outcome.engineering_knowledge_evolution,
            engineering_knowledge_sequence_analysis=(
                outcome.engineering_knowledge_sequence_analysis
            ),
            earlier_qualified_evaluation=outcome.earlier_qualified_evaluation,
            later_qualified_evaluation=outcome.later_qualified_evaluation,
            engineering_knowledge_evolution_unavailable_message=(
                outcome.engineering_knowledge_evolution_unavailable_message
            ),
        )
    )
    return json.loads(format_output(result, json_mode=True))


def _supported_conditions(outcome):
    return _json_output(outcome)["engineering_knowledge"][
        "supported_engineering_conditions"
    ]


def _unchanged_history() -> tuple[Snapshot, ...]:
    return tuple(_snapshot(_resource("resource-001", version=1)) for _ in range(5))


def _unchanged_six_snapshot_history() -> tuple[Snapshot, ...]:
    return tuple(_snapshot(_resource("resource-001", version=1)) for _ in range(6))


def _insufficient_history() -> tuple[Snapshot, ...]:
    return tuple(_snapshot(_resource("resource-001", version=1)) for _ in range(3))


def _cross_scope_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(
            _resource("resource-001", version=1),
            discovery_scope=DiscoveryScope("scope-001"),
        ),
        _snapshot(
            _resource("resource-001", version=2),
            discovery_scope=DiscoveryScope("scope-002"),
        ),
    )


def _modification_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(_resource("resource-001", version=1)),
        _snapshot(_resource("resource-001", version=2)),
        _snapshot(_resource("resource-001", version=3)),
        _snapshot(_resource("resource-001", version=3)),
        _snapshot(_resource("resource-001", version=4)),
    )


def _evolution_introduction_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(_resource("resource-001", version=1)),
        _snapshot(_resource("resource-001", version=2)),
        _snapshot(_resource("resource-001", version=3)),
        _snapshot(_resource("resource-001", version=3)),
        _snapshot(_resource("resource-001", version=3)),
        _snapshot(_resource("resource-001", version=4)),
    )


def _six_snapshot_modification_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(_resource("resource-001", version=1)),
        _snapshot(_resource("resource-001", version=2)),
        _snapshot(_resource("resource-001", version=3)),
        _snapshot(_resource("resource-001", version=3)),
        _snapshot(_resource("resource-001", version=4)),
        _snapshot(_resource("resource-001", version=5)),
    )


def _removal_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(
            _resource("removed-001", version=1),
            _resource("removed-002", version=1),
            _resource("removed-003", version=1),
        ),
        _snapshot(
            _resource("removed-002", version=1),
            _resource("removed-003", version=1),
        ),
        _snapshot(_resource("removed-003", version=1)),
        _snapshot(_resource("removed-003", version=1)),
        _snapshot(),
    )


def _introduction_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(),
        _snapshot(_resource("introduced-001", version=1)),
        _snapshot(
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
        ),
        _snapshot(
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
        ),
        _snapshot(
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
            _resource("introduced-003", version=1),
        ),
    )


def _removal_and_introduction_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(
            _resource("removed-001", version=1),
            _resource("removed-002", version=1),
            _resource("removed-003", version=1),
        ),
        _snapshot(
            _resource("removed-002", version=1),
            _resource("removed-003", version=1),
            _resource("introduced-001", version=1),
        ),
        _snapshot(
            _resource("removed-003", version=1),
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
        ),
        _snapshot(
            _resource("removed-003", version=1),
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
        ),
        _snapshot(
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
            _resource("introduced-003", version=1),
        ),
    )


def _modification_and_removal_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(
            _resource("resource-001", version=1),
            _resource("removed-001", version=1),
            _resource("removed-002", version=1),
            _resource("removed-003", version=1),
        ),
        _snapshot(
            _resource("resource-001", version=2),
            _resource("removed-002", version=1),
            _resource("removed-003", version=1),
        ),
        _snapshot(
            _resource("resource-001", version=3),
            _resource("removed-003", version=1),
        ),
        _snapshot(
            _resource("resource-001", version=3),
            _resource("removed-003", version=1),
        ),
        _snapshot(_resource("resource-001", version=4)),
    )


def _all_three_conditions_history() -> tuple[Snapshot, ...]:
    return (
        _snapshot(
            _resource("resource-001", version=1),
            _resource("removed-001", version=1),
            _resource("removed-002", version=1),
            _resource("removed-003", version=1),
        ),
        _snapshot(
            _resource("resource-001", version=2),
            _resource("removed-002", version=1),
            _resource("removed-003", version=1),
            _resource("introduced-001", version=1),
        ),
        _snapshot(
            _resource("resource-001", version=3),
            _resource("removed-003", version=1),
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
        ),
        _snapshot(
            _resource("resource-001", version=3),
            _resource("removed-003", version=1),
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
        ),
        _snapshot(
            _resource("resource-001", version=4),
            _resource("introduced-001", version=1),
            _resource("introduced-002", version=1),
            _resource("introduced-003", version=1),
        ),
    )


def _snapshot(
    *resources: Resource,
    snapshot_id: Identifier | None = None,
    discovery_scope: DiscoveryScope | None = None,
) -> Snapshot:
    return Snapshot(
        id=snapshot_id or Identifier.new(),
        discovery_scope=discovery_scope or DiscoveryScope("scope-001"),
        resources=resources,
    )


def _snapshot_id(snapshot: Snapshot) -> str:
    return str(snapshot.id)


def _resource(external_id: str, *, version: int) -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
        state=ResourceState(properties={"version": version}),
    )


def _completed_evaluation(
    *entries: EngineeringKnowledgeReportEntry,
    scope: str = "scope-001",
    previous_snapshot: str = "window-start",
    current_snapshot: str = "window-end",
):
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=FakeSnapshotHistoryStorage(_unchanged_history())
    )
    assert not isinstance(outcome, str)
    return replace(
        outcome,
        report_entries=entries,
        discovery_scope=DiscoveryScope(scope),
        observation_window_previous_snapshot_id=Identifier(previous_snapshot),
        observation_window_current_snapshot_id=Identifier(current_snapshot),
    )


def _report_entry(
    engineering_condition: str,
    *,
    scope: str = "scope-001",
    subject: str | None = None,
    previous_snapshot: str = "window-start",
    current_snapshot: str = "window-end",
) -> EngineeringKnowledgeReportEntry:
    return EngineeringKnowledgeReportEntry(
        engineering_condition=engineering_condition,
        recognition_outcome="supported",
        discovery_scope=DiscoveryScope(scope),
        canonical_subject=subject,
        recognition_basis=f"Recognition basis for {engineering_condition}",
        observation_window_previous_snapshot_id=Identifier(previous_snapshot),
        observation_window_current_snapshot_id=Identifier(current_snapshot),
        recognition_threshold=3,
        minimum_completed_interval_count=4,
    )


def _sequence_analysis(
    *,
    no_longer_supported: bool = False,
    reappeared: bool = False,
) -> EngineeringKnowledgeSequenceAnalysis:
    return EngineeringKnowledgeSequenceAnalysis(
        engineering_condition="frequent_infrastructure_modification",
        discovery_scope=DiscoveryScope("scope-001"),
        canonical_subject="resource-001",
        sequence_start_evaluation=EngineeringKnowledgeEvaluationContext(
            discovery_scope=DiscoveryScope("scope-001"),
            observation_window_previous_snapshot_id=Identifier("snapshot-001"),
            observation_window_current_snapshot_id=Identifier("snapshot-004"),
        ),
        sequence_end_evaluation=EngineeringKnowledgeEvaluationContext(
            discovery_scope=DiscoveryScope("scope-001"),
            observation_window_previous_snapshot_id=Identifier("snapshot-001"),
            observation_window_current_snapshot_id=Identifier("snapshot-005"),
        ),
        qualified_evaluation_count=2,
        supported_at_sequence_start=True,
        supported_at_sequence_end=False,
        continuously_supported=False,
        newly_supported=False,
        no_longer_supported=no_longer_supported,
        reappeared=reappeared,
    )


def _comparison_conditions(
    entries: tuple[EngineeringKnowledgeReportEntry, ...],
) -> tuple[str, ...]:
    return tuple(entry.engineering_condition for entry in entries)


def _comparison_scopes(
    entries: tuple[EngineeringKnowledgeReportEntry, ...],
) -> tuple[str, ...]:
    return tuple(entry.discovery_scope.value for entry in entries)


def _condition_support_comparison_result(
    *,
    status: str = "comparison_produced",
    classification: str = "SUPPORTED_IN_ALL_SCOPES",
    compared_scopes: tuple[DiscoveryScope, ...] = (
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-b"),
    ),
    supported_scopes: tuple[DiscoveryScope, ...] = (
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-b"),
    ),
    not_supported_scopes: tuple[DiscoveryScope, ...] = (),
    projection: EngineeringConditionSupportComparisonProjection | None = None,
    reason: str = "comparison_available",
) -> EngineeringConditionSupportComparisonWorkflowResult:
    if projection is None and status == "comparison_produced":
        projection = EngineeringConditionSupportComparisonProjection(
            engineering_condition="recurring_infrastructure_removal_activity",
            classification=classification,
            compared_discovery_scopes=compared_scopes,
            supported_discovery_scopes=supported_scopes,
            not_supported_discovery_scopes=not_supported_scopes,
        )

    return EngineeringConditionSupportComparisonWorkflowResult(
        status=status,
        engineering_condition="recurring_infrastructure_removal_activity",
        requested_scopes=compared_scopes,
        eligibility=EngineeringConditionComparisonEligibility(),
        projection=projection,
        reason=reason,
    )


class SpyEngineeringKnowledgeEvolutionComparisonService:
    def __init__(
        self,
        comparison: EngineeringKnowledgeEvolutionComparison,
    ):
        self.comparison = comparison
        self.calls = ()

    def compare(
        self,
        evaluation_a: tuple[EngineeringKnowledgeReportEntry, ...],
        evaluation_b: tuple[EngineeringKnowledgeReportEntry, ...],
    ) -> EngineeringKnowledgeEvolutionComparison:
        self.calls = (*self.calls, (evaluation_a, evaluation_b))
        return self.comparison


class FailingEngineeringKnowledgeEvolutionComparisonService:
    def compare(
        self,
        evaluation_a: tuple[EngineeringKnowledgeReportEntry, ...],
        evaluation_b: tuple[EngineeringKnowledgeReportEntry, ...],
    ) -> EngineeringKnowledgeEvolutionComparison:
        raise RuntimeError("comparison unavailable")


def _run_with_lifecycle_logs(caplog, **kwargs):
    with caplog.at_level("INFO", logger="opscript"):
        outcome = run_knowledge_review_workflow_outcome(**kwargs)

    return outcome, _knowledge_review_lifecycle_messages(caplog)


def _knowledge_review_lifecycle_messages(caplog) -> tuple[str, ...]:
    return tuple(
        record.message
        for record in caplog.records
        if "workflow=knowledge_review" in record.message
        and (
            "event=workflow_started" in record.message
            or "event=workflow_completed" in record.message
            or "event=workflow_failed" in record.message
            or "event=workflow_phase_started" in record.message
            or "event=workflow_phase_completed" in record.message
            or "event=workflow_phase_failed" in record.message
        )
    )


def _event_names(messages: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        part.removeprefix("event=")
        for message in messages
        for part in message.split()
        if part.startswith("event=")
    )


def _phase_names(messages: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        part.removeprefix("phase=")
        for message in messages
        for part in message.split()
        if part.startswith("phase=")
    )


def _phase_events(messages: tuple[str, ...], event: str) -> tuple[str, ...]:
    return tuple(message for message in messages if f"event={event}" in message)


def _phase_lifecycle_events(messages: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(message for message in messages if "event=workflow_phase_" in message)


def _workflow_events(messages: tuple[str, ...], event: str) -> tuple[str, ...]:
    return tuple(message for message in messages if f"event={event}" in message)


def _phase_pair_count(
    messages: tuple[str, ...],
    phase: str,
) -> tuple[int, int, int]:
    phase_messages = tuple(
        message for message in messages if f"phase={phase}" in message
    )
    return (
        len(_phase_events(phase_messages, "workflow_phase_started")),
        len(_phase_events(phase_messages, "workflow_phase_completed")),
        len(_phase_events(phase_messages, "workflow_phase_failed")),
    )


def _all_phase_events_have_required_fields(messages: tuple[str, ...]) -> bool:
    for message in _phase_lifecycle_events(messages):
        if "workflow=knowledge_review" not in message:
            return False
        if "phase=" not in message:
            return False
        if (
            "event=workflow_phase_started" not in message
            and "duration_ms=" not in message
        ):
            return False
        if "event=workflow_phase_failed" in message and "reason=" not in message:
            return False

    return True


def _has_non_negative_duration(message: str) -> bool:
    for part in message.split():
        if part.startswith("duration_ms="):
            return int(part.removeprefix("duration_ms=")) >= 0
    return False

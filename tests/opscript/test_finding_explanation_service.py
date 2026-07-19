from __future__ import annotations

from datetime import UTC, datetime

import pytest

from opscript.application import (
    FindingExplanationError,
    WorkflowOutcome,
    explain_workflow_outcome_findings,
    explain_finding,
    format_finding_explanation,
    render_workflow_outcome_explanations,
)
from opscript.application.workflow_execution import WorkflowExecutionResult
from opscript.application.workflow_metrics import WorkflowMetricsReport
from platformiq.core import Identifier
from platformiq.model import AnalysisResult, DiffResult, Finding, Observation, Resource
from platformiq.model.value_objects import ResourceState


TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)


def test_explain_created_resource_finding() -> None:
    resource = _resource("aws:ec2:i-001")
    analysis_result = _analysis_result(
        created=(resource,),
        observations=(_observation("resource_created", resource.external_id),),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )

    explanation = explain_finding(analysis_result, analysis_result.findings[0])

    assert explanation.finding_subject == resource.external_id
    assert explanation.finding_type == "new_infrastructure_introduced"
    assert explanation.finding_message == f"Finding for {resource.external_id}"
    assert explanation.observation_subject == resource.external_id
    assert explanation.observation_type == "resource_created"
    assert explanation.observation_message == f"Observation for {resource.external_id}"
    assert explanation.diff_category == "created"
    assert explanation.resource_external_id == resource.external_id
    assert explanation.previous_snapshot_id == analysis_result.diff.previous_snapshot_id
    assert explanation.current_snapshot_id == analysis_result.diff.current_snapshot_id


def test_explain_deleted_resource_finding() -> None:
    resource = _resource("aws:lambda:function-a")
    analysis_result = _analysis_result(
        deleted=(resource,),
        observations=(_observation("resource_deleted", resource.external_id),),
        findings=(
            _finding(
                "infrastructure_removed",
                "resource_deleted",
                resource.external_id,
            ),
        ),
    )

    explanation = explain_finding(analysis_result, analysis_result.findings[0])

    assert explanation.diff_category == "deleted"
    assert explanation.resource_external_id == resource.external_id
    assert explanation.previous_snapshot_id == analysis_result.diff.previous_snapshot_id
    assert explanation.current_snapshot_id == analysis_result.diff.current_snapshot_id


def test_explain_modified_resource_finding() -> None:
    resource = _resource("aws:s3:bucket-a")
    analysis_result = _analysis_result(
        modified=(resource,),
        observations=(_observation("resource_modified", resource.external_id),),
        findings=(
            _finding(
                "infrastructure_changed",
                "resource_modified",
                resource.external_id,
            ),
        ),
    )

    explanation = explain_finding(analysis_result, analysis_result.findings[0])

    assert explanation.diff_category == "modified"
    assert explanation.resource_external_id == resource.external_id
    assert explanation.previous_snapshot_id == analysis_result.diff.previous_snapshot_id
    assert explanation.current_snapshot_id == analysis_result.diff.current_snapshot_id


def test_explain_finding_fails_if_no_matching_observation_exists() -> None:
    resource = _resource("aws:ec2:i-001")
    analysis_result = _analysis_result(
        created=(resource,),
        observations=(),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )

    with pytest.raises(FindingExplanationError, match="No matching observation"):
        explain_finding(analysis_result, analysis_result.findings[0])


def test_explain_finding_fails_if_multiple_matching_observations_exist() -> None:
    resource = _resource("aws:ec2:i-001")
    matching_observation = _observation("resource_created", resource.external_id)
    analysis_result = _analysis_result(
        created=(resource,),
        observations=(matching_observation, matching_observation),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )

    with pytest.raises(FindingExplanationError, match="Multiple matching observations"):
        explain_finding(analysis_result, analysis_result.findings[0])


def test_explain_finding_fails_if_no_matching_diff_resource_exists() -> None:
    resource = _resource("aws:ec2:i-001")
    analysis_result = _analysis_result(
        created=(),
        observations=(_observation("resource_created", resource.external_id),),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )

    with pytest.raises(FindingExplanationError, match="No matching diff resource"):
        explain_finding(analysis_result, analysis_result.findings[0])


def test_explain_finding_fails_if_multiple_diff_resources_match() -> None:
    resource = _resource("aws:ec2:i-001")
    duplicate_resource = _resource(resource.external_id)
    analysis_result = _analysis_result(
        created=(resource, duplicate_resource),
        observations=(_observation("resource_created", resource.external_id),),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )

    with pytest.raises(
        FindingExplanationError, match="Multiple matching diff resources"
    ):
        explain_finding(analysis_result, analysis_result.findings[0])


def test_explain_finding_uses_existing_platformiq_models() -> None:
    resource = _resource("aws:ec2:i-001")
    observation = _observation("resource_created", resource.external_id)
    finding = _finding(
        "new_infrastructure_introduced",
        observation.type,
        observation.subject,
    )
    analysis_result = AnalysisResult(
        diff=DiffResult(
            previous_snapshot_id=Identifier.new(),
            current_snapshot_id=Identifier.new(),
            created=(resource,),
        ),
        observations=(observation,),
        findings=(finding,),
    )

    explanation = explain_finding(analysis_result, finding)

    assert explanation.finding_subject == finding.subject
    assert explanation.observation_subject == observation.subject
    assert explanation.previous_snapshot_id == analysis_result.diff.previous_snapshot_id


def test_format_finding_explanation_includes_explanation_chain() -> None:
    resource = _resource("aws:ec2:i-001")
    analysis_result = _analysis_result(
        created=(resource,),
        observations=(_observation("resource_created", resource.external_id),),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )
    explanation = explain_finding(analysis_result, analysis_result.findings[0])

    output = format_finding_explanation(explanation)

    assert "Finding Explanation" in output
    assert "Opscript states:" in output
    assert f"Finding for {resource.external_id}" in output
    assert "Evidence chain:" in output
    assert "1. Finding" in output
    assert "2. Observation" in output
    assert "3. Diff" in output
    assert "4. Compared snapshots" in output
    assert "   Type: new_infrastructure_introduced" in output
    assert f"   Subject: {resource.external_id}" in output
    assert "   Type: resource_created" in output
    assert f"   Subject: {resource.external_id}" in output
    assert f"Observation for {resource.external_id}" in output
    assert "   Category: created" in output
    assert f"   Resource: {resource.external_id}" in output
    assert f"   Previous: {analysis_result.diff.previous_snapshot_id}" in output
    assert f"   Current: {analysis_result.diff.current_snapshot_id}" in output
    assert "(subject=" not in output
    assert "(Previous snapshot:" not in output
    assert "(Current snapshot:" not in output


def test_explain_workflow_outcome_findings_returns_one_explanation_per_finding() -> (
    None
):
    first_resource = _resource("aws:ec2:i-001")
    second_resource = _resource("aws:s3:bucket-a")
    analysis_result = _analysis_result(
        created=(first_resource, second_resource),
        observations=(
            _observation("resource_created", first_resource.external_id),
            _observation("resource_created", second_resource.external_id),
        ),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                first_resource.external_id,
            ),
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                second_resource.external_id,
            ),
        ),
    )
    outcome = _workflow_outcome(
        report="Existing report output",
        analysis_result=analysis_result,
    )

    explanations = explain_workflow_outcome_findings(outcome)

    assert tuple(explanation.resource_external_id for explanation in explanations) == (
        first_resource.external_id,
        second_resource.external_id,
    )


def test_explain_workflow_outcome_findings_fails_without_analysis_result() -> None:
    outcome = _workflow_outcome(
        report="Existing report output",
        analysis_result=None,
    )

    with pytest.raises(FindingExplanationError, match="analysis_result"):
        explain_workflow_outcome_findings(outcome)


def test_explain_workflow_outcome_findings_does_not_change_report_output() -> None:
    report = "Existing report output"
    resource = _resource("aws:ec2:i-001")
    analysis_result = _analysis_result(
        created=(resource,),
        observations=(_observation("resource_created", resource.external_id),),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )
    outcome = _workflow_outcome(
        report=report,
        analysis_result=analysis_result,
    )

    explain_workflow_outcome_findings(outcome)

    assert outcome.report == report


def test_render_workflow_outcome_explanations_for_single_finding() -> None:
    resource = _resource("aws:ec2:i-001")
    analysis_result = _analysis_result(
        created=(resource,),
        observations=(_observation("resource_created", resource.external_id),),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )
    outcome = _workflow_outcome(
        report="Existing report output",
        analysis_result=analysis_result,
    )

    output = render_workflow_outcome_explanations(outcome)

    assert output.count("Finding Explanation") == 1
    assert "new_infrastructure_introduced" in output
    assert "   Category: created" in output
    assert f"   Resource: {resource.external_id}" in output


def test_render_workflow_outcome_explanations_for_multiple_findings() -> None:
    first_resource = _resource("aws:ec2:i-001")
    second_resource = _resource("aws:s3:bucket-a")
    analysis_result = _analysis_result(
        created=(first_resource, second_resource),
        observations=(
            _observation("resource_created", first_resource.external_id),
            _observation("resource_created", second_resource.external_id),
        ),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                first_resource.external_id,
            ),
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                second_resource.external_id,
            ),
        ),
    )
    outcome = _workflow_outcome(
        report="Existing report output",
        analysis_result=analysis_result,
    )

    output = render_workflow_outcome_explanations(outcome)

    assert output.count("Finding Explanation") == 2
    assert "\n\nFinding Explanation" in output
    assert first_resource.external_id in output
    assert second_resource.external_id in output


def test_render_workflow_outcome_explanations_returns_empty_string_for_no_findings() -> (
    None
):
    analysis_result = _analysis_result(
        observations=(),
        findings=(),
    )
    outcome = _workflow_outcome(
        report="Existing report output",
        analysis_result=analysis_result,
    )

    assert render_workflow_outcome_explanations(outcome) == ""


def test_render_workflow_outcome_explanations_propagates_missing_analysis_result() -> (
    None
):
    outcome = _workflow_outcome(
        report="Existing report output",
        analysis_result=None,
    )

    with pytest.raises(FindingExplanationError, match="analysis_result"):
        render_workflow_outcome_explanations(outcome)


def test_render_workflow_outcome_explanations_does_not_change_report_output() -> None:
    report = "Existing report output"
    resource = _resource("aws:ec2:i-001")
    analysis_result = _analysis_result(
        created=(resource,),
        observations=(_observation("resource_created", resource.external_id),),
        findings=(
            _finding(
                "new_infrastructure_introduced",
                "resource_created",
                resource.external_id,
            ),
        ),
    )
    outcome = _workflow_outcome(
        report=report,
        analysis_result=analysis_result,
    )

    render_workflow_outcome_explanations(outcome)

    assert outcome.report == report


def _resource(external_id: str) -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
        state=ResourceState(properties={"name": external_id}),
    )


def _observation(observation_type: str, subject: str) -> Observation:
    return Observation(
        subject=subject,
        type=observation_type,
        message=f"Observation for {subject}",
        timestamp=TIMESTAMP,
    )


def _finding(
    finding_type: str,
    source_observation_type: str,
    subject: str,
) -> Finding:
    return Finding(
        subject=subject,
        type=finding_type,
        message=f"Finding for {subject}",
        timestamp=TIMESTAMP,
        source_observation_type=source_observation_type,
    )


def _analysis_result(
    *,
    created: tuple[Resource, ...] = (),
    deleted: tuple[Resource, ...] = (),
    modified: tuple[Resource, ...] = (),
    observations: tuple[Observation, ...],
    findings: tuple[Finding, ...],
) -> AnalysisResult:
    return AnalysisResult(
        diff=DiffResult(
            previous_snapshot_id=Identifier.new(),
            current_snapshot_id=Identifier.new(),
            created=created,
            deleted=deleted,
            modified=modified,
        ),
        observations=observations,
        findings=findings,
    )


def _workflow_outcome(
    *,
    report: str,
    analysis_result: AnalysisResult | None,
) -> WorkflowOutcome:
    return WorkflowOutcome(
        report=report,
        execution=WorkflowExecutionResult(
            value="snapshot",
            duration_ms=1,
        ),
        metrics=WorkflowMetricsReport(
            workflow_name="observation",
            duration_ms=1,
        ),
        analysis_result=analysis_result,
    )

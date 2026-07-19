from __future__ import annotations

from dataclasses import dataclass

from platformiq.core import Identifier
from platformiq.model import AnalysisResult, Finding, Observation, Resource

from opscript.application.workflow_outcome import WorkflowOutcome


class FindingExplanationError(Exception):
    """Raised when a finding cannot be explained deterministically."""


@dataclass(frozen=True)
class FindingExplanation:
    finding_subject: str
    finding_type: str
    finding_message: str
    observation_subject: str
    observation_type: str
    observation_message: str
    diff_category: str
    resource_external_id: str
    previous_snapshot_id: Identifier
    current_snapshot_id: Identifier


def explain_finding(
    analysis_result: AnalysisResult,
    finding: Finding,
) -> FindingExplanation:
    observation = _match_single_observation(analysis_result, finding)
    diff_category = _diff_category_for_observation(observation)
    resource = _match_single_resource(analysis_result, observation, diff_category)

    return FindingExplanation(
        finding_subject=finding.subject,
        finding_type=finding.type,
        finding_message=finding.message,
        observation_subject=observation.subject,
        observation_type=observation.type,
        observation_message=observation.message,
        diff_category=diff_category,
        resource_external_id=resource.external_id,
        previous_snapshot_id=analysis_result.diff.previous_snapshot_id,
        current_snapshot_id=analysis_result.diff.current_snapshot_id,
    )


def explain_workflow_outcome_findings(
    outcome: WorkflowOutcome,
) -> tuple[FindingExplanation, ...]:
    if outcome.analysis_result is None:
        raise FindingExplanationError(
            "WorkflowOutcome does not include an analysis_result."
        )

    return tuple(
        explain_finding(outcome.analysis_result, finding)
        for finding in outcome.analysis_result.findings
    )


def format_finding_explanation(
    explanation: FindingExplanation,
) -> str:
    return "\n".join(
        (
            "Finding Explanation",
            "",
            "Opscript states:",
            explanation.finding_message,
            "",
            "Evidence chain:",
            "1. Finding",
            f"   Type: {explanation.finding_type}",
            f"   Subject: {explanation.finding_subject}",
            "",
            "2. Observation",
            f"   Type: {explanation.observation_type}",
            f"   Subject: {explanation.observation_subject}",
            f"   Message: {explanation.observation_message}",
            "",
            "3. Diff",
            f"   Category: {explanation.diff_category}",
            f"   Resource: {explanation.resource_external_id}",
            "",
            "4. Compared snapshots",
            f"   Previous: {explanation.previous_snapshot_id}",
            f"   Current: {explanation.current_snapshot_id}",
        )
    )


def render_workflow_outcome_explanations(
    outcome: WorkflowOutcome,
) -> str:
    explanations = explain_workflow_outcome_findings(outcome)
    if not explanations:
        return ""

    return "\n\n".join(
        format_finding_explanation(explanation) for explanation in explanations
    )


def _match_single_observation(
    analysis_result: AnalysisResult,
    finding: Finding,
) -> Observation:
    matches = tuple(
        observation
        for observation in analysis_result.observations
        if observation.subject == finding.subject
        and observation.type == finding.source_observation_type
        and observation.timestamp == finding.timestamp
        and observation.metadata == finding.metadata
    )

    if not matches:
        raise FindingExplanationError(
            f"No matching observation found for finding subject={finding.subject!r} "
            f"source_observation_type={finding.source_observation_type!r}."
        )
    if len(matches) > 1:
        raise FindingExplanationError(
            f"Multiple matching observations found for finding subject={finding.subject!r} "
            f"source_observation_type={finding.source_observation_type!r}."
        )
    return matches[0]


def _diff_category_for_observation(observation: Observation) -> str:
    match observation.type:
        case "resource_created":
            return "created"
        case "resource_deleted":
            return "deleted"
        case "resource_modified":
            return "modified"
        case _:
            raise FindingExplanationError(
                f"Observation type {observation.type!r} does not map to a diff category."
            )


def _match_single_resource(
    analysis_result: AnalysisResult,
    observation: Observation,
    diff_category: str,
) -> Resource:
    resources = getattr(analysis_result.diff, diff_category)
    matches = tuple(
        resource
        for resource in resources
        if resource.external_id == observation.subject
    )

    if not matches:
        raise FindingExplanationError(
            f"No matching diff resource found for observation subject={observation.subject!r} "
            f"diff_category={diff_category!r}."
        )
    if len(matches) > 1:
        raise FindingExplanationError(
            f"Multiple matching diff resources found for observation subject={observation.subject!r} "
            f"diff_category={diff_category!r}."
        )
    return matches[0]

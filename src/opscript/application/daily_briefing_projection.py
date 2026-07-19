from __future__ import annotations

from dataclasses import dataclass, field
from json import dumps
from typing import Any

from platformiq.core import Identifier
from platformiq.model import AnalysisResult, Finding, Observation


@dataclass(frozen=True)
class DailyBriefingScope:
    previous_snapshot_id: Identifier
    current_snapshot_id: Identifier

    def __post_init__(self) -> None:
        if not isinstance(self.previous_snapshot_id, Identifier):
            raise TypeError("previous_snapshot_id must be an Identifier.")
        if not isinstance(self.current_snapshot_id, Identifier):
            raise TypeError("current_snapshot_id must be an Identifier.")


@dataclass(frozen=True)
class DailyBriefingStructuralSummary:
    observation_count: int
    finding_count: int
    introduced_count: int
    modified_count: int
    removed_count: int
    distinct_affected_subject_count: int
    is_empty: bool


@dataclass(frozen=True)
class DailyBriefingProjectionResult:
    previous_snapshot_id: Identifier
    current_snapshot_id: Identifier
    observations: tuple[Observation, ...] = field(default_factory=tuple)
    findings: tuple[Finding, ...] = field(default_factory=tuple)
    scope: DailyBriefingScope | None = None
    structural_summary: DailyBriefingStructuralSummary | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.previous_snapshot_id, Identifier):
            raise TypeError("previous_snapshot_id must be an Identifier.")
        if not isinstance(self.current_snapshot_id, Identifier):
            raise TypeError("current_snapshot_id must be an Identifier.")

        observations = tuple(self.observations)
        findings = tuple(self.findings)
        provided_scope = self.scope
        provided_structural_summary = self.structural_summary

        for observation in observations:
            if not isinstance(observation, Observation):
                raise TypeError("observations must contain Observation instances.")

        for finding in findings:
            if not isinstance(finding, Finding):
                raise TypeError("findings must contain Finding instances.")

        object.__setattr__(self, "observations", _ordered_observations(observations))
        object.__setattr__(self, "findings", _ordered_findings(findings))

        scope = DailyBriefingScope(
            previous_snapshot_id=self.previous_snapshot_id,
            current_snapshot_id=self.current_snapshot_id,
        )
        structural_summary = _structural_summary(
            observations=self.observations,
            findings=self.findings,
        )

        if provided_scope is not None:
            _validate_scope(provided_scope, expected_scope=scope)
            scope = provided_scope

        if provided_structural_summary is not None:
            _validate_structural_summary(
                provided_structural_summary,
                expected_structural_summary=structural_summary,
            )
            structural_summary = provided_structural_summary

        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "structural_summary", structural_summary)


class DailyBriefingProjection:
    def project(
        self,
        analysis_result: AnalysisResult,
    ) -> DailyBriefingProjectionResult:
        previous_snapshot_id = analysis_result.diff.previous_snapshot_id
        current_snapshot_id = analysis_result.diff.current_snapshot_id

        return DailyBriefingProjectionResult(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=tuple(
                observation
                for observation in analysis_result.observations
                if _belongs_to_interval(
                    observation,
                    previous_snapshot_id=previous_snapshot_id,
                    current_snapshot_id=current_snapshot_id,
                )
            ),
            findings=tuple(
                finding
                for finding in analysis_result.findings
                if _belongs_to_interval(
                    finding,
                    previous_snapshot_id=previous_snapshot_id,
                    current_snapshot_id=current_snapshot_id,
                )
            ),
        )


def _belongs_to_interval(
    artifact: Observation | Finding,
    *,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
) -> bool:
    return (
        artifact.previous_snapshot_id == previous_snapshot_id
        and artifact.current_snapshot_id == current_snapshot_id
    )


def _structural_summary(
    *,
    observations: tuple[Observation, ...],
    findings: tuple[Finding, ...],
) -> DailyBriefingStructuralSummary:
    subjects = {observation.subject for observation in observations}
    subjects.update(finding.subject for finding in findings)

    return DailyBriefingStructuralSummary(
        observation_count=len(observations),
        finding_count=len(findings),
        introduced_count=sum(
            1 for observation in observations if observation.type == "resource_created"
        ),
        modified_count=sum(
            1 for observation in observations if observation.type == "resource_modified"
        ),
        removed_count=sum(
            1 for observation in observations if observation.type == "resource_deleted"
        ),
        distinct_affected_subject_count=len(subjects),
        is_empty=not observations and not findings,
    )


def _validate_scope(
    scope: DailyBriefingScope,
    *,
    expected_scope: DailyBriefingScope,
) -> None:
    if not isinstance(scope, DailyBriefingScope):
        raise TypeError("scope must be a DailyBriefingScope.")
    if scope != expected_scope:
        raise ValueError("Daily Briefing scope must match the comparison interval.")


def _validate_structural_summary(
    structural_summary: DailyBriefingStructuralSummary,
    *,
    expected_structural_summary: DailyBriefingStructuralSummary,
) -> None:
    if not isinstance(structural_summary, DailyBriefingStructuralSummary):
        raise TypeError("structural_summary must be a DailyBriefingStructuralSummary.")

    validations = (
        (
            structural_summary.observation_count,
            expected_structural_summary.observation_count,
            "Daily Briefing observation count must match selected observations.",
        ),
        (
            structural_summary.finding_count,
            expected_structural_summary.finding_count,
            "Daily Briefing finding count must match selected findings.",
        ),
        (
            structural_summary.introduced_count,
            expected_structural_summary.introduced_count,
            "Daily Briefing introduced count must match selected observations.",
        ),
        (
            structural_summary.modified_count,
            expected_structural_summary.modified_count,
            "Daily Briefing modified count must match selected observations.",
        ),
        (
            structural_summary.removed_count,
            expected_structural_summary.removed_count,
            "Daily Briefing removed count must match selected observations.",
        ),
        (
            structural_summary.distinct_affected_subject_count,
            expected_structural_summary.distinct_affected_subject_count,
            "Daily Briefing affected-subject count must match selected artifacts.",
        ),
        (
            structural_summary.is_empty,
            expected_structural_summary.is_empty,
            "Daily Briefing empty-state flag must match selected content.",
        ),
    )

    for actual, expected, message in validations:
        if actual != expected:
            raise ValueError(message)


def _ordered_observations(
    observations: tuple[Observation, ...],
) -> tuple[Observation, ...]:
    return tuple(sorted(observations, key=_observation_order_key))


def _ordered_findings(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    return tuple(sorted(findings, key=_finding_order_key))


def _observation_order_key(observation: Observation) -> tuple[str, ...]:
    return (
        str(observation.previous_snapshot_id),
        str(observation.current_snapshot_id),
        observation.type,
        observation.subject,
        observation.timestamp.isoformat(),
        observation.message,
        _metadata_order_key(observation.metadata),
    )


def _finding_order_key(finding: Finding) -> tuple[str, ...]:
    return (
        str(finding.previous_snapshot_id),
        str(finding.current_snapshot_id),
        finding.type,
        finding.subject,
        finding.source_observation_type,
        finding.timestamp.isoformat(),
        finding.message,
        _metadata_order_key(finding.metadata),
    )


def _metadata_order_key(metadata: dict[str, Any] | None) -> str:
    if metadata is None:
        return ""
    return dumps(metadata, default=str, sort_keys=True)

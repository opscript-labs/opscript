from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from inspect import getsource

import pytest

from opscript.application.daily_briefing_projection import (
    DailyBriefingProjection,
    DailyBriefingProjectionResult,
    DailyBriefingScope,
    DailyBriefingStructuralSummary,
)
from platformiq.core import Identifier
from platformiq.model import AnalysisResult, DiffResult, Finding, Observation


TIMESTAMP = datetime(2026, 1, 1, tzinfo=UTC)


def test_projection_exposes_authoritative_comparison_interval() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        )
    )

    assert result.previous_snapshot_id == previous_snapshot_id
    assert result.current_snapshot_id == current_snapshot_id
    assert result.scope.previous_snapshot_id == previous_snapshot_id
    assert result.scope.current_snapshot_id == current_snapshot_id


def test_projection_selects_every_matching_observation() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    first_observation = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    second_observation = _observation(
        "resource_modified",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(first_observation, second_observation),
        )
    )

    assert result.observations == (first_observation, second_observation)


def test_projection_selects_every_matching_finding() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    first_finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    second_finding = _finding(
        "infrastructure_changed",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            findings=(first_finding, second_finding),
        )
    )

    assert result.findings == (second_finding, first_finding)


def test_structural_summary_reconciles_with_selected_content() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    created = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    modified = _observation(
        "resource_modified",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    removed = _observation(
        "resource_deleted",
        "resource-c",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(created, modified, removed),
            findings=(finding,),
        )
    )

    assert result.structural_summary.observation_count == len(result.observations)
    assert result.structural_summary.finding_count == len(result.findings)
    assert result.structural_summary.introduced_count == 1
    assert result.structural_summary.modified_count == 1
    assert result.structural_summary.removed_count == 1
    assert result.structural_summary.distinct_affected_subject_count == 3
    assert result.structural_summary.is_empty is False


def test_projection_excludes_observations_from_other_intervals() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    matching_observation = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    other_observation = _observation(
        "resource_created",
        "resource-b",
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
    )

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(other_observation, matching_observation),
        )
    )

    assert result.observations == (matching_observation,)


def test_projection_excludes_findings_from_other_intervals() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    matching_finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    other_finding = _finding(
        "new_infrastructure_introduced",
        "resource-b",
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
    )

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            findings=(other_finding, matching_finding),
        )
    )

    assert result.findings == (matching_finding,)


def test_projection_excludes_unscoped_observations_and_findings() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = _unscoped_observation("resource_created", "resource-a")
    finding = _unscoped_finding("new_infrastructure_introduced", "resource-a")

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
            findings=(finding,),
        )
    )

    assert result.observations == ()
    assert result.findings == ()


def test_projection_returns_empty_immutable_collections_without_matching_candidates() -> (
    None
):
    result = DailyBriefingProjection().project(_analysis_result())

    assert result.observations == ()
    assert result.findings == ()
    assert isinstance(result.observations, tuple)
    assert isinstance(result.findings, tuple)
    assert result.structural_summary.observation_count == 0
    assert result.structural_summary.finding_count == 0
    assert result.structural_summary.introduced_count == 0
    assert result.structural_summary.modified_count == 0
    assert result.structural_summary.removed_count == 0
    assert result.structural_summary.distinct_affected_subject_count == 0
    assert result.structural_summary.is_empty is True


def test_equivalent_authoritative_inputs_produce_equivalent_projection_results() -> (
    None
):
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    first_result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
            findings=(finding,),
        )
    )
    second_result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
            findings=(finding,),
        )
    )

    assert first_result == second_result


def test_no_selected_observation_or_finding_is_omitted_from_contract_result() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observations = (
        _observation(
            "resource_created",
            "resource-a",
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        ),
        _observation(
            "resource_modified",
            "resource-b",
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        ),
    )
    findings = (
        _finding(
            "new_infrastructure_introduced",
            "resource-a",
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        ),
        _finding(
            "infrastructure_changed",
            "resource-b",
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        ),
    )

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=observations,
            findings=findings,
        )
    )

    assert result.observations == observations
    assert result.findings == (findings[1], findings[0])


def test_projection_result_is_immutable() -> None:
    result = DailyBriefingProjection().project(_analysis_result())

    with pytest.raises(FrozenInstanceError):
        result.previous_snapshot_id = Identifier.new()


def test_selected_collections_cannot_be_mutated() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
            findings=(finding,),
        )
    )

    with pytest.raises(AttributeError):
        result.observations.append(observation)

    with pytest.raises(AttributeError):
        result.findings.append(finding)


def test_observation_order_is_canonical_for_permuted_inputs() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    created = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    modified = _observation(
        "resource_modified",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    removed = _observation(
        "resource_deleted",
        "resource-c",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    first_result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(removed, modified, created),
        )
    )
    second_result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(created, modified, removed),
        )
    )

    assert first_result.observations == (created, removed, modified)
    assert first_result.observations == second_result.observations


def test_finding_order_is_canonical_for_permuted_inputs() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    changed = _finding(
        "infrastructure_changed",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        source_observation_type="resource_modified",
    )
    introduced = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        source_observation_type="resource_created",
    )
    removed = _finding(
        "infrastructure_removed",
        "resource-c",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        source_observation_type="resource_deleted",
    )

    first_result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            findings=(removed, changed, introduced),
        )
    )
    second_result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            findings=(introduced, changed, removed),
        )
    )

    assert first_result.findings == (changed, removed, introduced)
    assert first_result.findings == second_result.findings


def test_canonical_order_preserves_every_selected_artifact_once() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    created = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    modified = _observation(
        "resource_modified",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    changed = _finding(
        "infrastructure_changed",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        source_observation_type="resource_modified",
    )
    introduced = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        source_observation_type="resource_created",
    )

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(modified, created),
            findings=(introduced, changed),
        )
    )

    assert result.observations == (created, modified)
    assert result.findings == (changed, introduced)
    assert result.structural_summary.observation_count == 2
    assert result.structural_summary.finding_count == 2
    assert result.scope.previous_snapshot_id == previous_snapshot_id
    assert result.scope.current_snapshot_id == current_snapshot_id


def test_finding_membership_uses_direct_finding_interval_provenance() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    same_subject_other_interval = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
    )

    result = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            findings=(same_subject_other_interval, finding),
        )
    )

    assert result.findings == (finding,)


def test_projection_has_no_finding_explanation_membership_dependency() -> None:
    from opscript.application import daily_briefing_projection

    source = getsource(daily_briefing_projection)

    assert "explain_finding" not in source
    assert "FindingExplanation" not in source


def test_projection_result_rejects_invalid_selected_artifacts() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    with pytest.raises(TypeError, match="observations must contain Observation"):
        DailyBriefingProjectionResult(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=("not an observation",),
        )

    with pytest.raises(TypeError, match="findings must contain Finding"):
        DailyBriefingProjectionResult(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            findings=("not a finding",),
        )


def test_valid_projection_result_construction_accepts_reconciled_contract_values() -> (
    None
):
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    result = DailyBriefingProjectionResult(
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=(observation,),
        findings=(finding,),
        scope=DailyBriefingScope(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        ),
        structural_summary=DailyBriefingStructuralSummary(
            observation_count=1,
            finding_count=1,
            introduced_count=1,
            modified_count=0,
            removed_count=0,
            distinct_affected_subject_count=1,
            is_empty=False,
        ),
    )

    assert result.observations == (observation,)
    assert result.findings == (finding,)


@pytest.mark.parametrize(
    ("summary", "message"),
    (
        (
            DailyBriefingStructuralSummary(
                observation_count=2,
                finding_count=1,
                introduced_count=1,
                modified_count=0,
                removed_count=0,
                distinct_affected_subject_count=1,
                is_empty=False,
            ),
            "observation count",
        ),
        (
            DailyBriefingStructuralSummary(
                observation_count=1,
                finding_count=2,
                introduced_count=1,
                modified_count=0,
                removed_count=0,
                distinct_affected_subject_count=1,
                is_empty=False,
            ),
            "finding count",
        ),
        (
            DailyBriefingStructuralSummary(
                observation_count=1,
                finding_count=1,
                introduced_count=0,
                modified_count=0,
                removed_count=0,
                distinct_affected_subject_count=1,
                is_empty=False,
            ),
            "introduced count",
        ),
        (
            DailyBriefingStructuralSummary(
                observation_count=1,
                finding_count=1,
                introduced_count=1,
                modified_count=1,
                removed_count=0,
                distinct_affected_subject_count=1,
                is_empty=False,
            ),
            "modified count",
        ),
        (
            DailyBriefingStructuralSummary(
                observation_count=1,
                finding_count=1,
                introduced_count=1,
                modified_count=0,
                removed_count=1,
                distinct_affected_subject_count=1,
                is_empty=False,
            ),
            "removed count",
        ),
        (
            DailyBriefingStructuralSummary(
                observation_count=1,
                finding_count=1,
                introduced_count=1,
                modified_count=0,
                removed_count=0,
                distinct_affected_subject_count=2,
                is_empty=False,
            ),
            "affected-subject count",
        ),
        (
            DailyBriefingStructuralSummary(
                observation_count=1,
                finding_count=1,
                introduced_count=1,
                modified_count=0,
                removed_count=0,
                distinct_affected_subject_count=1,
                is_empty=True,
            ),
            "empty-state flag",
        ),
    ),
)
def test_projection_result_rejects_inconsistent_structural_summary(
    summary: DailyBriefingStructuralSummary,
    message: str,
) -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    with pytest.raises(ValueError, match=message):
        DailyBriefingProjectionResult(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
            findings=(finding,),
            structural_summary=summary,
        )


def test_projection_result_rejects_inconsistent_scope() -> None:
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    with pytest.raises(ValueError, match="scope must match"):
        DailyBriefingProjectionResult(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            scope=DailyBriefingScope(
                previous_snapshot_id=previous_snapshot_id,
                current_snapshot_id=Identifier.new(),
            ),
        )


def _analysis_result(
    *,
    previous_snapshot_id: Identifier | None = None,
    current_snapshot_id: Identifier | None = None,
    observations: tuple[Observation, ...] = (),
    findings: tuple[Finding, ...] = (),
) -> AnalysisResult:
    return AnalysisResult(
        diff=DiffResult(
            previous_snapshot_id=previous_snapshot_id or Identifier.new(),
            current_snapshot_id=current_snapshot_id or Identifier.new(),
        ),
        observations=observations,
        findings=findings,
    )


def _observation(
    observation_type: str,
    subject: str,
    *,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    message: str | None = None,
    timestamp: datetime = TIMESTAMP,
    metadata: dict[str, str] | None = None,
) -> Observation:
    return Observation(
        subject=subject,
        type=observation_type,
        message=message or f"Observation for {subject}",
        timestamp=timestamp,
        metadata=metadata,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )


def _unscoped_observation(observation_type: str, subject: str) -> Observation:
    return Observation(
        subject=subject,
        type=observation_type,
        message=f"Observation for {subject}",
        timestamp=TIMESTAMP,
    )


def _finding(
    finding_type: str,
    subject: str,
    *,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    source_observation_type: str = "resource_created",
    message: str | None = None,
    timestamp: datetime = TIMESTAMP,
    metadata: dict[str, str] | None = None,
) -> Finding:
    return Finding(
        subject=subject,
        type=finding_type,
        message=message or f"Finding for {subject}",
        timestamp=timestamp,
        source_observation_type=source_observation_type,
        metadata=metadata,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )


def _unscoped_finding(finding_type: str, subject: str) -> Finding:
    return Finding(
        subject=subject,
        type=finding_type,
        message=f"Finding for {subject}",
        timestamp=TIMESTAMP,
        source_observation_type="resource_created",
    )

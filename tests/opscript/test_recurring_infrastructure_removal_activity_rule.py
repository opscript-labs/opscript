from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation

from opscript.application.recurring_infrastructure_removal_activity_rule import (
    RecurringInfrastructureRemovalActivityRule,
)
from opscript.models import QualifiedHistoricalEvidence, RecognitionResult


def test_three_qualifying_removal_intervals_for_different_resources_are_supported():
    result = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                ("resource_removed",),
                ("other_resource_removed",),
                ("resource_created",),
                ("third_resource_removed",),
            )
        )
    )

    assert result.outcome == "supported"
    assert result.supported is True
    assert result.engineering_condition == "recurring_infrastructure_removal_activity"


def test_repeated_removal_of_same_resource_is_not_required():
    result = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                ("resource_removed",),
                ("other_resource_removed",),
                ("third_resource_removed",),
                ("resource_created",),
            )
        )
    )

    assert result.outcome == "supported"


@pytest.mark.parametrize(
    ("observation_types", "expected_outcome"),
    [
        (("resource_created",) * 4, "not_supported"),
        (
            (
                "resource_removed",
                "resource_created",
                "resource_modified",
                "resource_created",
            ),
            "not_supported",
        ),
        (
            (
                "resource_removed",
                "resource_created",
                "resource_removed",
                "resource_modified",
            ),
            "not_supported",
        ),
    ],
)
def test_zero_one_or_two_qualifying_removal_intervals_are_not_supported(
    observation_types: tuple[str, ...],
    expected_outcome: str,
):
    result = _rule().evaluate(_evidence(observation_types))

    assert result.outcome == expected_outcome
    assert result.supported is False
    assert result.engineering_condition == "recurring_infrastructure_removal_activity"


def test_four_completed_intervals_with_no_removals_are_admissible_but_not_supported():
    result = _rule().evaluate(_evidence(("resource_created",) * 4))

    assert result.outcome == "not_supported"
    assert result.supported is False


def test_duplicate_removals_inside_one_interval_count_once():
    result = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                ("resource_removed", "resource_removed"),
                ("resource_created",),
                ("resource_removed",),
                ("resource_removed",),
            )
        )
    )

    assert result.outcome == "supported"


def test_qualifying_removal_intervals_need_not_be_consecutive():
    result = _rule().evaluate(
        _evidence(
            (
                "resource_removed",
                "resource_created",
                "resource_removed",
                "resource_modified",
                "resource_removed",
            )
        )
    )

    assert result.outcome == "supported"


def test_zero_observation_intervals_are_non_qualifying_completed_intervals():
    result = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                (),
                ("resource_removed",),
                (),
                ("resource_removed",),
                ("resource_removed",),
            )
        )
    )

    assert result.outcome == "supported"


def test_created_observations_do_not_qualify():
    result = _rule().evaluate(
        _evidence(
            (
                "resource_removed",
                "resource_created",
                "resource_created",
                "resource_removed",
            )
        )
    )

    assert result.outcome == "not_supported"


def test_modified_observations_do_not_qualify():
    result = _rule().evaluate(
        _evidence(
            (
                "resource_removed",
                "resource_modified",
                "resource_modified",
                "resource_removed",
            )
        )
    )

    assert result.outcome == "not_supported"


def test_removals_for_different_subjects_contribute_to_scope_level_recognition():
    result = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                ("resource_removed",),
                ("other_resource_removed",),
                ("third_resource_removed",),
                ("resource_created",),
            )
        )
    )

    assert result.outcome == "supported"


def test_repeated_evaluation_of_equal_evidence_produces_equal_results():
    evidence = _evidence_from_observation_groups(
        (
            ("resource_removed",),
            ("other_resource_removed",),
            ("resource_created",),
            ("third_resource_removed",),
        )
    )

    assert _rule().evaluate(evidence) == _rule().evaluate(evidence)


@pytest.mark.parametrize("interval_count", (1, 2, 3))
def test_fewer_than_four_completed_intervals_raise_no_result(interval_count: int):
    with pytest.raises(ValueError, match="at least four completed intervals"):
        _rule().evaluate(_evidence(("resource_removed",) * interval_count))


def test_qualified_historical_evidence_is_not_modified():
    evidence = _evidence(("resource_removed",) * 4)
    intervals = evidence.completed_intervals

    _rule().evaluate(evidence)

    assert evidence.completed_intervals is intervals


def test_completed_comparison_intervals_are_not_modified():
    evidence = _evidence(("resource_removed",) * 4)
    interval = evidence.completed_intervals[0]
    observations = interval.observations

    _rule().evaluate(evidence)

    assert evidence.completed_intervals[0] is interval
    assert evidence.completed_intervals[0].observations is observations


def test_observations_are_not_modified():
    evidence = _evidence(("resource_removed",) * 4)
    observation = evidence.completed_intervals[0].observations[0]

    _rule().evaluate(evidence)

    assert evidence.completed_intervals[0].observations[0] is observation


def test_recognition_result_is_immutable():
    result = _rule().evaluate(_evidence(("resource_removed",) * 4))

    with pytest.raises(FrozenInstanceError):
        result.outcome = "not_supported"


def test_recognition_result_permits_approved_removal_condition():
    result = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=_evidence(("resource_removed",) * 4),
        engineering_condition="recurring_infrastructure_removal_activity",
    )

    assert result.engineering_condition == "recurring_infrastructure_removal_activity"


def _rule() -> RecurringInfrastructureRemovalActivityRule:
    return RecurringInfrastructureRemovalActivityRule()


def _evidence(
    observation_types: tuple[str, ...],
    *,
    canonical_subject: str | None = None,
) -> QualifiedHistoricalEvidence:
    return _evidence_from_observation_groups(
        tuple((observation_type,) for observation_type in observation_types),
        canonical_subject=canonical_subject,
    )


def _evidence_from_observation_groups(
    observation_groups: tuple[tuple[str, ...], ...],
    *,
    canonical_subject: str | None = None,
) -> QualifiedHistoricalEvidence:
    scope = DiscoveryScope("scope-001")
    snapshot_ids = tuple(Identifier.new() for _ in range(len(observation_groups) + 1))
    intervals = tuple(
        _interval(
            discovery_scope=scope,
            previous_snapshot_id=snapshot_ids[index],
            current_snapshot_id=snapshot_ids[index + 1],
            observation_types=observation_types,
        )
        for index, observation_types in enumerate(observation_groups)
    )
    return QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=snapshot_ids[0],
        observation_window_current_snapshot_id=snapshot_ids[-1],
        completed_intervals=intervals,
        canonical_subject=canonical_subject,
    )


def _interval(
    *,
    discovery_scope: DiscoveryScope,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    observation_types: tuple[str, ...],
) -> CompletedComparisonInterval:
    return CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=tuple(
            _observation(
                observation_type=observation_type,
                previous_snapshot_id=previous_snapshot_id,
                current_snapshot_id=current_snapshot_id,
            )
            for observation_type in observation_types
        ),
    )


def _observation(
    *,
    observation_type: str,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
) -> Observation:
    subject = "resource-001"
    normalized_type = observation_type
    if observation_type == "other_resource_removed":
        subject = "resource-002"
        normalized_type = "resource_removed"
    elif observation_type == "third_resource_removed":
        subject = "resource-003"
        normalized_type = "resource_removed"

    return Observation(
        subject=subject,
        type=normalized_type,
        message=f"{normalized_type}: {subject}",
        timestamp=datetime.now(UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation

from opscript.application.frequent_infrastructure_modification_rule import (
    FrequentInfrastructureModificationRule,
)
from opscript.models import QualifiedHistoricalEvidence, RecognitionResult


def test_recognition_result_is_immutable():
    result = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=_evidence(("resource_modified",) * 4),
    )

    with pytest.raises(FrozenInstanceError):
        result.outcome = "not_supported"


def test_recognition_result_permits_only_closed_outcomes():
    with pytest.raises(ValueError, match="supported or not_supported"):
        RecognitionResult(
            outcome="insufficient_evidence",  # type: ignore[arg-type]
            qualified_historical_evidence=_evidence(("resource_modified",) * 4),
        )


def test_supported_property_is_computed_from_outcome():
    supported = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=_evidence(("resource_modified",) * 4),
    )
    not_supported = RecognitionResult(
        outcome="not_supported",
        qualified_historical_evidence=_evidence(("resource_created",) * 4),
    )

    assert supported.supported is True
    assert not_supported.supported is False


def test_recognition_result_preserves_qualified_evidence_instance():
    evidence = _evidence(("resource_modified",) * 4)

    result = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=evidence,
    )

    assert result.qualified_historical_evidence is evidence


def test_recognition_result_exposes_fixed_condition_and_calibration():
    result = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=_evidence(("resource_modified",) * 4),
    )

    assert result.engineering_condition == "frequent_infrastructure_modification"
    assert result.recognition_threshold == 3
    assert result.minimum_completed_interval_count == 4


def test_recognition_result_has_no_insufficient_evidence_state():
    result = RecognitionResult(
        outcome="not_supported",
        qualified_historical_evidence=_evidence(("resource_created",) * 4),
    )

    assert result.outcome in {"supported", "not_supported"}
    assert result.outcome != "insufficient_evidence"


def test_recognition_result_has_no_finding_or_workflow_fields():
    result = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=_evidence(("resource_modified",) * 4),
    )

    assert not hasattr(result, "finding")
    assert not hasattr(result, "severity")
    assert not hasattr(result, "confidence")
    assert not hasattr(result, "recommendation")
    assert not hasattr(result, "workflow_state")


def test_three_qualifying_intervals_across_four_completed_intervals_are_supported():
    result = _rule().evaluate(
        _evidence(
            (
                "resource_modified",
                "resource_modified",
                "resource_modified",
                "resource_created",
            )
        )
    )

    assert result.outcome == "supported"
    assert result.supported is True


def test_four_qualifying_intervals_are_supported():
    result = _rule().evaluate(_evidence(("resource_modified",) * 4))

    assert result.outcome == "supported"


def test_qualifying_intervals_need_not_be_consecutive():
    result = _rule().evaluate(
        _evidence(
            (
                "resource_modified",
                "resource_created",
                "resource_modified",
                "resource_deleted",
                "resource_modified",
            )
        )
    )

    assert result.outcome == "supported"


def test_multiple_matching_modification_observations_in_one_interval_count_once():
    result = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                ("resource_modified", "resource_modified"),
                ("resource_created",),
                ("resource_modified",),
                ("resource_modified",),
            )
        )
    )

    assert result.outcome == "supported"


def test_observation_ordering_inside_interval_does_not_change_result():
    first = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                ("resource_created", "resource_modified"),
                ("resource_modified",),
                ("resource_deleted", "resource_modified"),
                ("resource_created",),
            )
        )
    )
    second = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                ("resource_modified", "resource_created"),
                ("resource_modified",),
                ("resource_modified", "resource_deleted"),
                ("resource_created",),
            )
        )
    )

    assert first.outcome == second.outcome == "supported"


@pytest.mark.parametrize(
    ("types", "expected_outcome"),
    [
        (("resource_created",) * 4, "not_supported"),
        (
            (
                "resource_modified",
                "resource_created",
                "resource_created",
                "resource_deleted",
            ),
            "not_supported",
        ),
        (
            (
                "resource_modified",
                "resource_modified",
                "resource_created",
                "resource_deleted",
            ),
            "not_supported",
        ),
    ],
)
def test_zero_one_or_two_qualifying_intervals_are_not_supported(
    types: tuple[str, ...],
    expected_outcome: str,
):
    result = _rule().evaluate(_evidence(types))

    assert result.outcome == expected_outcome
    assert result.supported is False


def test_created_and_deleted_observations_do_not_qualify():
    result = _rule().evaluate(
        _evidence(
            (
                "resource_created",
                "resource_deleted",
                "resource_created",
                "resource_deleted",
            )
        )
    )

    assert result.outcome == "not_supported"


def test_modifications_for_another_subject_do_not_qualify():
    result = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                ("other_resource_modified",),
                ("other_resource_modified",),
                ("other_resource_modified",),
                ("resource_created",),
            )
        )
    )

    assert result.outcome == "not_supported"


def test_zero_observation_intervals_are_non_qualifying_completed_intervals():
    result = _rule().evaluate(
        _evidence_from_observation_groups(
            (
                (),
                ("resource_modified",),
                (),
                ("resource_modified",),
                ("resource_modified",),
            )
        )
    )

    assert result.outcome == "supported"


@pytest.mark.parametrize("interval_count", (1, 2, 3))
def test_fewer_than_four_completed_intervals_raises_no_result(interval_count: int):
    with pytest.raises(ValueError, match="at least four completed intervals"):
        _rule().evaluate(_evidence(("resource_modified",) * interval_count))


def test_missing_canonical_subject_raises_no_result():
    with pytest.raises(ValueError, match="requires a subject"):
        _rule().evaluate(_evidence(("resource_modified",) * 4, canonical_subject=None))


def test_repeated_evaluation_of_equal_evidence_produces_equal_results():
    evidence = _evidence(("resource_modified",) * 4)
    rule = _rule()

    assert rule.evaluate(evidence) == rule.evaluate(evidence)


def test_qualified_historical_evidence_remains_unchanged():
    evidence = _evidence(("resource_modified",) * 4)
    original_intervals = evidence.completed_intervals

    _rule().evaluate(evidence)

    assert evidence.completed_intervals == original_intervals


def test_completed_intervals_remain_unchanged():
    evidence = _evidence(("resource_modified",) * 4)
    interval = evidence.completed_intervals[0]
    original_observations = interval.observations

    _rule().evaluate(evidence)

    assert interval.observations == original_observations


def test_observations_remain_unchanged():
    evidence = _evidence(("resource_modified",) * 4)
    observation = evidence.completed_intervals[0].observations[0]
    original_type = observation.type
    original_subject = observation.subject

    _rule().evaluate(evidence)

    assert observation.type == original_type
    assert observation.subject == original_subject


def test_tuple_populations_remain_unchanged():
    evidence = _evidence(("resource_modified",) * 4)
    intervals = evidence.completed_intervals
    observations = evidence.completed_intervals[0].observations

    _rule().evaluate(evidence)

    assert evidence.completed_intervals is intervals
    assert evidence.completed_intervals[0].observations is observations


def _rule() -> FrequentInfrastructureModificationRule:
    return FrequentInfrastructureModificationRule()


def _evidence(
    observation_types: tuple[str, ...],
    *,
    canonical_subject: str | None = "resource-001",
) -> QualifiedHistoricalEvidence:
    return _evidence_from_observation_groups(
        tuple((observation_type,) for observation_type in observation_types),
        canonical_subject=canonical_subject,
    )


def _evidence_from_observation_groups(
    observation_groups: tuple[tuple[str, ...], ...],
    *,
    canonical_subject: str | None = "resource-001",
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
    if observation_type == "other_resource_modified":
        subject = "resource-002"
        normalized_type = "resource_modified"

    return Observation(
        subject=subject,
        type=normalized_type,
        message=f"{normalized_type}: {subject}",
        timestamp=datetime.now(UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

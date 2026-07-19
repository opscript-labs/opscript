from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation

from opscript.application.engineering_condition_evaluation import (
    EngineeringConditionComparisonEligibility,
    EngineeringConditionSupportDistributionComparison,
    ExcludedEngineeringConditionEvaluation,
    compare_engineering_condition_support_distribution,
)
from opscript.models import (
    QualifiedHistoricalEvidence,
    RecognitionResult,
    ScopeLocalEngineeringConditionEvaluation,
)


ENGINEERING_CONDITION = (
    RecognitionResult.recurring_infrastructure_removal_activity_condition
)


def test_result_is_immutable():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    with pytest.raises(FrozenInstanceError):
        comparison.classification = "SUPPORTED_IN_NO_SCOPES"


def test_equivalent_semantic_contents_compare_equal():
    eligibility = _eligibility(
        _evaluation("scope-a", "supported"),
        _evaluation("scope-b", "not_supported"),
    )

    assert _compare(eligibility) == _compare(eligibility)


def test_result_contains_selected_engineering_condition():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert comparison.engineering_condition == ENGINEERING_CONDITION


def test_result_preserves_eligible_and_excluded_evaluations():
    eligible = _evaluation("scope-a", "supported")
    excluded_evaluation = _other_condition_evaluation("scope-b")
    excluded = ExcludedEngineeringConditionEvaluation(
        evaluation=excluded_evaluation,
        reason="engineering_condition_mismatch",
    )

    comparison = _compare(
        _eligibility(
            eligible, _evaluation("scope-c", "supported"), excluded=(excluded,)
        )
    )

    assert comparison.eligible_evaluations[0] is eligible
    assert comparison.excluded_evaluations == (excluded,)


def test_result_has_no_speculative_fields():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    for field_name in (
        "score",
        "rank",
        "health",
        "risk",
        "confidence",
        "timestamp",
        "id",
        "execution_id",
    ):
        assert not hasattr(comparison, field_name)


def test_two_supported_evaluations_are_supported_in_all_scopes():
    scope_a = _evaluation("scope-a", "supported")
    scope_b = _evaluation("scope-b", "supported")

    comparison = _compare(_eligibility(scope_a, scope_b))

    assert comparison.classification == "SUPPORTED_IN_ALL_SCOPES"
    assert comparison.supported_evaluations == (scope_a, scope_b)
    assert comparison.not_supported_evaluations == ()


def test_three_supported_evaluations_are_supported_in_all_scopes():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
            _evaluation("scope-c", "supported"),
        )
    )

    assert comparison.classification == "SUPPORTED_IN_ALL_SCOPES"


def test_mixed_evaluations_are_supported_in_some_scopes():
    supported = _evaluation("scope-a", "supported")
    not_supported = _evaluation("scope-b", "not_supported")

    comparison = _compare(_eligibility(supported, not_supported))

    assert comparison.classification == "SUPPORTED_IN_SOME_SCOPES"
    assert comparison.supported_evaluations == (supported,)
    assert comparison.not_supported_evaluations == (not_supported,)


def test_multiple_mixed_evaluations_are_supported_in_some_scopes():
    supported_a = _evaluation("scope-a", "supported")
    not_supported_a = _evaluation("scope-b", "not_supported")
    supported_b = _evaluation("scope-c", "supported")
    not_supported_b = _evaluation("scope-d", "not_supported")

    comparison = _compare(
        _eligibility(
            supported_a,
            not_supported_a,
            supported_b,
            not_supported_b,
        )
    )

    assert comparison.classification == "SUPPORTED_IN_SOME_SCOPES"
    assert comparison.supported_evaluations == (supported_a, supported_b)
    assert comparison.not_supported_evaluations == (
        not_supported_a,
        not_supported_b,
    )


def test_two_not_supported_evaluations_are_supported_in_no_scopes():
    scope_a = _evaluation("scope-a", "not_supported")
    scope_b = _evaluation("scope-b", "not_supported")

    comparison = _compare(_eligibility(scope_a, scope_b))

    assert comparison.classification == "SUPPORTED_IN_NO_SCOPES"
    assert comparison.supported_evaluations == ()
    assert comparison.not_supported_evaluations == (scope_a, scope_b)


def test_three_not_supported_evaluations_are_supported_in_no_scopes():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "not_supported"),
            _evaluation("scope-b", "not_supported"),
            _evaluation("scope-c", "not_supported"),
        )
    )

    assert comparison.classification == "SUPPORTED_IN_NO_SCOPES"


def test_zero_eligible_evaluations_are_rejected():
    with pytest.raises(ValueError, match="At least two eligible evaluations"):
        _compare(EngineeringConditionComparisonEligibility())


def test_one_eligible_evaluation_is_rejected():
    with pytest.raises(ValueError, match="At least two eligible evaluations"):
        _compare(_eligibility(_evaluation("scope-a", "supported")))


def test_excluded_evaluations_do_not_satisfy_minimum():
    excluded = ExcludedEngineeringConditionEvaluation(
        evaluation=_other_condition_evaluation("scope-b"),
        reason="engineering_condition_mismatch",
    )

    with pytest.raises(ValueError, match="At least two eligible evaluations"):
        _compare(
            _eligibility(_evaluation("scope-a", "supported"), excluded=(excluded,))
        )


def test_two_eligible_evaluations_plus_exclusions_compare_successfully():
    excluded = ExcludedEngineeringConditionEvaluation(
        evaluation=_other_condition_evaluation("scope-c"),
        reason="engineering_condition_mismatch",
    )

    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
            excluded=(excluded,),
        )
    )

    assert comparison.classification == "SUPPORTED_IN_SOME_SCOPES"
    assert comparison.excluded_evaluations == (excluded,)


def test_eligible_equals_supported_plus_not_supported():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
            _evaluation("scope-c", "supported"),
        )
    )

    partition = comparison.supported_evaluations + comparison.not_supported_evaluations

    assert {id(evaluation) for evaluation in comparison.eligible_evaluations} == {
        id(evaluation) for evaluation in partition
    }


def test_no_overlap_between_support_state_subgroups():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
        )
    )

    supported_ids = {id(evaluation) for evaluation in comparison.supported_evaluations}
    not_supported_ids = {
        id(evaluation) for evaluation in comparison.not_supported_evaluations
    }
    assert supported_ids.isdisjoint(not_supported_ids)


def test_no_eligible_evaluation_is_omitted_or_duplicated():
    scope_a = _evaluation("scope-a", "supported")
    scope_b = _evaluation("scope-b", "not_supported")
    comparison = _compare(_eligibility(scope_a, scope_b))

    partition = comparison.supported_evaluations + comparison.not_supported_evaluations

    assert set(id(evaluation) for evaluation in partition) == {
        id(scope_a),
        id(scope_b),
    }
    assert len(partition) == len(set(id(evaluation) for evaluation in partition))


def test_excluded_evaluations_never_enter_support_state_subgroups():
    excluded = ExcludedEngineeringConditionEvaluation(
        evaluation=_other_condition_evaluation("scope-c"),
        reason="engineering_condition_mismatch",
    )

    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
            excluded=(excluded,),
        )
    )

    support_state_ids = {
        id(evaluation)
        for evaluation in (
            comparison.supported_evaluations + comparison.not_supported_evaluations
        )
    }
    assert id(excluded.evaluation) not in support_state_ids


def test_repeated_comparison_returns_equal_results():
    eligibility = _eligibility(
        _evaluation("scope-a", "supported"),
        _evaluation("scope-b", "not_supported"),
    )

    assert _compare(eligibility) == _compare(eligibility)


def test_permuting_eligible_evaluations_does_not_change_classification():
    scope_a = _evaluation("scope-a", "supported")
    scope_b = _evaluation("scope-b", "not_supported")

    assert _compare(_eligibility(scope_a, scope_b)).classification == (
        _compare(_eligibility(scope_b, scope_a)).classification
    )


def test_permuting_eligible_evaluations_changes_only_preserved_order():
    scope_a = _evaluation("scope-a", "supported")
    scope_b = _evaluation("scope-b", "not_supported")

    first = _compare(_eligibility(scope_a, scope_b))
    second = _compare(_eligibility(scope_b, scope_a))

    assert first.classification == second.classification
    assert first.eligible_evaluations == (scope_a, scope_b)
    assert second.eligible_evaluations == (scope_b, scope_a)
    assert set(first.supported_evaluations) == set(second.supported_evaluations)
    assert set(first.not_supported_evaluations) == set(second.not_supported_evaluations)


def test_requested_and_excluded_order_do_not_affect_classification():
    first_excluded = ExcludedEngineeringConditionEvaluation(
        evaluation=_other_condition_evaluation("scope-x"),
        reason="engineering_condition_mismatch",
    )
    second_excluded = ExcludedEngineeringConditionEvaluation(
        evaluation=_other_condition_evaluation("scope-y"),
        reason="engineering_condition_mismatch",
    )
    eligible = (
        _evaluation("scope-a", "supported"),
        _evaluation("scope-b", "not_supported"),
    )

    first = _compare(
        _eligibility(*eligible, excluded=(first_excluded, second_excluded))
    )
    second = _compare(
        _eligibility(*eligible, excluded=(second_excluded, first_excluded))
    )

    assert first.classification == second.classification


def test_invalid_classification_is_rejected():
    scope_a = _evaluation("scope-a", "supported")
    scope_b = _evaluation("scope-b", "supported")

    with pytest.raises(ValueError, match="classification"):
        EngineeringConditionSupportDistributionComparison(
            engineering_condition=ENGINEERING_CONDITION,
            eligible_evaluations=(scope_a, scope_b),
            supported_evaluations=(scope_a, scope_b),
            classification="SUPPORTED_GAINED",
        )


def test_inconsistent_eligible_engineering_conditions_are_rejected():
    with pytest.raises(ValueError, match="one Engineering Condition"):
        _compare(
            EngineeringConditionComparisonEligibility(
                eligible_evaluations=(
                    _evaluation("scope-a", "supported"),
                    _other_condition_evaluation("scope-b"),
                ),
            )
        )


def test_service_does_not_rerun_recognition_or_reassess_compatibility():
    source_names = compare_engineering_condition_support_distribution.__code__.co_names

    assert "FrequentInfrastructureModificationRule" not in source_names
    assert "RecurringInfrastructureRemovalActivityRule" not in source_names
    assert "RecurringInfrastructureIntroductionActivityRule" not in source_names
    assert "assess_engineering_condition_comparison_eligibility" not in source_names


def test_service_does_not_create_findings_or_public_output():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert not hasattr(comparison, "findings")
    assert not hasattr(comparison, "report")
    assert not hasattr(comparison, "json")


def test_service_does_not_merge_evidence_or_infer_chronology():
    scope_a = _evaluation("scope-a", "supported")
    scope_b = _evaluation("scope-b", "supported")

    comparison = _compare(_eligibility(scope_a, scope_b))

    assert comparison.eligible_evaluations[0].qualified_historical_evidence is (
        scope_a.qualified_historical_evidence
    )
    assert comparison.eligible_evaluations[1].qualified_historical_evidence is (
        scope_b.qualified_historical_evidence
    )
    assert (
        scope_a.qualified_historical_evidence.observation_window_previous_snapshot_id
        != scope_b.qualified_historical_evidence.observation_window_previous_snapshot_id
    )


def test_service_does_not_infer_global_resource_identity():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert not hasattr(comparison, "global_subject")
    assert not hasattr(comparison, "global_resource_identity")


def test_service_performs_no_io_aws_storage_workflow_or_telemetry():
    source_names = compare_engineering_condition_support_distribution.__code__.co_names

    assert "open" not in source_names
    assert "boto3" not in source_names
    assert "load_history" not in source_names
    assert "load_latest" not in source_names
    assert "save" not in source_names
    assert "format_log_event" not in source_names


def test_no_unavailable_or_temporal_classification_exists():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
        )
    )

    assert comparison.classification in {
        "SUPPORTED_IN_ALL_SCOPES",
        "SUPPORTED_IN_SOME_SCOPES",
        "SUPPORTED_IN_NO_SCOPES",
    }
    assert comparison.classification != "COMPARISON_UNAVAILABLE"
    assert not hasattr(comparison, "supported_gained")
    assert not hasattr(comparison, "supported_lost")
    assert not hasattr(comparison, "unchanged")


def test_platformiq_remains_uninvolved():
    comparison = _compare(
        _eligibility(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert comparison.__class__.__module__.startswith("opscript.")


def _compare(
    eligibility: EngineeringConditionComparisonEligibility,
) -> EngineeringConditionSupportDistributionComparison:
    return compare_engineering_condition_support_distribution(eligibility)


def _eligibility(
    *eligible_evaluations: ScopeLocalEngineeringConditionEvaluation,
    excluded: tuple[ExcludedEngineeringConditionEvaluation, ...] = (),
) -> EngineeringConditionComparisonEligibility:
    return EngineeringConditionComparisonEligibility(
        requested_evaluations=tuple(eligible_evaluations)
        + tuple(exclusion.evaluation for exclusion in excluded),
        eligible_evaluations=eligible_evaluations,
        excluded_evaluations=excluded,
    )


def _evaluation(
    scope_value: str,
    outcome: str,
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome=outcome,
        qualified_historical_evidence=_qualified_evidence(
            DiscoveryScope(scope_value),
            "resource_removed" if outcome == "supported" else "resource_created",
        ),
        engineering_condition=ENGINEERING_CONDITION,
    )


def _other_condition_evaluation(
    scope_value: str,
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome="supported",
        qualified_historical_evidence=_qualified_evidence(
            DiscoveryScope(scope_value),
            "resource_created",
        ),
        engineering_condition=(
            RecognitionResult.recurring_infrastructure_introduction_activity_condition
        ),
    )


def _qualified_evidence(
    scope: DiscoveryScope,
    observation_type: str,
) -> QualifiedHistoricalEvidence:
    snapshot_ids = tuple(Identifier.new() for _ in range(5))
    intervals = tuple(
        CompletedComparisonInterval(
            discovery_scope=scope,
            previous_snapshot_id=snapshot_ids[index],
            current_snapshot_id=snapshot_ids[index + 1],
            observations=(
                Observation(
                    subject=f"{scope.value}-{index}",
                    type=observation_type,
                    message=f"{observation_type}: {scope.value}",
                    timestamp=datetime.now(UTC),
                    previous_snapshot_id=snapshot_ids[index],
                    current_snapshot_id=snapshot_ids[index + 1],
                ),
            ),
        )
        for index in range(4)
    )
    return QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=snapshot_ids[0],
        observation_window_current_snapshot_id=snapshot_ids[-1],
        completed_intervals=intervals,
        canonical_subject=None,
    )

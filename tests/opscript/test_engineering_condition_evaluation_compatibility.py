from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation

from opscript.application.engineering_condition_evaluation import (
    EngineeringConditionComparisonEligibility,
    ExcludedEngineeringConditionEvaluation,
    assess_engineering_condition_comparison_eligibility,
)
from opscript.models import (
    QualifiedHistoricalEvidence,
    RecognitionResult,
    ScopeLocalEngineeringConditionEvaluation,
)


SCOPE_LEVEL_CONDITION = (
    RecognitionResult.recurring_infrastructure_removal_activity_condition
)
RESOURCE_LEVEL_CONDITION = (
    RecognitionResult.frequent_infrastructure_modification_condition
)
OTHER_SCOPE_LEVEL_CONDITION = (
    RecognitionResult.recurring_infrastructure_introduction_activity_condition
)


def test_eligibility_result_is_immutable():
    result = _assess((_scope_level_evaluation("scope-a", "supported"),))

    with pytest.raises(FrozenInstanceError):
        result.eligible_evaluations = ()


def test_equivalent_inputs_produce_equal_results():
    evaluation = _scope_level_evaluation("scope-a", "supported")

    assert _assess((evaluation,)) == _assess((evaluation,))


def test_requested_order_is_preserved():
    scope_a = _scope_level_evaluation("scope-a", "supported")
    scope_b = _scope_level_evaluation("scope-b", "not_supported")
    resource_level = _resource_level_evaluation("scope-c", "resource-001")

    result = _assess((resource_level, scope_b, scope_a))

    assert result.requested_evaluations == (resource_level, scope_b, scope_a)


def test_eligible_order_follows_requested_order():
    scope_a = _scope_level_evaluation("scope-a", "supported")
    scope_b = _scope_level_evaluation("scope-b", "not_supported")

    result = _assess((scope_b, scope_a))

    assert result.eligible_evaluations == (scope_b, scope_a)


def test_excluded_order_follows_requested_order():
    mismatch = _scope_level_evaluation(
        "scope-a",
        "supported",
        engineering_condition=OTHER_SCOPE_LEVEL_CONDITION,
    )
    resource_level = _resource_level_evaluation("scope-b", "resource-001")

    result = _assess((resource_level, mismatch))

    assert tuple(excluded.evaluation for excluded in result.excluded_evaluations) == (
        resource_level,
        mismatch,
    )


def test_no_candidate_is_omitted_or_duplicated():
    eligible = _scope_level_evaluation("scope-a", "supported")
    excluded = _resource_level_evaluation("scope-b", "resource-001")

    result = _assess((eligible, excluded))

    partition = result.eligible_evaluations + tuple(
        item.evaluation for item in result.excluded_evaluations
    )
    assert partition == result.requested_evaluations
    assert len(partition) == len(set(id(evaluation) for evaluation in partition))


def test_candidate_never_appears_in_both_populations():
    eligible = _scope_level_evaluation("scope-a", "supported")
    excluded = _resource_level_evaluation("scope-b", "resource-001")

    result = _assess((eligible, excluded))

    eligible_ids = {id(evaluation) for evaluation in result.eligible_evaluations}
    excluded_ids = {id(excluded.evaluation) for excluded in result.excluded_evaluations}
    assert eligible_ids.isdisjoint(excluded_ids)


def test_selected_scope_level_condition_evaluations_are_eligible():
    supported = _scope_level_evaluation("scope-a", "supported")
    not_supported = _scope_level_evaluation("scope-b", "not_supported")

    result = _assess((supported, not_supported))

    assert result.eligible_evaluations == (supported, not_supported)
    assert result.excluded_evaluations == ()


def test_condition_mismatch_is_excluded_deterministically():
    mismatch = _scope_level_evaluation(
        "scope-a",
        "supported",
        engineering_condition=OTHER_SCOPE_LEVEL_CONDITION,
    )

    result = _assess((mismatch,))

    assert result.eligible_evaluations == ()
    assert result.excluded_evaluations == (
        ExcludedEngineeringConditionEvaluation(
            evaluation=mismatch,
            reason="engineering_condition_mismatch",
        ),
    )


def test_condition_identity_is_not_normalized_or_aliased():
    evaluation = _scope_level_evaluation("scope-a", "supported")

    with pytest.raises(ValueError, match="Engineering condition"):
        assess_engineering_condition_comparison_eligibility(
            (evaluation,),
            engineering_condition=SCOPE_LEVEL_CONDITION.upper(),
        )


def test_supported_evaluation_may_be_eligible():
    evaluation = _scope_level_evaluation("scope-a", "supported")

    result = _assess((evaluation,))

    assert result.eligible_evaluations == (evaluation,)


def test_not_supported_evaluation_may_be_eligible():
    evaluation = _scope_level_evaluation("scope-a", "not_supported")

    result = _assess((evaluation,))

    assert result.eligible_evaluations == (evaluation,)


def test_outcome_does_not_affect_compatibility():
    supported = _scope_level_evaluation("scope-a", "supported")
    not_supported = _scope_level_evaluation("scope-b", "not_supported")

    result = _assess((not_supported, supported))

    assert result.eligible_evaluations == (not_supported, supported)


def test_exclusion_does_not_alter_original_outcome():
    evaluation = _resource_level_evaluation(
        "scope-a",
        "resource-001",
        outcome="not_supported",
    )

    result = _assess_resource_level((evaluation,))

    assert result.excluded_evaluations[0].evaluation.outcome == "not_supported"


def test_discovery_scope_level_conditions_are_eligible():
    removal = _scope_level_evaluation(
        "scope-a",
        "supported",
        engineering_condition=SCOPE_LEVEL_CONDITION,
    )

    result = _assess((removal,))

    assert result.eligible_evaluations == (removal,)


def test_resource_level_evaluations_are_excluded_without_subject_equivalence():
    evaluation = _resource_level_evaluation("scope-a", "resource-001")

    result = _assess_resource_level((evaluation,))

    assert result.excluded_evaluations[0].reason == "unsupported_subject_comparison"


def test_matching_resource_identifiers_do_not_create_equivalence():
    scope_a = _resource_level_evaluation("scope-a", "resource-001")
    scope_b = _resource_level_evaluation("scope-b", "resource-001")

    result = _assess_resource_level((scope_a, scope_b))

    assert result.eligible_evaluations == ()
    assert tuple(excluded.reason for excluded in result.excluded_evaluations) == (
        "unsupported_subject_comparison",
        "unsupported_subject_comparison",
    )


def test_matching_canonical_subjects_do_not_create_global_identity():
    scope_a = _resource_level_evaluation("scope-a", "shared-resource")
    scope_b = _resource_level_evaluation("scope-b", "shared-resource")

    result = _assess_resource_level((scope_a, scope_b))

    assert result.eligible_evaluations == ()


def test_qualified_evidence_references_are_preserved():
    evaluation = _scope_level_evaluation("scope-a", "supported")
    evidence = evaluation.qualified_historical_evidence

    result = _assess((evaluation,))

    assert result.eligible_evaluations[0].qualified_historical_evidence is evidence


def test_evidence_is_not_copied():
    evaluation = _scope_level_evaluation("scope-a", "supported")

    result = _assess((evaluation,))

    assert result.eligible_evaluations[0] is evaluation


def test_histories_are_not_merged():
    scope_a = _scope_level_evaluation("scope-a", "supported")
    scope_b = _scope_level_evaluation("scope-b", "supported")

    result = _assess((scope_a, scope_b))

    assert result.eligible_evaluations[0].qualified_historical_evidence is (
        scope_a.qualified_historical_evidence
    )
    assert result.eligible_evaluations[1].qualified_historical_evidence is (
        scope_b.qualified_historical_evidence
    )


def test_shared_chronology_is_not_required_or_inferred():
    scope_a = _scope_level_evaluation("scope-a", "supported")
    scope_b = _scope_level_evaluation("scope-b", "supported")

    result = _assess((scope_a, scope_b))

    assert (
        scope_a.qualified_historical_evidence.observation_window_previous_snapshot_id
        != (
            scope_b.qualified_historical_evidence.observation_window_previous_snapshot_id
        )
    )
    assert result.eligible_evaluations == (scope_a, scope_b)


def test_different_snapshot_ids_do_not_cause_exclusion():
    scope_a = _scope_level_evaluation("scope-a", "supported")
    scope_b = _scope_level_evaluation("scope-b", "not_supported")

    result = _assess((scope_a, scope_b))

    assert result.excluded_evaluations == ()


def test_compatibility_does_not_rerun_recognition():
    source_names = assess_engineering_condition_comparison_eligibility.__code__.co_names

    assert "FrequentInfrastructureModificationRule" not in source_names
    assert "RecurringInfrastructureRemovalActivityRule" not in source_names
    assert "RecurringInfrastructureIntroductionActivityRule" not in source_names


def test_compatibility_does_not_create_findings():
    result = _assess((_scope_level_evaluation("scope-a", "supported"),))

    assert not hasattr(result, "findings")


def test_compatibility_does_not_produce_support_distribution_classification():
    result = _assess((_scope_level_evaluation("scope-a", "supported"),))

    assert not hasattr(result, "classification")
    assert not hasattr(result, "supported_in_all_scopes")
    assert not hasattr(result, "supported_in_some_scopes")
    assert not hasattr(result, "supported_in_no_scopes")


def test_no_io_aws_storage_workflow_or_telemetry_is_used():
    source_names = assess_engineering_condition_comparison_eligibility.__code__.co_names

    assert "open" not in source_names
    assert "load_history" not in source_names
    assert "load_latest" not in source_names
    assert "save" not in source_names
    assert "boto3" not in source_names
    assert "format_log_event" not in source_names


def test_platformiq_remains_uninvolved():
    result = _assess((_scope_level_evaluation("scope-a", "supported"),))

    assert result.__class__.__module__.startswith("opscript.")


def test_result_may_contain_two_or_more_eligible_evaluations():
    scope_a = _scope_level_evaluation("scope-a", "supported")
    scope_b = _scope_level_evaluation("scope-b", "not_supported")

    result = _assess((scope_a, scope_b))

    assert len(result.eligible_evaluations) == 2


def test_result_may_contain_fewer_than_two_eligible_without_unavailable_state():
    resource_level = _resource_level_evaluation("scope-a", "resource-001")

    result = _assess((resource_level,))

    assert result.eligible_evaluations == ()
    assert not hasattr(result, "unavailable")
    assert not hasattr(result, "comparison_status")


def test_result_preserves_information_for_later_orchestration():
    eligible = _scope_level_evaluation("scope-a", "supported")
    excluded = _scope_level_evaluation(
        "scope-b",
        "supported",
        engineering_condition=OTHER_SCOPE_LEVEL_CONDITION,
    )

    result = _assess((eligible, excluded))

    assert result.requested_evaluations == (eligible, excluded)
    assert result.eligible_evaluations == (eligible,)
    assert result.excluded_evaluations[0].evaluation is excluded
    assert result.excluded_evaluations[0].reason == "engineering_condition_mismatch"


def test_result_rejects_invalid_exclusion_reason():
    evaluation = _scope_level_evaluation("scope-a", "supported")

    with pytest.raises(ValueError, match="Exclusion reason"):
        ExcludedEngineeringConditionEvaluation(
            evaluation=evaluation,
            reason="unknown",
        )


def test_assessment_rejects_non_evaluation_inputs():
    with pytest.raises(TypeError, match="ScopeLocalEngineeringConditionEvaluation"):
        assess_engineering_condition_comparison_eligibility(
            ("not-an-evaluation",),
            engineering_condition=SCOPE_LEVEL_CONDITION,
        )


def _assess(
    evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...],
) -> EngineeringConditionComparisonEligibility:
    return assess_engineering_condition_comparison_eligibility(
        evaluations,
        engineering_condition=SCOPE_LEVEL_CONDITION,
    )


def _assess_resource_level(
    evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...],
) -> EngineeringConditionComparisonEligibility:
    return assess_engineering_condition_comparison_eligibility(
        evaluations,
        engineering_condition=RESOURCE_LEVEL_CONDITION,
    )


def _scope_level_evaluation(
    scope_value: str,
    outcome: str,
    *,
    engineering_condition: str = SCOPE_LEVEL_CONDITION,
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome=outcome,
        qualified_historical_evidence=_qualified_evidence(
            DiscoveryScope(scope_value),
            ("resource_removed",) * 4
            if outcome == "supported"
            else ("resource_created",) * 4,
            canonical_subject=None,
        ),
        engineering_condition=engineering_condition,
    )


def _resource_level_evaluation(
    scope_value: str,
    canonical_subject: str,
    *,
    outcome: str = "supported",
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome=outcome,
        qualified_historical_evidence=_qualified_evidence(
            DiscoveryScope(scope_value),
            ("resource_modified",) * 4
            if outcome == "supported"
            else ("resource_created",) * 4,
            canonical_subject=canonical_subject,
        ),
        engineering_condition=RESOURCE_LEVEL_CONDITION,
    )


def _qualified_evidence(
    scope: DiscoveryScope,
    observation_types: tuple[str, ...],
    *,
    canonical_subject: str | None,
) -> QualifiedHistoricalEvidence:
    snapshot_ids = tuple(Identifier.new() for _ in range(len(observation_types) + 1))
    intervals = tuple(
        CompletedComparisonInterval(
            discovery_scope=scope,
            previous_snapshot_id=snapshot_ids[index],
            current_snapshot_id=snapshot_ids[index + 1],
            observations=(
                _observation(
                    observation_type=observation_type,
                    previous_snapshot_id=snapshot_ids[index],
                    current_snapshot_id=snapshot_ids[index + 1],
                    subject=canonical_subject or f"scope-{index}",
                ),
            ),
        )
        for index, observation_type in enumerate(observation_types)
    )
    return QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=snapshot_ids[0],
        observation_window_current_snapshot_id=snapshot_ids[-1],
        completed_intervals=intervals,
        canonical_subject=canonical_subject,
    )


def _observation(
    *,
    observation_type: str,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    subject: str,
) -> Observation:
    return Observation(
        subject=subject,
        type=observation_type,
        message=f"{observation_type}: {subject}",
        timestamp=datetime.now(UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

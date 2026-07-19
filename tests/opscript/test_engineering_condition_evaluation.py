from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation

from opscript.application.engineering_condition_evaluation import (
    collect_scope_local_engineering_condition_evaluations,
    engineering_condition_evaluation_from_recognition_result,
)
from opscript.application.frequent_infrastructure_modification_rule import (
    FrequentInfrastructureModificationRule,
)
from opscript.application.recognized_finding_projection import (
    recognized_finding_from_recognition,
)
from opscript.models import (
    QualifiedHistoricalEvidence,
    RecognitionResult,
    ScopeLocalEngineeringConditionEvaluation,
)


def test_evaluation_is_immutable():
    evaluation = _evaluation("supported")

    with pytest.raises(FrozenInstanceError):
        evaluation.outcome = "not_supported"


def test_equivalent_values_compare_deterministically():
    recognition_result = _recognition_result("supported")

    first = ScopeLocalEngineeringConditionEvaluation(
        outcome="supported",
        qualified_historical_evidence=recognition_result.qualified_historical_evidence,
        engineering_condition=recognition_result.engineering_condition,
    )
    second = ScopeLocalEngineeringConditionEvaluation(
        outcome="supported",
        qualified_historical_evidence=recognition_result.qualified_historical_evidence,
        engineering_condition=recognition_result.engineering_condition,
    )

    assert first == second


def test_supported_is_accepted():
    evaluation = _evaluation("supported")

    assert evaluation.outcome == "supported"
    assert evaluation.supported is True


def test_not_supported_is_accepted():
    evaluation = _evaluation("not_supported")

    assert evaluation.outcome == "not_supported"
    assert evaluation.supported is False


def test_other_outcome_is_rejected():
    recognition_result = _recognition_result("supported")

    with pytest.raises(ValueError, match="supported or not_supported"):
        ScopeLocalEngineeringConditionEvaluation(
            outcome="unknown",
            qualified_historical_evidence=(
                recognition_result.qualified_historical_evidence
            ),
            engineering_condition=recognition_result.engineering_condition,
        )


def test_engineering_condition_identity_is_preserved():
    recognition_result = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=_qualified_evidence(
            ("resource_removed",) * 4,
            canonical_subject=None,
        ),
        engineering_condition="recurring_infrastructure_removal_activity",
    )

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert (
        evaluation.engineering_condition == "recurring_infrastructure_removal_activity"
    )


def test_unknown_engineering_condition_is_rejected():
    recognition_result = _recognition_result("supported")

    with pytest.raises(ValueError, match="engineering condition"):
        ScopeLocalEngineeringConditionEvaluation(
            outcome="supported",
            qualified_historical_evidence=(
                recognition_result.qualified_historical_evidence
            ),
            engineering_condition="unknown_condition",
        )


def test_discovery_scope_identity_is_preserved_from_qualified_evidence():
    recognition_result = _recognition_result("supported")

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert (
        evaluation.discovery_scope
        is recognition_result.qualified_historical_evidence.discovery_scope
    )


def test_qualified_evidence_reference_is_preserved():
    recognition_result = _recognition_result("supported")

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert (
        evaluation.qualified_historical_evidence
        is recognition_result.qualified_historical_evidence
    )


def test_canonical_subject_remains_accessible_through_qualified_evidence():
    recognition_result = _recognition_result("supported")

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert evaluation.qualified_historical_evidence.canonical_subject == "resource-001"


def test_supported_recognition_result_maps_to_supported_evaluation():
    recognition_result = _recognition_result("supported")

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert evaluation.outcome == "supported"


def test_not_supported_recognition_result_maps_to_not_supported_evaluation():
    recognition_result = _recognition_result("not_supported")

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert evaluation.outcome == "not_supported"


def test_same_recognition_result_always_produces_equal_evaluation():
    recognition_result = _recognition_result("supported")

    assert engineering_condition_evaluation_from_recognition_result(
        recognition_result
    ) == engineering_condition_evaluation_from_recognition_result(recognition_result)


def test_adapter_does_not_create_a_finding():
    recognition_result = _recognition_result("supported")

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert not hasattr(evaluation, "finding")


def test_not_supported_requires_no_finding():
    recognition_result = _recognition_result("not_supported")

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert evaluation.outcome == "not_supported"
    with pytest.raises(ValueError, match="supported recognition"):
        recognized_finding_from_recognition(recognition_result)


def test_existing_recognition_result_is_not_mutated():
    recognition_result = _recognition_result("supported")
    original = (
        recognition_result.outcome,
        recognition_result.qualified_historical_evidence,
        recognition_result.engineering_condition,
    )

    engineering_condition_evaluation_from_recognition_result(recognition_result)

    assert (
        recognition_result.outcome,
        recognition_result.qualified_historical_evidence,
        recognition_result.engineering_condition,
    ) == original


def test_existing_qualified_evidence_is_referenced_not_copied():
    recognition_result = _recognition_result("supported")
    evidence = recognition_result.qualified_historical_evidence

    evaluation = engineering_condition_evaluation_from_recognition_result(
        recognition_result
    )

    assert evaluation.qualified_historical_evidence is evidence
    assert evaluation.qualified_historical_evidence.completed_intervals is (
        evidence.completed_intervals
    )


def test_no_history_merge_or_cross_scope_comparison_fields_are_present():
    evaluation = _evaluation("supported")

    assert not hasattr(evaluation, "compared_scopes")
    assert not hasattr(evaluation, "requested_scopes")
    assert not hasattr(evaluation, "excluded_scopes")


def test_no_global_resource_identity_is_inferred():
    evaluation = _evaluation("supported")

    assert not hasattr(evaluation, "global_subject")
    assert not hasattr(evaluation, "global_resource_identity")


def test_provider_specific_fields_are_unnecessary():
    evaluation = _evaluation("supported")

    assert not hasattr(evaluation, "provider")
    assert not hasattr(evaluation, "account_id")
    assert not hasattr(evaluation, "region")


def test_adapter_performs_no_io():
    source_names = (
        engineering_condition_evaluation_from_recognition_result.__code__.co_names
    )

    assert "open" not in source_names
    assert "load_history" not in source_names
    assert "load_latest" not in source_names
    assert "save" not in source_names


def test_direct_rule_invocation_behavior_remains_unchanged():
    evidence = _qualified_evidence(("resource_modified",) * 4)

    result = FrequentInfrastructureModificationRule().evaluate(evidence)

    assert isinstance(result, RecognitionResult)
    assert result.outcome == "supported"


def test_supported_finding_projection_remains_unchanged():
    recognition_result = _recognition_result("supported")

    finding = recognized_finding_from_recognition(recognition_result)

    assert finding.recognition_result is recognition_result


def test_not_supported_recognition_remains_absent_from_finding_projection():
    recognition_result = _recognition_result("not_supported")

    with pytest.raises(ValueError, match="supported recognition"):
        recognized_finding_from_recognition(recognition_result)


def test_collection_returns_requested_condition_evaluations_in_scope_order():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    scope_c = DiscoveryScope("scope-c")
    evaluation_a = _evaluation_for_scope(scope_a, "supported")
    evaluation_b = _evaluation_for_scope(scope_b, "not_supported")
    evaluation_c = _evaluation_for_scope(scope_c, "supported")

    collected = collect_scope_local_engineering_condition_evaluations(
        (evaluation_b, evaluation_c, evaluation_a),
        engineering_condition="frequent_infrastructure_modification",
        discovery_scopes=(scope_a, scope_b),
    )

    assert collected == (evaluation_a, evaluation_b)


def test_collection_preserves_supported_and_not_supported_outcomes():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    supported = _evaluation_for_scope(scope_a, "supported")
    not_supported = _evaluation_for_scope(scope_b, "not_supported")

    collected = collect_scope_local_engineering_condition_evaluations(
        (supported, not_supported),
        engineering_condition="frequent_infrastructure_modification",
        discovery_scopes=(scope_a, scope_b),
    )

    assert tuple(evaluation.outcome for evaluation in collected) == (
        "supported",
        "not_supported",
    )


def test_collection_preserves_qualified_evidence_references():
    scope = DiscoveryScope("scope-a")
    evaluation = _evaluation_for_scope(scope, "supported")
    evidence = evaluation.qualified_historical_evidence

    collected = collect_scope_local_engineering_condition_evaluations(
        (evaluation,),
        engineering_condition="frequent_infrastructure_modification",
        discovery_scopes=(scope,),
    )

    assert collected[0] is evaluation
    assert collected[0].qualified_historical_evidence is evidence


def test_collection_ignores_other_engineering_conditions():
    scope = DiscoveryScope("scope-a")
    requested = _evaluation_for_scope(scope, "supported")
    other_condition = ScopeLocalEngineeringConditionEvaluation(
        outcome="supported",
        qualified_historical_evidence=_qualified_evidence_for_scope(
            DiscoveryScope("scope-b"),
            ("resource_removed",) * 4,
            canonical_subject=None,
        ),
        engineering_condition="recurring_infrastructure_removal_activity",
    )

    collected = collect_scope_local_engineering_condition_evaluations(
        (other_condition, requested),
        engineering_condition="frequent_infrastructure_modification",
        discovery_scopes=(scope,),
    )

    assert collected == (requested,)


def test_collection_requires_completed_evaluation_for_every_requested_scope():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    evaluation_a = _evaluation_for_scope(scope_a, "supported")

    with pytest.raises(ValueError, match="every requested scope"):
        collect_scope_local_engineering_condition_evaluations(
            (evaluation_a,),
            engineering_condition="frequent_infrastructure_modification",
            discovery_scopes=(scope_a, scope_b),
        )


def test_collection_rejects_duplicate_requested_scopes():
    scope = DiscoveryScope("scope-a")
    evaluation = _evaluation_for_scope(scope, "supported")

    with pytest.raises(ValueError, match="Duplicate Discovery Scopes"):
        collect_scope_local_engineering_condition_evaluations(
            (evaluation,),
            engineering_condition="frequent_infrastructure_modification",
            discovery_scopes=(scope, scope),
        )


def test_collection_rejects_duplicate_evaluations_for_one_scope_and_condition():
    scope = DiscoveryScope("scope-a")
    first = _evaluation_for_scope(scope, "supported")
    second = _evaluation_for_scope(scope, "not_supported")

    with pytest.raises(ValueError, match="Duplicate scope-local evaluations"):
        collect_scope_local_engineering_condition_evaluations(
            (first, second),
            engineering_condition="frequent_infrastructure_modification",
            discovery_scopes=(scope,),
        )


def test_collection_rejects_unknown_engineering_condition():
    scope = DiscoveryScope("scope-a")
    evaluation = _evaluation_for_scope(scope, "supported")

    with pytest.raises(ValueError, match="Engineering condition"):
        collect_scope_local_engineering_condition_evaluations(
            (evaluation,),
            engineering_condition="unknown_condition",
            discovery_scopes=(scope,),
        )


def test_collection_rejects_non_evaluation_inputs():
    scope = DiscoveryScope("scope-a")

    with pytest.raises(TypeError, match="ScopeLocalEngineeringConditionEvaluation"):
        collect_scope_local_engineering_condition_evaluations(
            ("not-an-evaluation",),
            engineering_condition="frequent_infrastructure_modification",
            discovery_scopes=(scope,),
        )


def test_collection_rejects_empty_requested_scope_population():
    with pytest.raises(ValueError, match="At least one Discovery Scope"):
        collect_scope_local_engineering_condition_evaluations(
            (),
            engineering_condition="frequent_infrastructure_modification",
            discovery_scopes=(),
        )


def test_collection_does_not_add_comparison_or_unavailable_state():
    scope = DiscoveryScope("scope-a")
    evaluation = _evaluation_for_scope(scope, "supported")

    collected = collect_scope_local_engineering_condition_evaluations(
        (evaluation,),
        engineering_condition="frequent_infrastructure_modification",
        discovery_scopes=(scope,),
    )

    assert not hasattr(collected[0], "comparison_status")
    assert not hasattr(collected[0], "unavailable")
    assert not hasattr(collected[0], "excluded")


def _evaluation(outcome: str) -> ScopeLocalEngineeringConditionEvaluation:
    return engineering_condition_evaluation_from_recognition_result(
        _recognition_result(outcome)
    )


def _recognition_result(outcome: str) -> RecognitionResult:
    return RecognitionResult(
        outcome=outcome,
        qualified_historical_evidence=_qualified_evidence(
            ("resource_modified",) * 4
            if outcome == "supported"
            else ("resource_created",) * 4
        ),
    )


def _evaluation_for_scope(
    scope: DiscoveryScope,
    outcome: str,
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome=outcome,
        qualified_historical_evidence=_qualified_evidence_for_scope(
            scope,
            ("resource_modified",) * 4
            if outcome == "supported"
            else ("resource_created",) * 4,
        ),
        engineering_condition="frequent_infrastructure_modification",
    )


def _qualified_evidence(
    observation_types: tuple[str, ...],
    *,
    canonical_subject: str | None = "resource-001",
) -> QualifiedHistoricalEvidence:
    return _qualified_evidence_for_scope(
        DiscoveryScope("scope-001"),
        observation_types,
        canonical_subject=canonical_subject,
    )


def _qualified_evidence_for_scope(
    scope: DiscoveryScope,
    observation_types: tuple[str, ...],
    *,
    canonical_subject: str | None = "resource-001",
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
) -> Observation:
    return Observation(
        subject="resource-001",
        type=observation_type,
        message=f"{observation_type}: resource-001",
        timestamp=datetime.now(UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

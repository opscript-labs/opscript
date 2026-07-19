from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation

from opscript.application.engineering_condition_evaluation import (
    EngineeringConditionComparisonEligibility,
    ExcludedEngineeringConditionEvaluation,
    compare_engineering_condition_support_distribution,
)
from opscript.application.engineering_condition_support_comparison_projection import (
    EngineeringConditionSupportComparisonProjection,
    ExcludedDiscoveryScopeProjection,
    project_engineering_condition_support_comparison,
)
from opscript.models import (
    QualifiedHistoricalEvidence,
    RecognitionResult,
    ScopeLocalEngineeringConditionEvaluation,
)


ENGINEERING_CONDITION = (
    RecognitionResult.recurring_infrastructure_removal_activity_condition
)


def test_projection_is_immutable():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    with pytest.raises(FrozenInstanceError):
        projection.classification = "SUPPORTED_IN_NO_SCOPES"


def test_equivalent_semantic_values_compare_equal():
    comparison = _comparison(
        _evaluation("scope-a", "supported"),
        _evaluation("scope-b", "not_supported"),
    )

    assert _project(comparison) == _project(comparison)


def test_projection_has_no_speculative_or_formatting_fields():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    for field_name in (
        "id",
        "timestamp",
        "score",
        "confidence",
        "health",
        "risk",
        "severity",
        "ranking",
        "recommendation",
        "message",
        "markdown",
        "json",
        "report",
    ):
        assert not hasattr(projection, field_name)


def test_populations_use_immutable_collections():
    projection = EngineeringConditionSupportComparisonProjection(
        engineering_condition=ENGINEERING_CONDITION,
        classification="SUPPORTED_IN_ALL_SCOPES",
        compared_discovery_scopes=[DiscoveryScope("scope-a")],
        supported_discovery_scopes=[DiscoveryScope("scope-a")],
        not_supported_discovery_scopes=[],
    )

    assert isinstance(projection.compared_discovery_scopes, tuple)
    assert isinstance(projection.supported_discovery_scopes, tuple)
    assert isinstance(projection.not_supported_discovery_scopes, tuple)
    assert isinstance(projection.excluded_discovery_scopes, tuple)


def test_engineering_condition_identity_is_preserved():
    comparison = _comparison(
        _evaluation("scope-a", "supported"),
        _evaluation("scope-b", "supported"),
    )

    projection = _project(comparison)

    assert projection.engineering_condition == comparison.engineering_condition


@pytest.mark.parametrize(
    ("outcomes", "classification"),
    (
        (("supported", "supported"), "SUPPORTED_IN_ALL_SCOPES"),
        (("supported", "not_supported"), "SUPPORTED_IN_SOME_SCOPES"),
        (("not_supported", "not_supported"), "SUPPORTED_IN_NO_SCOPES"),
    ),
)
def test_classification_is_preserved(outcomes, classification):
    projection = _project(
        _comparison(
            *(
                _evaluation(f"scope-{index}", outcome)
                for index, outcome in enumerate(outcomes)
            )
        )
    )

    assert projection.classification == classification


def test_projection_does_not_recalculate_classification():
    scope_a = DiscoveryScope("scope-a")
    projection = EngineeringConditionSupportComparisonProjection(
        engineering_condition=ENGINEERING_CONDITION,
        classification="SUPPORTED_IN_NO_SCOPES",
        compared_discovery_scopes=(scope_a,),
        supported_discovery_scopes=(scope_a,),
        not_supported_discovery_scopes=(),
    )

    assert projection.classification == "SUPPORTED_IN_NO_SCOPES"


def test_compared_scopes_match_eligible_evaluation_scopes():
    scope_a = _evaluation("scope-a", "supported")
    scope_b = _evaluation("scope-b", "not_supported")
    projection = _project(_comparison(scope_a, scope_b))

    assert projection.compared_discovery_scopes == (
        scope_a.discovery_scope,
        scope_b.discovery_scope,
    )


def test_compared_order_follows_eligible_order():
    scope_b = _evaluation("scope-b", "not_supported")
    scope_a = _evaluation("scope-a", "supported")
    projection = _project(_comparison(scope_b, scope_a))

    assert projection.compared_discovery_scopes == (
        scope_b.discovery_scope,
        scope_a.discovery_scope,
    )


def test_excluded_scope_does_not_appear_in_compared():
    excluded = _excluded("scope-c")
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
            excluded=(excluded,),
        )
    )

    assert (
        excluded.evaluation.discovery_scope not in projection.compared_discovery_scopes
    )


def test_supported_scopes_match_supported_evaluations():
    supported_a = _evaluation("scope-a", "supported")
    not_supported = _evaluation("scope-b", "not_supported")
    supported_b = _evaluation("scope-c", "supported")

    projection = _project(_comparison(supported_a, not_supported, supported_b))

    assert projection.supported_discovery_scopes == (
        supported_a.discovery_scope,
        supported_b.discovery_scope,
    )


def test_supported_order_is_preserved():
    supported_b = _evaluation("scope-b", "supported")
    not_supported = _evaluation("scope-a", "not_supported")
    supported_c = _evaluation("scope-c", "supported")

    projection = _project(_comparison(supported_b, not_supported, supported_c))

    assert projection.supported_discovery_scopes == (
        supported_b.discovery_scope,
        supported_c.discovery_scope,
    )


def test_all_supported_case_preserves_all_compared_scopes_as_supported():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert projection.supported_discovery_scopes == projection.compared_discovery_scopes


def test_no_supported_case_produces_empty_supported_group():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "not_supported"),
            _evaluation("scope-b", "not_supported"),
        )
    )

    assert projection.supported_discovery_scopes == ()


def test_not_supported_scopes_match_not_supported_evaluations():
    supported = _evaluation("scope-a", "supported")
    not_supported_a = _evaluation("scope-b", "not_supported")
    not_supported_b = _evaluation("scope-c", "not_supported")

    projection = _project(_comparison(supported, not_supported_a, not_supported_b))

    assert projection.not_supported_discovery_scopes == (
        not_supported_a.discovery_scope,
        not_supported_b.discovery_scope,
    )


def test_not_supported_order_is_preserved():
    not_supported_b = _evaluation("scope-b", "not_supported")
    supported = _evaluation("scope-a", "supported")
    not_supported_c = _evaluation("scope-c", "not_supported")

    projection = _project(_comparison(not_supported_b, supported, not_supported_c))

    assert projection.not_supported_discovery_scopes == (
        not_supported_b.discovery_scope,
        not_supported_c.discovery_scope,
    )


def test_all_supported_case_produces_empty_not_supported_group():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert projection.not_supported_discovery_scopes == ()


def test_no_supported_case_preserves_all_compared_scopes_as_not_supported():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "not_supported"),
            _evaluation("scope-b", "not_supported"),
        )
    )

    assert (
        projection.not_supported_discovery_scopes
        == projection.compared_discovery_scopes
    )


def test_excluded_scopes_are_preserved():
    excluded = _excluded("scope-c")
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
            excluded=(excluded,),
        )
    )

    assert projection.excluded_discovery_scopes[0].discovery_scope == (
        excluded.evaluation.discovery_scope
    )


def test_exclusion_reasons_are_preserved_exactly():
    excluded = _excluded("scope-c", reason="engineering_condition_mismatch")
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
            excluded=(excluded,),
        )
    )

    assert projection.excluded_discovery_scopes[0].reason == (
        "engineering_condition_mismatch"
    )


def test_excluded_order_is_preserved():
    excluded_b = _excluded("scope-b")
    excluded_c = _excluded("scope-c")
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-d", "not_supported"),
            excluded=(excluded_b, excluded_c),
        )
    )

    assert projection.excluded_discovery_scopes == (
        ExcludedDiscoveryScopeProjection(
            discovery_scope=excluded_b.evaluation.discovery_scope,
            reason=excluded_b.reason,
        ),
        ExcludedDiscoveryScopeProjection(
            discovery_scope=excluded_c.evaluation.discovery_scope,
            reason=excluded_c.reason,
        ),
    )


def test_excluded_scope_is_never_projected_as_not_supported():
    excluded = _excluded("scope-c")
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
            excluded=(excluded,),
        )
    )

    assert excluded.evaluation.discovery_scope not in (
        projection.not_supported_discovery_scopes
    )


def test_projection_does_not_translate_reason_wording():
    projection = EngineeringConditionSupportComparisonProjection(
        engineering_condition=ENGINEERING_CONDITION,
        classification="SUPPORTED_IN_ALL_SCOPES",
        compared_discovery_scopes=(DiscoveryScope("scope-a"),),
        supported_discovery_scopes=(DiscoveryScope("scope-a"),),
        excluded_discovery_scopes=(
            ExcludedDiscoveryScopeProjection(
                discovery_scope=DiscoveryScope("scope-b"),
                reason="future_reason",
            ),
        ),
    )

    assert projection.excluded_discovery_scopes[0].reason == "future_reason"


def test_supported_plus_not_supported_equals_compared():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
            _evaluation("scope-c", "supported"),
        )
    )

    assert set(
        projection.supported_discovery_scopes
        + projection.not_supported_discovery_scopes
    ) == set(projection.compared_discovery_scopes)


def test_no_overlap_between_support_state_groups():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
        )
    )

    assert set(projection.supported_discovery_scopes).isdisjoint(
        projection.not_supported_discovery_scopes
    )


def test_no_omission_or_duplication():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
            _evaluation("scope-c", "supported"),
        )
    )
    partition = (
        projection.supported_discovery_scopes
        + projection.not_supported_discovery_scopes
    )

    assert set(partition) == set(projection.compared_discovery_scopes)
    assert len(partition) == len(set(partition))


def test_classification_only_projection_is_rejected():
    with pytest.raises(ValueError, match="compared_discovery_scopes"):
        EngineeringConditionSupportComparisonProjection(
            engineering_condition=ENGINEERING_CONDITION,
            classification="SUPPORTED_IN_ALL_SCOPES",
        )


def test_engineering_condition_identity_is_mandatory():
    with pytest.raises(ValueError, match="engineering_condition"):
        EngineeringConditionSupportComparisonProjection(
            engineering_condition="",
            classification="SUPPORTED_IN_ALL_SCOPES",
            compared_discovery_scopes=(DiscoveryScope("scope-a"),),
            supported_discovery_scopes=(DiscoveryScope("scope-a"),),
        )


def test_projection_does_not_execute_comparison():
    names = project_engineering_condition_support_comparison.__code__.co_names

    assert "compare_engineering_condition_support_distribution" not in names


def test_projection_does_not_assess_compatibility():
    names = project_engineering_condition_support_comparison.__code__.co_names

    assert "assess_engineering_condition_comparison_eligibility" not in names


def test_projection_does_not_inspect_findings():
    names = project_engineering_condition_support_comparison.__code__.co_names

    assert "Finding" not in names
    assert "findings" not in names


def test_projection_does_not_copy_evidence():
    projection_fields = {
        field.name for field in fields(EngineeringConditionSupportComparisonProjection)
    }

    assert "qualified_historical_evidence" not in projection_fields
    assert "completed_intervals" not in projection_fields
    assert "observations" not in projection_fields


def test_projection_does_not_create_narrative_strings():
    projection_fields = {
        field.name for field in fields(EngineeringConditionSupportComparisonProjection)
    }

    assert "message" not in projection_fields
    assert "summary" not in projection_fields
    assert "description" not in projection_fields


def test_projection_performs_no_io_aws_storage_workflow_or_telemetry():
    names = project_engineering_condition_support_comparison.__code__.co_names

    assert "open" not in names
    assert "boto3" not in names
    assert "load_history" not in names
    assert "load_latest" not in names
    assert "save" not in names
    assert "format_log_event" not in names
    assert "Workflow" not in names


def test_no_cli_or_json_behavior_exists():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert not hasattr(projection, "json")
    assert not hasattr(projection, "cli")
    assert not hasattr(projection, "output")


def test_platformiq_remains_uninvolved():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert projection.__class__.__module__.startswith("opscript.")


def test_no_unavailable_state_exists():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
        )
    )

    assert projection.classification != "COMPARISON_UNAVAILABLE"
    assert not hasattr(projection, "availability")
    assert not hasattr(projection, "unavailable_reason")


def test_no_multi_condition_representation_exists():
    projection = _project(
        _comparison(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert not hasattr(projection, "engineering_conditions")
    assert not hasattr(projection, "comparisons")


def test_duplicate_compared_scopes_are_rejected():
    scope = DiscoveryScope("scope-a")

    with pytest.raises(ValueError, match="duplicates"):
        EngineeringConditionSupportComparisonProjection(
            engineering_condition=ENGINEERING_CONDITION,
            classification="SUPPORTED_IN_ALL_SCOPES",
            compared_discovery_scopes=(scope, scope),
            supported_discovery_scopes=(scope,),
        )


def test_excluded_scope_cannot_be_compared():
    scope = DiscoveryScope("scope-a")

    with pytest.raises(ValueError, match="Excluded"):
        EngineeringConditionSupportComparisonProjection(
            engineering_condition=ENGINEERING_CONDITION,
            classification="SUPPORTED_IN_ALL_SCOPES",
            compared_discovery_scopes=(scope,),
            supported_discovery_scopes=(scope,),
            excluded_discovery_scopes=(
                ExcludedDiscoveryScopeProjection(
                    discovery_scope=scope,
                    reason="engineering_condition_mismatch",
                ),
            ),
        )


def _project(comparison):
    return project_engineering_condition_support_comparison(comparison)


def _comparison(
    *eligible_evaluations: ScopeLocalEngineeringConditionEvaluation,
    excluded: tuple[ExcludedEngineeringConditionEvaluation, ...] = (),
):
    return compare_engineering_condition_support_distribution(
        EngineeringConditionComparisonEligibility(
            requested_evaluations=tuple(eligible_evaluations)
            + tuple(exclusion.evaluation for exclusion in excluded),
            eligible_evaluations=eligible_evaluations,
            excluded_evaluations=excluded,
        )
    )


def _excluded(
    scope_value: str,
    *,
    reason: str = "engineering_condition_mismatch",
) -> ExcludedEngineeringConditionEvaluation:
    return ExcludedEngineeringConditionEvaluation(
        evaluation=_other_condition_evaluation(scope_value),
        reason=reason,
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

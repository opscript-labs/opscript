from dataclasses import FrozenInstanceError, fields

import pytest

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope

from opscript.application.engineering_condition_evaluation import (
    EngineeringConditionComparisonEligibility,
    ExcludedEngineeringConditionEvaluation,
)
from opscript.application.engineering_condition_public_identity import (
    PublicEngineeringConditionIdentifier,
    public_engineering_condition_identifiers,
)
from opscript.application.engineering_condition_support_comparison_projection import (
    EngineeringConditionSupportComparisonProjection,
    ExcludedDiscoveryScopeProjection,
)
from opscript.application.engineering_condition_support_comparison_workflow import (
    EngineeringConditionSupportComparisonWorkflowResult,
)
from opscript.application.knowledge_review_request import KnowledgeReviewAnalysis
from opscript.application.knowledge_review_structured_result import (
    KnowledgeReviewExcludedDiscoveryScope,
    KnowledgeReviewStructuredResult,
    KnowledgeReviewStructuredResultError,
    knowledge_review_structured_result_from_result,
)
from opscript.execution import get_active_execution
from opscript.models import (
    QualifiedHistoricalEvidence,
    RecognitionResult,
    ScopeLocalEngineeringConditionEvaluation,
)


def test_structured_result_is_immutable():
    structured = knowledge_review_structured_result_from_result(_produced_result())

    with pytest.raises(FrozenInstanceError):
        structured.analysis = (
            KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON
        )


def test_structured_result_reuses_existing_analysis_identity():
    structured = knowledge_review_structured_result_from_result(_produced_result())

    assert (
        structured.analysis
        is KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON
    )


def test_structured_result_uses_public_condition_identifier():
    structured = knowledge_review_structured_result_from_result(_produced_result())

    assert structured.engineering_condition_identifier == (
        PublicEngineeringConditionIdentifier("EC-002")
    )
    assert structured.engineering_condition_identifier.value != (
        RecognitionResult.recurring_infrastructure_removal_activity_condition
    )


def test_collection_fields_are_tuple_based():
    structured = knowledge_review_structured_result_from_result(_produced_result())

    assert isinstance(structured.discovery_scopes, tuple)
    assert isinstance(structured.comparison.compared_discovery_scopes, tuple)
    assert isinstance(structured.comparison.supported_discovery_scopes, tuple)
    assert isinstance(structured.comparison.not_supported_discovery_scopes, tuple)
    assert isinstance(structured.comparison.excluded_discovery_scopes, tuple)


def test_deterministic_value_equality():
    result = _produced_result()

    assert knowledge_review_structured_result_from_result(
        result
    ) == knowledge_review_structured_result_from_result(result)


@pytest.mark.parametrize(
    ("engineering_condition", "public_identifier"),
    [
        (
            RecognitionResult.frequent_infrastructure_modification_condition,
            "EC-001",
        ),
        (
            RecognitionResult.recurring_infrastructure_removal_activity_condition,
            "EC-002",
        ),
        (
            RecognitionResult.recurring_infrastructure_introduction_activity_condition,
            "EC-003",
        ),
    ],
)
def test_completed_result_projects_to_public_identifier(
    engineering_condition,
    public_identifier,
):
    structured = knowledge_review_structured_result_from_result(
        _produced_result(engineering_condition=engineering_condition)
    )

    assert structured.engineering_condition_identifier == (
        PublicEngineeringConditionIdentifier(public_identifier)
    )


def test_unknown_internal_condition_identity_is_rejected():
    result = object.__new__(EngineeringConditionSupportComparisonWorkflowResult)
    object.__setattr__(result, "engineering_condition", "unknown_condition")
    object.__setattr__(result, "requested_scopes", _scopes("scope-a", "scope-b"))
    object.__setattr__(result, "status", "comparison_produced")
    object.__setattr__(result, "projection", None)
    object.__setattr__(result, "reason", "comparison_available")
    object.__setattr__(result, "eligibility", _eligibility())

    with pytest.raises(KnowledgeReviewStructuredResultError):
        knowledge_review_structured_result_from_result(result)


def test_public_identity_mapping_delegates_to_approved_catalog():
    assert tuple(
        identifier.value for identifier in public_engineering_condition_identifiers()
    ) == ("EC-001", "EC-002", "EC-003")

    structured = knowledge_review_structured_result_from_result(_produced_result())

    assert structured.engineering_condition_identifier.value == "EC-002"


def test_comparison_classification_is_preserved():
    result = _produced_result(classification="SUPPORTED_IN_SOME_SCOPES")

    structured = knowledge_review_structured_result_from_result(result)

    assert structured.comparison.classification == result.projection.classification


def test_scope_level_support_meaning_is_preserved():
    result = _produced_result(
        supported=("scope-b",),
        not_supported=("scope-a",),
    )

    structured = knowledge_review_structured_result_from_result(result)

    assert structured.comparison.supported_discovery_scopes == _scopes("scope-b")
    assert structured.comparison.not_supported_discovery_scopes == _scopes("scope-a")


def test_excluded_scope_meaning_is_preserved():
    result = _produced_result(
        excluded=(
            ExcludedDiscoveryScopeProjection(
                discovery_scope=DiscoveryScope("scope-c"),
                reason="engineering_condition_mismatch",
            ),
        )
    )

    structured = knowledge_review_structured_result_from_result(result)

    assert structured.comparison.excluded_discovery_scopes == (
        KnowledgeReviewExcludedDiscoveryScope(
            discovery_scope=DiscoveryScope("scope-c"),
            reason="engineering_condition_mismatch",
        ),
    )


def test_unsupported_is_not_converted_to_excluded():
    structured = knowledge_review_structured_result_from_result(
        _produced_result(
            supported=(),
            not_supported=("scope-a", "scope-b"),
            classification="SUPPORTED_IN_NO_SCOPES",
        )
    )

    assert structured.comparison.not_supported_discovery_scopes == _scopes(
        "scope-a",
        "scope-b",
    )
    assert structured.comparison.excluded_discovery_scopes == ()


def test_excluded_is_not_converted_to_unsupported():
    structured = knowledge_review_structured_result_from_result(
        _produced_result(
            excluded=(
                ExcludedDiscoveryScopeProjection(
                    discovery_scope=DiscoveryScope("scope-c"),
                    reason="unsupported_subject_comparison",
                ),
            )
        )
    )

    assert DiscoveryScope("scope-c") not in (
        structured.comparison.not_supported_discovery_scopes
    )
    assert structured.comparison.excluded_discovery_scopes[0].discovery_scope == (
        DiscoveryScope("scope-c")
    )


def test_absence_is_not_converted_into_false():
    structured = knowledge_review_structured_result_from_result(_unavailable_result())

    assert structured.comparison.status == "comparison_unavailable"
    assert structured.comparison.classification is None
    assert structured.comparison.supported_discovery_scopes == ()
    assert structured.comparison.not_supported_discovery_scopes == ()


def test_requested_scope_order_is_preserved():
    result = _produced_result(
        requested=("scope-b", "scope-a", "scope-c"),
        compared=("scope-b", "scope-a"),
        supported=("scope-b",),
        not_supported=("scope-a",),
        excluded=(
            ExcludedDiscoveryScopeProjection(
                discovery_scope=DiscoveryScope("scope-c"),
                reason="engineering_condition_mismatch",
            ),
        ),
    )

    structured = knowledge_review_structured_result_from_result(result)

    assert structured.discovery_scopes == _scopes("scope-b", "scope-a", "scope-c")
    assert structured.comparison.compared_discovery_scopes == _scopes(
        "scope-b",
        "scope-a",
    )
    assert structured.comparison.excluded_discovery_scopes[0].discovery_scope == (
        DiscoveryScope("scope-c")
    )


def test_repeated_projection_is_deterministic():
    result = _produced_result()

    assert knowledge_review_structured_result_from_result(
        result
    ) == knowledge_review_structured_result_from_result(result)


def test_projection_does_not_mutate_source_result():
    result = _produced_result()
    before = result

    knowledge_review_structured_result_from_result(result)

    assert result == before


def test_projection_requires_completed_comparison_workflow_result():
    with pytest.raises(TypeError):
        knowledge_review_structured_result_from_result(object())


def test_projection_performs_no_runtime_side_effects():
    assert get_active_execution() is None

    knowledge_review_structured_result_from_result(_produced_result())

    assert get_active_execution() is None


def test_no_cli_formatter_json_or_serialization_fields_exist():
    structured = knowledge_review_structured_result_from_result(_produced_result())

    for unexpected in (
        "json",
        "serializer",
        "formatter",
        "schema_version",
        "to_dict",
        "to_json",
        "as_json",
        "command",
        "workflow",
        "storage",
        "aws",
        "telemetry",
        "persistence",
    ):
        assert not hasattr(structured, unexpected)
        assert not hasattr(structured.comparison, unexpected)


def test_existing_request_model_remains_unchanged():
    assert tuple(field.name for field in fields(KnowledgeReviewStructuredResult)) == (
        "analysis",
        "engineering_condition_identifier",
        "discovery_scopes",
        "comparison",
    )


def test_unavailable_result_preserves_reason_and_exclusions():
    excluded = ExcludedEngineeringConditionEvaluation(
        evaluation=_evaluation(
            "scope-b",
            engineering_condition=(
                RecognitionResult.frequent_infrastructure_modification_condition
            ),
        ),
        reason="engineering_condition_mismatch",
    )
    result = _unavailable_result(excluded=(excluded,))

    structured = knowledge_review_structured_result_from_result(result)

    assert structured.comparison.status == "comparison_unavailable"
    assert structured.comparison.reason == "insufficient_eligible_evaluations"
    assert structured.comparison.excluded_discovery_scopes == (
        KnowledgeReviewExcludedDiscoveryScope(
            discovery_scope=DiscoveryScope("scope-b"),
            reason="engineering_condition_mismatch",
        ),
    )


def _produced_result(
    *,
    engineering_condition: str = (
        RecognitionResult.recurring_infrastructure_removal_activity_condition
    ),
    requested: tuple[str, ...] = ("scope-a", "scope-b"),
    compared: tuple[str, ...] = ("scope-a", "scope-b"),
    supported: tuple[str, ...] = ("scope-a",),
    not_supported: tuple[str, ...] = ("scope-b",),
    excluded: tuple[ExcludedDiscoveryScopeProjection, ...] = (),
    classification: str = "SUPPORTED_IN_SOME_SCOPES",
) -> EngineeringConditionSupportComparisonWorkflowResult:
    return EngineeringConditionSupportComparisonWorkflowResult(
        status="comparison_produced",
        engineering_condition=engineering_condition,
        requested_scopes=_scopes(*requested),
        eligibility=_eligibility(engineering_condition=engineering_condition),
        projection=EngineeringConditionSupportComparisonProjection(
            engineering_condition=engineering_condition,
            classification=classification,
            compared_discovery_scopes=_scopes(*compared),
            supported_discovery_scopes=_scopes(*supported),
            not_supported_discovery_scopes=_scopes(*not_supported),
            excluded_discovery_scopes=excluded,
        ),
    )


def _unavailable_result(
    *,
    engineering_condition: str = (
        RecognitionResult.recurring_infrastructure_removal_activity_condition
    ),
    excluded: tuple[ExcludedEngineeringConditionEvaluation, ...] = (),
) -> EngineeringConditionSupportComparisonWorkflowResult:
    return EngineeringConditionSupportComparisonWorkflowResult(
        status="comparison_unavailable",
        engineering_condition=engineering_condition,
        requested_scopes=_scopes("scope-a", "scope-b"),
        eligibility=_eligibility(
            engineering_condition=engineering_condition,
            excluded=excluded,
        ),
        reason="insufficient_eligible_evaluations",
    )


def _eligibility(
    *,
    engineering_condition: str = (
        RecognitionResult.recurring_infrastructure_removal_activity_condition
    ),
    excluded: tuple[ExcludedEngineeringConditionEvaluation, ...] = (),
) -> EngineeringConditionComparisonEligibility:
    return EngineeringConditionComparisonEligibility(
        requested_evaluations=(
            _evaluation("scope-a", engineering_condition=engineering_condition),
            _evaluation("scope-b", engineering_condition=engineering_condition),
        )
        + tuple(item.evaluation for item in excluded),
        eligible_evaluations=(
            _evaluation("scope-a", engineering_condition=engineering_condition),
            _evaluation("scope-b", engineering_condition=engineering_condition),
        ),
        excluded_evaluations=excluded,
    )


def _evaluation(
    scope: str,
    *,
    outcome: str = "supported",
    engineering_condition: str = (
        RecognitionResult.recurring_infrastructure_removal_activity_condition
    ),
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome=outcome,
        engineering_condition=engineering_condition,
        qualified_historical_evidence=_evidence(scope),
    )


def _evidence(scope: str) -> QualifiedHistoricalEvidence:
    previous = Identifier.from_string("00000000-0000-0000-0000-000000000001")
    current = Identifier.from_string("00000000-0000-0000-0000-000000000002")
    discovery_scope = DiscoveryScope(scope)
    return QualifiedHistoricalEvidence(
        discovery_scope=discovery_scope,
        observation_window_previous_snapshot_id=previous,
        observation_window_current_snapshot_id=current,
        completed_intervals=(
            CompletedComparisonInterval(
                discovery_scope=discovery_scope,
                previous_snapshot_id=previous,
                current_snapshot_id=current,
            ),
        ),
    )


def _scopes(*values: str) -> tuple[DiscoveryScope, ...]:
    return tuple(DiscoveryScope(value) for value in values)

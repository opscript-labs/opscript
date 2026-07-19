from dataclasses import FrozenInstanceError

import pytest

from platformiq.model import DiscoveryScope

from opscript.application.engineering_condition_public_identity import (
    PublicEngineeringConditionIdentifier,
    public_engineering_condition_identifiers,
)
from opscript.application.knowledge_review_request import (
    KnowledgeReviewAnalysis,
    KnowledgeReviewRequest,
    KnowledgeReviewRequestError,
    knowledge_review_selection_from_request,
)
from opscript.application.knowledge_review_workflow import (
    EngineeringConditionSupportComparisonSelection,
)
from opscript.execution import get_active_execution


def test_analysis_selection_is_immutable():
    assert (
        KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON.value
        == "ENGINEERING_CONDITION_SUPPORT_COMPARISON"
    )


def test_only_authorized_analysis_selection_exists():
    assert tuple(KnowledgeReviewAnalysis) == (
        KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON,
    )


def test_analysis_selection_has_no_alias_or_normalization_behavior():
    with pytest.raises(ValueError):
        KnowledgeReviewAnalysis("engineering_condition_support_comparison")


@pytest.mark.parametrize(
    ("public_identifier", "internal_identity"),
    [
        ("EC-001", "frequent_infrastructure_modification"),
        ("EC-002", "recurring_infrastructure_removal_activity"),
        ("EC-003", "recurring_infrastructure_introduction_activity"),
    ],
)
def test_valid_request_translates_public_identifier_to_internal_selection(
    public_identifier,
    internal_identity,
):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    request = _request(public_identifier, (scope_a, scope_b))

    selection = knowledge_review_selection_from_request(request)

    assert isinstance(selection, EngineeringConditionSupportComparisonSelection)
    assert selection.engineering_condition == internal_identity
    assert selection.discovery_scopes == (scope_a, scope_b)


def test_request_is_immutable():
    request = _request("EC-001", _scopes("scope-a", "scope-b"))

    with pytest.raises(FrozenInstanceError):
        request.analysis = (
            KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON
        )


def test_discovery_scope_order_is_preserved():
    scopes = _scopes("scope-b", "scope-a", "scope-c")

    request = _request("EC-002", scopes)

    assert request.discovery_scopes == scopes
    assert knowledge_review_selection_from_request(request).discovery_scopes == scopes


def test_three_or_more_scopes_are_accepted():
    request = _request("EC-003", _scopes("scope-a", "scope-b", "scope-c"))

    assert tuple(scope.value for scope in request.discovery_scopes) == (
        "scope-a",
        "scope-b",
        "scope-c",
    )


def test_exactly_two_scopes_are_accepted():
    request = _request("EC-001", _scopes("scope-a", "scope-b"))

    assert len(request.discovery_scopes) == 2


@pytest.mark.parametrize(
    "scopes",
    [
        (),
        (DiscoveryScope("scope-a"),),
    ],
)
def test_fewer_than_two_scopes_are_rejected(scopes):
    with pytest.raises(KnowledgeReviewRequestError, match="At least two"):
        _request("EC-001", scopes)


@pytest.mark.parametrize(
    "scopes",
    [
        (DiscoveryScope("scope-a"), DiscoveryScope("scope-a")),
        (
            DiscoveryScope("scope-a"),
            DiscoveryScope("scope-b"),
            DiscoveryScope("scope-a"),
        ),
    ],
)
def test_duplicate_scopes_are_rejected(scopes):
    with pytest.raises(KnowledgeReviewRequestError, match="Duplicate"):
        _request("EC-001", scopes)


@pytest.mark.parametrize(
    "public_identifier",
    [
        "EC-004",
        "ec-001",
        "EC001",
        "EC_001",
        "frequent_infrastructure_modification",
    ],
)
def test_unknown_variant_or_internal_identifier_is_rejected(public_identifier):
    with pytest.raises(KnowledgeReviewRequestError):
        _request(public_identifier, _scopes("scope-a", "scope-b"))


def test_unsupported_analysis_is_rejected():
    with pytest.raises(KnowledgeReviewRequestError, match="Analysis"):
        KnowledgeReviewRequest(
            analysis="ENGINEERING_CONDITION_SUPPORT_COMPARISON",
            engineering_condition_identifier=PublicEngineeringConditionIdentifier(
                "EC-001"
            ),
            discovery_scopes=_scopes("scope-a", "scope-b"),
        )


def test_translation_does_not_modify_public_request():
    request = _request("EC-001", _scopes("scope-a", "scope-b"))
    before = request

    knowledge_review_selection_from_request(request)

    assert request == before


def test_translation_is_deterministic():
    request = _request("EC-002", _scopes("scope-a", "scope-b"))

    assert knowledge_review_selection_from_request(
        request
    ) == knowledge_review_selection_from_request(request)


def test_translation_requires_request_model():
    with pytest.raises(TypeError):
        knowledge_review_selection_from_request(object())


def test_request_uses_public_identifier_catalog_as_mapping_authority():
    assert tuple(
        identifier.value for identifier in public_engineering_condition_identifiers()
    ) == (
        "EC-001",
        "EC-002",
        "EC-003",
    )

    assert (
        knowledge_review_selection_from_request(
            _request("EC-003", _scopes("scope-a", "scope-b"))
        ).engineering_condition
        == "recurring_infrastructure_introduction_activity"
    )


def test_request_has_no_runtime_side_effects():
    assert get_active_execution() is None

    request = _request("EC-001", _scopes("scope-a", "scope-b"))
    knowledge_review_selection_from_request(request)

    assert get_active_execution() is None


def test_no_cli_json_formatting_or_workflow_fields_exist():
    request = _request("EC-001", _scopes("scope-a", "scope-b"))

    for unexpected in (
        "json",
        "serializer",
        "formatter",
        "workflow",
        "storage",
        "aws",
        "telemetry",
    ):
        assert not hasattr(request, unexpected)


def test_existing_internal_selection_semantics_remain_unchanged():
    selection = EngineeringConditionSupportComparisonSelection(
        engineering_condition="frequent_infrastructure_modification",
        discovery_scopes=_scopes("scope-a", "scope-a"),
    )

    assert selection.discovery_scopes == _scopes("scope-a", "scope-a")


def _request(
    public_identifier: str,
    discovery_scopes: tuple[DiscoveryScope, ...],
) -> KnowledgeReviewRequest:
    return KnowledgeReviewRequest(
        analysis=KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON,
        engineering_condition_identifier=PublicEngineeringConditionIdentifier(
            public_identifier
        ),
        discovery_scopes=discovery_scopes,
    )


def _scopes(*values: str) -> tuple[DiscoveryScope, ...]:
    return tuple(DiscoveryScope(value) for value in values)

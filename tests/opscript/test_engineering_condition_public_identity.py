from dataclasses import FrozenInstanceError, fields

import pytest

from opscript.application.engineering_condition_evaluation import (
    _validate_engineering_condition,
)
from opscript.application.engineering_condition_public_identity import (
    EngineeringConditionPublicIdentityError,
    PublicEngineeringConditionIdentifier,
    engineering_condition_from_public_identifier,
    public_engineering_condition_identifiers,
    public_identifier_for_engineering_condition,
)
from opscript.application.frequent_infrastructure_modification_rule import (
    FrequentInfrastructureModificationRule,
)
from opscript.application.recurring_infrastructure_introduction_activity_rule import (
    RecurringInfrastructureIntroductionActivityRule,
)
from opscript.application.recurring_infrastructure_removal_activity_rule import (
    RecurringInfrastructureRemovalActivityRule,
)
from opscript.execution import get_active_execution
from opscript.models import RecognitionResult


APPROVED_MAPPINGS = (
    ("EC-001", "frequent_infrastructure_modification"),
    ("EC-002", "recurring_infrastructure_removal_activity"),
    ("EC-003", "recurring_infrastructure_introduction_activity"),
)


def test_public_identifier_is_immutable():
    identifier = PublicEngineeringConditionIdentifier("EC-001")

    with pytest.raises(FrozenInstanceError):
        identifier.value = "EC-002"


def test_public_identifier_equality_is_value_based():
    assert PublicEngineeringConditionIdentifier(
        "EC-001"
    ) == PublicEngineeringConditionIdentifier("EC-001")
    assert PublicEngineeringConditionIdentifier(
        "EC-001"
    ) != PublicEngineeringConditionIdentifier("EC-002")


@pytest.mark.parametrize("value", ["", "   "])
def test_public_identifier_rejects_empty_or_whitespace_only_value(value):
    with pytest.raises(ValueError):
        PublicEngineeringConditionIdentifier(value)


def test_public_identifier_preserves_exact_value_without_normalization():
    identifier = PublicEngineeringConditionIdentifier(" EC-001 ")

    assert identifier.value == " EC-001 "


def test_public_identifier_has_no_display_or_implementation_fields():
    assert tuple(
        field.name for field in fields(PublicEngineeringConditionIdentifier)
    ) == ("value",)
    identifier = PublicEngineeringConditionIdentifier("EC-001")

    for unexpected in ("display_name", "rule", "provider", "version"):
        assert not hasattr(identifier, unexpected)


@pytest.mark.parametrize(("public_identifier", "internal_identity"), APPROVED_MAPPINGS)
def test_public_identifier_maps_to_approved_internal_identity(
    public_identifier,
    internal_identity,
):
    assert (
        engineering_condition_from_public_identifier(
            PublicEngineeringConditionIdentifier(public_identifier)
        )
        == internal_identity
    )


@pytest.mark.parametrize(("public_identifier", "internal_identity"), APPROVED_MAPPINGS)
def test_internal_identity_maps_to_approved_public_identifier(
    public_identifier,
    internal_identity,
):
    assert public_identifier_for_engineering_condition(
        internal_identity
    ) == PublicEngineeringConditionIdentifier(public_identifier)


def test_catalog_contains_exactly_approved_identifiers_in_deterministic_order():
    identifiers = public_engineering_condition_identifiers()

    assert identifiers == tuple(
        PublicEngineeringConditionIdentifier(public_identifier)
        for public_identifier, _ in APPROVED_MAPPINGS
    )


def test_catalog_public_and_internal_identities_are_unique():
    identifiers = public_engineering_condition_identifiers()
    internal_identities = tuple(
        engineering_condition_from_public_identifier(identifier)
        for identifier in identifiers
    )

    assert len(set(identifiers)) == len(identifiers)
    assert len(set(internal_identities)) == len(internal_identities)


def test_every_public_identifier_round_trips_through_internal_identity():
    for public_identifier, _ in APPROVED_MAPPINGS:
        identifier = PublicEngineeringConditionIdentifier(public_identifier)

        assert (
            public_identifier_for_engineering_condition(
                engineering_condition_from_public_identifier(identifier)
            )
            == identifier
        )


def test_every_internal_identity_round_trips_through_public_identifier():
    for _, internal_identity in APPROVED_MAPPINGS:
        assert (
            engineering_condition_from_public_identifier(
                public_identifier_for_engineering_condition(internal_identity)
            )
            == internal_identity
        )


@pytest.mark.parametrize(
    "public_identifier",
    [
        "EC-004",
        "ec-001",
        "Ec-001",
        "EC001",
        "EC_001",
        " EC-001",
        "EC-001 ",
        "frequent_infrastructure_modification",
    ],
)
def test_unknown_variant_or_internal_name_public_identifier_is_rejected(
    public_identifier,
):
    with pytest.raises(EngineeringConditionPublicIdentityError):
        engineering_condition_from_public_identifier(
            PublicEngineeringConditionIdentifier(public_identifier)
        )


@pytest.mark.parametrize(
    "internal_identity",
    [
        "unknown_condition",
        "EC-001",
        "recurring_infrastructure_removal_activity ",
    ],
)
def test_unknown_or_public_value_internal_identity_is_rejected(internal_identity):
    with pytest.raises(EngineeringConditionPublicIdentityError):
        public_identifier_for_engineering_condition(internal_identity)


def test_existing_internal_engineering_condition_identities_remain_unchanged():
    assert (
        RecognitionResult.frequent_infrastructure_modification_condition
        == "frequent_infrastructure_modification"
    )
    assert (
        RecognitionResult.recurring_infrastructure_removal_activity_condition
        == "recurring_infrastructure_removal_activity"
    )
    assert (
        RecognitionResult.recurring_infrastructure_introduction_activity_condition
        == "recurring_infrastructure_introduction_activity"
    )


def test_recognition_rule_internal_conditions_remain_unchanged():
    assert (
        FrequentInfrastructureModificationRule.engineering_condition
        == "frequent_infrastructure_modification"
    )
    assert (
        RecurringInfrastructureRemovalActivityRule.engineering_condition
        == "recurring_infrastructure_removal_activity"
    )
    assert (
        RecurringInfrastructureIntroductionActivityRule.engineering_condition
        == "recurring_infrastructure_introduction_activity"
    )


def test_comparison_eligibility_internal_condition_validation_is_unchanged():
    for _, internal_identity in APPROVED_MAPPINGS:
        _validate_engineering_condition(internal_identity)

    with pytest.raises(ValueError):
        _validate_engineering_condition("EC-001")


def test_catalog_has_no_runtime_side_effects():
    assert get_active_execution() is None

    public_identifier_for_engineering_condition(
        "recurring_infrastructure_removal_activity"
    )
    engineering_condition_from_public_identifier(
        PublicEngineeringConditionIdentifier("EC-002")
    )

    assert get_active_execution() is None


def test_no_alias_or_deprecation_behavior_exists():
    identifier = PublicEngineeringConditionIdentifier("EC-001")

    for unexpected in ("aliases", "deprecated", "replacement", "version"):
        assert not hasattr(identifier, unexpected)

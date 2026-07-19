from dataclasses import dataclass

from opscript.models import RecognitionResult


class EngineeringConditionPublicIdentityError(ValueError):
    pass


@dataclass(frozen=True)
class PublicEngineeringConditionIdentifier:
    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("Public Engineering Condition identifier must be a string.")

        if not self.value:
            raise ValueError("Public Engineering Condition identifier is required.")

        if self.value.isspace():
            raise ValueError(
                "Public Engineering Condition identifier must not be whitespace."
            )


_PUBLIC_TO_INTERNAL = (
    (
        PublicEngineeringConditionIdentifier("EC-001"),
        RecognitionResult.frequent_infrastructure_modification_condition,
    ),
    (
        PublicEngineeringConditionIdentifier("EC-002"),
        RecognitionResult.recurring_infrastructure_removal_activity_condition,
    ),
    (
        PublicEngineeringConditionIdentifier("EC-003"),
        RecognitionResult.recurring_infrastructure_introduction_activity_condition,
    ),
)


def public_engineering_condition_identifiers() -> tuple[
    PublicEngineeringConditionIdentifier, ...
]:
    return tuple(public_identifier for public_identifier, _ in _catalog_entries())


def engineering_condition_from_public_identifier(
    public_identifier: PublicEngineeringConditionIdentifier,
) -> str:
    if not isinstance(public_identifier, PublicEngineeringConditionIdentifier):
        raise TypeError(
            "public_identifier must be PublicEngineeringConditionIdentifier."
        )

    for candidate, engineering_condition in _catalog_entries():
        if candidate == public_identifier:
            return engineering_condition

    raise EngineeringConditionPublicIdentityError(
        "Public Engineering Condition identifier is not supported."
    )


def public_identifier_for_engineering_condition(
    engineering_condition: str,
) -> PublicEngineeringConditionIdentifier:
    if not isinstance(engineering_condition, str):
        raise TypeError("engineering_condition must be a string.")

    for public_identifier, candidate in _catalog_entries():
        if candidate == engineering_condition:
            return public_identifier

    raise EngineeringConditionPublicIdentityError(
        "Engineering Condition identity is not supported."
    )


def _catalog_entries() -> tuple[tuple[PublicEngineeringConditionIdentifier, str], ...]:
    _validate_catalog(_PUBLIC_TO_INTERNAL)
    return _PUBLIC_TO_INTERNAL


def _validate_catalog(
    entries: tuple[tuple[PublicEngineeringConditionIdentifier, str], ...],
) -> None:
    public_identifiers = tuple(public_identifier for public_identifier, _ in entries)
    internal_identities = tuple(
        engineering_condition for _, engineering_condition in entries
    )

    if len(set(public_identifiers)) != len(public_identifiers):
        raise EngineeringConditionPublicIdentityError(
            "Public Engineering Condition identifiers must be unique."
        )

    if len(set(internal_identities)) != len(internal_identities):
        raise EngineeringConditionPublicIdentityError(
            "Engineering Condition identities must be unique."
        )

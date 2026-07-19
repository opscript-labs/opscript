from dataclasses import dataclass, field

from platformiq.model import DiscoveryScope

from opscript.application.engineering_condition_evaluation import (
    EngineeringConditionSupportDistributionComparison,
)


@dataclass(frozen=True)
class ExcludedDiscoveryScopeProjection:
    discovery_scope: DiscoveryScope
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.discovery_scope, DiscoveryScope):
            raise TypeError("discovery_scope must be a DiscoveryScope.")

        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason is required.")


@dataclass(frozen=True)
class EngineeringConditionSupportComparisonProjection:
    engineering_condition: str
    classification: str
    compared_discovery_scopes: tuple[DiscoveryScope, ...] = field(default_factory=tuple)
    supported_discovery_scopes: tuple[DiscoveryScope, ...] = field(
        default_factory=tuple
    )
    not_supported_discovery_scopes: tuple[DiscoveryScope, ...] = field(
        default_factory=tuple
    )
    excluded_discovery_scopes: tuple[ExcludedDiscoveryScopeProjection, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        if not isinstance(self.engineering_condition, str) or (
            not self.engineering_condition
        ):
            raise ValueError("engineering_condition is required.")

        if self.classification not in {
            "SUPPORTED_IN_ALL_SCOPES",
            "SUPPORTED_IN_SOME_SCOPES",
            "SUPPORTED_IN_NO_SCOPES",
        }:
            raise ValueError("classification is not supported.")

        object.__setattr__(
            self,
            "compared_discovery_scopes",
            tuple(self.compared_discovery_scopes),
        )
        object.__setattr__(
            self,
            "supported_discovery_scopes",
            tuple(self.supported_discovery_scopes),
        )
        object.__setattr__(
            self,
            "not_supported_discovery_scopes",
            tuple(self.not_supported_discovery_scopes),
        )
        object.__setattr__(
            self,
            "excluded_discovery_scopes",
            tuple(self.excluded_discovery_scopes),
        )

        _validate_scope_population(
            self.compared_discovery_scopes,
            field_name="compared_discovery_scopes",
        )
        if not self.compared_discovery_scopes:
            raise ValueError("compared_discovery_scopes is required.")

        _validate_scope_population(
            self.supported_discovery_scopes,
            field_name="supported_discovery_scopes",
        )
        _validate_scope_population(
            self.not_supported_discovery_scopes,
            field_name="not_supported_discovery_scopes",
        )
        for excluded in self.excluded_discovery_scopes:
            if not isinstance(excluded, ExcludedDiscoveryScopeProjection):
                raise TypeError(
                    "excluded_discovery_scopes must contain "
                    "ExcludedDiscoveryScopeProjection."
                )

        supported = set(self.supported_discovery_scopes)
        not_supported = set(self.not_supported_discovery_scopes)
        compared = set(self.compared_discovery_scopes)
        excluded = {
            excluded_scope.discovery_scope
            for excluded_scope in self.excluded_discovery_scopes
        }

        if supported & not_supported:
            raise ValueError(
                "Discovery Scopes cannot be both supported and not supported."
            )

        if supported | not_supported != compared:
            raise ValueError(
                "Supported and not-supported scopes must partition compared scopes."
            )

        if excluded & compared:
            raise ValueError("Excluded scopes must not be compared scopes.")


def project_engineering_condition_support_comparison(
    comparison: EngineeringConditionSupportDistributionComparison,
) -> EngineeringConditionSupportComparisonProjection:
    if not isinstance(comparison, EngineeringConditionSupportDistributionComparison):
        raise TypeError(
            "comparison must be EngineeringConditionSupportDistributionComparison."
        )

    return EngineeringConditionSupportComparisonProjection(
        engineering_condition=comparison.engineering_condition,
        classification=comparison.classification,
        compared_discovery_scopes=tuple(
            evaluation.discovery_scope for evaluation in comparison.eligible_evaluations
        ),
        supported_discovery_scopes=tuple(
            evaluation.discovery_scope
            for evaluation in comparison.supported_evaluations
        ),
        not_supported_discovery_scopes=tuple(
            evaluation.discovery_scope
            for evaluation in comparison.not_supported_evaluations
        ),
        excluded_discovery_scopes=tuple(
            ExcludedDiscoveryScopeProjection(
                discovery_scope=excluded.evaluation.discovery_scope,
                reason=excluded.reason,
            )
            for excluded in comparison.excluded_evaluations
        ),
    )


def _validate_scope_population(
    discovery_scopes: tuple[DiscoveryScope, ...],
    *,
    field_name: str,
) -> None:
    for discovery_scope in discovery_scopes:
        if not isinstance(discovery_scope, DiscoveryScope):
            raise TypeError(f"{field_name} must contain DiscoveryScope.")

    if len(set(discovery_scopes)) != len(discovery_scopes):
        raise ValueError(f"{field_name} must not contain duplicates.")

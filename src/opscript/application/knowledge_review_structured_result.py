from dataclasses import dataclass, field

from platformiq.model import DiscoveryScope

from opscript.application.engineering_condition_public_identity import (
    EngineeringConditionPublicIdentityError,
    PublicEngineeringConditionIdentifier,
    public_identifier_for_engineering_condition,
)
from opscript.application.engineering_condition_support_comparison_projection import (
    ExcludedDiscoveryScopeProjection,
)
from opscript.application.engineering_condition_support_comparison_workflow import (
    EngineeringConditionSupportComparisonWorkflowResult,
)
from opscript.application.knowledge_review_request import KnowledgeReviewAnalysis


class KnowledgeReviewStructuredResultError(ValueError):
    pass


@dataclass(frozen=True)
class KnowledgeReviewExcludedDiscoveryScope:
    discovery_scope: DiscoveryScope
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.discovery_scope, DiscoveryScope):
            raise TypeError("discovery_scope must be DiscoveryScope.")

        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason is required.")


@dataclass(frozen=True)
class KnowledgeReviewEngineeringConditionSupportComparison:
    status: str
    classification: str | None = None
    compared_discovery_scopes: tuple[DiscoveryScope, ...] = field(default_factory=tuple)
    supported_discovery_scopes: tuple[DiscoveryScope, ...] = field(
        default_factory=tuple
    )
    not_supported_discovery_scopes: tuple[DiscoveryScope, ...] = field(
        default_factory=tuple
    )
    excluded_discovery_scopes: tuple[KnowledgeReviewExcludedDiscoveryScope, ...] = (
        field(default_factory=tuple)
    )
    reason: str = "comparison_available"

    def __post_init__(self) -> None:
        if self.status not in {"comparison_produced", "comparison_unavailable"}:
            raise ValueError("status is not supported.")

        if self.classification is not None and self.classification not in {
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

        _validate_discovery_scopes(self.compared_discovery_scopes)
        _validate_discovery_scopes(self.supported_discovery_scopes)
        _validate_discovery_scopes(self.not_supported_discovery_scopes)
        for excluded in self.excluded_discovery_scopes:
            if not isinstance(excluded, KnowledgeReviewExcludedDiscoveryScope):
                raise TypeError(
                    "excluded_discovery_scopes must contain "
                    "KnowledgeReviewExcludedDiscoveryScope."
                )

        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason is required.")

        if self.status == "comparison_produced":
            if self.classification is None:
                raise ValueError("Produced comparison requires classification.")
            if self.reason != "comparison_available":
                raise ValueError("Produced comparison reason is not supported.")
            return

        if self.classification is not None:
            raise ValueError("Unavailable comparison must not include classification.")
        if self.compared_discovery_scopes:
            raise ValueError(
                "Unavailable comparison must not include compared Discovery Scopes."
            )
        if self.supported_discovery_scopes:
            raise ValueError(
                "Unavailable comparison must not include supported Discovery Scopes."
            )
        if self.not_supported_discovery_scopes:
            raise ValueError(
                "Unavailable comparison must not include not-supported Discovery Scopes."
            )


@dataclass(frozen=True)
class KnowledgeReviewStructuredResult:
    analysis: KnowledgeReviewAnalysis
    engineering_condition_identifier: PublicEngineeringConditionIdentifier
    discovery_scopes: tuple[DiscoveryScope, ...]
    comparison: KnowledgeReviewEngineeringConditionSupportComparison

    def __post_init__(self) -> None:
        if (
            self.analysis
            != KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON
        ):
            raise ValueError("analysis is not supported.")

        if not isinstance(
            self.engineering_condition_identifier,
            PublicEngineeringConditionIdentifier,
        ):
            raise TypeError(
                "engineering_condition_identifier must be "
                "PublicEngineeringConditionIdentifier."
            )

        object.__setattr__(self, "discovery_scopes", tuple(self.discovery_scopes))
        _validate_discovery_scopes(self.discovery_scopes)

        if not isinstance(
            self.comparison,
            KnowledgeReviewEngineeringConditionSupportComparison,
        ):
            raise TypeError(
                "comparison must be KnowledgeReviewEngineeringConditionSupportComparison."
            )


def knowledge_review_structured_result_from_result(
    result: EngineeringConditionSupportComparisonWorkflowResult,
) -> KnowledgeReviewStructuredResult:
    if not isinstance(result, EngineeringConditionSupportComparisonWorkflowResult):
        raise TypeError(
            "result must be EngineeringConditionSupportComparisonWorkflowResult."
        )

    try:
        public_identifier = public_identifier_for_engineering_condition(
            result.engineering_condition
        )
    except EngineeringConditionPublicIdentityError as error:
        raise KnowledgeReviewStructuredResultError(
            "Engineering Condition identity is not supported."
        ) from error

    return KnowledgeReviewStructuredResult(
        analysis=KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON,
        engineering_condition_identifier=public_identifier,
        discovery_scopes=result.requested_scopes,
        comparison=_comparison_from_result(result),
    )


def _comparison_from_result(
    result: EngineeringConditionSupportComparisonWorkflowResult,
) -> KnowledgeReviewEngineeringConditionSupportComparison:
    if result.status == "comparison_unavailable":
        return KnowledgeReviewEngineeringConditionSupportComparison(
            status=result.status,
            excluded_discovery_scopes=tuple(
                KnowledgeReviewExcludedDiscoveryScope(
                    discovery_scope=excluded.evaluation.discovery_scope,
                    reason=excluded.reason,
                )
                for excluded in result.eligibility.excluded_evaluations
            ),
            reason=result.reason,
        )

    if result.projection is None:
        raise KnowledgeReviewStructuredResultError(
            "Completed comparison result requires projection."
        )

    return KnowledgeReviewEngineeringConditionSupportComparison(
        status=result.status,
        classification=result.projection.classification,
        compared_discovery_scopes=result.projection.compared_discovery_scopes,
        supported_discovery_scopes=result.projection.supported_discovery_scopes,
        not_supported_discovery_scopes=(
            result.projection.not_supported_discovery_scopes
        ),
        excluded_discovery_scopes=tuple(
            _excluded_scope_from_projection(excluded)
            for excluded in result.projection.excluded_discovery_scopes
        ),
        reason=result.reason,
    )


def _excluded_scope_from_projection(
    excluded: ExcludedDiscoveryScopeProjection,
) -> KnowledgeReviewExcludedDiscoveryScope:
    return KnowledgeReviewExcludedDiscoveryScope(
        discovery_scope=excluded.discovery_scope,
        reason=excluded.reason,
    )


def _validate_discovery_scopes(discovery_scopes: tuple[DiscoveryScope, ...]) -> None:
    for discovery_scope in discovery_scopes:
        if not isinstance(discovery_scope, DiscoveryScope):
            raise TypeError("discovery_scopes must contain DiscoveryScope.")

from dataclasses import dataclass
from enum import Enum

from platformiq.model import DiscoveryScope

from opscript.application.engineering_condition_public_identity import (
    EngineeringConditionPublicIdentityError,
    PublicEngineeringConditionIdentifier,
    engineering_condition_from_public_identifier,
)
from opscript.application.knowledge_review_workflow import (
    EngineeringConditionSupportComparisonSelection,
)


class KnowledgeReviewRequestError(ValueError):
    pass


class KnowledgeReviewAnalysis(str, Enum):
    ENGINEERING_CONDITION_SUPPORT_COMPARISON = (
        "ENGINEERING_CONDITION_SUPPORT_COMPARISON"
    )


@dataclass(frozen=True)
class KnowledgeReviewRequest:
    analysis: KnowledgeReviewAnalysis
    engineering_condition_identifier: PublicEngineeringConditionIdentifier
    discovery_scopes: tuple[DiscoveryScope, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.analysis, KnowledgeReviewAnalysis) or (
            self.analysis
            != KnowledgeReviewAnalysis.ENGINEERING_CONDITION_SUPPORT_COMPARISON
        ):
            raise KnowledgeReviewRequestError("Analysis selection is not supported.")

        if not isinstance(
            self.engineering_condition_identifier,
            PublicEngineeringConditionIdentifier,
        ):
            raise TypeError(
                "engineering_condition_identifier must be "
                "PublicEngineeringConditionIdentifier."
            )

        try:
            engineering_condition_from_public_identifier(
                self.engineering_condition_identifier
            )
        except EngineeringConditionPublicIdentityError as error:
            raise KnowledgeReviewRequestError(
                "Engineering Condition public identifier is not supported."
            ) from error

        object.__setattr__(self, "discovery_scopes", tuple(self.discovery_scopes))
        if len(self.discovery_scopes) < 2:
            raise KnowledgeReviewRequestError(
                "At least two Discovery Scopes are required."
            )

        if len(set(self.discovery_scopes)) != len(self.discovery_scopes):
            raise KnowledgeReviewRequestError(
                "Duplicate Discovery Scopes are not allowed."
            )

        for discovery_scope in self.discovery_scopes:
            if not isinstance(discovery_scope, DiscoveryScope):
                raise TypeError("discovery_scopes must contain DiscoveryScope.")


def knowledge_review_selection_from_request(
    request: KnowledgeReviewRequest,
) -> EngineeringConditionSupportComparisonSelection:
    if not isinstance(request, KnowledgeReviewRequest):
        raise TypeError("request must be KnowledgeReviewRequest.")

    return EngineeringConditionSupportComparisonSelection(
        engineering_condition=engineering_condition_from_public_identifier(
            request.engineering_condition_identifier
        ),
        discovery_scopes=request.discovery_scopes,
    )

from dataclasses import dataclass, field
from typing import Literal

from opscript.models import (
    RecognitionResult,
    ScopeLocalEngineeringConditionEvaluation,
)
from platformiq.model import DiscoveryScope


@dataclass(frozen=True)
class ExcludedEngineeringConditionEvaluation:
    evaluation: ScopeLocalEngineeringConditionEvaluation
    reason: Literal[
        "engineering_condition_mismatch",
        "unsupported_subject_comparison",
    ]

    def __post_init__(self) -> None:
        if not isinstance(self.evaluation, ScopeLocalEngineeringConditionEvaluation):
            raise TypeError(
                "evaluation must be ScopeLocalEngineeringConditionEvaluation."
            )

        if self.reason not in {
            "engineering_condition_mismatch",
            "unsupported_subject_comparison",
        }:
            raise ValueError("Exclusion reason is not supported.")


@dataclass(frozen=True)
class EngineeringConditionComparisonEligibility:
    requested_evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...] = field(
        default_factory=tuple
    )
    eligible_evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...] = field(
        default_factory=tuple
    )
    excluded_evaluations: tuple[ExcludedEngineeringConditionEvaluation, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "requested_evaluations",
            tuple(self.requested_evaluations),
        )
        object.__setattr__(
            self,
            "eligible_evaluations",
            tuple(self.eligible_evaluations),
        )
        object.__setattr__(
            self,
            "excluded_evaluations",
            tuple(self.excluded_evaluations),
        )

        for evaluation in self.requested_evaluations:
            if not isinstance(evaluation, ScopeLocalEngineeringConditionEvaluation):
                raise TypeError(
                    "requested_evaluations must contain "
                    "ScopeLocalEngineeringConditionEvaluation."
                )

        for evaluation in self.eligible_evaluations:
            if not isinstance(evaluation, ScopeLocalEngineeringConditionEvaluation):
                raise TypeError(
                    "eligible_evaluations must contain "
                    "ScopeLocalEngineeringConditionEvaluation."
                )

        for excluded in self.excluded_evaluations:
            if not isinstance(excluded, ExcludedEngineeringConditionEvaluation):
                raise TypeError(
                    "excluded_evaluations must contain "
                    "ExcludedEngineeringConditionEvaluation."
                )


@dataclass(frozen=True)
class EngineeringConditionSupportDistributionComparison:
    engineering_condition: str
    eligible_evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...] = field(
        default_factory=tuple
    )
    supported_evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...] = field(
        default_factory=tuple
    )
    not_supported_evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...] = (
        field(default_factory=tuple)
    )
    classification: Literal[
        "SUPPORTED_IN_ALL_SCOPES",
        "SUPPORTED_IN_SOME_SCOPES",
        "SUPPORTED_IN_NO_SCOPES",
    ] = "SUPPORTED_IN_NO_SCOPES"
    excluded_evaluations: tuple[ExcludedEngineeringConditionEvaluation, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        _validate_engineering_condition(self.engineering_condition)
        _validate_classification(self.classification)
        object.__setattr__(
            self,
            "eligible_evaluations",
            tuple(self.eligible_evaluations),
        )
        object.__setattr__(
            self,
            "supported_evaluations",
            tuple(self.supported_evaluations),
        )
        object.__setattr__(
            self,
            "not_supported_evaluations",
            tuple(self.not_supported_evaluations),
        )
        object.__setattr__(
            self,
            "excluded_evaluations",
            tuple(self.excluded_evaluations),
        )

        for evaluation in self.eligible_evaluations:
            _validate_comparison_evaluation(
                evaluation,
                engineering_condition=self.engineering_condition,
            )

        for evaluation in self.supported_evaluations:
            _validate_comparison_evaluation(
                evaluation,
                engineering_condition=self.engineering_condition,
            )

        for evaluation in self.not_supported_evaluations:
            _validate_comparison_evaluation(
                evaluation,
                engineering_condition=self.engineering_condition,
            )

        for excluded in self.excluded_evaluations:
            if not isinstance(excluded, ExcludedEngineeringConditionEvaluation):
                raise TypeError(
                    "excluded_evaluations must contain "
                    "ExcludedEngineeringConditionEvaluation."
                )


def engineering_condition_evaluation_from_recognition_result(
    recognition_result: RecognitionResult,
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome=recognition_result.outcome,
        qualified_historical_evidence=recognition_result.qualified_historical_evidence,
        engineering_condition=recognition_result.engineering_condition,
    )


def collect_scope_local_engineering_condition_evaluations(
    evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...],
    *,
    engineering_condition: str,
    discovery_scopes: tuple[DiscoveryScope, ...],
) -> tuple[ScopeLocalEngineeringConditionEvaluation, ...]:
    _validate_engineering_condition(engineering_condition)
    _validate_requested_scopes(discovery_scopes)

    evaluations_by_scope: dict[
        DiscoveryScope,
        ScopeLocalEngineeringConditionEvaluation,
    ] = {}

    for evaluation in evaluations:
        if not isinstance(evaluation, ScopeLocalEngineeringConditionEvaluation):
            raise TypeError(
                "evaluations must contain ScopeLocalEngineeringConditionEvaluation."
            )

        if evaluation.engineering_condition != engineering_condition:
            continue

        if evaluation.discovery_scope in evaluations_by_scope:
            raise ValueError(
                "Duplicate scope-local evaluations are not allowed for one condition."
            )

        evaluations_by_scope[evaluation.discovery_scope] = evaluation

    missing_scopes = tuple(
        discovery_scope
        for discovery_scope in discovery_scopes
        if discovery_scope not in evaluations_by_scope
    )
    if missing_scopes:
        raise ValueError(
            "Completed scope-local evaluation is required for every requested scope."
        )

    return tuple(evaluations_by_scope[scope] for scope in discovery_scopes)


def assess_engineering_condition_comparison_eligibility(
    evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...],
    *,
    engineering_condition: str,
) -> EngineeringConditionComparisonEligibility:
    _validate_engineering_condition(engineering_condition)

    eligible_evaluations = []
    excluded_evaluations = []

    for evaluation in evaluations:
        if not isinstance(evaluation, ScopeLocalEngineeringConditionEvaluation):
            raise TypeError(
                "evaluations must contain ScopeLocalEngineeringConditionEvaluation."
            )

        exclusion_reason = _exclusion_reason(
            evaluation,
            engineering_condition=engineering_condition,
        )
        if exclusion_reason is None:
            eligible_evaluations.append(evaluation)
            continue

        excluded_evaluations.append(
            ExcludedEngineeringConditionEvaluation(
                evaluation=evaluation,
                reason=exclusion_reason,
            )
        )

    return EngineeringConditionComparisonEligibility(
        requested_evaluations=evaluations,
        eligible_evaluations=tuple(eligible_evaluations),
        excluded_evaluations=tuple(excluded_evaluations),
    )


def compare_engineering_condition_support_distribution(
    eligibility: EngineeringConditionComparisonEligibility,
) -> EngineeringConditionSupportDistributionComparison:
    if not isinstance(eligibility, EngineeringConditionComparisonEligibility):
        raise TypeError(
            "eligibility must be EngineeringConditionComparisonEligibility."
        )

    if len(eligibility.eligible_evaluations) < 2:
        raise ValueError(
            "At least two eligible evaluations are required for comparison."
        )

    engineering_condition = _eligible_engineering_condition(
        eligibility.eligible_evaluations
    )
    supported_evaluations = tuple(
        evaluation
        for evaluation in eligibility.eligible_evaluations
        if evaluation.outcome == "supported"
    )
    not_supported_evaluations = tuple(
        evaluation
        for evaluation in eligibility.eligible_evaluations
        if evaluation.outcome == "not_supported"
    )

    return EngineeringConditionSupportDistributionComparison(
        engineering_condition=engineering_condition,
        eligible_evaluations=eligibility.eligible_evaluations,
        supported_evaluations=supported_evaluations,
        not_supported_evaluations=not_supported_evaluations,
        classification=_support_distribution_classification(
            supported_evaluations,
            not_supported_evaluations,
        ),
        excluded_evaluations=eligibility.excluded_evaluations,
    )


def _eligible_engineering_condition(
    eligible_evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...],
) -> str:
    engineering_condition = eligible_evaluations[0].engineering_condition
    for evaluation in eligible_evaluations:
        _validate_comparison_evaluation(
            evaluation,
            engineering_condition=engineering_condition,
        )

    return engineering_condition


def _support_distribution_classification(
    supported_evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...],
    not_supported_evaluations: tuple[ScopeLocalEngineeringConditionEvaluation, ...],
) -> Literal[
    "SUPPORTED_IN_ALL_SCOPES",
    "SUPPORTED_IN_SOME_SCOPES",
    "SUPPORTED_IN_NO_SCOPES",
]:
    if supported_evaluations and not_supported_evaluations:
        return "SUPPORTED_IN_SOME_SCOPES"

    if supported_evaluations:
        return "SUPPORTED_IN_ALL_SCOPES"

    return "SUPPORTED_IN_NO_SCOPES"


def _validate_comparison_evaluation(
    evaluation: ScopeLocalEngineeringConditionEvaluation,
    *,
    engineering_condition: str,
) -> None:
    if not isinstance(evaluation, ScopeLocalEngineeringConditionEvaluation):
        raise TypeError(
            "evaluations must contain ScopeLocalEngineeringConditionEvaluation."
        )

    if evaluation.engineering_condition != engineering_condition:
        raise ValueError("Eligible evaluations must share one Engineering Condition.")


def _validate_classification(classification: str) -> None:
    if classification not in {
        "SUPPORTED_IN_ALL_SCOPES",
        "SUPPORTED_IN_SOME_SCOPES",
        "SUPPORTED_IN_NO_SCOPES",
    }:
        raise ValueError("Support distribution classification is not supported.")


def _exclusion_reason(
    evaluation: ScopeLocalEngineeringConditionEvaluation,
    *,
    engineering_condition: str,
) -> (
    Literal[
        "engineering_condition_mismatch",
        "unsupported_subject_comparison",
    ]
    | None
):
    if evaluation.engineering_condition != engineering_condition:
        return "engineering_condition_mismatch"

    if (
        engineering_condition
        == RecognitionResult.frequent_infrastructure_modification_condition
    ):
        return "unsupported_subject_comparison"

    return None


def _validate_engineering_condition(engineering_condition: str) -> None:
    if engineering_condition not in {
        RecognitionResult.frequent_infrastructure_modification_condition,
        RecognitionResult.recurring_infrastructure_removal_activity_condition,
        RecognitionResult.recurring_infrastructure_introduction_activity_condition,
    }:
        raise ValueError("Engineering condition is not supported.")


def _validate_requested_scopes(discovery_scopes: tuple[DiscoveryScope, ...]) -> None:
    if not discovery_scopes:
        raise ValueError("At least one Discovery Scope is required.")

    if len(set(discovery_scopes)) != len(discovery_scopes):
        raise ValueError("Duplicate Discovery Scopes are not allowed.")

    for discovery_scope in discovery_scopes:
        if not isinstance(discovery_scope, DiscoveryScope):
            raise TypeError("discovery_scopes must contain DiscoveryScope.")

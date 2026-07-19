from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from platformiq.analysis import SnapshotDiffer
from platformiq.model import DiscoveryScope

from opscript.application.analysis_service import AnalysisService
from opscript.application.engineering_condition_evaluation import (
    EngineeringConditionComparisonEligibility,
    assess_engineering_condition_comparison_eligibility,
    collect_scope_local_engineering_condition_evaluations,
    compare_engineering_condition_support_distribution,
    engineering_condition_evaluation_from_recognition_result,
)
from opscript.application.engineering_condition_support_comparison_projection import (
    EngineeringConditionSupportComparisonProjection,
    project_engineering_condition_support_comparison,
)
from opscript.application.frequent_infrastructure_modification_rule import (
    FrequentInfrastructureModificationRule,
)
from opscript.application.qualified_historical_evidence_service import (
    build_qualified_historical_evidence,
    canonical_subject_from_history,
    scope_level_qualified_historical_evidence,
)
from opscript.application.recurring_infrastructure_introduction_activity_rule import (
    RecurringInfrastructureIntroductionActivityRule,
)
from opscript.application.recurring_infrastructure_removal_activity_rule import (
    RecurringInfrastructureRemovalActivityRule,
)
from opscript.models import (
    QualifiedHistoricalEvidence,
    RecognitionResult,
    ScopeLocalEngineeringConditionEvaluation,
)


@dataclass(frozen=True)
class EngineeringConditionSupportComparisonWorkflowResult:
    status: Literal["comparison_produced", "comparison_unavailable"]
    engineering_condition: str
    requested_scopes: tuple[DiscoveryScope, ...]
    eligibility: EngineeringConditionComparisonEligibility
    projection: EngineeringConditionSupportComparisonProjection | None = None
    reason: str = "comparison_available"

    def __post_init__(self) -> None:
        if self.status not in {"comparison_produced", "comparison_unavailable"}:
            raise ValueError("Workflow result status is not supported.")

        if self.engineering_condition not in _SUPPORTED_ENGINEERING_CONDITIONS:
            raise ValueError("Engineering condition is not supported.")

        object.__setattr__(self, "requested_scopes", tuple(self.requested_scopes))
        for discovery_scope in self.requested_scopes:
            if not isinstance(discovery_scope, DiscoveryScope):
                raise TypeError("requested_scopes must contain DiscoveryScope.")

        if not isinstance(self.eligibility, EngineeringConditionComparisonEligibility):
            raise TypeError(
                "eligibility must be EngineeringConditionComparisonEligibility."
            )

        if self.status == "comparison_produced":
            if not isinstance(
                self.projection, EngineeringConditionSupportComparisonProjection
            ):
                raise TypeError(
                    "Completed workflow result requires a comparison projection."
                )
            if self.reason != "comparison_available":
                raise ValueError("Completed workflow result reason is not supported.")
            return

        if self.projection is not None:
            raise ValueError("Unavailable workflow result must not include projection.")
        if self.reason != "insufficient_eligible_evaluations":
            raise ValueError("Unavailable workflow result reason is not supported.")


class EngineeringConditionSupportComparisonWorkflowError(ValueError):
    pass


class EngineeringConditionSupportComparisonWorkflow:
    def __init__(
        self,
        *,
        storage_factory: Callable[[DiscoveryScope], object],
        analysis_service: AnalysisService | None = None,
    ):
        self.storage_factory = storage_factory
        self.analysis_service = analysis_service or AnalysisService(SnapshotDiffer())

    def run(
        self,
        *,
        engineering_condition: str,
        discovery_scopes: tuple[DiscoveryScope, ...],
    ) -> EngineeringConditionSupportComparisonWorkflowResult:
        _validate_engineering_condition(engineering_condition)
        _validate_requested_scopes(discovery_scopes)

        evaluations = tuple(
            self._evaluate_scope(
                discovery_scope,
                engineering_condition=engineering_condition,
            )
            for discovery_scope in discovery_scopes
        )
        collected = collect_scope_local_engineering_condition_evaluations(
            evaluations,
            engineering_condition=engineering_condition,
            discovery_scopes=discovery_scopes,
        )
        eligibility = assess_engineering_condition_comparison_eligibility(
            collected,
            engineering_condition=engineering_condition,
        )

        if len(eligibility.eligible_evaluations) < 2:
            return EngineeringConditionSupportComparisonWorkflowResult(
                status="comparison_unavailable",
                engineering_condition=engineering_condition,
                requested_scopes=discovery_scopes,
                eligibility=eligibility,
                reason="insufficient_eligible_evaluations",
            )

        comparison = compare_engineering_condition_support_distribution(eligibility)
        projection = project_engineering_condition_support_comparison(comparison)
        return EngineeringConditionSupportComparisonWorkflowResult(
            status="comparison_produced",
            engineering_condition=engineering_condition,
            requested_scopes=discovery_scopes,
            eligibility=eligibility,
            projection=projection,
        )

    def _evaluate_scope(
        self,
        discovery_scope: DiscoveryScope,
        *,
        engineering_condition: str,
    ) -> ScopeLocalEngineeringConditionEvaluation:
        storage = self.storage_factory(discovery_scope)
        history = storage.load_history()
        analysis_history = self.analysis_service.analyze_history(history)
        evidence = build_qualified_historical_evidence(
            analysis_history,
            discovery_scope=discovery_scope,
            canonical_subject=canonical_subject_from_history(analysis_history),
        )
        recognition_result = _evaluate_engineering_condition(
            engineering_condition,
            evidence,
        )
        return engineering_condition_evaluation_from_recognition_result(
            recognition_result
        )


def _evaluate_engineering_condition(
    engineering_condition: str,
    evidence: QualifiedHistoricalEvidence,
) -> RecognitionResult:
    if (
        engineering_condition
        == RecognitionResult.frequent_infrastructure_modification_condition
    ):
        return FrequentInfrastructureModificationRule().evaluate(evidence)

    scope_level_evidence = scope_level_qualified_historical_evidence(evidence)

    if (
        engineering_condition
        == RecognitionResult.recurring_infrastructure_removal_activity_condition
    ):
        return RecurringInfrastructureRemovalActivityRule().evaluate(
            scope_level_evidence
        )

    return RecurringInfrastructureIntroductionActivityRule().evaluate(
        scope_level_evidence
    )


_SUPPORTED_ENGINEERING_CONDITIONS = {
    RecognitionResult.frequent_infrastructure_modification_condition,
    RecognitionResult.recurring_infrastructure_removal_activity_condition,
    RecognitionResult.recurring_infrastructure_introduction_activity_condition,
}


def _validate_engineering_condition(engineering_condition: str) -> None:
    if engineering_condition not in _SUPPORTED_ENGINEERING_CONDITIONS:
        raise EngineeringConditionSupportComparisonWorkflowError(
            "Engineering condition is not supported."
        )


def _validate_requested_scopes(discovery_scopes: tuple[DiscoveryScope, ...]) -> None:
    if len(discovery_scopes) < 2:
        raise EngineeringConditionSupportComparisonWorkflowError(
            "At least two Discovery Scopes are required."
        )

    if len(set(discovery_scopes)) != len(discovery_scopes):
        raise EngineeringConditionSupportComparisonWorkflowError(
            "Duplicate Discovery Scopes are not allowed."
        )

    for discovery_scope in discovery_scopes:
        if not isinstance(discovery_scope, DiscoveryScope):
            raise TypeError("discovery_scopes must contain DiscoveryScope.")

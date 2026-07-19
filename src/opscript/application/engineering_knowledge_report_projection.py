from dataclasses import dataclass
from typing import TYPE_CHECKING

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope

from opscript.models import RecognizedFinding, ServiceResult

if TYPE_CHECKING:
    from opscript.application.engineering_knowledge_evolution_comparison_service import (
        EngineeringKnowledgeEvolutionComparison,
    )
    from opscript.application.engineering_knowledge_sequence_analysis_service import (
        EngineeringKnowledgeSequenceAnalysisResult,
    )


_RECOGNITION_BASIS_BY_ENGINEERING_CONDITION = {
    "frequent_infrastructure_modification": (
        "Qualified historical evidence demonstrated repeated modification of the "
        "reported subject across the qualified observation window."
    ),
    "recurring_infrastructure_removal_activity": (
        "Qualified historical evidence demonstrated recurring infrastructure "
        "removal activity across the qualified observation window for the "
        "Discovery Scope."
    ),
    "recurring_infrastructure_introduction_activity": (
        "Qualified historical evidence demonstrated recurring infrastructure "
        "introduction activity across the qualified observation window for the "
        "Discovery Scope."
    ),
}


@dataclass(frozen=True)
class EngineeringKnowledgeReportEntry:
    """
    Projects recognized findings into structured report entries.
    """

    engineering_condition: str
    recognition_outcome: str
    discovery_scope: DiscoveryScope
    canonical_subject: str | None
    recognition_basis: str
    observation_window_previous_snapshot_id: Identifier
    observation_window_current_snapshot_id: Identifier
    recognition_threshold: int
    minimum_completed_interval_count: int


@dataclass
class EngineeringKnowledgeServiceResult(ServiceResult):
    supported_engineering_conditions: tuple[EngineeringKnowledgeReportEntry, ...]
    engineering_knowledge_evolution: "EngineeringKnowledgeEvolutionComparison | None" = None
    engineering_knowledge_sequence_analysis: "EngineeringKnowledgeSequenceAnalysisResult | None" = None
    earlier_qualified_evaluation: "EngineeringKnowledgeEvaluationContext | None" = None
    later_qualified_evaluation: "EngineeringKnowledgeEvaluationContext | None" = None
    engineering_knowledge_evolution_unavailable_message: str | None = None


@dataclass(frozen=True)
class EngineeringKnowledgeEvaluationContext:
    discovery_scope: DiscoveryScope
    observation_window_previous_snapshot_id: Identifier
    observation_window_current_snapshot_id: Identifier


def project_engineering_knowledge_report(
    recognized_findings: tuple[RecognizedFinding, ...],
) -> tuple[EngineeringKnowledgeReportEntry, ...]:
    return tuple(
        _entry_from_recognized_finding(recognized_finding)
        for recognized_finding in recognized_findings
    )


def _entry_from_recognized_finding(
    recognized_finding: RecognizedFinding,
) -> EngineeringKnowledgeReportEntry:
    if not isinstance(recognized_finding, RecognizedFinding):
        raise TypeError("recognized_findings must contain RecognizedFinding instances.")

    recognition_result = recognized_finding.recognition_result
    evidence = recognition_result.qualified_historical_evidence

    return EngineeringKnowledgeReportEntry(
        engineering_condition=recognition_result.engineering_condition,
        recognition_outcome=recognition_result.outcome,
        discovery_scope=evidence.discovery_scope,
        canonical_subject=evidence.canonical_subject,
        recognition_basis=_recognition_basis(recognition_result.engineering_condition),
        observation_window_previous_snapshot_id=(
            evidence.observation_window_previous_snapshot_id
        ),
        observation_window_current_snapshot_id=(
            evidence.observation_window_current_snapshot_id
        ),
        recognition_threshold=recognition_result.recognition_threshold,
        minimum_completed_interval_count=(
            recognition_result.minimum_completed_interval_count
        ),
    )


def _recognition_basis(engineering_condition: str) -> str:
    try:
        return _RECOGNITION_BASIS_BY_ENGINEERING_CONDITION[engineering_condition]
    except KeyError as exc:
        raise ValueError(
            "Engineering condition has no approved recognition basis."
        ) from exc

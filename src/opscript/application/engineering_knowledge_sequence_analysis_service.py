from dataclasses import dataclass, field

from platformiq.model import DiscoveryScope

from opscript.application.engineering_knowledge_report_projection import (
    EngineeringKnowledgeEvaluationContext,
    EngineeringKnowledgeReportEntry,
)


@dataclass(frozen=True)
class EngineeringKnowledgeSequenceAnalysis:
    engineering_condition: str
    discovery_scope: DiscoveryScope
    canonical_subject: str | None
    sequence_start_evaluation: EngineeringKnowledgeEvaluationContext
    sequence_end_evaluation: EngineeringKnowledgeEvaluationContext
    qualified_evaluation_count: int
    supported_at_sequence_start: bool
    supported_at_sequence_end: bool
    continuously_supported: bool
    newly_supported: bool
    no_longer_supported: bool
    reappeared: bool


ENGINEERING_KNOWLEDGE_SEQUENCE_ANALYSIS_UNAVAILABLE_MESSAGE = (
    "Engineering Knowledge Sequence Analysis is unavailable because a qualified "
    "compatible evaluation sequence could not be established."
)


@dataclass(frozen=True)
class EngineeringKnowledgeSequenceAnalysisResult:
    availability: str
    analysis: EngineeringKnowledgeSequenceAnalysis | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        if self.availability not in {"available", "unavailable"}:
            raise ValueError(
                "Engineering Knowledge Sequence Analysis availability is invalid."
            )

        if self.availability == "available" and self.analysis is None:
            raise ValueError(
                "Available Engineering Knowledge Sequence Analysis requires analysis."
            )

        if self.availability == "unavailable" and self.message is None:
            raise ValueError(
                "Unavailable Engineering Knowledge Sequence Analysis requires message."
            )


@dataclass(frozen=True)
class EngineeringKnowledgeSequenceEvaluation:
    report_entries: tuple[EngineeringKnowledgeReportEntry, ...] = field(
        default_factory=tuple
    )
    context: EngineeringKnowledgeEvaluationContext | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_entries", tuple(self.report_entries))


class EngineeringKnowledgeSequenceAnalysisService:
    def analyze(
        self,
        evaluations: tuple[EngineeringKnowledgeSequenceEvaluation, ...],
    ) -> EngineeringKnowledgeSequenceAnalysisResult:
        evaluations = tuple(evaluations)
        if len(evaluations) < 2:
            return _unavailable_result()

        _validate_evaluations(evaluations)

        supported_by_identity = tuple(
            _supported_identities(evaluation) for evaluation in evaluations
        )
        identities = sorted(set().union(*supported_by_identity))

        if not identities:
            return _unavailable_result()

        return EngineeringKnowledgeSequenceAnalysisResult(
            availability="available",
            analysis=_sequence_analysis(
                identities[0],
                evaluations,
                supported_by_identity,
            ),
        )


def _unavailable_result() -> EngineeringKnowledgeSequenceAnalysisResult:
    return EngineeringKnowledgeSequenceAnalysisResult(
        availability="unavailable",
        message=ENGINEERING_KNOWLEDGE_SEQUENCE_ANALYSIS_UNAVAILABLE_MESSAGE,
    )


def _validate_evaluations(
    evaluations: tuple[EngineeringKnowledgeSequenceEvaluation, ...],
) -> None:
    first_context = evaluations[0].context
    if first_context is None:
        raise ValueError("Engineering Knowledge sequence evaluation requires context.")

    previous_window = first_context.observation_window_previous_snapshot_id

    for evaluation in evaluations:
        context = evaluation.context
        if context is None:
            raise ValueError(
                "Engineering Knowledge sequence evaluation requires context."
            )

        if context.discovery_scope != first_context.discovery_scope:
            raise ValueError(
                "Engineering Knowledge sequence evaluations must share Discovery Scope."
            )

        if context.observation_window_previous_snapshot_id != previous_window:
            raise ValueError(
                "Engineering Knowledge sequence evaluations must share a sequence start."
            )

        for entry in evaluation.report_entries:
            if entry.discovery_scope != context.discovery_scope:
                raise ValueError(
                    "Engineering Knowledge entry Discovery Scope must match evaluation."
                )
            if (
                entry.observation_window_previous_snapshot_id
                != context.observation_window_previous_snapshot_id
                or entry.observation_window_current_snapshot_id
                != context.observation_window_current_snapshot_id
            ):
                raise ValueError(
                    "Engineering Knowledge entry observation window must match evaluation."
                )


def _supported_identities(
    evaluation: EngineeringKnowledgeSequenceEvaluation,
) -> dict[tuple[str, str, str], EngineeringKnowledgeReportEntry]:
    entries: dict[tuple[str, str, str], EngineeringKnowledgeReportEntry] = {}

    for entry in evaluation.report_entries:
        identity = _identity(entry)
        if identity in entries:
            raise ValueError(
                "Engineering Knowledge sequence evaluation contains duplicate identities."
            )
        entries[identity] = entry

    return entries


def _sequence_analysis(
    identity: tuple[str, str, str],
    evaluations: tuple[EngineeringKnowledgeSequenceEvaluation, ...],
    supported_by_identity: tuple[
        dict[tuple[str, str, str], EngineeringKnowledgeReportEntry], ...
    ],
) -> EngineeringKnowledgeSequenceAnalysis:
    support_states = tuple(
        identity in identities for identities in supported_by_identity
    )
    representative = next(
        identities[identity]
        for identities in supported_by_identity
        if identity in identities
    )

    return EngineeringKnowledgeSequenceAnalysis(
        engineering_condition=representative.engineering_condition,
        discovery_scope=representative.discovery_scope,
        canonical_subject=representative.canonical_subject,
        sequence_start_evaluation=evaluations[0].context,
        sequence_end_evaluation=evaluations[-1].context,
        qualified_evaluation_count=len(evaluations),
        supported_at_sequence_start=support_states[0],
        supported_at_sequence_end=support_states[-1],
        continuously_supported=all(support_states),
        newly_supported=_has_transition(support_states, before=False, after=True),
        no_longer_supported=_has_transition(support_states, before=True, after=False),
        reappeared=_has_reappearance(support_states),
    )


def _identity(
    entry: EngineeringKnowledgeReportEntry,
) -> tuple[str, str, str]:
    return (
        entry.engineering_condition,
        entry.discovery_scope.value,
        entry.canonical_subject or "",
    )


def _has_transition(
    support_states: tuple[bool, ...],
    *,
    before: bool,
    after: bool,
) -> bool:
    return any(
        previous is before and current is after
        for previous, current in zip(support_states, support_states[1:], strict=False)
    )


def _has_reappearance(support_states: tuple[bool, ...]) -> bool:
    saw_supported = False
    saw_unsupported_after_supported = False

    for supported in support_states:
        if supported and saw_unsupported_after_supported:
            return True
        if supported:
            saw_supported = True
        elif saw_supported:
            saw_unsupported_after_supported = True

    return False

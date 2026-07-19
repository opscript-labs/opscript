from dataclasses import dataclass
from time import perf_counter

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope

from opscript.application import (
    HistoryValidationError,
    HistoryValidator,
    WorkflowMetricsFactory,
    WorkflowOutcome,
)
from opscript.application.engineering_knowledge_report_projection import (
    EngineeringKnowledgeEvaluationContext,
    EngineeringKnowledgeReportEntry,
    project_engineering_knowledge_report,
)
from opscript.application.engineering_knowledge_sequence_analysis_service import (
    EngineeringKnowledgeSequenceAnalysis,
    EngineeringKnowledgeSequenceAnalysisResult,
    EngineeringKnowledgeSequenceAnalysisService,
    EngineeringKnowledgeSequenceEvaluation,
)
from opscript.application.engineering_knowledge_evolution_comparison_service import (
    EngineeringKnowledgeEvolutionComparison,
    EngineeringKnowledgeEvolutionComparisonService,
)
from opscript.application.engineering_condition_support_comparison_formatter import (
    format_engineering_condition_support_comparison,
)
from opscript.application.engineering_condition_support_comparison_workflow import (
    EngineeringConditionSupportComparisonWorkflow,
    EngineeringConditionSupportComparisonWorkflowResult,
)
from opscript.application.knowledge_evaluation_workflow import (
    evaluate_engineering_knowledge,
)
from opscript.application.qualified_historical_evidence_service import (
    build_qualified_historical_evidence,
    canonical_subject_from_history,
)
from opscript.application.workflow_execution import WorkflowExecution
from opscript.bootstrap import (
    build_analysis_service,
    build_config,
    build_snapshot_storage,
    build_snapshot_storage_for_discovery_scope,
)
from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger
from opscript.storage import SnapshotStorageError

logger = get_logger()


WORKFLOW_NAME = "knowledge_review"


@dataclass(frozen=True)
class KnowledgeReviewWorkflowOutcome(WorkflowOutcome):
    report_entries: tuple[EngineeringKnowledgeReportEntry, ...] = ()
    discovery_scope: DiscoveryScope | None = None
    observation_window_previous_snapshot_id: Identifier | None = None
    observation_window_current_snapshot_id: Identifier | None = None
    engineering_knowledge_evolution: EngineeringKnowledgeEvolutionComparison | None = (
        None
    )
    engineering_knowledge_sequence_analysis: (
        EngineeringKnowledgeSequenceAnalysisResult | None
    ) = None
    earlier_qualified_evaluation: EngineeringKnowledgeEvaluationContext | None = None
    later_qualified_evaluation: EngineeringKnowledgeEvaluationContext | None = None
    engineering_knowledge_evolution_unavailable_message: str | None = None


@dataclass(frozen=True)
class _EngineeringKnowledgeEvaluation:
    report_entries: tuple[EngineeringKnowledgeReportEntry, ...]
    context: EngineeringKnowledgeEvaluationContext


@dataclass(frozen=True)
class EngineeringConditionSupportComparisonSelection:
    engineering_condition: str
    discovery_scopes: tuple[DiscoveryScope, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "discovery_scopes", tuple(self.discovery_scopes))
        if not isinstance(self.engineering_condition, str) or (
            not self.engineering_condition
        ):
            raise ValueError("engineering_condition is required.")

        for discovery_scope in self.discovery_scopes:
            if not isinstance(discovery_scope, DiscoveryScope):
                raise TypeError("discovery_scopes must contain DiscoveryScope.")


ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE = (
    "Engineering Knowledge Evolution is unavailable because fewer than two "
    "qualified Engineering Knowledge evaluations are available for comparison."
)


def run_knowledge_review_workflow_outcome(
    snapshot_storage=None,
    config=None,
    include_engineering_knowledge_evolution: bool = False,
    include_engineering_knowledge_sequence_analysis: bool = False,
    engineering_condition_support_comparison_selection: (
        EngineeringConditionSupportComparisonSelection | None
    ) = None,
    comparison_service: EngineeringKnowledgeEvolutionComparisonService | None = None,
    sequence_analysis_service: EngineeringKnowledgeSequenceAnalysisService
    | None = None,
    engineering_condition_support_comparison_workflow: (
        EngineeringConditionSupportComparisonWorkflow | None
    ) = None,
) -> KnowledgeReviewWorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow=WORKFLOW_NAME),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "history_loading"
    try:
        execution = _run_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        logger.error(
            format_log_event(
                "workflow_failed",
                **_workflow_lifecycle_fields(
                    workflow=WORKFLOW_NAME,
                    phase=current_phase,
                    reason="snapshot_storage_error",
                    duration_ms=_duration_ms(workflow_started_at),
                ),
            )
        )
        return f"Knowledge review failed: {error}"

    snapshots = execution.value

    current_phase = "history_validation"
    try:
        _run_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        logger.error(
            format_log_event(
                "workflow_failed",
                **_workflow_lifecycle_fields(
                    workflow=WORKFLOW_NAME,
                    phase=current_phase,
                    reason="validation_error",
                    duration_ms=_duration_ms(workflow_started_at),
                ),
            )
        )
        return f"Knowledge review failed: {error}"

    current_phase = "engineering_knowledge_evaluation"
    (
        analysis_history,
        discovery_scope,
        observation_window_previous_snapshot_id,
        observation_window_current_snapshot_id,
        report_entries,
        qualified_evaluations,
    ) = _run_workflow_phase(
        current_phase,
        lambda: _evaluate_current_engineering_knowledge(
            snapshots,
            config=config,
        ),
        workflow_started_at=workflow_started_at,
    )

    engineering_knowledge_evolution = None
    engineering_knowledge_sequence_analysis = None
    earlier_qualified_evaluation = None
    later_qualified_evaluation = None
    engineering_knowledge_evolution_unavailable_message = None
    engineering_condition_support_comparison = None

    if include_engineering_knowledge_evolution:
        current_phase = "engineering_knowledge_evolution"
        (
            engineering_knowledge_evolution,
            earlier_qualified_evaluation,
            later_qualified_evaluation,
            engineering_knowledge_evolution_unavailable_message,
        ) = _run_workflow_phase(
            current_phase,
            lambda: _evaluate_engineering_knowledge_evolution(
                qualified_evaluations,
                comparison_service=comparison_service,
            ),
            workflow_started_at=workflow_started_at,
        )

    if include_engineering_knowledge_sequence_analysis:
        current_phase = "engineering_knowledge_sequence_analysis"
        engineering_knowledge_sequence_analysis = _run_workflow_phase(
            current_phase,
            lambda: (
                sequence_analysis_service
                or EngineeringKnowledgeSequenceAnalysisService()
            ).analyze(
                tuple(
                    EngineeringKnowledgeSequenceEvaluation(
                        report_entries=evaluation.report_entries,
                        context=evaluation.context,
                    )
                    for evaluation in qualified_evaluations
                )
            ),
            workflow_started_at=workflow_started_at,
        )

    if engineering_condition_support_comparison_selection is not None:
        current_phase = "engineering_condition_support_comparison"
        engineering_condition_support_comparison = _run_workflow_phase(
            current_phase,
            lambda: _evaluate_engineering_condition_support_comparison(
                engineering_condition_support_comparison_selection,
                config=config,
                workflow=engineering_condition_support_comparison_workflow,
            ),
            workflow_started_at=workflow_started_at,
        )

    current_phase = "report_projection"
    report = _run_workflow_phase(
        current_phase,
        lambda: render_engineering_knowledge_report(
            report_entries,
            engineering_knowledge_evolution=engineering_knowledge_evolution,
            engineering_knowledge_sequence_analysis=(
                engineering_knowledge_sequence_analysis
            ),
            earlier_qualified_evaluation=earlier_qualified_evaluation,
            later_qualified_evaluation=later_qualified_evaluation,
            engineering_knowledge_evolution_unavailable_message=(
                engineering_knowledge_evolution_unavailable_message
            ),
            engineering_condition_support_comparison=(
                engineering_condition_support_comparison
            ),
        ),
        workflow_started_at=workflow_started_at,
    )

    metrics = WorkflowMetricsFactory().create(
        workflow_name=WORKFLOW_NAME,
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "comparisons": len(analysis_history),
            "supported_conditions": len(report_entries),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow=WORKFLOW_NAME,
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                comparisons=metrics.measurements["comparisons"],
                supported_conditions=metrics.measurements["supported_conditions"],
            ),
        )
    )

    return KnowledgeReviewWorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
        report_entries=report_entries,
        discovery_scope=discovery_scope,
        observation_window_previous_snapshot_id=observation_window_previous_snapshot_id,
        observation_window_current_snapshot_id=observation_window_current_snapshot_id,
        engineering_knowledge_evolution=engineering_knowledge_evolution,
        engineering_knowledge_sequence_analysis=engineering_knowledge_sequence_analysis,
        earlier_qualified_evaluation=earlier_qualified_evaluation,
        later_qualified_evaluation=later_qualified_evaluation,
        engineering_knowledge_evolution_unavailable_message=(
            engineering_knowledge_evolution_unavailable_message
        ),
    )


def run_knowledge_review_workflow(
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_knowledge_review_workflow_outcome(
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def _duration_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def _workflow_lifecycle_fields(**fields: object) -> dict[str, object]:
    return {
        **active_execution_log_fields(),
        **fields,
    }


def _workflow_phase_lifecycle_fields(**fields: object) -> dict[str, object]:
    return {
        **active_execution_log_fields(),
        **fields,
    }


def _run_phase(phase: str, operation, *, failure_reason: str = "workflow_error"):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow=WORKFLOW_NAME,
                phase=phase,
            ),
        )
    )

    try:
        result = operation()
    except Exception:
        _log_phase_failed(
            phase,
            started_at=phase_started_at,
            reason=failure_reason,
        )
        raise

    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow=WORKFLOW_NAME,
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def _run_workflow_phase(
    phase: str,
    operation,
    *,
    workflow_started_at: float,
):
    try:
        return _run_phase(phase, operation)
    except Exception:
        _log_workflow_failed(
            phase,
            workflow_started_at=workflow_started_at,
            reason="workflow_error",
        )
        raise


def _log_phase_failed(
    phase: str,
    *,
    started_at: float | None = None,
    reason: str = "workflow_error",
) -> None:
    fields = {
        "workflow": WORKFLOW_NAME,
        "phase": phase,
        "reason": reason,
    }
    if started_at is not None:
        fields["duration_ms"] = _duration_ms(started_at)

    logger.error(
        format_log_event(
            "workflow_phase_failed",
            **_workflow_phase_lifecycle_fields(**fields),
        )
    )


def _log_workflow_failed(
    phase: str,
    *,
    workflow_started_at: float,
    reason: str,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow=WORKFLOW_NAME,
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _evaluate_current_engineering_knowledge(
    snapshots,
    *,
    config,
):
    analysis = build_analysis_service(config=config)
    analysis_history = analysis.analyze_history(snapshots)

    discovery_scope = snapshots[0].discovery_scope if snapshots else None
    observation_window_previous_snapshot_id = None
    observation_window_current_snapshot_id = None

    qualified_evaluations = _qualified_engineering_knowledge_evaluations(
        analysis_history,
        discovery_scope=discovery_scope,
    )

    if not qualified_evaluations:
        report_entries: tuple[EngineeringKnowledgeReportEntry, ...] = ()
    else:
        current_evaluation = qualified_evaluations[-1]
        observation_window_previous_snapshot_id = (
            current_evaluation.context.observation_window_previous_snapshot_id
        )
        observation_window_current_snapshot_id = (
            current_evaluation.context.observation_window_current_snapshot_id
        )
        report_entries = current_evaluation.report_entries

    return (
        analysis_history,
        discovery_scope,
        observation_window_previous_snapshot_id,
        observation_window_current_snapshot_id,
        report_entries,
        qualified_evaluations,
    )


def _evaluate_engineering_knowledge_evolution(
    qualified_evaluations: tuple[_EngineeringKnowledgeEvaluation, ...],
    *,
    comparison_service: EngineeringKnowledgeEvolutionComparisonService | None,
):
    if len(qualified_evaluations) < 2:
        return (
            None,
            None,
            None,
            ENGINEERING_KNOWLEDGE_EVOLUTION_UNAVAILABLE_MESSAGE,
        )

    earlier_evaluation = qualified_evaluations[-2]
    later_evaluation = qualified_evaluations[-1]
    engineering_knowledge_evolution = (
        comparison_service or EngineeringKnowledgeEvolutionComparisonService()
    ).compare(
        earlier_evaluation.report_entries,
        later_evaluation.report_entries,
    )

    return (
        engineering_knowledge_evolution,
        earlier_evaluation.context,
        later_evaluation.context,
        None,
    )


def _evaluate_engineering_condition_support_comparison(
    selection: EngineeringConditionSupportComparisonSelection,
    *,
    config,
    workflow: EngineeringConditionSupportComparisonWorkflow | None,
) -> EngineeringConditionSupportComparisonWorkflowResult:
    if workflow is not None:
        return workflow.run(
            engineering_condition=selection.engineering_condition,
            discovery_scopes=selection.discovery_scopes,
        )

    active_config = config or build_config()
    active_config.validate()

    comparison_workflow = EngineeringConditionSupportComparisonWorkflow(
        storage_factory=lambda discovery_scope: (
            build_snapshot_storage_for_discovery_scope(
                active_config,
                discovery_scope,
            )
        ),
        analysis_service=build_analysis_service(active_config),
    )

    return comparison_workflow.run(
        engineering_condition=selection.engineering_condition,
        discovery_scopes=selection.discovery_scopes,
    )


def render_engineering_knowledge_report(
    report_entries: tuple[EngineeringKnowledgeReportEntry, ...],
    engineering_knowledge_evolution: EngineeringKnowledgeEvolutionComparison
    | None = None,
    engineering_knowledge_sequence_analysis: (
        EngineeringKnowledgeSequenceAnalysisResult | None
    ) = None,
    earlier_qualified_evaluation: EngineeringKnowledgeEvaluationContext | None = None,
    later_qualified_evaluation: EngineeringKnowledgeEvaluationContext | None = None,
    engineering_knowledge_evolution_unavailable_message: str | None = None,
    engineering_condition_support_comparison: (
        EngineeringConditionSupportComparisonWorkflowResult | None
    ) = None,
) -> str:
    title = "Engineering Knowledge"

    if not report_entries:
        report = "\n".join(
            [
                title,
                "",
                "No Engineering Conditions were supported by the qualified historical evidence.",
            ]
        )
        return _append_engineering_condition_support_comparison(
            _append_engineering_knowledge_evolution(
                _append_engineering_knowledge_sequence_analysis(
                    report,
                    engineering_knowledge_sequence_analysis,
                ),
                engineering_knowledge_evolution,
                earlier_qualified_evaluation=earlier_qualified_evaluation,
                later_qualified_evaluation=later_qualified_evaluation,
                engineering_knowledge_evolution_unavailable_message=(
                    engineering_knowledge_evolution_unavailable_message
                ),
            ),
            engineering_condition_support_comparison,
        )

    lines = [title]

    for entry in report_entries:
        lines.extend(
            [
                "",
                "Supported Engineering Condition:",
                f"    {entry.engineering_condition}",
                "",
                "Recognition Basis:",
                f"    {entry.recognition_basis}",
                "",
                "Discovery Scope:",
                f"    {entry.discovery_scope}",
            ]
        )

        if entry.canonical_subject is not None:
            lines.extend(
                [
                    "",
                    "Subject:",
                    f"    {entry.canonical_subject}",
                ]
            )

        lines.extend(
            [
                "",
                "Observation Window:",
                "",
                f"{entry.observation_window_previous_snapshot_id}",
                "",
                "↓",
                "",
                f"{entry.observation_window_current_snapshot_id}",
            ]
        )

    return _append_engineering_condition_support_comparison(
        _append_engineering_knowledge_evolution(
            _append_engineering_knowledge_sequence_analysis(
                "\n".join(lines),
                engineering_knowledge_sequence_analysis,
            ),
            engineering_knowledge_evolution,
            earlier_qualified_evaluation=earlier_qualified_evaluation,
            later_qualified_evaluation=later_qualified_evaluation,
            engineering_knowledge_evolution_unavailable_message=(
                engineering_knowledge_evolution_unavailable_message
            ),
        ),
        engineering_condition_support_comparison,
    )


def _append_engineering_knowledge_sequence_analysis(
    report: str,
    result: EngineeringKnowledgeSequenceAnalysisResult | None,
) -> str:
    if result is None:
        return report

    lines = [
        report,
        "",
        "Engineering Knowledge Sequence Analysis",
    ]

    if result.availability == "unavailable":
        lines.extend(["", result.message])
        return "\n".join(lines)

    lines.extend(_engineering_knowledge_sequence_analysis_section(result.analysis))

    return "\n".join(lines)


def _engineering_knowledge_sequence_analysis_section(
    analysis: EngineeringKnowledgeSequenceAnalysis,
) -> list[str]:
    lines = [
        "",
        "Supported Engineering Condition:",
        f"    {analysis.engineering_condition}",
        "",
        "Discovery Scope:",
        f"    {analysis.discovery_scope}",
    ]

    if analysis.canonical_subject is not None:
        lines.extend(
            [
                "",
                "Subject:",
                f"    {analysis.canonical_subject}",
            ]
        )

    lines.extend(
        [
            "",
            "Qualified Evaluation Sequence",
            "",
            "Sequence Start Evaluation:",
            f"    {analysis.sequence_start_evaluation.observation_window_current_snapshot_id}",
            "",
            "Sequence End Evaluation:",
            f"    {analysis.sequence_end_evaluation.observation_window_current_snapshot_id}",
            "",
            "Qualified Evaluation Count:",
            f"    {analysis.qualified_evaluation_count}",
            "",
            "Support State at Sequence Start:",
            f"    {_support_state(analysis.supported_at_sequence_start)}",
            "",
            "Support State at Sequence End:",
            f"    {_support_state(analysis.supported_at_sequence_end)}",
        ]
    )

    if analysis.continuously_supported:
        lines.extend(
            ["", "Continuously supported across the qualified evaluation sequence."]
        )

    if analysis.newly_supported:
        lines.extend(["", "Newly supported"])

    if analysis.no_longer_supported:
        lines.extend(["", "No longer supported"])

    if analysis.reappeared:
        lines.extend(["", "Reappeared"])

    if (
        not analysis.continuously_supported
        and not analysis.newly_supported
        and not analysis.no_longer_supported
        and not analysis.reappeared
    ):
        lines.extend(
            [
                "",
                "No additional approved support-state pattern was established across the qualified evaluation sequence.",
            ]
        )

    return lines


def _support_state(supported: bool) -> str:
    if supported:
        return "supported"

    return "unsupported"


def _append_engineering_condition_support_comparison(
    report: str,
    result: EngineeringConditionSupportComparisonWorkflowResult | None,
) -> str:
    if result is None:
        return report

    if result.status != "comparison_produced" or result.projection is None:
        return report

    return "\n".join(
        [
            report,
            "",
            format_engineering_condition_support_comparison(result.projection),
        ]
    )


def _append_engineering_knowledge_evolution(
    report: str,
    engineering_knowledge_evolution: EngineeringKnowledgeEvolutionComparison | None,
    *,
    earlier_qualified_evaluation: EngineeringKnowledgeEvaluationContext | None = None,
    later_qualified_evaluation: EngineeringKnowledgeEvaluationContext | None = None,
    engineering_knowledge_evolution_unavailable_message: str | None = None,
) -> str:
    if engineering_knowledge_evolution_unavailable_message is not None:
        return "\n".join(
            [
                report,
                "",
                "Engineering Knowledge Evolution",
                "",
                engineering_knowledge_evolution_unavailable_message,
            ]
        )

    if engineering_knowledge_evolution is None:
        return report

    lines = [
        report,
        "",
        "Engineering Knowledge Evolution",
    ]

    if (
        earlier_qualified_evaluation is not None
        and later_qualified_evaluation is not None
    ):
        lines.extend(
            _engineering_knowledge_evaluation_context_section(
                "Earlier Qualified Evaluation",
                earlier_qualified_evaluation,
            )
        )
        lines.extend(
            _engineering_knowledge_evaluation_context_section(
                "Later Qualified Evaluation",
                later_qualified_evaluation,
            )
        )

    if (
        not engineering_knowledge_evolution.introduced
        and not engineering_knowledge_evolution.removed
        and not engineering_knowledge_evolution.unchanged
    ):
        lines.extend(
            [
                "",
                "No change in supported Engineering Knowledge was identified between the compared qualified evaluations.",
            ]
        )
        return "\n".join(lines)

    if engineering_knowledge_evolution.introduced:
        lines.extend(
            _engineering_knowledge_evolution_section(
                "Introduced Supported Engineering Conditions",
                engineering_knowledge_evolution.introduced,
            )
        )

    if engineering_knowledge_evolution.removed:
        lines.extend(
            _engineering_knowledge_evolution_section(
                "Removed Supported Engineering Conditions",
                engineering_knowledge_evolution.removed,
            )
        )

    if engineering_knowledge_evolution.unchanged:
        lines.extend(
            _engineering_knowledge_evolution_section(
                "Unchanged Supported Engineering Conditions",
                tuple(
                    unchanged.evaluation_b
                    for unchanged in engineering_knowledge_evolution.unchanged
                ),
            )
        )

    return "\n".join(lines)


def _engineering_knowledge_evolution_section(
    title: str,
    entries: tuple[EngineeringKnowledgeReportEntry, ...],
) -> list[str]:
    lines = ["", title]

    for entry in entries:
        lines.extend(
            [
                "",
                "Supported Engineering Condition:",
                f"    {entry.engineering_condition}",
                "",
                "Discovery Scope:",
                f"    {entry.discovery_scope}",
            ]
        )

        if entry.canonical_subject is not None:
            lines.extend(
                [
                    "",
                    "Subject:",
                    f"    {entry.canonical_subject}",
                ]
            )

    return lines


def _engineering_knowledge_evaluation_context_section(
    title: str,
    context: EngineeringKnowledgeEvaluationContext,
) -> list[str]:
    return [
        "",
        title,
        "",
        "Discovery Scope:",
        f"    {context.discovery_scope}",
        "",
        "Qualified Observation Window:",
        "",
        f"{context.observation_window_previous_snapshot_id}",
        "",
        "â†“",
        "",
        f"{context.observation_window_current_snapshot_id}",
    ]


def compare_engineering_knowledge_evaluations(
    evaluation_a: KnowledgeReviewWorkflowOutcome,
    evaluation_b: KnowledgeReviewWorkflowOutcome,
    *,
    comparison_service: EngineeringKnowledgeEvolutionComparisonService | None = None,
) -> EngineeringKnowledgeEvolutionComparison:
    _validate_completed_evaluation(evaluation_a)
    _validate_completed_evaluation(evaluation_b)

    service = comparison_service or EngineeringKnowledgeEvolutionComparisonService()
    return service.compare(evaluation_a.report_entries, evaluation_b.report_entries)


def _validate_completed_evaluation(
    evaluation: KnowledgeReviewWorkflowOutcome,
) -> None:
    if evaluation.discovery_scope is None:
        raise ValueError("Engineering Knowledge evaluation requires Discovery Scope.")

    if (
        evaluation.observation_window_previous_snapshot_id is None
        or evaluation.observation_window_current_snapshot_id is None
    ):
        raise ValueError(
            "Engineering Knowledge evaluation requires an observation window."
        )

    for entry in evaluation.report_entries:
        if entry.discovery_scope != evaluation.discovery_scope:
            raise ValueError(
                "Engineering Knowledge entry Discovery Scope must match evaluation."
            )

        if (
            entry.observation_window_previous_snapshot_id
            != evaluation.observation_window_previous_snapshot_id
            or entry.observation_window_current_snapshot_id
            != evaluation.observation_window_current_snapshot_id
        ):
            raise ValueError(
                "Engineering Knowledge entry observation window must match evaluation."
            )


def _qualified_engineering_knowledge_evaluations(
    analysis_history,
    *,
    discovery_scope,
) -> tuple[_EngineeringKnowledgeEvaluation, ...]:
    if discovery_scope is None:
        return ()

    return tuple(
        evaluation
        for evaluation in (
            _try_engineering_knowledge_evaluation(
                analysis_history[:window_end],
                discovery_scope=discovery_scope,
            )
            for window_end in range(1, len(analysis_history) + 1)
        )
        if evaluation is not None
    )


def _try_engineering_knowledge_evaluation(
    analysis_history,
    *,
    discovery_scope,
) -> _EngineeringKnowledgeEvaluation | None:
    try:
        return _engineering_knowledge_evaluation(
            analysis_history,
            discovery_scope=discovery_scope,
        )
    except ValueError as error:
        if "requires at least four completed intervals" in str(error):
            return None
        raise


def _engineering_knowledge_evaluation(
    analysis_history,
    *,
    discovery_scope,
) -> _EngineeringKnowledgeEvaluation:
    evidence = build_qualified_historical_evidence(
        analysis_history,
        discovery_scope=discovery_scope,
        canonical_subject=canonical_subject_from_history(analysis_history),
    )
    return _EngineeringKnowledgeEvaluation(
        report_entries=project_engineering_knowledge_report(
            tuple(evaluate_engineering_knowledge(evidence))
        ),
        context=EngineeringKnowledgeEvaluationContext(
            discovery_scope=discovery_scope,
            observation_window_previous_snapshot_id=(
                evidence.observation_window_previous_snapshot_id
            ),
            observation_window_current_snapshot_id=(
                evidence.observation_window_current_snapshot_id
            ),
        ),
    )

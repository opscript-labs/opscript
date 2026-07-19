from dataclasses import replace
from platformiq.core import Identifier
from platformiq.errors.provider import ProviderError
from platformiq.model import Snapshot
from time import perf_counter

from opscript.application import (
    FindingExplanationError,
    HistoryValidationError,
    HistoryValidator,
    InfrastructureChangeSummaryService,
    WorkflowMetricsFactory,
    WorkflowOutcome,
    render_workflow_outcome_explanations,
)
from opscript.application.workflow_execution import WorkflowExecution
from opscript.application.knowledge_review_workflow import (
    run_knowledge_review_workflow_outcome,
)
from opscript.application.engineering_knowledge_report_projection import (
    EngineeringKnowledgeServiceResult,
)
from opscript.bootstrap import (
    build_analysis_service,
    build_inventory_service,
    build_reporting_service,
    build_snapshot_storage,
)
from opscript.errors import OpscriptProviderError
from opscript.execution import active_execution_log_fields
from opscript.formatter import format_output
from opscript.logger import format_log_event, get_logger
from opscript.models import Failure, ServiceResult, Success
from opscript.storage import SnapshotStorageError

logger = get_logger()

DEFAULT_CHURN_REPORT_LIMIT = 20


def _duration_ms(
    started_at: float,
) -> int:
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


def _log_observation_workflow_phase_started(phase: str) -> None:
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="observation",
                phase=phase,
            ),
        )
    )


def _log_observation_workflow_phase_completed(phase: str, duration_ms: int) -> None:
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="observation",
                phase=phase,
                duration_ms=duration_ms,
            ),
        )
    )


def _log_observation_workflow_phase_failed(
    phase: str,
    *,
    reason: str,
    duration_ms: int,
) -> None:
    logger.error(
        format_log_event(
            "workflow_phase_failed",
            **_workflow_phase_lifecycle_fields(
                workflow="observation",
                phase=phase,
                reason=reason,
                duration_ms=duration_ms,
            ),
        )
    )


def _run_observation_workflow_phase(phase: str, operation):
    phase_started_at = perf_counter()
    _log_observation_workflow_phase_started(phase)
    try:
        result = operation()
    except ProviderError:
        _log_observation_workflow_phase_failed(
            phase,
            reason="provider_error",
            duration_ms=_duration_ms(phase_started_at),
        )
        raise
    except SnapshotStorageError:
        _log_observation_workflow_phase_failed(
            phase,
            reason="snapshot_storage_error",
            duration_ms=_duration_ms(phase_started_at),
        )
        raise
    except Exception:
        _log_observation_workflow_phase_failed(
            phase,
            reason="internal_error",
            duration_ms=_duration_ms(phase_started_at),
        )
        raise
    _log_observation_workflow_phase_completed(
        phase,
        _duration_ms(phase_started_at),
    )
    return result


def _log_resource_evolution_workflow_phase_started(phase: str) -> None:
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="resource_evolution",
                phase=phase,
            ),
        )
    )


def _log_resource_evolution_workflow_phase_completed(
    phase: str,
    duration_ms: int,
) -> None:
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="resource_evolution",
                phase=phase,
                duration_ms=duration_ms,
            ),
        )
    )


def _log_resource_evolution_workflow_phase_failed(
    phase: str,
    *,
    reason: str,
    duration_ms: int,
) -> None:
    logger.error(
        format_log_event(
            "workflow_phase_failed",
            **_workflow_phase_lifecycle_fields(
                workflow="resource_evolution",
                phase=phase,
                reason=reason,
                duration_ms=duration_ms,
            ),
        )
    )


def _log_resource_evolution_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="resource_evolution",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_resource_evolution_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    _log_resource_evolution_workflow_phase_started(phase)
    try:
        result = operation()
    except Exception:
        _log_resource_evolution_workflow_phase_failed(
            phase,
            reason=failure_reason,
            duration_ms=_duration_ms(phase_started_at),
        )
        raise
    _log_resource_evolution_workflow_phase_completed(
        phase,
        _duration_ms(phase_started_at),
    )
    return result


def _log_environment_evolution_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="environment_evolution",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_environment_evolution_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="environment_evolution",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="environment_evolution",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="environment_evolution",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def _log_change_frequency_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="change_frequency",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_change_frequency_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="change_frequency",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="change_frequency",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="change_frequency",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def _log_instability_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="instability",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_instability_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="instability",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="instability",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="instability",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def _log_activity_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="activity",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_activity_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="activity",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="activity",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="activity",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def _log_stability_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="stability",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_stability_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="stability",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="stability",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="stability",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def _log_metadata_grouping_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="metadata_grouping",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_metadata_grouping_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="metadata_grouping",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="metadata_grouping",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="metadata_grouping",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def _log_inventory_history_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="inventory_history",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_inventory_history_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="inventory_history",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="inventory_history",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="inventory_history",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def _log_workflow_failed(
    *,
    workflow: str,
    phase: str,
    reason: str,
    error: Exception,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow=workflow,
                phase=phase,
                reason=reason,
                error=error,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def run_observation_workflow_outcome(
    discovery_provider=None,
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    current_phase = "latest_snapshot_loading"
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="observation"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    try:
        previous_snapshot = _run_observation_workflow_phase(
            current_phase,
            storage.load_latest,
        )
    except SnapshotStorageError as error:
        _log_workflow_failed(
            workflow="observation",
            phase=current_phase,
            reason="snapshot_storage_error",
            error=error,
            workflow_started_at=workflow_started_at,
        )
        return f"Infrastructure observation failed: {error}"

    current_phase = "current_snapshot_collection"
    inventory = build_inventory_service(
        discovery_provider=discovery_provider,
        snapshot_storage=storage,
        config=config,
    )

    try:
        execution = _run_observation_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(inventory.collect_snapshot),
        )
    except ProviderError as error:
        failure_fields = {
            "workflow": "observation",
            "reason": "provider_error",
            "phase": current_phase,
            "duration_ms": _duration_ms(workflow_started_at),
        }
        if isinstance(error, OpscriptProviderError):
            failure_fields["failure_category"] = error.category.name
        logger.error(
            format_log_event(
                "workflow_failed",
                **_workflow_lifecycle_fields(**failure_fields),
            )
        )
        return f"Infrastructure observation failed: {error}"
    except SnapshotStorageError as error:
        _log_workflow_failed(
            workflow="observation",
            phase=current_phase,
            reason="snapshot_storage_error",
            error=error,
            workflow_started_at=workflow_started_at,
        )
        return f"Infrastructure observation failed: {error}"

    current_snapshot = execution.value
    if previous_snapshot is None:
        previous_snapshot = Snapshot(
            id=Identifier.new(),
            discovery_scope=current_snapshot.discovery_scope,
        )

    current_phase = "change_analysis"
    try:
        analysis_result = _run_observation_workflow_phase(
            current_phase,
            lambda: build_analysis_service(config=config).analyze_full(
                previous_snapshot,
                current_snapshot,
            ),
        )
    except Exception as error:
        _log_workflow_failed(
            workflow="observation",
            phase=current_phase,
            reason="internal_error",
            error=error,
            workflow_started_at=workflow_started_at,
        )
        return f"Infrastructure observation failed: {error}"

    current_phase = "change_report_projection"
    try:
        report = _run_observation_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_infrastructure_change_summary_report(
                InfrastructureChangeSummaryService().summarize(analysis_result)
            ),
        )
    except Exception as error:
        _log_workflow_failed(
            workflow="observation",
            phase=current_phase,
            reason="internal_error",
            error=error,
            workflow_started_at=workflow_started_at,
        )
        return f"Infrastructure observation failed: {error}"

    metrics = WorkflowMetricsFactory().create(
        workflow_name="observation",
        execution=execution,
        measurements={
            "resources": len(current_snapshot.resources),
            "observations": len(analysis_result.observations),
            "findings": len(analysis_result.findings),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="observation",
                duration_ms=metrics.duration_ms,
                resources=metrics.measurements["resources"],
                observations=metrics.measurements["observations"],
                findings=metrics.measurements["findings"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
        analysis_result=analysis_result,
    )


def run_observation_workflow(
    discovery_provider=None,
    snapshot_storage=None,
) -> str:
    outcome = run_observation_workflow_outcome(
        discovery_provider=discovery_provider,
        snapshot_storage=snapshot_storage,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_resource_evolution_workflow_outcome(
    resource_external_id: str,
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(
                workflow="resource_evolution",
                resource=resource_external_id,
            ),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_resource_evolution_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        logger.error(
            format_log_event(
                "workflow_failed",
                **_workflow_lifecycle_fields(
                    workflow="resource_evolution",
                    phase=current_phase,
                    reason="snapshot_storage_error",
                    duration_ms=_duration_ms(workflow_started_at),
                ),
            )
        )
        return f"Resource evolution failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_resource_evolution_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        logger.error(
            format_log_event(
                "workflow_failed",
                **_workflow_lifecycle_fields(
                    workflow="resource_evolution",
                    phase=current_phase,
                    reason="validation_error",
                    duration_ms=_duration_ms(workflow_started_at),
                ),
            )
        )
        return f"Resource evolution failed: {error}"

    current_phase = "historical_analysis"

    def analyze_resource_evolution():
        analysis = build_analysis_service(config=config)
        history = analysis.analyze_history(snapshots)
        filtered_history = analysis.filter_history_for_resource(
            history,
            resource_external_id,
        )
        change_history = analysis.analyze_resource_change_history(
            history,
            resource_external_id,
        )
        return history, filtered_history, change_history

    try:
        history, filtered_history, change_history = (
            _run_resource_evolution_workflow_phase(
                current_phase,
                analyze_resource_evolution,
                failure_reason="analysis_error",
            )
        )
    except Exception:
        _log_resource_evolution_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_resource_evolution_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_resource_evolution_report(
                resource_external_id,
                filtered_history,
                change_history,
            ),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_resource_evolution_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="resource_evolution",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "comparisons": len(history),
            "matched_comparisons": len(filtered_history),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="resource_evolution",
                duration_ms=metrics.duration_ms,
                resource=resource_external_id,
                snapshots=metrics.measurements["snapshots"],
                comparisons=metrics.measurements["comparisons"],
                matched_comparisons=metrics.measurements["matched_comparisons"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def run_resource_evolution_workflow(
    resource_external_id: str,
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_resource_evolution_workflow_outcome(
        resource_external_id,
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_environment_evolution_workflow_outcome(
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="environment_evolution"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_environment_evolution_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_environment_evolution_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Environment evolution failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_environment_evolution_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_environment_evolution_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Environment evolution failed: {error}"

    current_phase = "historical_analysis"

    def analyze_environment_evolution():
        analysis = build_analysis_service(config=config)
        history = analysis.analyze_history(snapshots)
        latest_change_index = analysis.analyze_latest_environment_change(history)
        return history, latest_change_index

    try:
        history, latest_change_index = _run_environment_evolution_workflow_phase(
            current_phase,
            analyze_environment_evolution,
            failure_reason="analysis_error",
        )
    except Exception:
        _log_environment_evolution_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_environment_evolution_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_environment_evolution_report(
                history,
                latest_change_index,
            ),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_environment_evolution_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="environment_evolution",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "comparisons": len(history),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="environment_evolution",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                comparisons=metrics.measurements["comparisons"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def run_environment_evolution_workflow(
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_environment_evolution_workflow_outcome(
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_instability_workflow_outcome(
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="instability"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_instability_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_instability_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Instability concentration failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_instability_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_instability_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Instability concentration failed: {error}"

    current_phase = "historical_analysis"

    def analyze_instability():
        analysis = build_analysis_service(config=config)
        history = analysis.analyze_history(snapshots)
        instability_summary = analysis.analyze_instability_concentration(history)
        return history, instability_summary

    try:
        analysis_history, summary = _run_instability_workflow_phase(
            current_phase,
            analyze_instability,
            failure_reason="analysis_error",
        )
    except Exception:
        _log_instability_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_instability_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_instability_concentration_report(summary),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_instability_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="instability",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "comparisons": len(analysis_history),
            "resources": len(summary.resource_summaries),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="instability",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                comparisons=metrics.measurements["comparisons"],
                resources=metrics.measurements["resources"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def run_instability_workflow(
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_instability_workflow_outcome(
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_stability_workflow_outcome(
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="stability"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_stability_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_stability_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Environment stability trend failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_stability_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_stability_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Environment stability trend failed: {error}"

    current_phase = "historical_analysis"

    def analyze_stability():
        analysis = build_analysis_service(config=config)
        history = analysis.analyze_history(snapshots)
        stability_trend = analysis.analyze_environment_stability_trend(history)
        return history, stability_trend

    try:
        analysis_history, trend = _run_stability_workflow_phase(
            current_phase,
            analyze_stability,
            failure_reason="analysis_error",
        )
    except Exception:
        _log_stability_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_stability_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_environment_stability_trend_report(trend),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_stability_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="stability",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "comparisons": len(analysis_history),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="stability",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                comparisons=metrics.measurements["comparisons"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def run_stability_workflow(
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_stability_workflow_outcome(
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_activity_workflow_outcome(
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="activity"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_activity_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_activity_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Operational activity dominance failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_activity_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_activity_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Operational activity dominance failed: {error}"

    current_phase = "historical_analysis"

    def analyze_activity():
        analysis = build_analysis_service(config=config)
        history = analysis.analyze_history(snapshots)
        activity_summary = analysis.analyze_operational_activity_dominance(history)
        return history, activity_summary

    try:
        analysis_history, summary = _run_activity_workflow_phase(
            current_phase,
            analyze_activity,
            failure_reason="analysis_error",
        )
    except Exception:
        _log_activity_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_activity_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_operational_activity_dominance_report(summary),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_activity_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="activity",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "comparisons": len(analysis_history),
            "activities": len(summary.activity_summaries),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="activity",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                comparisons=metrics.measurements["comparisons"],
                activities=metrics.measurements["activities"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def run_activity_workflow(
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_activity_workflow_outcome(
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_change_frequency_workflow_outcome(
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="change_frequency"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_change_frequency_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_change_frequency_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Resource change frequency failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_change_frequency_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_change_frequency_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Resource change frequency failed: {error}"

    current_phase = "historical_analysis"
    try:
        summary = _run_change_frequency_workflow_phase(
            current_phase,
            lambda: build_analysis_service(
                config=config
            ).analyze_resource_change_frequency(snapshots),
            failure_reason="analysis_error",
        )
    except Exception:
        _log_change_frequency_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_change_frequency_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_resource_change_frequency_report(summary),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_change_frequency_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="change_frequency",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "resources": len(summary.resource_summaries),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="change_frequency",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                resources=metrics.measurements["resources"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def run_change_frequency_workflow(
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_change_frequency_workflow_outcome(
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def _log_churn_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="churn",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_churn_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="churn",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="churn",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="churn",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def run_churn_workflow_outcome(
    snapshot_storage=None,
    report_limit: int | None = None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="churn"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_churn_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_churn_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Resource churn trend failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_churn_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_churn_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Resource churn trend failed: {error}"

    current_phase = "historical_analysis"
    try:
        analysis_history, summary = _run_churn_workflow_phase(
            current_phase,
            lambda: _analyze_churn(snapshots, config=config),
            failure_reason="analysis_error",
        )
    except Exception:
        _log_churn_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_churn_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_resource_churn_trend_report(
                summary,
                limit=report_limit,
            ),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_churn_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="churn",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "comparisons": len(analysis_history),
            "resources": len(summary.resource_trends),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="churn",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                comparisons=metrics.measurements["comparisons"],
                resources=metrics.measurements["resources"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def _analyze_churn(
    snapshots,
    *,
    config=None,
):
    analysis = build_analysis_service(config=config)
    analysis_history = analysis.analyze_history(snapshots)
    summary = analysis.analyze_resource_churn_trends(analysis_history)
    return analysis_history, summary


def run_churn_workflow(
    snapshot_storage=None,
    report_limit: int | None = None,
    config=None,
) -> str:
    outcome = run_churn_workflow_outcome(
        snapshot_storage=snapshot_storage,
        report_limit=report_limit,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_metadata_grouping_workflow_outcome(
    metadata_path: str,
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="metadata_grouping"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_metadata_grouping_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_metadata_grouping_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Resource metadata grouping failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_metadata_grouping_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_metadata_grouping_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Resource metadata grouping failed: {error}"

    current_phase = "historical_analysis"
    try:
        groups = _run_metadata_grouping_workflow_phase(
            current_phase,
            lambda: build_analysis_service(
                config=config
            ).analyze_resource_metadata_groups(
                snapshots,
                metadata_path,
            ),
            failure_reason="analysis_error",
        )
    except Exception:
        _log_metadata_grouping_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_metadata_grouping_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_resource_metadata_grouping_report(groups),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_metadata_grouping_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="metadata_grouping",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "groups": len(groups),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="metadata_grouping",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                groups=metrics.measurements["groups"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def run_metadata_grouping_workflow(
    metadata_path: str,
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_metadata_grouping_workflow_outcome(
        metadata_path,
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def _log_observation_history_workflow_failed(
    phase: str,
    *,
    reason: str,
    workflow_started_at: float,
) -> None:
    logger.error(
        format_log_event(
            "workflow_failed",
            **_workflow_lifecycle_fields(
                workflow="observation_history",
                phase=phase,
                reason=reason,
                duration_ms=_duration_ms(workflow_started_at),
            ),
        )
    )


def _run_observation_history_workflow_phase(
    phase: str,
    operation,
    *,
    failure_reason: str,
):
    phase_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_phase_started",
            **_workflow_phase_lifecycle_fields(
                workflow="observation_history",
                phase=phase,
            ),
        )
    )
    try:
        result = operation()
    except Exception:
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow="observation_history",
                    phase=phase,
                    reason=failure_reason,
                    duration_ms=_duration_ms(phase_started_at),
                ),
            )
        )
        raise
    logger.info(
        format_log_event(
            "workflow_phase_completed",
            **_workflow_phase_lifecycle_fields(
                workflow="observation_history",
                phase=phase,
                duration_ms=_duration_ms(phase_started_at),
            ),
        )
    )
    return result


def run_observation_history_workflow_outcome(
    resource_external_id: str | None = None,
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="observation_history"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_observation_history_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_observation_history_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Resource observation history failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_observation_history_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_observation_history_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Resource observation history failed: {error}"

    current_phase = "historical_analysis"
    try:
        summaries = _run_observation_history_workflow_phase(
            current_phase,
            lambda: _analyze_observation_history(
                snapshots,
                resource_external_id,
                config=config,
            ),
            failure_reason="analysis_error",
        )
    except Exception:
        _log_observation_history_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_observation_history_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_resource_observation_history_report(summaries),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_observation_history_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="observation_history",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "resources": len(summaries),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="observation_history",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                resources=metrics.measurements["resources"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def _analyze_observation_history(
    snapshots,
    resource_external_id: str | None,
    *,
    config=None,
):
    analysis = build_analysis_service(config=config)
    summaries = analysis.analyze_resource_observation_history(snapshots)
    if resource_external_id is not None:
        summaries = tuple(
            summary
            for summary in summaries
            if summary.resource_external_id == resource_external_id
        )
    return summaries


def run_observation_history_workflow(
    resource_external_id: str | None = None,
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_observation_history_workflow_outcome(
        resource_external_id,
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_inventory_history_workflow_outcome(
    snapshot_storage=None,
    config=None,
) -> WorkflowOutcome | str:
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(workflow="inventory_history"),
        )
    )

    storage = snapshot_storage or build_snapshot_storage(config=config)

    current_phase = "historical_evidence_loading"
    try:
        execution = _run_inventory_history_workflow_phase(
            current_phase,
            lambda: WorkflowExecution().run(lambda: storage.load_history()),
            failure_reason="snapshot_storage_error",
        )
    except SnapshotStorageError as error:
        _log_inventory_history_workflow_failed(
            current_phase,
            reason="snapshot_storage_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Historical inventory timeline failed: {error}"

    snapshots = execution.value

    current_phase = "historical_evidence_validation"
    try:
        _run_inventory_history_workflow_phase(
            current_phase,
            lambda: HistoryValidator().validate(snapshots),
            failure_reason="validation_error",
        )
    except HistoryValidationError as error:
        _log_inventory_history_workflow_failed(
            current_phase,
            reason="validation_error",
            workflow_started_at=workflow_started_at,
        )
        return f"Historical inventory timeline failed: {error}"

    current_phase = "historical_analysis"
    try:
        observations = _run_inventory_history_workflow_phase(
            current_phase,
            lambda: build_analysis_service(
                config=config
            ).analyze_historical_inventory_timeline(snapshots),
            failure_reason="analysis_error",
        )
    except Exception:
        _log_inventory_history_workflow_failed(
            current_phase,
            reason="analysis_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    current_phase = "historical_report_projection"
    try:
        report = _run_inventory_history_workflow_phase(
            current_phase,
            lambda: build_reporting_service(
                config=config
            ).generate_historical_inventory_timeline_report(observations),
            failure_reason="report_projection_error",
        )
    except Exception:
        _log_inventory_history_workflow_failed(
            current_phase,
            reason="report_projection_error",
            workflow_started_at=workflow_started_at,
        )
        raise

    metrics = WorkflowMetricsFactory().create(
        workflow_name="inventory_history",
        execution=execution,
        measurements={
            "snapshots": len(snapshots),
            "observations": len(observations),
        },
    )

    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="inventory_history",
                duration_ms=metrics.duration_ms,
                snapshots=metrics.measurements["snapshots"],
                observations=metrics.measurements["observations"],
            ),
        )
    )

    return WorkflowOutcome(
        report=report,
        execution=execution,
        metrics=metrics,
    )


def run_inventory_history_workflow(
    snapshot_storage=None,
    config=None,
) -> str:
    outcome = run_inventory_history_workflow_outcome(
        snapshot_storage=snapshot_storage,
        config=config,
    )

    if isinstance(outcome, str):
        return outcome

    return outcome.report


def run_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript run failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_observation_workflow_outcome(config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def explain_command(args, config=None):
    logger.info(
        format_log_event(
            "explain_started",
            workflow="explain",
            **active_execution_log_fields(),
        )
    )

    if args.fail:
        result = Failure(error="Opscript explain failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_observation_workflow_outcome(config=config)

    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    subject = getattr(args, "subject", None)
    if subject is not None:
        matching_findings = tuple(
            finding
            for finding in outcome.analysis_result.findings
            if finding.subject == subject
        )
        outcome = replace(
            outcome,
            analysis_result=replace(
                outcome.analysis_result,
                findings=matching_findings,
            ),
        )

    try:
        explanations = render_workflow_outcome_explanations(outcome)
    except FindingExplanationError as error:
        logger.error(
            format_log_event(
                "explain_failed",
                workflow="explain",
                phase="explanation_rendering",
                reason="finding_explanation_error",
                **active_execution_log_fields(),
            )
        )
        result = Failure(error=f"Finding explanation failed: {error}")
        output = format_output(result, json_mode=args.json)
        return result, output

    logger.info(
        format_log_event(
            "explain_explanations_rendered",
            workflow="explain",
            phase="explanation_rendering",
            explanation_count=len(outcome.analysis_result.findings),
        )
    )

    if explanations:
        output = "\n\n".join(
            (
                outcome.report,
                "Finding Explanations:",
                explanations,
            )
        )
    elif subject is not None:
        output = "\n\n".join(
            (
                outcome.report,
                "Finding Explanations:",
                f"No findings found for subject '{subject}'.",
            )
        )
    else:
        output = "\n\n".join(
            (
                outcome.report,
                "Finding Explanations:",
                "No finding explanations available.",
            )
        )

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def resource_evolution_command(args, config=None):
    outcome = run_resource_evolution_workflow_outcome(
        args.resource_external_id,
        config=config,
    )
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def environment_evolution_command(args, config=None):
    outcome = run_environment_evolution_workflow_outcome(config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def instability_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript instability failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_instability_workflow_outcome(config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def stability_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript stability failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_stability_workflow_outcome(config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def activity_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript activity failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_activity_workflow_outcome(config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def change_frequency_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript change-frequency failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_change_frequency_workflow_outcome(config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def churn_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript churn failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    report_limit = None if args.all else DEFAULT_CHURN_REPORT_LIMIT
    outcome = run_churn_workflow_outcome(report_limit=report_limit, config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def knowledge_review_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript knowledge-review failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_knowledge_review_workflow_outcome(
        config=config,
        include_engineering_knowledge_evolution=getattr(args, "evolution", False),
        include_engineering_knowledge_sequence_analysis=getattr(
            args,
            "sequence",
            False,
        ),
    )
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    result = Success(
        value=EngineeringKnowledgeServiceResult(
            message=outcome.report,
            supported_engineering_conditions=outcome.report_entries,
            engineering_knowledge_evolution=outcome.engineering_knowledge_evolution,
            engineering_knowledge_sequence_analysis=(
                outcome.engineering_knowledge_sequence_analysis
            ),
            earlier_qualified_evaluation=outcome.earlier_qualified_evaluation,
            later_qualified_evaluation=outcome.later_qualified_evaluation,
            engineering_knowledge_evolution_unavailable_message=(
                outcome.engineering_knowledge_evolution_unavailable_message
            ),
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def metadata_grouping_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript metadata-grouping failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_metadata_grouping_workflow_outcome(args.metadata, config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def observation_history_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript observation-history failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_observation_history_workflow_outcome(
        args.resource_external_id,
        config=config,
    )
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def inventory_history_command(args, config=None):
    if args.fail:
        result = Failure(error="Opscript inventory-history failed")
        output = format_output(result, json_mode=args.json)
        return result, output

    outcome = run_inventory_history_workflow_outcome(config=config)
    if isinstance(outcome, str):
        result = Failure(error=outcome)
        output = format_output(result, json_mode=args.json)
        return result, output

    output = outcome.report

    result = Success(
        value=ServiceResult(
            message=output,
        )
    )

    output = format_output(result, json_mode=args.json)

    return result, output


def version_command(args):
    try:
        from opscript._version import __version__
    except ModuleNotFoundError as error:
        if error.name != "opscript._version":
            raise

        from importlib.metadata import version

        __version__ = version("opscript")

    result = Success(value=ServiceResult(message=f"opscript v{__version__}"))

    output = format_output(result, json_mode=args.json)
    return result, output


def inventory_command(args, config=None):
    json_mode = getattr(args, "json", False)

    try:
        inventory = build_inventory_service(config=config)
        current_snapshot = inventory.collect_snapshot()
    except ProviderError as error:
        result = Failure(error=f"Inventory collection failed: {error}")
        output = format_output(result, json_mode=json_mode)
        return result, output
    except SnapshotStorageError as error:
        result = Failure(error=f"Inventory collection failed: {error}")
        output = format_output(result, json_mode=json_mode)
        return result, output

    result = Success(
        value=ServiceResult(
            message=f"Inventory collected: {len(current_snapshot.resources)} resources",
        )
    )

    output = format_output(result, json_mode=json_mode)

    return result, output


def cross_scope_activity_command(args, config=None):
    from platformiq.model import DiscoveryScope
    from opscript.bootstrap import build_discovery_scope_activity_workflow
    from opscript.application.discovery_scope_activity_workflow import (
        DiscoveryScopeActivityWorkflowError,
    )
    from opscript.models import DiscoveryScopeActivityServiceResult

    json_mode = getattr(args, "json", False)
    scopes = getattr(args, "comparison_discovery_scopes", None) or []
    workflow_started_at = perf_counter()
    logger.info(
        format_log_event(
            "workflow_started",
            **_workflow_lifecycle_fields(
                workflow="cross_scope_activity",
                discovery_scopes=",".join(scopes),
            ),
        )
    )

    # Check duplicate scopes explicitly at CLI boundary
    if len(scopes) != len(set(scopes)):
        logger.error(
            format_log_event(
                "workflow_failed",
                **_workflow_lifecycle_fields(
                    workflow="cross_scope_activity",
                    reason="duplicate_discovery_scopes",
                    duration_ms=_duration_ms(workflow_started_at),
                ),
            )
        )
        result = Failure(error="Duplicate Discovery Scopes are not allowed.")
        output = format_output(result, json_mode=json_mode)
        return result, output

    # Check fewer than two scopes explicitly at CLI boundary
    if len(scopes) < 2:
        logger.error(
            format_log_event(
                "workflow_failed",
                **_workflow_lifecycle_fields(
                    workflow="cross_scope_activity",
                    reason="insufficient_discovery_scopes",
                    duration_ms=_duration_ms(workflow_started_at),
                ),
            )
        )
        result = Failure(error="At least two Discovery Scopes are required.")
        output = format_output(result, json_mode=json_mode)
        return result, output

    # Convert to DiscoveryScope tuple
    discovery_scopes = tuple(DiscoveryScope(s) for s in scopes)

    try:
        workflow = build_discovery_scope_activity_workflow(config=config)
        workflow_result = workflow.run(discovery_scopes)
    except DiscoveryScopeActivityWorkflowError as error:
        logger.error(
            format_log_event(
                "workflow_failed",
                **_workflow_lifecycle_fields(
                    workflow="cross_scope_activity",
                    reason="workflow_error",
                    duration_ms=_duration_ms(workflow_started_at),
                ),
            )
        )
        result = Failure(error=str(error))
        output = format_output(result, json_mode=json_mode)
        return result, output

    message = _format_cross_scope_activity_report(workflow_result)

    service_result = DiscoveryScopeActivityServiceResult(
        message=message,
        workflow_result=workflow_result,
    )

    result = Success(value=service_result)
    output = format_output(result, json_mode=json_mode)
    logger.info(
        format_log_event(
            "workflow_completed",
            **_workflow_lifecycle_fields(
                workflow="cross_scope_activity",
                duration_ms=_duration_ms(workflow_started_at),
                requested_scopes=len(discovery_scopes),
                eligible_scopes=len(workflow_result.eligible_scopes),
                excluded_scopes=len(workflow_result.excluded_scopes),
                status=workflow_result.comparison_status,
            ),
        )
    )
    return result, output


def _format_cross_scope_activity_report(result) -> str:
    lines = []
    lines.append("Cross-Scope Activity Comparison")
    lines.append("===============================")
    lines.append("")
    lines.append(
        f"Requested Scopes: {', '.join(s.value for s in result.requested_scopes)}"
    )
    lines.append(
        f"Eligible Scopes: {', '.join(s.value for s in result.eligible_scopes) or 'None'}"
    )

    if result.excluded_scopes:
        lines.append("Excluded Scopes:")
        for exc in result.excluded_scopes:
            lines.append(
                f"  - {exc.discovery_scope.value}: {exc.reason} ({exc.eligibility_status})"
            )
    else:
        lines.append("Excluded Scopes: None")
    lines.append("")

    if result.comparison_status == "comparison_produced" and result.activity_report:
        report = result.activity_report
        lines.append(f"Compared Scopes: {report.compared_scope_count}")
        lines.append("")

        # Per-scope activity
        for scope_report in report.scope_reports:
            lines.append(f"Scope: {scope_report.discovery_scope.value}")
            lines.append(
                f"  Effective Evidence Window: {scope_report.effective_evidence_window or 'N/A'}"
            )
            lines.append(f"  Snapshot Count: {scope_report.snapshot_count}")
            lines.append(f"  Valid Interval Count: {scope_report.valid_interval_count}")
            lines.append(
                f"  Endpoint Resource Count: {scope_report.endpoint_resource_count}"
            )
            lines.append(f"  Introduced: {scope_report.introduced_count}")
            lines.append(f"  Modified: {scope_report.modified_count}")
            lines.append(f"  Removed: {scope_report.removed_count}")
            lines.append(
                f"  Total Represented Changes: {scope_report.total_represented_change_count}"
            )
            lines.append("")

        # Aggregate totals
        lines.append("Aggregate Totals:")
        lines.append(f"  Total Endpoint Resources: {report.total_endpoint_resources}")
        lines.append(f"  Total Introduced: {report.total_introduced}")
        lines.append(f"  Total Modified: {report.total_modified}")
        lines.append(f"  Total Removed: {report.total_removed}")
        lines.append(f"  Total Represented Changes: {report.total_represented_changes}")
    else:
        lines.append("Comparison Status: Insufficient Evidence")
        lines.append(f"Reason: {result.reason}")

    return "\n".join(lines)

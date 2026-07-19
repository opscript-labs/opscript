from collections.abc import Callable
from time import perf_counter

from platformiq.model import DiscoveryScope

from opscript.application.discovery_scope_activity_comparison_service import (
    DiscoveryScopeActivityComparisonService,
)
from opscript.application.discovery_scope_activity_facts_service import (
    DiscoveryScopeActivityFactsService,
)
from opscript.application.discovery_scope_activity_report_service import (
    DiscoveryScopeActivityReportService,
)
from opscript.application.discovery_scope_eligibility_workflow import (
    DiscoveryScopeEligibilityWorkflow,
)
from opscript.models import (
    DiscoveryScopeActivityWorkflowResult,
    ExcludedDiscoveryScopeActivity,
)
from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger


WORKFLOW_NAME = "cross_scope_activity"

logger = get_logger()


class DiscoveryScopeActivityWorkflowError(ValueError):
    pass


class DiscoveryScopeActivityWorkflow:
    def __init__(
        self,
        *,
        eligibility_workflow: DiscoveryScopeEligibilityWorkflow,
        activity_facts_service: DiscoveryScopeActivityFactsService,
        comparison_service: DiscoveryScopeActivityComparisonService,
        report_service: DiscoveryScopeActivityReportService,
        storage_factory: Callable[[DiscoveryScope], object],
    ):
        self.eligibility_workflow = eligibility_workflow
        self.activity_facts_service = activity_facts_service
        self.comparison_service = comparison_service
        self.report_service = report_service
        self.storage_factory = storage_factory

    def run(
        self,
        discovery_scopes: tuple[DiscoveryScope, ...],
    ) -> DiscoveryScopeActivityWorkflowResult:
        self._validate_requested_scopes(discovery_scopes)

        (
            eligible_scopes,
            excluded_scopes,
            eligible_scope_storages,
        ) = _run_workflow_phase(
            "scope_qualification",
            lambda: self._qualify_scopes(discovery_scopes),
        )

        if len(eligible_scopes) == 0:
            return DiscoveryScopeActivityWorkflowResult(
                comparison_status="no_eligible_scopes",
                reason="No requested Discovery Scopes are eligible for comparison.",
                requested_scopes=discovery_scopes,
                eligible_scopes=(),
                excluded_scopes=excluded_scopes,
            )

        if len(eligible_scopes) == 1:
            return DiscoveryScopeActivityWorkflowResult(
                comparison_status="insufficient_eligible_scopes",
                reason="At least two eligible Discovery Scopes are required for comparison.",
                requested_scopes=discovery_scopes,
                eligible_scopes=eligible_scopes,
                excluded_scopes=excluded_scopes,
            )

        activity_facts = _run_workflow_phase(
            "activity_fact_derivation",
            lambda: self._derive_activity_facts(eligible_scope_storages),
        )
        comparison = _run_workflow_phase(
            "cross_scope_comparison",
            lambda: self.comparison_service.compare(activity_facts),
        )
        activity_report = _run_workflow_phase(
            "activity_report_projection",
            lambda: self.report_service.project(comparison),
        )

        return DiscoveryScopeActivityWorkflowResult(
            comparison_status="comparison_produced",
            reason="comparison_available",
            requested_scopes=discovery_scopes,
            eligible_scopes=eligible_scopes,
            excluded_scopes=excluded_scopes,
            activity_report=activity_report,
        )

    def _qualify_scopes(
        self,
        discovery_scopes: tuple[DiscoveryScope, ...],
    ):
        eligible_scopes: list[DiscoveryScope] = []
        excluded_scopes: list[ExcludedDiscoveryScopeActivity] = []
        eligible_scope_storages = []

        for discovery_scope in discovery_scopes:
            storage = self.storage_factory(discovery_scope)
            eligibility = self.eligibility_workflow.run(discovery_scope, storage)

            if eligibility.eligibility_status == "eligible":
                eligible_scopes.append(discovery_scope)
                eligible_scope_storages.append((eligibility, storage))
                continue

            excluded_scopes.append(
                ExcludedDiscoveryScopeActivity(
                    discovery_scope=discovery_scope,
                    eligibility_status=eligibility.eligibility_status,
                    reason=eligibility.reason,
                )
            )

        return (
            tuple(eligible_scopes),
            tuple(excluded_scopes),
            tuple(eligible_scope_storages),
        )

    def _derive_activity_facts(
        self,
        eligible_scope_storages,
    ):
        activity_facts = []
        for eligibility, storage in eligible_scope_storages:
            history = storage.load_history()
            activity_facts.append(
                self.activity_facts_service.derive(eligibility, history)
            )

        return tuple(activity_facts)

    def _validate_requested_scopes(
        self,
        discovery_scopes: tuple[DiscoveryScope, ...],
    ) -> None:
        if len(discovery_scopes) < 2:
            raise DiscoveryScopeActivityWorkflowError(
                "At least two Discovery Scopes are required."
            )

        if len(set(discovery_scopes)) != len(discovery_scopes):
            raise DiscoveryScopeActivityWorkflowError(
                "Duplicate Discovery Scopes are not allowed."
            )


def _run_workflow_phase(
    phase: str,
    operation,
):
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
        logger.error(
            format_log_event(
                "workflow_phase_failed",
                **_workflow_phase_lifecycle_fields(
                    workflow=WORKFLOW_NAME,
                    phase=phase,
                    duration_ms=_duration_ms(phase_started_at),
                    reason=_failure_reason(phase),
                ),
            )
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


def _workflow_phase_lifecycle_fields(**fields: object) -> dict[str, object]:
    return {
        **active_execution_log_fields(),
        **fields,
    }


def _duration_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


def _failure_reason(phase: str) -> str:
    return f"{phase}_failed"

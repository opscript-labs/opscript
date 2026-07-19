from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Literal

from platformiq.core import Identifier
from platformiq.model import (
    CompletedComparisonInterval,
    DiscoveryScope,
    Finding,
    Observation,
    Resource,
)


@dataclass
class ServiceResult:
    message: str


@dataclass
class Success:
    value: ServiceResult
    status: str = "success"


@dataclass
class Failure:
    error: str
    status: str = "error"


@dataclass
class InventoryItem:
    service: str
    resource: str
    metadata: Dict[str, Any]


@dataclass
class InventorySnapshot:
    items: List[InventoryItem]


@dataclass(frozen=True)
class ResourceSummary:
    """
    Opscript product artifact representing everything known about
    one changed resource during infrastructure review.
    """

    resource: Resource
    change_type: str
    observations: tuple[Observation, ...] = field(default_factory=tuple)
    findings: tuple[Finding, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InfrastructureChangeSummary:
    """
    Opscript product artifact for summarizing infrastructure changes
    in a form suitable for engineer investigation.
    """

    title: str
    resource_summaries: tuple[ResourceSummary, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResourceChangeHistory:
    """
    Opscript-local analysis model representing the recorded change history
    for a single resource across comparisons history.
    """

    resource_external_id: str
    first_recorded_change: int | None
    most_recent_recorded_change: int | None
    recorded_change_count: int
    recorded_change_span: str | None
    comparison_indices: tuple[int, ...]


@dataclass(frozen=True)
class ResourceObservationSummary:
    """
    Opscript-local deterministic observation span summary for one resource.
    """

    resource_external_id: str
    first_observed_snapshot_id: Identifier
    latest_observed_snapshot_id: Identifier
    observed_snapshot_count: int
    observation_gap_count: int = 0


@dataclass(frozen=True)
class HistoricalInventoryObservation:
    """
    Opscript-local deterministic inventory observation for one snapshot.
    """

    snapshot_id: Identifier
    recorded_resource_count: int


@dataclass(frozen=True)
class DiscoveryScopeEligibility:
    """
    Opscript-local evidence qualification for one Discovery Scope.
    """

    discovery_scope: DiscoveryScope
    eligibility_status: str
    reason: str
    snapshot_count: int
    valid_interval_count: int


@dataclass(frozen=True)
class DiscoveryScopeActivityFacts:
    """
    Opscript-local historical activity facts for one Discovery Scope.
    """

    discovery_scope: DiscoveryScope
    effective_evidence_window: str | None
    snapshot_count: int
    valid_interval_count: int
    endpoint_resource_count: int
    introduced_count: int
    modified_count: int
    removed_count: int
    total_represented_change_count: int


@dataclass(frozen=True)
class DiscoveryScopeActivityComparison:
    """
    Opscript-local aggregate comparison of pre-derived Discovery Scope facts.
    """

    compared_scope_count: int
    compared_scopes: tuple[DiscoveryScope, ...] = field(default_factory=tuple)
    total_endpoint_resources: int = 0
    total_introduced: int = 0
    total_modified: int = 0
    total_removed: int = 0
    total_represented_changes: int = 0
    evidence_windows: tuple[str | None, ...] = field(default_factory=tuple)
    per_scope: tuple[DiscoveryScopeActivityFacts, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScopeActivityReport:
    """
    Opscript-local presentation-ready activity facts for one Discovery Scope.
    """

    discovery_scope: DiscoveryScope
    snapshot_count: int
    valid_interval_count: int
    endpoint_resource_count: int
    introduced_count: int
    modified_count: int
    removed_count: int
    total_represented_change_count: int
    effective_evidence_window: str | None


@dataclass(frozen=True)
class DiscoveryScopeActivityReport:
    """
    Opscript-local presentation-ready cross-scope activity report model.
    """

    compared_scope_count: int
    scope_reports: tuple[ScopeActivityReport, ...] = field(default_factory=tuple)
    total_endpoint_resources: int = 0
    total_introduced: int = 0
    total_modified: int = 0
    total_removed: int = 0
    total_represented_changes: int = 0


@dataclass(frozen=True)
class ExcludedDiscoveryScopeActivity:
    """
    Opscript-local record of a Discovery Scope excluded from activity comparison.
    """

    discovery_scope: DiscoveryScope
    eligibility_status: str
    reason: str


@dataclass(frozen=True)
class DiscoveryScopeActivityWorkflowResult:
    """
    Opscript-local workflow result for cross-scope activity orchestration.
    """

    comparison_status: str
    reason: str
    requested_scopes: tuple[DiscoveryScope, ...] = field(default_factory=tuple)
    eligible_scopes: tuple[DiscoveryScope, ...] = field(default_factory=tuple)
    excluded_scopes: tuple[ExcludedDiscoveryScopeActivity, ...] = field(
        default_factory=tuple
    )
    activity_report: DiscoveryScopeActivityReport | None = None


@dataclass(frozen=True)
class ResourceInstabilitySummary:
    """
    Opscript-local deterministic activity concentration summary for one resource.
    """

    resource_external_id: str
    comparison_count: int
    change_count: int
    observation_count: int
    finding_count: int
    first_observed_comparison: int | None
    most_recent_observed_comparison: int | None
    recorded_activity_count: int


@dataclass(frozen=True)
class EnvironmentInstabilitySummary:
    """
    Opscript-local deterministic activity concentration summary for an environment.
    """

    resource_summaries: tuple[ResourceInstabilitySummary, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class ComparisonActivity:
    """
    Opscript-local recorded activity counts for one comparison.
    """

    comparison_index: int
    change_count: int
    observation_count: int
    finding_count: int
    recorded_activity_count: int


@dataclass(frozen=True)
class EnvironmentStabilityTrend:
    """
    Opscript-local deterministic activity trend summary for an environment.
    """

    comparison_activity: tuple[ComparisonActivity, ...] = field(default_factory=tuple)
    first_activity_count: int | None = None
    most_recent_activity_count: int | None = None
    activity_delta: int | None = None
    trend_direction: str = "insufficient_history"


@dataclass(frozen=True)
class OperationalActivitySummary:
    """
    Opscript-local deterministic activity count for one activity type.
    """

    activity_layer: str
    activity_type: str
    activity_count: int
    comparison_count: int


@dataclass(frozen=True)
class EnvironmentActivityDominanceSummary:
    """
    Opscript-local deterministic activity type summary for an environment.
    """

    activity_summaries: tuple[OperationalActivitySummary, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class ResourceChangeFrequencySummary:
    """
    Opscript-local deterministic change frequency summary for one resource.
    """

    resource_external_id: str
    observed_snapshot_count: int
    observed_comparison_count: int
    recorded_change_count: int
    first_observed_snapshot_index: int
    most_recent_observed_snapshot_index: int
    first_changed_comparison: int | None
    most_recent_changed_comparison: int | None


@dataclass(frozen=True)
class EnvironmentChangeFrequencySummary:
    """
    Opscript-local deterministic change frequency summary for an environment.
    """

    resource_summaries: tuple[ResourceChangeFrequencySummary, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class ResourceComparisonActivity:
    """
    Opscript-local recorded activity counts for one resource in one comparison.
    """

    comparison_index: int
    change_count: int
    observation_count: int
    finding_count: int
    recorded_activity_count: int


@dataclass(frozen=True)
class ResourceChurnTrend:
    """
    Opscript-local deterministic recorded activity trend for one resource.
    """

    resource_external_id: str
    comparison_activity: tuple[ResourceComparisonActivity, ...]
    first_activity_count: int | None
    most_recent_activity_count: int | None
    activity_delta: int | None
    trend_direction: str


@dataclass(frozen=True)
class EnvironmentChurnTrendSummary:
    """
    Opscript-local deterministic recorded activity trend summary for resources.
    """

    resource_trends: tuple[ResourceChurnTrend, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResourceMetadataGroup:
    """
    Opscript-local deterministic grouping of resources by metadata value.
    """

    metadata_key: str
    metadata_value: str
    resource_count: int
    resource_external_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resource_external_ids",
            tuple(sorted(self.resource_external_ids)),
        )


@dataclass
class DiscoveryScopeActivityServiceResult(ServiceResult):
    workflow_result: DiscoveryScopeActivityWorkflowResult


@dataclass(frozen=True)
class QualifiedHistoricalEvidence:
    """
    Opscript-local qualified evidence for one observation window.
    """

    discovery_scope: DiscoveryScope
    observation_window_previous_snapshot_id: Identifier
    observation_window_current_snapshot_id: Identifier
    completed_intervals: tuple[CompletedComparisonInterval, ...] = field(
        default_factory=tuple
    )
    canonical_subject: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.discovery_scope, DiscoveryScope):
            raise TypeError("discovery_scope must be a DiscoveryScope.")

        if not isinstance(self.observation_window_previous_snapshot_id, Identifier):
            raise TypeError(
                "observation_window_previous_snapshot_id must be an Identifier."
            )

        if not isinstance(self.observation_window_current_snapshot_id, Identifier):
            raise TypeError(
                "observation_window_current_snapshot_id must be an Identifier."
            )

        object.__setattr__(
            self,
            "completed_intervals",
            tuple(self.completed_intervals),
        )

        if not self.completed_intervals:
            raise ValueError("Qualified evidence requires completed intervals.")

        seen_boundaries: set[tuple[Identifier, Identifier]] = set()
        previous_current_snapshot_id: Identifier | None = None

        for index, interval in enumerate(self.completed_intervals):
            if interval.discovery_scope != self.discovery_scope:
                raise ValueError(
                    "Completed interval discovery_scope must match qualified evidence."
                )

            boundaries = (interval.previous_snapshot_id, interval.current_snapshot_id)
            if boundaries in seen_boundaries:
                raise ValueError("Completed intervals must not contain duplicates.")
            seen_boundaries.add(boundaries)

            if index == 0:
                if (
                    interval.previous_snapshot_id
                    != self.observation_window_previous_snapshot_id
                ):
                    raise ValueError(
                        "First completed interval must start at the observation window."
                    )
            elif interval.previous_snapshot_id != previous_current_snapshot_id:
                raise ValueError("Completed intervals must be ordered contiguously.")

            previous_current_snapshot_id = interval.current_snapshot_id

        if self.completed_intervals and (
            self.completed_intervals[-1].current_snapshot_id
            != self.observation_window_current_snapshot_id
        ):
            raise ValueError(
                "Last completed interval must end at the observation window."
            )


@dataclass(frozen=True)
class RecognitionResult:
    """
    Opscript-local completed binary recognition result.
    """

    outcome: Literal["supported", "not_supported"]
    qualified_historical_evidence: QualifiedHistoricalEvidence
    engineering_condition: Literal[
        "frequent_infrastructure_modification",
        "recurring_infrastructure_removal_activity",
        "recurring_infrastructure_introduction_activity",
    ] = "frequent_infrastructure_modification"

    frequent_infrastructure_modification_condition: ClassVar[str] = (
        "frequent_infrastructure_modification"
    )
    recurring_infrastructure_removal_activity_condition: ClassVar[str] = (
        "recurring_infrastructure_removal_activity"
    )
    recurring_infrastructure_introduction_activity_condition: ClassVar[str] = (
        "recurring_infrastructure_introduction_activity"
    )
    recognition_threshold: ClassVar[int] = 3
    minimum_completed_interval_count: ClassVar[int] = 4

    def __post_init__(self) -> None:
        if self.outcome not in {"supported", "not_supported"}:
            raise ValueError("Recognition outcome must be supported or not_supported.")

        if self.engineering_condition not in {
            self.frequent_infrastructure_modification_condition,
            self.recurring_infrastructure_removal_activity_condition,
            self.recurring_infrastructure_introduction_activity_condition,
        }:
            raise ValueError("Recognition engineering condition is not supported.")

        if not isinstance(
            self.qualified_historical_evidence, QualifiedHistoricalEvidence
        ):
            raise TypeError(
                "qualified_historical_evidence must be QualifiedHistoricalEvidence."
            )

    @property
    def supported(self) -> bool:
        return self.outcome == "supported"


@dataclass(frozen=True)
class ScopeLocalEngineeringConditionEvaluation:
    """
    Completed scope-local Engineering Condition evaluation outcome.
    """

    outcome: Literal["supported", "not_supported"]
    qualified_historical_evidence: QualifiedHistoricalEvidence
    engineering_condition: Literal[
        "frequent_infrastructure_modification",
        "recurring_infrastructure_removal_activity",
        "recurring_infrastructure_introduction_activity",
    ]

    def __post_init__(self) -> None:
        if self.outcome not in {"supported", "not_supported"}:
            raise ValueError("Evaluation outcome must be supported or not_supported.")

        if self.engineering_condition not in {
            RecognitionResult.frequent_infrastructure_modification_condition,
            RecognitionResult.recurring_infrastructure_removal_activity_condition,
            RecognitionResult.recurring_infrastructure_introduction_activity_condition,
        }:
            raise ValueError("Evaluation engineering condition is not supported.")

        if not isinstance(
            self.qualified_historical_evidence, QualifiedHistoricalEvidence
        ):
            raise TypeError(
                "qualified_historical_evidence must be QualifiedHistoricalEvidence."
            )

    @property
    def discovery_scope(self) -> DiscoveryScope:
        return self.qualified_historical_evidence.discovery_scope

    @property
    def supported(self) -> bool:
        return self.outcome == "supported"


@dataclass(frozen=True)
class RecognizedFinding:
    """
    Immutable representation of a supported recognition result.
    """

    recognition_result: RecognitionResult

    def __post_init__(self) -> None:
        if not isinstance(self.recognition_result, RecognitionResult):
            raise TypeError("recognition_result must be a RecognitionResult.")

        if not self.recognition_result.supported:
            raise ValueError("Recognized finding requires a supported recognition.")

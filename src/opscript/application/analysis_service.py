from __future__ import annotations

from platformiq.analysis.findings import findings_from_observations
from platformiq.analysis.observations import observations_from_diff
from platformiq.analysis.snapshot_differ import SnapshotDiffer
from platformiq.model import (
    AnalysisResult,
    DiffResult,
    Finding,
    Observation,
    Resource,
    Snapshot,
)

from opscript.models import (
    ComparisonActivity,
    EnvironmentActivityDominanceSummary,
    EnvironmentChangeFrequencySummary,
    EnvironmentChurnTrendSummary,
    EnvironmentInstabilitySummary,
    EnvironmentStabilityTrend,
    HistoricalInventoryObservation,
    OperationalActivitySummary,
    ResourceChurnTrend,
    ResourceChangeFrequencySummary,
    ResourceChangeHistory,
    ResourceComparisonActivity,
    ResourceInstabilitySummary,
    ResourceMetadataGroup,
    ResourceObservationSummary,
)


class AnalysisService:
    """
    Application service responsible for
    infrastructure drift analysis.
    """

    def __init__(self, snapshot_differ: SnapshotDiffer):
        self.snapshot_differ = snapshot_differ

    def analyze(
        self,
        previous: Snapshot,
        current: Snapshot,
    ) -> DiffResult:
        """
        Compare two snapshots and return structural drift results.
        """

        return self.snapshot_differ.compare(
            previous,
            current,
        )

    def observe(
        self,
        previous: Snapshot,
        current: Snapshot,
    ) -> tuple[Observation, ...]:
        """
        Compare two snapshots and return semantic observations.
        """

        diff_result = self.analyze(
            previous,
            current,
        )

        return observations_from_diff(diff_result)

    def find(
        self,
        previous: Snapshot,
        current: Snapshot,
    ) -> tuple[Finding, ...]:
        """
        Compare two snapshots and return interpreted findings.
        """

        observations = self.observe(
            previous,
            current,
        )

        return findings_from_observations(observations)

    def analyze_full(
        self,
        previous: Snapshot,
        current: Snapshot,
    ) -> AnalysisResult:
        """
        Compare two snapshots and return the complete analysis result.
        """

        diff_result = self.analyze(
            previous,
            current,
        )

        observations = observations_from_diff(diff_result)
        findings = findings_from_observations(observations)

        return AnalysisResult(
            diff=diff_result,
            observations=observations,
            findings=findings,
        )

    def analyze_history(
        self,
        snapshots: tuple[Snapshot, ...],
    ) -> tuple[AnalysisResult, ...]:
        """
        Analyze snapshot history by comparing adjacent snapshots in order.
        """

        if len(snapshots) < 2:
            return ()

        results: list[AnalysisResult] = []

        for index in range(len(snapshots) - 1):
            results.append(
                self.analyze_full(
                    snapshots[index],
                    snapshots[index + 1],
                )
            )

        return tuple(results)

    def filter_history_for_resource(
        self,
        history: tuple[AnalysisResult, ...],
        resource_external_id: str,
    ) -> tuple[AnalysisResult, ...]:
        """
        Return only history entries involving the specified resource.
        """

        filtered: list[AnalysisResult] = []

        for result in history:
            if self._contains_resource(
                result,
                resource_external_id,
            ):
                filtered.append(result)

        return tuple(filtered)

    def analyze_resource_change_history(
        self,
        history: tuple[AnalysisResult, ...],
        resource_external_id: str,
    ) -> ResourceChangeHistory:
        """
        Derive deterministic change history knowledge for a given resource from historical comparison diffs.
        """
        comparison_indices: list[int] = []
        for index, result in enumerate(history, start=1):
            is_changed = any(
                resource.external_id == resource_external_id
                for resource in self._changed_resources(result)
            )
            if is_changed:
                comparison_indices.append(index)

        if not comparison_indices:
            return ResourceChangeHistory(
                resource_external_id=resource_external_id,
                first_recorded_change=None,
                most_recent_recorded_change=None,
                recorded_change_count=0,
                recorded_change_span=None,
                comparison_indices=(),
            )

        first = comparison_indices[0]
        last = comparison_indices[-1]
        span = f"Comparison {first} -> Comparison {last}"

        return ResourceChangeHistory(
            resource_external_id=resource_external_id,
            first_recorded_change=first,
            most_recent_recorded_change=last,
            recorded_change_count=len(comparison_indices),
            recorded_change_span=span,
            comparison_indices=tuple(comparison_indices),
        )

    def analyze_latest_environment_change(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> int | None:
        """
        Identify the latest 1-indexed comparison index that contains recorded infrastructure changes.
        """
        for index in range(len(history), 0, -1):
            result = history[index - 1]
            if result.diff.created or result.diff.modified or result.diff.deleted:
                return index
        return None

    def analyze_instability_concentration(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> EnvironmentInstabilitySummary:
        """
        Summarize recorded infrastructure activity concentration by resource.
        """
        summaries: dict[str, dict[str, object]] = {}

        def summary_for(resource_external_id: str) -> dict[str, object]:
            if resource_external_id not in summaries:
                summaries[resource_external_id] = {
                    "change_count": 0,
                    "observation_count": 0,
                    "finding_count": 0,
                    "comparison_indices": set(),
                }
            return summaries[resource_external_id]

        for comparison_index, result in enumerate(history, start=1):
            resources_in_comparison: set[str] = set()

            for resource in self._changed_resources(result):
                summary = summary_for(resource.external_id)
                summary["change_count"] = int(summary["change_count"]) + 1
                resources_in_comparison.add(resource.external_id)

            for observation in result.observations:
                summary = summary_for(observation.subject)
                summary["observation_count"] = int(summary["observation_count"]) + 1
                resources_in_comparison.add(observation.subject)

            for finding in result.findings:
                summary = summary_for(finding.subject)
                summary["finding_count"] = int(summary["finding_count"]) + 1
                resources_in_comparison.add(finding.subject)

            for resource_external_id in resources_in_comparison:
                summary = summary_for(resource_external_id)
                comparison_indices = summary["comparison_indices"]
                assert isinstance(comparison_indices, set)
                comparison_indices.add(comparison_index)

        resource_summaries = []
        for resource_external_id, summary in summaries.items():
            comparison_indices = summary["comparison_indices"]
            assert isinstance(comparison_indices, set)
            ordered_indices = tuple(sorted(comparison_indices))
            change_count = int(summary["change_count"])
            observation_count = int(summary["observation_count"])
            finding_count = int(summary["finding_count"])
            recorded_activity_count = change_count + observation_count + finding_count

            resource_summaries.append(
                ResourceInstabilitySummary(
                    resource_external_id=resource_external_id,
                    comparison_count=len(ordered_indices),
                    change_count=change_count,
                    observation_count=observation_count,
                    finding_count=finding_count,
                    first_observed_comparison=ordered_indices[0]
                    if ordered_indices
                    else None,
                    most_recent_observed_comparison=ordered_indices[-1]
                    if ordered_indices
                    else None,
                    recorded_activity_count=recorded_activity_count,
                )
            )

        return EnvironmentInstabilitySummary(
            resource_summaries=tuple(
                sorted(
                    resource_summaries,
                    key=lambda summary: (
                        -summary.recorded_activity_count,
                        summary.resource_external_id,
                    ),
                )
            )
        )

    def analyze_environment_stability_trend(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> EnvironmentStabilityTrend:
        comparison_activity = tuple(
            self._comparison_activity(index, result)
            for index, result in enumerate(history, start=1)
        )

        if not comparison_activity:
            return EnvironmentStabilityTrend()

        first_activity_count = comparison_activity[0].recorded_activity_count
        most_recent_activity_count = comparison_activity[-1].recorded_activity_count
        activity_delta = most_recent_activity_count - first_activity_count

        if len(comparison_activity) == 1:
            trend_direction = "insufficient_history"
        elif activity_delta < 0:
            trend_direction = "decreasing"
        elif activity_delta > 0:
            trend_direction = "increasing"
        else:
            trend_direction = "unchanged"

        return EnvironmentStabilityTrend(
            comparison_activity=comparison_activity,
            first_activity_count=first_activity_count,
            most_recent_activity_count=most_recent_activity_count,
            activity_delta=activity_delta,
            trend_direction=trend_direction,
        )

    def analyze_operational_activity_dominance(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> EnvironmentActivityDominanceSummary:
        summaries: dict[tuple[str, str], dict[str, object]] = {}

        def summary_for(
            activity_layer: str,
            activity_type: str,
        ) -> dict[str, object]:
            key = (activity_layer, activity_type)
            if key not in summaries:
                summaries[key] = {
                    "activity_count": 0,
                    "comparison_indices": set(),
                }
            return summaries[key]

        def record_activity(
            activity_layer: str,
            activity_type: str,
            activity_count: int,
            comparison_index: int,
        ) -> None:
            if activity_count == 0:
                return

            summary = summary_for(activity_layer, activity_type)
            summary["activity_count"] = int(summary["activity_count"]) + activity_count
            comparison_indices = summary["comparison_indices"]
            assert isinstance(comparison_indices, set)
            comparison_indices.add(comparison_index)

        for comparison_index, result in enumerate(history, start=1):
            record_activity(
                "change",
                "created",
                len(result.diff.created),
                comparison_index,
            )
            record_activity(
                "change",
                "modified",
                len(result.diff.modified),
                comparison_index,
            )
            record_activity(
                "change",
                "deleted",
                len(result.diff.deleted),
                comparison_index,
            )

            for observation in result.observations:
                record_activity(
                    "observation",
                    observation.type,
                    1,
                    comparison_index,
                )

            for finding in result.findings:
                record_activity(
                    "finding",
                    finding.type,
                    1,
                    comparison_index,
                )

        activity_summaries = []
        for (activity_layer, activity_type), summary in summaries.items():
            comparison_indices = summary["comparison_indices"]
            assert isinstance(comparison_indices, set)
            activity_summaries.append(
                OperationalActivitySummary(
                    activity_layer=activity_layer,
                    activity_type=activity_type,
                    activity_count=int(summary["activity_count"]),
                    comparison_count=len(comparison_indices),
                )
            )

        return EnvironmentActivityDominanceSummary(
            activity_summaries=tuple(
                sorted(
                    activity_summaries,
                    key=lambda summary: (
                        -summary.activity_count,
                        summary.activity_layer,
                        summary.activity_type,
                    ),
                )
            )
        )

    def analyze_resource_change_frequency(
        self,
        snapshots: tuple[Snapshot, ...],
    ) -> EnvironmentChangeFrequencySummary:
        summaries: dict[str, dict[str, object]] = {}

        def summary_for(resource_external_id: str) -> dict[str, object]:
            if resource_external_id not in summaries:
                summaries[resource_external_id] = {
                    "snapshot_indices": set(),
                    "comparison_indices": set(),
                    "changed_comparison_indices": set(),
                }
            return summaries[resource_external_id]

        for snapshot_index, snapshot in enumerate(snapshots, start=1):
            for resource in snapshot.resources:
                summary = summary_for(resource.external_id)
                snapshot_indices = summary["snapshot_indices"]
                assert isinstance(snapshot_indices, set)
                snapshot_indices.add(snapshot_index)

        for comparison_index in range(1, len(snapshots)):
            previous = snapshots[comparison_index - 1]
            current = snapshots[comparison_index]
            previous_resource_ids = {
                resource.external_id for resource in previous.resources
            }
            current_resource_ids = {
                resource.external_id for resource in current.resources
            }
            observed_resource_ids = previous_resource_ids | current_resource_ids

            for resource_external_id in observed_resource_ids:
                summary = summary_for(resource_external_id)
                comparison_indices = summary["comparison_indices"]
                assert isinstance(comparison_indices, set)
                comparison_indices.add(comparison_index)

            diff = self.analyze(previous, current)
            changed_resource_ids = {
                resource.external_id
                for resource in self._changed_resources(AnalysisResult(diff=diff))
            }

            for resource_external_id in changed_resource_ids:
                summary = summary_for(resource_external_id)
                changed_comparison_indices = summary["changed_comparison_indices"]
                assert isinstance(changed_comparison_indices, set)
                changed_comparison_indices.add(comparison_index)

        resource_summaries = []
        for resource_external_id, summary in summaries.items():
            snapshot_indices = summary["snapshot_indices"]
            comparison_indices = summary["comparison_indices"]
            changed_comparison_indices = summary["changed_comparison_indices"]
            assert isinstance(snapshot_indices, set)
            assert isinstance(comparison_indices, set)
            assert isinstance(changed_comparison_indices, set)

            ordered_snapshot_indices = tuple(sorted(snapshot_indices))
            ordered_changed_comparison_indices = tuple(
                sorted(changed_comparison_indices)
            )

            resource_summaries.append(
                ResourceChangeFrequencySummary(
                    resource_external_id=resource_external_id,
                    observed_snapshot_count=len(ordered_snapshot_indices),
                    observed_comparison_count=len(comparison_indices),
                    recorded_change_count=len(ordered_changed_comparison_indices),
                    first_observed_snapshot_index=ordered_snapshot_indices[0],
                    most_recent_observed_snapshot_index=ordered_snapshot_indices[-1],
                    first_changed_comparison=ordered_changed_comparison_indices[0]
                    if ordered_changed_comparison_indices
                    else None,
                    most_recent_changed_comparison=ordered_changed_comparison_indices[
                        -1
                    ]
                    if ordered_changed_comparison_indices
                    else None,
                )
            )

        return EnvironmentChangeFrequencySummary(
            resource_summaries=tuple(
                sorted(
                    resource_summaries,
                    key=lambda summary: (
                        summary.recorded_change_count,
                        -summary.observed_snapshot_count,
                        summary.resource_external_id,
                    ),
                )
            )
        )

    def analyze_resource_churn_trends(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> EnvironmentChurnTrendSummary:
        resource_activities: dict[str, list[ResourceComparisonActivity]] = {}

        for comparison_index, result in enumerate(history, start=1):
            resource_ids = {
                resource.external_id for resource in self._changed_resources(result)
            }
            resource_ids.update(
                observation.subject for observation in result.observations
            )
            resource_ids.update(finding.subject for finding in result.findings)

            for resource_external_id in resource_ids:
                change_count = sum(
                    1
                    for resource in self._changed_resources(result)
                    if resource.external_id == resource_external_id
                )
                observation_count = sum(
                    1
                    for observation in result.observations
                    if observation.subject == resource_external_id
                )
                finding_count = sum(
                    1
                    for finding in result.findings
                    if finding.subject == resource_external_id
                )
                recorded_activity_count = (
                    change_count + observation_count + finding_count
                )

                if recorded_activity_count == 0:
                    continue

                resource_activities.setdefault(resource_external_id, []).append(
                    ResourceComparisonActivity(
                        comparison_index=comparison_index,
                        change_count=change_count,
                        observation_count=observation_count,
                        finding_count=finding_count,
                        recorded_activity_count=recorded_activity_count,
                    )
                )

        resource_trends = []
        for resource_external_id, comparison_activities in resource_activities.items():
            first_activity_count = comparison_activities[0].recorded_activity_count
            most_recent_activity_count = comparison_activities[
                -1
            ].recorded_activity_count
            activity_delta = most_recent_activity_count - first_activity_count

            if len(comparison_activities) == 1:
                trend_direction = "insufficient_history"
                activity_delta = 0
            elif activity_delta > 0:
                trend_direction = "increasing"
            elif activity_delta < 0:
                trend_direction = "decreasing"
            else:
                trend_direction = "unchanged"

            resource_trends.append(
                ResourceChurnTrend(
                    resource_external_id=resource_external_id,
                    comparison_activity=tuple(comparison_activities),
                    first_activity_count=first_activity_count,
                    most_recent_activity_count=most_recent_activity_count,
                    activity_delta=activity_delta,
                    trend_direction=trend_direction,
                )
            )

        trend_priority = {
            "increasing": 0,
            "decreasing": 1,
            "unchanged": 2,
            "insufficient_history": 3,
        }

        return EnvironmentChurnTrendSummary(
            resource_trends=tuple(
                sorted(
                    resource_trends,
                    key=lambda trend: (
                        trend_priority[trend.trend_direction],
                        -(trend.activity_delta or 0),
                        trend.resource_external_id,
                    ),
                )
            )
        )

    def analyze_resource_metadata_groups(
        self,
        snapshots: tuple[Snapshot, ...],
        metadata_path: str,
    ) -> tuple[ResourceMetadataGroup, ...]:
        latest_metadata_by_resource: dict[str, str] = {}

        for snapshot in snapshots:
            for resource in snapshot.resources:
                metadata_value = self._metadata_value(
                    resource.state.properties,
                    metadata_path,
                )
                if metadata_value is None:
                    continue

                latest_metadata_by_resource[resource.external_id] = str(metadata_value)

        groups: dict[str, set[str]] = {}
        for resource_external_id, metadata_value in latest_metadata_by_resource.items():
            groups.setdefault(metadata_value, set()).add(resource_external_id)

        return tuple(
            ResourceMetadataGroup(
                metadata_key=metadata_path,
                metadata_value=metadata_value,
                resource_count=len(resource_external_ids),
                resource_external_ids=tuple(resource_external_ids),
            )
            for metadata_value, resource_external_ids in sorted(groups.items())
        )

    def analyze_resource_observation_history(
        self,
        snapshots: tuple[Snapshot, ...],
    ) -> tuple[ResourceObservationSummary, ...]:
        summaries: dict[str, dict[str, object]] = {}

        for snapshot_index, snapshot in enumerate(snapshots, start=1):
            resource_ids_in_snapshot = {
                resource.external_id for resource in snapshot.resources
            }
            for resource_external_id in resource_ids_in_snapshot:
                if resource_external_id not in summaries:
                    summaries[resource_external_id] = {
                        "first_observed_snapshot_id": snapshot.id,
                        "latest_observed_snapshot_id": snapshot.id,
                        "first_observed_snapshot_index": snapshot_index,
                        "latest_observed_snapshot_index": snapshot_index,
                        "observed_snapshot_count": 0,
                    }

                summary = summaries[resource_external_id]
                summary["latest_observed_snapshot_id"] = snapshot.id
                summary["latest_observed_snapshot_index"] = snapshot_index
                summary["observed_snapshot_count"] = (
                    int(summary["observed_snapshot_count"]) + 1
                )

        return tuple(
            ResourceObservationSummary(
                resource_external_id=resource_external_id,
                first_observed_snapshot_id=summary["first_observed_snapshot_id"],
                latest_observed_snapshot_id=summary["latest_observed_snapshot_id"],
                observed_snapshot_count=int(summary["observed_snapshot_count"]),
                observation_gap_count=(
                    int(summary["latest_observed_snapshot_index"])
                    - int(summary["first_observed_snapshot_index"])
                    + 1
                    - int(summary["observed_snapshot_count"])
                ),
            )
            for resource_external_id, summary in sorted(summaries.items())
        )

    def analyze_historical_inventory_timeline(
        self,
        snapshots: tuple[Snapshot, ...],
    ) -> tuple[HistoricalInventoryObservation, ...]:
        return tuple(
            HistoricalInventoryObservation(
                snapshot_id=snapshot.id,
                recorded_resource_count=len(snapshot.resources),
            )
            for snapshot in snapshots
        )

    def _comparison_activity(
        self,
        comparison_index: int,
        result: AnalysisResult,
    ) -> ComparisonActivity:
        change_count = len(self._changed_resources(result))
        observation_count = len(result.observations)
        finding_count = len(result.findings)

        return ComparisonActivity(
            comparison_index=comparison_index,
            change_count=change_count,
            observation_count=observation_count,
            finding_count=finding_count,
            recorded_activity_count=change_count + observation_count + finding_count,
        )

    def _contains_resource(
        self,
        result: AnalysisResult,
        resource_external_id: str,
    ) -> bool:
        return (
            any(
                resource.external_id == resource_external_id
                for resource in self._changed_resources(result)
            )
            or any(
                observation.subject == resource_external_id
                for observation in result.observations
            )
            or any(
                finding.subject == resource_external_id for finding in result.findings
            )
        )

    def _changed_resources(
        self,
        result: AnalysisResult,
    ) -> tuple[Resource, ...]:
        return result.diff.created + result.diff.modified + result.diff.deleted

    def _metadata_value(
        self,
        properties: dict,
        metadata_path: str,
    ) -> object | None:
        value: object = properties

        for path_part in metadata_path.split("."):
            if not isinstance(value, dict) or path_part not in value:
                return None
            value = value[path_part]

        return value

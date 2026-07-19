from __future__ import annotations

from platformiq.contracts import Reporter
from platformiq.model import AnalysisResult, DiffResult, Finding, Observation

from opscript.models import (
    EnvironmentActivityDominanceSummary,
    EnvironmentChangeFrequencySummary,
    EnvironmentChurnTrendSummary,
    EnvironmentStabilityTrend,
    EnvironmentInstabilitySummary,
    HistoricalInventoryObservation,
    InfrastructureChangeSummary,
    ResourceSummary,
    ResourceChangeHistory,
    ResourceMetadataGroup,
    ResourceObservationSummary,
)


_NOT_PROVIDED = object()


class ReportingService:
    """
    Application service responsible for rendering Opscript reports.
    """

    def __init__(self, reporter: Reporter):
        self.reporter = reporter

    def generate_report(self, result: DiffResult) -> str:
        return self.reporter.report(result)

    def generate_observation_report(
        self,
        observations: tuple[Observation, ...],
    ) -> str:
        if not observations:
            return "No observations."

        lines = ["Observations:"]

        for observation in observations:
            lines.append(f"- {observation.message}")

        return "\n".join(lines)

    def generate_finding_report(
        self,
        findings: tuple[Finding, ...],
    ) -> str:
        if not findings:
            return "No findings."

        lines = ["Findings:"]

        for finding in findings:
            lines.append(f"- {finding.message}")

        return "\n".join(lines)

    def generate_analysis_report(
        self,
        result: AnalysisResult,
    ) -> str:
        observation_report = self.generate_observation_report(result.observations)

        if not result.observations:
            return observation_report

        finding_report = self.generate_finding_report(result.findings)

        return f"{observation_report}\n\n{finding_report}"

    def generate_infrastructure_change_summary_report(
        self,
        summary: InfrastructureChangeSummary,
    ) -> str:
        if not summary.resource_summaries:
            return "No observations."

        lines = [
            summary.title,
            "=" * len(summary.title),
            "",
            "Resources:",
        ]

        for resource_summary in summary.resource_summaries:
            lines.extend(
                [
                    "",
                    self._render_resource_summary(resource_summary),
                ]
            )

        return "\n".join(lines)

    def generate_resource_evolution_report(
        self,
        resource_external_id: str,
        history: tuple[AnalysisResult, ...],
        change_history: ResourceChangeHistory | None = None,
    ) -> str:
        if not history:
            return f"No history found for resource: {resource_external_id}"

        lines = [
            f"Resource Evolution: {resource_external_id}",
            "=" * len(f"Resource Evolution: {resource_external_id}"),
        ]

        if change_history is not None:
            lines.extend(
                [
                    "",
                    self.generate_resource_change_history_report(change_history),
                ]
            )

        for index, result in enumerate(history, start=1):
            lines.extend(
                [
                    "",
                    f"Change {index}:",
                    "",
                    self.generate_observation_report(result.observations),
                    "",
                    self.generate_finding_report(result.findings),
                ]
            )

        return "\n".join(lines)

    def generate_resource_change_history_report(
        self,
        history: ResourceChangeHistory,
    ) -> str:
        """
        Render the ResourceChangeHistory analysis result into a deterministic report.
        """
        if history.recorded_change_count == 0:
            return f"No recorded change history found for resource: {history.resource_external_id}"

        lines = [
            f"Resource Change History: {history.resource_external_id}",
            "=" * len(f"Resource Change History: {history.resource_external_id}"),
            "",
            "Summary:",
            f"- First recorded change: Comparison {history.first_recorded_change}",
            f"- Most recent recorded change: Comparison {history.most_recent_recorded_change}",
            f"- Recorded change count: {history.recorded_change_count}",
            f"- Recorded change span: {history.recorded_change_span}",
            "",
            "Comparisons containing recorded changes:",
        ]

        for index in history.comparison_indices:
            lines.append(f"- Comparison {index}")

        return "\n".join(lines)

    def generate_instability_concentration_report(
        self,
        summary: EnvironmentInstabilitySummary,
    ) -> str:
        title = "Operational Instability Concentration"

        if not summary.resource_summaries:
            return "\n".join(
                [
                    title,
                    "",
                    "No recorded infrastructure activity found.",
                ]
            )

        lines = [
            title,
            "=" * len(title),
        ]

        for resource_summary in summary.resource_summaries:
            lines.extend(
                [
                    "",
                    f"Resource: {resource_summary.resource_external_id}",
                    f"Recorded activity: {resource_summary.recorded_activity_count}",
                    f"Comparisons involved: {resource_summary.comparison_count}",
                    f"Changes: {resource_summary.change_count}",
                    f"Observations: {resource_summary.observation_count}",
                    f"Findings: {resource_summary.finding_count}",
                    f"First observed comparison: {resource_summary.first_observed_comparison}",
                    f"Most recent observed comparison: {resource_summary.most_recent_observed_comparison}",
                ]
            )

        return "\n".join(lines)

    def generate_environment_stability_trend_report(
        self,
        trend: EnvironmentStabilityTrend,
    ) -> str:
        title = "Environment Stability Trend"

        if trend.trend_direction == "insufficient_history":
            return "\n".join(
                [
                    title,
                    "",
                    "Insufficient history to determine activity direction.",
                ]
            )

        lines = [
            title,
            "=" * len(title),
            "",
            f"Trend direction: {trend.trend_direction}",
            f"First recorded activity: {trend.first_activity_count}",
            f"Most recent recorded activity: {trend.most_recent_activity_count}",
            f"Activity delta: {trend.activity_delta}",
            "",
            "Comparison Activity:",
        ]

        for activity in trend.comparison_activity:
            lines.append(
                "- "
                f"Comparison {activity.comparison_index}: "
                f"recorded activity={activity.recorded_activity_count}, "
                f"changes={activity.change_count}, "
                f"observations={activity.observation_count}, "
                f"findings={activity.finding_count}"
            )

        return "\n".join(lines)

    def generate_operational_activity_dominance_report(
        self,
        summary: EnvironmentActivityDominanceSummary,
    ) -> str:
        title = "Operational Activity Dominance"

        if not summary.activity_summaries:
            return "\n".join(
                [
                    title,
                    "",
                    "No recorded operational activity found.",
                ]
            )

        lines = [
            title,
            "=" * len(title),
            "",
            "Activity Summary:",
        ]

        for activity in summary.activity_summaries:
            lines.append(
                "- "
                f"Layer: {activity.activity_layer}, "
                f"Type: {activity.activity_type}, "
                f"Count: {activity.activity_count}, "
                f"Comparisons: {activity.comparison_count}"
            )

        return "\n".join(lines)

    def generate_resource_change_frequency_report(
        self,
        summary: EnvironmentChangeFrequencySummary,
    ) -> str:
        title = "Resource Change Frequency"

        if not summary.resource_summaries:
            return "\n".join(
                [
                    title,
                    "",
                    "No observed resources found.",
                ]
            )

        lines = [
            title,
            "=" * len(title),
            "",
            "Resources:",
        ]

        for resource_summary in summary.resource_summaries:
            lines.extend(
                [
                    "",
                    f"- Resource: {resource_summary.resource_external_id}",
                    f"  Observed snapshots: {resource_summary.observed_snapshot_count}",
                    f"  Observed comparisons: {resource_summary.observed_comparison_count}",
                    f"  Recorded changes: {resource_summary.recorded_change_count}",
                    f"  First observed snapshot: {resource_summary.first_observed_snapshot_index}",
                    f"  Most recent observed snapshot: {resource_summary.most_recent_observed_snapshot_index}",
                    f"  First changed comparison: {resource_summary.first_changed_comparison}",
                    f"  Most recent changed comparison: {resource_summary.most_recent_changed_comparison}",
                ]
            )

        return "\n".join(lines)

    def generate_resource_churn_trend_report(
        self,
        summary: EnvironmentChurnTrendSummary,
        limit: int | None = None,
    ) -> str:
        title = "Resource Churn Trend"

        if not summary.resource_trends:
            return "\n".join(
                [
                    title,
                    "",
                    "No recorded resource activity found.",
                ]
            )

        lines = [
            title,
            "=" * len(title),
            "",
            "Resources:",
        ]

        resource_trends = summary.resource_trends
        displayed_trends = (
            resource_trends[:limit] if limit is not None else resource_trends
        )

        for trend in displayed_trends:
            lines.extend(
                [
                    "",
                    f"- Resource: {trend.resource_external_id}",
                    f"  Trend direction: {trend.trend_direction}",
                    f"  First activity count: {trend.first_activity_count}",
                    f"  Most recent activity count: {trend.most_recent_activity_count}",
                    f"  Activity delta: {trend.activity_delta}",
                    "",
                    "  Comparison Activity:",
                ]
            )

            for activity in trend.comparison_activity:
                lines.extend(
                    [
                        "",
                        f"    Comparison {activity.comparison_index}",
                        f"      Recorded activity: {activity.recorded_activity_count}",
                        f"      Changes: {activity.change_count}",
                        f"      Observations: {activity.observation_count}",
                        f"      Findings: {activity.finding_count}",
                    ]
                )

        if limit is not None and len(resource_trends) > limit:
            total = len(resource_trends)
            omitted = total - limit
            lines.extend(
                [
                    "",
                    (
                        f"Showing {limit} of {total} resource trends. "
                        f"{omitted} omitted. "
                        "Use --all to show the complete report."
                    ),
                ]
            )

        return "\n".join(lines)

    def generate_resource_metadata_grouping_report(
        self,
        groups: tuple[ResourceMetadataGroup, ...],
    ) -> str:
        title = "Resource Metadata Grouping"

        if not groups:
            return "\n".join(
                [
                    title,
                    "",
                    "No recorded metadata groups found.",
                ]
            )

        metadata_key = groups[0].metadata_key
        lines = [
            title,
            "=" * len(title),
            "",
            f"Metadata: {metadata_key}",
        ]

        for group in groups:
            lines.extend(
                [
                    "",
                    f"Value: {group.metadata_value}",
                    f"Recorded resources: {group.resource_count}",
                    "Resources:",
                    *self._render_resource_id_lines(group.resource_external_ids),
                ]
            )

        return "\n".join(lines)

    def generate_historical_inventory_timeline_report(
        self,
        observations: tuple[HistoricalInventoryObservation, ...],
    ) -> str:
        title = "Historical Inventory Timeline"

        if not observations:
            return "\n".join(
                [
                    title,
                    "",
                    "No historical inventory observations found.",
                ]
            )

        lines = [
            title,
            "=" * len(title),
        ]

        for observation in observations:
            lines.extend(
                [
                    "",
                    f"Snapshot: {observation.snapshot_id}",
                    f"Recorded resources: {observation.recorded_resource_count}",
                ]
            )

        return "\n".join(lines)

    def generate_resource_observation_history_report(
        self,
        summaries: tuple[ResourceObservationSummary, ...],
    ) -> str:
        title = "Resource Observation History"

        if not summaries:
            return "\n".join(
                [
                    title,
                    "",
                    "No resource observation history found.",
                ]
            )

        lines = [
            title,
            "=" * len(title),
        ]

        for summary in summaries:
            lines.extend(
                [
                    "",
                    f"Resource: {summary.resource_external_id}",
                    f"First observed snapshot: {summary.first_observed_snapshot_id}",
                    f"Latest observed snapshot: {summary.latest_observed_snapshot_id}",
                    f"Observed snapshots: {summary.observed_snapshot_count}",
                    f"Observation gaps: {summary.observation_gap_count}",
                ]
            )

        return "\n".join(lines)

    def generate_environment_evolution_report(
        self,
        history: tuple[AnalysisResult, ...],
        latest_change_index: int | None | object = _NOT_PROVIDED,
    ) -> str:
        if not history:
            return "No environment history."

        created_resources = self._resource_ids_from_created(history)
        modified_resources = self._resource_ids_from_modified(history)
        deleted_resources = self._resource_ids_from_deleted(history)

        observation_count = sum(len(result.observations) for result in history)
        finding_count = sum(len(result.findings) for result in history)

        lines = [
            "Environment Evolution",
            "=====================",
            "",
        ]

        if latest_change_index is not _NOT_PROVIDED:
            if latest_change_index is not None:
                lines.extend(
                    [
                        f"Latest comparison containing recorded changes: Comparison {latest_change_index}",
                        "",
                    ]
                )
            else:
                lines.extend(
                    [
                        "No recorded infrastructure changes found.",
                        "",
                    ]
                )

        lines.extend(
            [
                "Summary:",
                f"- Comparisons analyzed: {len(history)}",
                f"- Resources introduced: {len(created_resources)}",
                f"- Resources modified: {len(modified_resources)}",
                f"- Resources removed: {len(deleted_resources)}",
                f"- Observations: {observation_count}",
                f"- Findings: {finding_count}",
                "",
                "Most frequently changing resources:",
                *self._render_most_frequently_changing_resource_lines(history),
                "",
                "Operational activity concentration:",
                *self._render_operational_activity_concentration_lines(history),
                "",
                "Infrastructure activity breakdown:",
                *self._render_infrastructure_activity_breakdown_lines(history),
                "",
                "Recent infrastructure activity:",
                *self._render_recent_activity_lines(history),
                "",
                "Operational Review Queue:",
                *self._render_operational_review_queue_lines(history),
                "",
                "Introduced:",
                *self._render_resource_id_lines(created_resources),
                "",
                "Modified:",
                *self._render_resource_id_lines(modified_resources),
                "",
                "Removed:",
                *self._render_resource_id_lines(deleted_resources),
            ]
        )

        return "\n".join(lines)

    def _render_most_frequently_changing_resource_lines(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> list[str]:
        change_counts = self._count_resource_activity(history)

        if not change_counts:
            return ["- None"]

        ordered_changes = sorted(
            change_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )

        return [
            f"- {resource_id}: {change_count} change(s)"
            for resource_id, change_count in ordered_changes
        ]

    def _render_operational_activity_concentration_lines(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> list[str]:
        change_counts = self._count_resource_activity(history)

        if not change_counts:
            return ["- None"]

        total_changes = sum(change_counts.values())

        ordered_changes = sorted(
            change_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )

        return [
            (
                f"- {resource_id}: "
                f"{self._percentage(change_count, total_changes)}% "
                f"({change_count} of {total_changes} changes)"
            )
            for resource_id, change_count in ordered_changes
        ]

    def _render_infrastructure_activity_breakdown_lines(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> list[str]:
        created_count = sum(len(result.diff.created) for result in history)
        modified_count = sum(len(result.diff.modified) for result in history)
        deleted_count = sum(len(result.diff.deleted) for result in history)

        total_changes = created_count + modified_count + deleted_count

        if total_changes == 0:
            return ["- None"]

        return [
            (
                f"- Created: {self._percentage(created_count, total_changes)}% "
                f"({created_count} of {total_changes} changes)"
            ),
            (
                f"- Modified: {self._percentage(modified_count, total_changes)}% "
                f"({modified_count} of {total_changes} changes)"
            ),
            (
                f"- Deleted: {self._percentage(deleted_count, total_changes)}% "
                f"({deleted_count} of {total_changes} changes)"
            ),
        ]

    def _render_recent_activity_lines(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> list[str]:
        activity_lines: list[str] = []

        for index, result in enumerate(history, start=1):
            change_count = (
                len(result.diff.created)
                + len(result.diff.modified)
                + len(result.diff.deleted)
            )

            activity_lines.append(f"- Comparison {index}: {change_count} change(s)")

        return activity_lines

    def _render_operational_review_queue_lines(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> list[str]:
        change_counts = self._count_resource_activity(history)

        if not change_counts:
            return ["- None"]

        ordered_resources = sorted(
            change_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )

        lines: list[str] = []
        for index, (resource_id, count) in enumerate(ordered_resources, start=1):
            if index > 1:
                lines.append("")
            lines.append(f"{index}. {resource_id}")
            lines.append(f"   Appeared in {count} comparisons")

        return lines

    def _count_resource_activity(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> dict[str, int]:
        change_counts: dict[str, int] = {}
        for result in history:
            ids = {
                resource.external_id
                for resource in (
                    result.diff.created + result.diff.modified + result.diff.deleted
                )
            }
            for external_id in ids:
                change_counts[external_id] = change_counts.get(external_id, 0) + 1
        return change_counts

    def _percentage(
        self,
        count: int,
        total: int,
    ) -> str:
        return f"{(count / total) * 100:.1f}"

    def _resource_ids_from_created(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    resource.external_id
                    for result in history
                    for resource in result.diff.created
                }
            )
        )

    def _resource_ids_from_modified(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    resource.external_id
                    for result in history
                    for resource in result.diff.modified
                }
            )
        )

    def _resource_ids_from_deleted(
        self,
        history: tuple[AnalysisResult, ...],
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    resource.external_id
                    for result in history
                    for resource in result.diff.deleted
                }
            )
        )

    def _render_resource_id_lines(
        self,
        resource_ids: tuple[str, ...],
    ) -> list[str]:
        if not resource_ids:
            return ["- None"]

        return [f"- {resource_id}" for resource_id in resource_ids]

    def _render_resource_summary(
        self,
        resource_summary: ResourceSummary,
    ) -> str:
        lines = [
            f"Resource: {resource_summary.resource.external_id}",
            f"Change type: {resource_summary.change_type}",
            "",
            "Observations:",
        ]

        if resource_summary.observations:
            for observation in resource_summary.observations:
                lines.append(f"- {observation.message}")
        else:
            lines.append("- None")

        lines.append("")
        lines.append("Findings:")

        if resource_summary.findings:
            for finding in resource_summary.findings:
                lines.append(f"- {finding.message}")
        else:
            lines.append("- None")

        return "\n".join(lines)

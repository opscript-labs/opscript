from __future__ import annotations

from platformiq.model import AnalysisResult, Finding, Observation, Resource

from opscript.models import InfrastructureChangeSummary, ResourceSummary


class InfrastructureChangeSummaryService:
    """
    Application service responsible for turning structured engineering
    knowledge into a Opscript infrastructure change summary.
    """

    def summarize(
        self,
        result: AnalysisResult,
    ) -> InfrastructureChangeSummary:
        resource_summaries: list[ResourceSummary] = []
        observations_by_subject = self._observations_by_subject(result.observations)
        findings_by_subject = self._findings_by_subject(result.findings)

        resource_summaries.extend(
            self._summaries_for_resources(
                resources=self._sort_resources(result.diff.created),
                change_type="created",
                observations_by_subject=observations_by_subject,
                findings_by_subject=findings_by_subject,
            )
        )

        resource_summaries.extend(
            self._summaries_for_resources(
                resources=self._sort_resources(result.diff.modified),
                change_type="modified",
                observations_by_subject=observations_by_subject,
                findings_by_subject=findings_by_subject,
            )
        )

        resource_summaries.extend(
            self._summaries_for_resources(
                resources=self._sort_resources(result.diff.deleted),
                change_type="deleted",
                observations_by_subject=observations_by_subject,
                findings_by_subject=findings_by_subject,
            )
        )

        return InfrastructureChangeSummary(
            title="Infrastructure Change Summary",
            resource_summaries=tuple(resource_summaries),
        )

    def _summaries_for_resources(
        self,
        resources: tuple[Resource, ...],
        change_type: str,
        observations_by_subject: dict[str, tuple[Observation, ...]],
        findings_by_subject: dict[str, tuple[Finding, ...]],
    ) -> tuple[ResourceSummary, ...]:
        summaries: list[ResourceSummary] = []

        for resource in resources:
            summaries.append(
                ResourceSummary(
                    resource=resource,
                    change_type=change_type,
                    observations=observations_by_subject.get(resource.external_id, ()),
                    findings=findings_by_subject.get(resource.external_id, ()),
                )
            )

        return tuple(summaries)

    def _observations_by_subject(
        self,
        observations: tuple[Observation, ...],
    ) -> dict[str, tuple[Observation, ...]]:
        by_subject: dict[str, list[Observation]] = {}

        for observation in observations:
            by_subject.setdefault(observation.subject, []).append(observation)

        return {
            subject: tuple(subject_observations)
            for subject, subject_observations in by_subject.items()
        }

    def _findings_by_subject(
        self,
        findings: tuple[Finding, ...],
    ) -> dict[str, tuple[Finding, ...]]:
        by_subject: dict[str, list[Finding]] = {}

        for finding in findings:
            by_subject.setdefault(finding.subject, []).append(finding)

        return {
            subject: tuple(subject_findings)
            for subject, subject_findings in by_subject.items()
        }

    def _sort_resources(
        self,
        resources: tuple[Resource, ...],
    ) -> tuple[Resource, ...]:
        return tuple(
            sorted(
                resources,
                key=lambda resource: resource.external_id,
            )
        )

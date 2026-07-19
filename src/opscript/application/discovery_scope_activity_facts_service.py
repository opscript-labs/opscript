from platformiq.model import Snapshot

from opscript.application.analysis_service import AnalysisService
from opscript.models import DiscoveryScopeActivityFacts, DiscoveryScopeEligibility


class DiscoveryScopeActivityFactsService:
    """
    Application service for deriving scope-local historical activity facts.
    """

    def __init__(
        self,
        analysis_service: AnalysisService,
    ):
        self.analysis_service = analysis_service

    def derive(
        self,
        eligibility: DiscoveryScopeEligibility,
        history: tuple[Snapshot, ...],
    ) -> DiscoveryScopeActivityFacts:
        snapshot_count = len(history)
        valid_interval_count = max(snapshot_count - 1, 0)
        endpoint_resource_count = len(history[-1].resources) if history else 0

        introduced_count = 0
        modified_count = 0
        removed_count = 0

        if eligibility.eligibility_status == "eligible":
            analysis_history = self.analysis_service.analyze_history(history)
            introduced_count = sum(
                len(result.diff.created) for result in analysis_history
            )
            modified_count = sum(
                len(result.diff.modified) for result in analysis_history
            )
            removed_count = sum(len(result.diff.deleted) for result in analysis_history)

        return DiscoveryScopeActivityFacts(
            discovery_scope=eligibility.discovery_scope,
            effective_evidence_window=self._effective_evidence_window(snapshot_count),
            snapshot_count=snapshot_count,
            valid_interval_count=valid_interval_count,
            endpoint_resource_count=endpoint_resource_count,
            introduced_count=introduced_count,
            modified_count=modified_count,
            removed_count=removed_count,
            total_represented_change_count=(
                introduced_count + modified_count + removed_count
            ),
        )

    def _effective_evidence_window(
        self,
        snapshot_count: int,
    ) -> str | None:
        if snapshot_count == 0:
            return None
        if snapshot_count == 1:
            return "Snapshot 1"
        return f"Snapshot 1 -> Snapshot {snapshot_count}"

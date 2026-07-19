from opscript.models import (
    DiscoveryScopeActivityComparison,
    DiscoveryScopeActivityReport,
    ScopeActivityReport,
)


class DiscoveryScopeActivityReportService:
    """
    Application service for projecting cross-scope activity comparison reports.
    """

    def project(
        self,
        comparison: DiscoveryScopeActivityComparison,
    ) -> DiscoveryScopeActivityReport:
        return DiscoveryScopeActivityReport(
            compared_scope_count=comparison.compared_scope_count,
            scope_reports=tuple(
                ScopeActivityReport(
                    discovery_scope=facts.discovery_scope,
                    snapshot_count=facts.snapshot_count,
                    valid_interval_count=facts.valid_interval_count,
                    endpoint_resource_count=facts.endpoint_resource_count,
                    introduced_count=facts.introduced_count,
                    modified_count=facts.modified_count,
                    removed_count=facts.removed_count,
                    total_represented_change_count=(
                        facts.total_represented_change_count
                    ),
                    effective_evidence_window=facts.effective_evidence_window,
                )
                for facts in comparison.per_scope
            ),
            total_endpoint_resources=comparison.total_endpoint_resources,
            total_introduced=comparison.total_introduced,
            total_modified=comparison.total_modified,
            total_removed=comparison.total_removed,
            total_represented_changes=comparison.total_represented_changes,
        )

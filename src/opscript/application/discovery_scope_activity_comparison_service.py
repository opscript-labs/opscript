from opscript.models import (
    DiscoveryScopeActivityComparison,
    DiscoveryScopeActivityFacts,
)


class DiscoveryScopeActivityComparisonService:
    """
    Application service for aggregating pre-derived Discovery Scope facts.
    """

    def compare(
        self,
        facts: tuple[DiscoveryScopeActivityFacts, ...],
    ) -> DiscoveryScopeActivityComparison:
        return DiscoveryScopeActivityComparison(
            compared_scope_count=len(facts),
            compared_scopes=tuple(fact.discovery_scope for fact in facts),
            total_endpoint_resources=sum(
                fact.endpoint_resource_count for fact in facts
            ),
            total_introduced=sum(fact.introduced_count for fact in facts),
            total_modified=sum(fact.modified_count for fact in facts),
            total_removed=sum(fact.removed_count for fact in facts),
            total_represented_changes=sum(
                fact.total_represented_change_count for fact in facts
            ),
            evidence_windows=tuple(fact.effective_evidence_window for fact in facts),
            per_scope=facts,
        )

from platformiq.model import DiscoveryScope

from opscript.application import DiscoveryScopeActivityReportService
from opscript.models import (
    DiscoveryScopeActivityComparison,
    DiscoveryScopeActivityFacts,
)


def test_activity_report_projects_empty_comparison():
    service = DiscoveryScopeActivityReportService()

    report = service.project(DiscoveryScopeActivityComparison(compared_scope_count=0))

    assert report.compared_scope_count == 0
    assert report.scope_reports == ()
    assert report.total_endpoint_resources == 0
    assert report.total_introduced == 0
    assert report.total_modified == 0
    assert report.total_removed == 0
    assert report.total_represented_changes == 0


def test_activity_report_projects_single_scope():
    service = DiscoveryScopeActivityReportService()
    facts = _facts(
        "scope-a",
        endpoint_resources=2,
        introduced=1,
        modified=2,
        removed=3,
        window="Snapshot 1 -> Snapshot 2",
    )
    comparison = _comparison((facts,))

    report = service.project(comparison)

    assert report.compared_scope_count == 1
    assert len(report.scope_reports) == 1
    assert report.total_endpoint_resources == 2
    assert report.total_introduced == 1
    assert report.total_modified == 2
    assert report.total_removed == 3
    assert report.total_represented_changes == 6
    scope_report = report.scope_reports[0]
    assert scope_report.discovery_scope == DiscoveryScope("scope-a")
    assert scope_report.snapshot_count == 2
    assert scope_report.valid_interval_count == 1
    assert scope_report.endpoint_resource_count == 2
    assert scope_report.introduced_count == 1
    assert scope_report.modified_count == 2
    assert scope_report.removed_count == 3
    assert scope_report.total_represented_change_count == 6
    assert scope_report.effective_evidence_window == "Snapshot 1 -> Snapshot 2"


def test_activity_report_projects_multiple_scopes():
    service = DiscoveryScopeActivityReportService()
    scope_a = _facts("scope-a", endpoint_resources=2, introduced=1)
    scope_b = _facts("scope-b", endpoint_resources=4, modified=2)
    comparison = _comparison((scope_a, scope_b))

    report = service.project(comparison)

    assert report.compared_scope_count == 2
    assert tuple(scope.discovery_scope for scope in report.scope_reports) == (
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-b"),
    )
    assert report.total_endpoint_resources == 6
    assert report.total_introduced == 1
    assert report.total_modified == 2
    assert report.total_removed == 0
    assert report.total_represented_changes == 3


def test_activity_report_projection_is_deterministic():
    service = DiscoveryScopeActivityReportService()
    comparison = _comparison(
        (
            _facts("scope-a", endpoint_resources=2, introduced=1),
            _facts("scope-b", endpoint_resources=4, removed=3),
        )
    )

    first = service.project(comparison)
    second = service.project(comparison)

    assert first == second


def test_activity_report_preserves_scope_provenance_values():
    service = DiscoveryScopeActivityReportService()
    scope_a = _facts(
        "scope-a",
        endpoint_resources=2,
        introduced=1,
        window="Snapshot 1 -> Snapshot 2",
    )
    scope_b = _facts(
        "scope-b",
        endpoint_resources=4,
        removed=3,
        window="Snapshot 1 -> Snapshot 3",
    )

    report = service.project(_comparison((scope_a, scope_b)))

    assert tuple(scope.discovery_scope for scope in report.scope_reports) == (
        scope_a.discovery_scope,
        scope_b.discovery_scope,
    )
    assert tuple(scope.effective_evidence_window for scope in report.scope_reports) == (
        scope_a.effective_evidence_window,
        scope_b.effective_evidence_window,
    )
    assert tuple(scope.snapshot_count for scope in report.scope_reports) == (
        scope_a.snapshot_count,
        scope_b.snapshot_count,
    )
    assert tuple(scope.valid_interval_count for scope in report.scope_reports) == (
        scope_a.valid_interval_count,
        scope_b.valid_interval_count,
    )


def test_activity_report_does_not_mutate_comparison_input():
    service = DiscoveryScopeActivityReportService()
    scope_a = _facts("scope-a", endpoint_resources=2, introduced=1)
    scope_b = _facts("scope-b", endpoint_resources=4, removed=3)
    comparison = _comparison((scope_a, scope_b))

    service.project(comparison)

    assert comparison.per_scope == (scope_a, scope_b)
    assert comparison.total_endpoint_resources == 6
    assert comparison.total_represented_changes == 4


def _comparison(
    facts: tuple[DiscoveryScopeActivityFacts, ...],
) -> DiscoveryScopeActivityComparison:
    return DiscoveryScopeActivityComparison(
        compared_scope_count=len(facts),
        compared_scopes=tuple(fact.discovery_scope for fact in facts),
        total_endpoint_resources=sum(fact.endpoint_resource_count for fact in facts),
        total_introduced=sum(fact.introduced_count for fact in facts),
        total_modified=sum(fact.modified_count for fact in facts),
        total_removed=sum(fact.removed_count for fact in facts),
        total_represented_changes=sum(
            fact.total_represented_change_count for fact in facts
        ),
        evidence_windows=tuple(fact.effective_evidence_window for fact in facts),
        per_scope=facts,
    )


def _facts(
    scope: str,
    endpoint_resources: int = 0,
    introduced: int = 0,
    modified: int = 0,
    removed: int = 0,
    window: str | None = "Snapshot 1 -> Snapshot 2",
) -> DiscoveryScopeActivityFacts:
    return DiscoveryScopeActivityFacts(
        discovery_scope=DiscoveryScope(scope),
        effective_evidence_window=window,
        snapshot_count=2 if window else 0,
        valid_interval_count=1 if window else 0,
        endpoint_resource_count=endpoint_resources,
        introduced_count=introduced,
        modified_count=modified,
        removed_count=removed,
        total_represented_change_count=introduced + modified + removed,
    )

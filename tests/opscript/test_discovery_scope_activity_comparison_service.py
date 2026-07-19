from platformiq.model import DiscoveryScope

from opscript.application import DiscoveryScopeActivityComparisonService
from opscript.models import DiscoveryScopeActivityFacts


def test_activity_comparison_compares_two_qualified_scopes():
    service = DiscoveryScopeActivityComparisonService()
    scope_a = _facts(
        "scope-a",
        endpoint_resources=2,
        introduced=1,
        modified=2,
        removed=3,
        window="Snapshot 1 -> Snapshot 2",
    )
    scope_b = _facts(
        "scope-b",
        endpoint_resources=4,
        introduced=5,
        modified=6,
        removed=7,
        window="Snapshot 1 -> Snapshot 3",
    )

    comparison = service.compare((scope_a, scope_b))

    assert comparison.compared_scope_count == 2
    assert comparison.compared_scopes == (
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-b"),
    )
    assert comparison.total_endpoint_resources == 6
    assert comparison.total_introduced == 6
    assert comparison.total_modified == 8
    assert comparison.total_removed == 10
    assert comparison.total_represented_changes == 24
    assert comparison.evidence_windows == (
        "Snapshot 1 -> Snapshot 2",
        "Snapshot 1 -> Snapshot 3",
    )


def test_activity_comparison_compares_three_qualified_scopes():
    service = DiscoveryScopeActivityComparisonService()

    comparison = service.compare(
        (
            _facts("scope-a", endpoint_resources=1, introduced=1),
            _facts("scope-b", endpoint_resources=2, modified=2),
            _facts("scope-c", endpoint_resources=3, removed=3),
        )
    )

    assert comparison.compared_scope_count == 3
    assert comparison.compared_scopes == (
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-b"),
        DiscoveryScope("scope-c"),
    )
    assert comparison.total_endpoint_resources == 6
    assert comparison.total_introduced == 1
    assert comparison.total_modified == 2
    assert comparison.total_removed == 3
    assert comparison.total_represented_changes == 6


def test_activity_comparison_handles_identical_fact_sets():
    service = DiscoveryScopeActivityComparisonService()
    scope_a = _facts("scope-a", endpoint_resources=2, introduced=1)
    scope_b = _facts("scope-b", endpoint_resources=2, introduced=1)

    comparison = service.compare((scope_a, scope_b))

    assert comparison.total_endpoint_resources == 4
    assert comparison.total_introduced == 2
    assert comparison.total_modified == 0
    assert comparison.total_removed == 0
    assert comparison.total_represented_changes == 2


def test_activity_comparison_handles_empty_comparison_set():
    service = DiscoveryScopeActivityComparisonService()

    comparison = service.compare(())

    assert comparison.compared_scope_count == 0
    assert comparison.compared_scopes == ()
    assert comparison.total_endpoint_resources == 0
    assert comparison.total_introduced == 0
    assert comparison.total_modified == 0
    assert comparison.total_removed == 0
    assert comparison.total_represented_changes == 0
    assert comparison.evidence_windows == ()
    assert comparison.per_scope == ()


def test_activity_comparison_is_deterministic():
    service = DiscoveryScopeActivityComparisonService()
    facts = (
        _facts("scope-a", endpoint_resources=2, introduced=1),
        _facts("scope-b", endpoint_resources=4, removed=3),
    )

    first = service.compare(facts)
    second = service.compare(facts)

    assert first == second


def test_activity_comparison_preserves_provenance():
    service = DiscoveryScopeActivityComparisonService()
    scope_a = _facts("scope-a", endpoint_resources=2, introduced=1)
    scope_b = _facts("scope-b", endpoint_resources=4, removed=3)

    comparison = service.compare((scope_a, scope_b))

    assert comparison.per_scope == (scope_a, scope_b)
    assert comparison.per_scope[0] is scope_a
    assert comparison.per_scope[1] is scope_b


def test_activity_comparison_does_not_mutate_input_facts():
    service = DiscoveryScopeActivityComparisonService()
    scope_a = _facts("scope-a", endpoint_resources=2, introduced=1)
    scope_b = _facts("scope-b", endpoint_resources=4, removed=3)
    facts = (scope_a, scope_b)

    service.compare(facts)

    assert facts == (scope_a, scope_b)


def test_activity_comparison_preserves_input_order_without_ranking():
    service = DiscoveryScopeActivityComparisonService()
    high_change_scope = _facts("scope-z", endpoint_resources=1, introduced=10)
    low_change_scope = _facts("scope-a", endpoint_resources=1, introduced=1)

    comparison = service.compare((high_change_scope, low_change_scope))

    assert comparison.compared_scopes == (
        DiscoveryScope("scope-z"),
        DiscoveryScope("scope-a"),
    )
    assert comparison.per_scope == (high_change_scope, low_change_scope)


def test_activity_comparison_preserves_raw_counts_without_normalization():
    service = DiscoveryScopeActivityComparisonService()
    facts = (
        _facts("scope-a", endpoint_resources=10, introduced=2),
        _facts("scope-b", endpoint_resources=5, introduced=1),
    )

    comparison = service.compare(facts)

    assert comparison.total_endpoint_resources == 15
    assert comparison.total_introduced == 3
    assert not hasattr(comparison, "introduced_rate")
    assert not hasattr(comparison, "introduced_percentage")


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

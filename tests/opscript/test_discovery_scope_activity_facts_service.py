from platformiq.analysis import SnapshotDiffer
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.model.value_objects import ResourceState

from opscript.application import (
    AnalysisService,
    DiscoveryScopeActivityFactsService,
)
from opscript.models import DiscoveryScopeEligibility


def test_activity_facts_for_two_snapshots_with_no_changes():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    resource = _resource("resource-001")
    history = (
        _snapshot(discovery_scope, resource),
        _snapshot(discovery_scope, resource),
    )

    facts = service.derive(_eligible(discovery_scope, history), history)

    assert facts.discovery_scope == discovery_scope
    assert facts.effective_evidence_window == "Snapshot 1 -> Snapshot 2"
    assert facts.snapshot_count == 2
    assert facts.valid_interval_count == 1
    assert facts.endpoint_resource_count == 1
    assert facts.introduced_count == 0
    assert facts.modified_count == 0
    assert facts.removed_count == 0
    assert facts.total_represented_change_count == 0


def test_activity_facts_count_introduced_resources():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    resource = _resource("resource-001")
    history = (
        _snapshot(discovery_scope),
        _snapshot(discovery_scope, resource),
    )

    facts = service.derive(_eligible(discovery_scope, history), history)

    assert facts.endpoint_resource_count == 1
    assert facts.introduced_count == 1
    assert facts.modified_count == 0
    assert facts.removed_count == 0
    assert facts.total_represented_change_count == 1


def test_activity_facts_count_modified_resources():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    original = _resource("resource-001", version="one")
    updated = _resource("resource-001", version="two")
    history = (
        _snapshot(discovery_scope, original),
        _snapshot(discovery_scope, updated),
    )

    facts = service.derive(_eligible(discovery_scope, history), history)

    assert facts.endpoint_resource_count == 1
    assert facts.introduced_count == 0
    assert facts.modified_count == 1
    assert facts.removed_count == 0
    assert facts.total_represented_change_count == 1


def test_activity_facts_count_removed_resources():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    resource = _resource("resource-001")
    history = (
        _snapshot(discovery_scope, resource),
        _snapshot(discovery_scope),
    )

    facts = service.derive(_eligible(discovery_scope, history), history)

    assert facts.endpoint_resource_count == 0
    assert facts.introduced_count == 0
    assert facts.modified_count == 0
    assert facts.removed_count == 1
    assert facts.total_represented_change_count == 1


def test_activity_facts_count_multiple_valid_intervals():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    created = _resource("resource-created")
    original = _resource("resource-modified", version="one")
    updated = _resource("resource-modified", version="two")
    removed = _resource("resource-removed")
    history = (
        _snapshot(discovery_scope, original, removed),
        _snapshot(discovery_scope, original, removed, created),
        _snapshot(discovery_scope, updated, created),
    )

    facts = service.derive(_eligible(discovery_scope, history), history)

    assert facts.effective_evidence_window == "Snapshot 1 -> Snapshot 3"
    assert facts.snapshot_count == 3
    assert facts.valid_interval_count == 2
    assert facts.endpoint_resource_count == 2
    assert facts.introduced_count == 1
    assert facts.modified_count == 1
    assert facts.removed_count == 1
    assert facts.total_represented_change_count == 3


def test_activity_facts_for_empty_history():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    history: tuple[Snapshot, ...] = ()

    facts = service.derive(
        DiscoveryScopeEligibility(
            discovery_scope=discovery_scope,
            eligibility_status="ineligible",
            reason="no_snapshot_history",
            snapshot_count=0,
            valid_interval_count=0,
        ),
        history,
    )

    assert facts.effective_evidence_window is None
    assert facts.snapshot_count == 0
    assert facts.valid_interval_count == 0
    assert facts.endpoint_resource_count == 0
    assert facts.total_represented_change_count == 0


def test_activity_facts_for_partially_eligible_scope_do_not_count_interval_activity():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    resource = _resource("resource-001")
    history = (_snapshot(discovery_scope, resource),)

    facts = service.derive(
        DiscoveryScopeEligibility(
            discovery_scope=discovery_scope,
            eligibility_status="partially_eligible",
            reason="insufficient_comparison_history",
            snapshot_count=1,
            valid_interval_count=0,
        ),
        history,
    )

    assert facts.effective_evidence_window == "Snapshot 1"
    assert facts.snapshot_count == 1
    assert facts.valid_interval_count == 0
    assert facts.endpoint_resource_count == 1
    assert facts.introduced_count == 0
    assert facts.modified_count == 0
    assert facts.removed_count == 0
    assert facts.total_represented_change_count == 0


def test_activity_facts_are_deterministic():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    resource = _resource("resource-001")
    history = (
        _snapshot(discovery_scope),
        _snapshot(discovery_scope, resource),
    )
    eligibility = _eligible(discovery_scope, history)

    first = service.derive(eligibility, history)
    second = service.derive(eligibility, history)

    assert first == second


def test_activity_facts_do_not_mutate_history():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    resource = _resource("resource-001")
    first_snapshot = _snapshot(discovery_scope)
    second_snapshot = _snapshot(discovery_scope, resource)
    history = (first_snapshot, second_snapshot)

    service.derive(_eligible(discovery_scope, history), history)

    assert history == (first_snapshot, second_snapshot)


def test_activity_facts_do_not_use_storage():
    service = _service()
    discovery_scope = DiscoveryScope("scope-a")
    resource = _resource("resource-001")
    history = (
        _snapshot(discovery_scope),
        _snapshot(discovery_scope, resource),
    )

    facts = service.derive(_eligible(discovery_scope, history), history)

    assert facts.snapshot_count == 2


def _service() -> DiscoveryScopeActivityFactsService:
    return DiscoveryScopeActivityFactsService(
        analysis_service=AnalysisService(SnapshotDiffer())
    )


def _eligible(
    discovery_scope: DiscoveryScope,
    history: tuple[Snapshot, ...],
) -> DiscoveryScopeEligibility:
    return DiscoveryScopeEligibility(
        discovery_scope=discovery_scope,
        eligibility_status="eligible",
        reason="comparison_history_available",
        snapshot_count=len(history),
        valid_interval_count=max(len(history) - 1, 0),
    )


def _snapshot(
    discovery_scope: DiscoveryScope,
    *resources: Resource,
) -> Snapshot:
    return Snapshot(
        discovery_scope=discovery_scope,
        id=Identifier.new(),
        resources=resources,
    )


def _resource(
    external_id: str,
    version: str = "one",
) -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
        state=ResourceState(properties={"version": version}),
    )

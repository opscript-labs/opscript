from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Snapshot

from opscript.application import (
    DiscoveryScopeEligibilityService,
    DiscoveryScopeEligibilityWorkflow,
)
from opscript.storage import SnapshotStorageError


class FakeWorkflowStorage:
    def __init__(
        self,
        history: tuple[Snapshot, ...],
        latest: Snapshot | None,
    ):
        self.history = history
        self.latest = latest
        self.save_calls = 0
        self.load_history_calls = 0
        self.load_latest_calls = 0

    def save(
        self,
        snapshot: Snapshot,
    ) -> None:
        self.save_calls += 1

    def load_history(self) -> tuple[Snapshot, ...]:
        self.load_history_calls += 1
        return self.history

    def load_latest(self) -> Snapshot | None:
        self.load_latest_calls += 1
        return self.latest


class FailingWorkflowStorage:
    def __init__(
        self,
        message: str,
    ):
        self.message = message
        self.save_calls = 0
        self.load_history_calls = 0
        self.load_latest_calls = 0

    def save(
        self,
        snapshot: Snapshot,
    ) -> None:
        self.save_calls += 1

    def load_history(self) -> tuple[Snapshot, ...]:
        self.load_history_calls += 1
        raise SnapshotStorageError(self.message)

    def load_latest(self) -> Snapshot | None:
        self.load_latest_calls += 1
        return None


def test_discovery_scope_eligibility_workflow_returns_eligible_scope():
    workflow = _workflow()
    discovery_scope = DiscoveryScope("scope-a")
    first = _snapshot(discovery_scope)
    second = _snapshot(discovery_scope)
    storage = FakeWorkflowStorage(history=(first, second), latest=second)

    eligibility = workflow.run(discovery_scope, storage)

    assert eligibility.discovery_scope == discovery_scope
    assert eligibility.eligibility_status == "eligible"
    assert eligibility.reason == "comparison_history_available"
    assert eligibility.snapshot_count == 2
    assert eligibility.valid_interval_count == 1


def test_discovery_scope_eligibility_workflow_returns_partially_eligible_scope():
    workflow = _workflow()
    discovery_scope = DiscoveryScope("scope-a")
    snapshot = _snapshot(discovery_scope)
    storage = FakeWorkflowStorage(history=(snapshot,), latest=snapshot)

    eligibility = workflow.run(discovery_scope, storage)

    assert eligibility.eligibility_status == "partially_eligible"
    assert eligibility.reason == "insufficient_comparison_history"
    assert eligibility.snapshot_count == 1
    assert eligibility.valid_interval_count == 0


def test_discovery_scope_eligibility_workflow_returns_ineligible_scope():
    workflow = _workflow()
    discovery_scope = DiscoveryScope("scope-a")
    storage = FakeWorkflowStorage(history=(), latest=None)

    eligibility = workflow.run(discovery_scope, storage)

    assert eligibility.eligibility_status == "ineligible"
    assert eligibility.reason == "no_snapshot_history"
    assert eligibility.snapshot_count == 0
    assert eligibility.valid_interval_count == 0


def test_discovery_scope_eligibility_workflow_returns_storage_failure_result():
    workflow = _workflow()
    discovery_scope = DiscoveryScope("scope-a")
    storage = FailingWorkflowStorage("snapshot history is unavailable")

    eligibility = workflow.run(discovery_scope, storage)

    assert eligibility.eligibility_status == "ineligible"
    assert eligibility.reason == (
        "snapshot_history_unavailable: snapshot history is unavailable"
    )
    assert eligibility.snapshot_count == 0
    assert eligibility.valid_interval_count == 0


def test_discovery_scope_eligibility_workflow_is_deterministic():
    workflow = _workflow()
    discovery_scope = DiscoveryScope("scope-a")
    first = _snapshot(discovery_scope)
    second = _snapshot(discovery_scope)
    storage = FakeWorkflowStorage(history=(first, second), latest=second)

    first_result = workflow.run(discovery_scope, storage)
    second_result = workflow.run(discovery_scope, storage)

    assert first_result == second_result


def test_discovery_scope_eligibility_workflow_does_not_mutate_storage():
    workflow = _workflow()
    discovery_scope = DiscoveryScope("scope-a")
    first = _snapshot(discovery_scope)
    second = _snapshot(discovery_scope)
    storage = FakeWorkflowStorage(history=(first, second), latest=second)

    workflow.run(discovery_scope, storage)

    assert storage.save_calls == 0
    assert storage.load_history_calls == 1
    assert storage.load_latest_calls == 1


def test_discovery_scope_eligibility_workflow_does_not_modify_history():
    workflow = _workflow()
    discovery_scope = DiscoveryScope("scope-a")
    first = _snapshot(discovery_scope)
    second = _snapshot(discovery_scope)
    history = (first, second)
    storage = FakeWorkflowStorage(history=history, latest=second)

    workflow.run(discovery_scope, storage)

    assert storage.history == history


def _workflow() -> DiscoveryScopeEligibilityWorkflow:
    return DiscoveryScopeEligibilityWorkflow(
        eligibility_service=DiscoveryScopeEligibilityService()
    )


def _snapshot(
    discovery_scope: DiscoveryScope,
) -> Snapshot:
    return Snapshot(
        discovery_scope=discovery_scope,
        id=Identifier.new(),
    )

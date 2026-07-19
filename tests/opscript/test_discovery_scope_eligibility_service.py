from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Snapshot

from opscript.application import DiscoveryScopeEligibilityService
from opscript.storage import SnapshotStorageError


class FakeEligibilityStorage:
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


class FailingEligibilityStorage:
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


def test_discovery_scope_eligibility_empty_history_is_ineligible():
    service = DiscoveryScopeEligibilityService()
    discovery_scope = DiscoveryScope("scope-a")
    storage = FakeEligibilityStorage(history=(), latest=None)

    eligibility = service.qualify(discovery_scope, storage)

    assert eligibility.discovery_scope == discovery_scope
    assert eligibility.eligibility_status == "ineligible"
    assert eligibility.reason == "no_snapshot_history"
    assert eligibility.snapshot_count == 0
    assert eligibility.valid_interval_count == 0


def test_discovery_scope_eligibility_one_snapshot_is_partially_eligible():
    service = DiscoveryScopeEligibilityService()
    discovery_scope = DiscoveryScope("scope-a")
    snapshot = _snapshot(discovery_scope)
    storage = FakeEligibilityStorage(history=(snapshot,), latest=snapshot)

    eligibility = service.qualify(discovery_scope, storage)

    assert eligibility.eligibility_status == "partially_eligible"
    assert eligibility.reason == "insufficient_comparison_history"
    assert eligibility.snapshot_count == 1
    assert eligibility.valid_interval_count == 0


def test_discovery_scope_eligibility_two_snapshots_is_eligible():
    service = DiscoveryScopeEligibilityService()
    discovery_scope = DiscoveryScope("scope-a")
    first = _snapshot(discovery_scope)
    second = _snapshot(discovery_scope)
    storage = FakeEligibilityStorage(history=(first, second), latest=second)

    eligibility = service.qualify(discovery_scope, storage)

    assert eligibility.eligibility_status == "eligible"
    assert eligibility.reason == "comparison_history_available"
    assert eligibility.snapshot_count == 2
    assert eligibility.valid_interval_count == 1


def test_discovery_scope_eligibility_missing_latest_with_history_is_partially_eligible():
    service = DiscoveryScopeEligibilityService()
    discovery_scope = DiscoveryScope("scope-a")
    first = _snapshot(discovery_scope)
    second = _snapshot(discovery_scope)
    storage = FakeEligibilityStorage(history=(first, second), latest=None)

    eligibility = service.qualify(discovery_scope, storage)

    assert eligibility.eligibility_status == "partially_eligible"
    assert eligibility.reason == "latest_snapshot_unavailable"
    assert eligibility.snapshot_count == 2
    assert eligibility.valid_interval_count == 1


def test_discovery_scope_eligibility_unavailable_history_is_ineligible():
    service = DiscoveryScopeEligibilityService()
    discovery_scope = DiscoveryScope("scope-a")
    storage = FailingEligibilityStorage("snapshot history is unavailable")

    eligibility = service.qualify(discovery_scope, storage)

    assert eligibility.discovery_scope == discovery_scope
    assert eligibility.eligibility_status == "ineligible"
    assert eligibility.reason == (
        "snapshot_history_unavailable: snapshot history is unavailable"
    )
    assert eligibility.snapshot_count == 0
    assert eligibility.valid_interval_count == 0


def test_discovery_scope_eligibility_corrupted_history_is_ineligible():
    service = DiscoveryScopeEligibilityService()
    discovery_scope = DiscoveryScope("scope-a")
    storage = FailingEligibilityStorage("Malformed snapshot history object")

    eligibility = service.qualify(discovery_scope, storage)

    assert eligibility.eligibility_status == "ineligible"
    assert eligibility.reason == (
        "snapshot_history_unavailable: Malformed snapshot history object"
    )
    assert eligibility.snapshot_count == 0
    assert eligibility.valid_interval_count == 0


def test_discovery_scope_eligibility_is_deterministic():
    service = DiscoveryScopeEligibilityService()
    discovery_scope = DiscoveryScope("scope-a")
    first = _snapshot(discovery_scope)
    second = _snapshot(discovery_scope)
    storage = FakeEligibilityStorage(history=(first, second), latest=second)

    first_result = service.qualify(discovery_scope, storage)
    second_result = service.qualify(discovery_scope, storage)

    assert first_result == second_result


def test_discovery_scope_eligibility_does_not_mutate_storage_or_history():
    service = DiscoveryScopeEligibilityService()
    discovery_scope = DiscoveryScope("scope-a")
    first = _snapshot(discovery_scope)
    second = _snapshot(discovery_scope)
    history = (first, second)
    storage = FakeEligibilityStorage(history=history, latest=second)

    service.qualify(discovery_scope, storage)

    assert storage.save_calls == 0
    assert storage.history == history
    assert storage.load_history_calls == 1
    assert storage.load_latest_calls == 1


def _snapshot(
    discovery_scope: DiscoveryScope,
) -> Snapshot:
    return Snapshot(
        discovery_scope=discovery_scope,
        id=Identifier.new(),
    )

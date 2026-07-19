from opscript.config import DEFAULT_DISCOVERY_SCOPE
import pytest

from opscript.storage import InMemorySnapshotStorage, SnapshotStorageError
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Snapshot


def _snapshot(
    discovery_scope: DiscoveryScope,
) -> Snapshot:
    return Snapshot(discovery_scope=discovery_scope, id=Identifier.new())


def test_memory_storage_saves_and_loads_snapshot():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(snapshot)

    assert storage.load_latest() == snapshot


def test_memory_storage_loads_snapshot_history_in_save_order():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(first)
    storage.save(second)

    assert storage.load_history() == (first, second)


def test_memory_storage_returns_empty_history_when_no_snapshots_exist():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    assert storage.load_history() == ()


def test_memory_storage_rejects_mismatched_scope_save():
    storage = InMemorySnapshotStorage(discovery_scope=DiscoveryScope("scope-001"))
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("scope-002"),
        id=Identifier.new(),
    )

    with pytest.raises(SnapshotStorageError, match="discovery scope"):
        storage.save(snapshot)


def test_memory_storage_instances_keep_independent_scope_histories():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = InMemorySnapshotStorage(discovery_scope=scope_a)
    storage_b = InMemorySnapshotStorage(discovery_scope=scope_b)
    first_a = _snapshot(scope_a)
    second_a = _snapshot(scope_a)
    only_b = _snapshot(scope_b)

    storage_a.save(first_a)
    storage_b.save(only_b)
    storage_a.save(second_a)

    assert storage_a.load_history() == (first_a, second_a)
    assert storage_b.load_history() == (only_b,)
    assert storage_a.load_latest() == second_a
    assert storage_b.load_latest() == only_b

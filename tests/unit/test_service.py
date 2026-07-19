from platformiq.contracts import SnapshotStorage
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Snapshot


class FakeSnapshotStorage(SnapshotStorage):
    def __init__(self):
        self.snapshot = None

    def save(self, snapshot: Snapshot) -> None:
        self.snapshot = snapshot

    def load_latest(self) -> Snapshot | None:
        return self.snapshot


def test_snapshot_storage_can_save_and_load():
    storage = FakeSnapshotStorage()

    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )

    storage.save(snapshot)

    assert storage.load_latest() == snapshot

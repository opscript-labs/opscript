from __future__ import annotations

from platformiq.model import DiscoveryScope, Snapshot

from opscript.storage.errors import SnapshotStorageError


class InMemorySnapshotStorage:
    """
    Simple snapshot storage for testing
    and local execution.
    """

    def __init__(
        self,
        discovery_scope: DiscoveryScope,
    ):
        self.discovery_scope = discovery_scope
        self.snapshots: list[Snapshot] = []

    def save(
        self,
        snapshot: Snapshot,
    ) -> None:
        self._ensure_matching_scope(snapshot)
        self.snapshots.append(snapshot)

    def load_latest(
        self,
    ) -> Snapshot | None:
        if not self.snapshots:
            return None

        return self._ensure_matching_scope(self.snapshots[-1])

    def load_history(
        self,
    ) -> tuple[Snapshot, ...]:
        return self._ensure_single_scope(tuple(self.snapshots))

    def _ensure_matching_scope(
        self,
        snapshot: Snapshot,
    ) -> Snapshot:
        if snapshot.discovery_scope != self.discovery_scope:
            raise SnapshotStorageError(
                "Snapshot discovery scope does not match storage discovery scope."
            )
        return snapshot

    def _ensure_single_scope(
        self,
        snapshots: tuple[Snapshot, ...],
    ) -> tuple[Snapshot, ...]:
        for snapshot in snapshots:
            self._ensure_matching_scope(snapshot)
        return snapshots

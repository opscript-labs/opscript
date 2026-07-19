from __future__ import annotations

from platformiq.model import DiffResult, Snapshot


class SnapshotScopeMismatchError(Exception):
    """
    Raised when attempting to compare snapshots from different discovery scopes.
    """


class SnapshotDiffer:
    """
    Compares two infrastructure snapshots.
    """

    def compare(self, previous: Snapshot, current: Snapshot) -> DiffResult:
        """
        Compare two snapshots and identify created, deleted,
        and modified resources.
        """
        if previous.discovery_scope != current.discovery_scope:
            raise SnapshotScopeMismatchError(
                "Cannot compare snapshots from different discovery scopes."
            )

        previous_by_id = {
            resource.external_id: resource for resource in previous.resources
        }

        current_by_id = {
            resource.external_id: resource for resource in current.resources
        }

        created = tuple(
            resource
            for external_id, resource in current_by_id.items()
            if external_id not in previous_by_id
        )

        deleted = tuple(
            resource
            for external_id, resource in previous_by_id.items()
            if external_id not in current_by_id
        )

        modified = tuple(
            current_by_id[external_id]
            for external_id in previous_by_id.keys() & current_by_id.keys()
            if previous_by_id[external_id].state != current_by_id[external_id].state
        )

        return DiffResult(
            previous_snapshot_id=previous.id,
            current_snapshot_id=current.id,
            created=created,
            deleted=deleted,
            modified=modified,
        )

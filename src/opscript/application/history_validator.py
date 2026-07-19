from __future__ import annotations

from platformiq.model import Snapshot


class HistoryValidationError(Exception):
    """Raised when snapshot history validation fails."""

    pass


class HistoryValidator:
    """
    Validates snapshot history sequence integrity before analysis.
    """

    def validate(self, snapshots: tuple[Snapshot, ...]) -> None:
        """
        Perform sequence-level history integrity validations on a sequence of snapshots.

        Note: Chronological validation is not yet possible because the
        current Snapshot model does not contain timestamp or ordering metadata.
        """
        if not isinstance(snapshots, tuple):
            raise HistoryValidationError(
                "Snapshot history must be a tuple of Snapshot objects."
            )

        seen_snapshot_ids = set()
        discovery_scope = None

        for snapshot in snapshots:
            if snapshot.id in seen_snapshot_ids:
                raise HistoryValidationError(
                    f"Duplicate snapshot ID detected in history: {snapshot.id}"
                )
            seen_snapshot_ids.add(snapshot.id)

            if discovery_scope is None:
                discovery_scope = snapshot.discovery_scope
                continue

            if snapshot.discovery_scope != discovery_scope:
                raise HistoryValidationError(
                    "Snapshot history contains multiple discovery scopes."
                )

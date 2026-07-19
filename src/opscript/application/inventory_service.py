from __future__ import annotations

from time import perf_counter
from typing import Callable

from platformiq.contracts import DiscoveryProvider, SnapshotStorage
from platformiq.model import Snapshot

from opscript.application.retry_policy import RetryPolicy
from opscript.errors import classify_provider_error
from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger
from opscript.storage import SnapshotCommittedWithDegradedLatestError

logger = get_logger()


class InventoryService:
    """
    Application service responsible for inventory collection.
    """

    def __init__(
        self,
        discovery_provider: DiscoveryProvider,
        snapshot_storage: SnapshotStorage,
        retry_policy: RetryPolicy | None = None,
    ):
        self.discovery_provider = discovery_provider
        self.snapshot_storage = snapshot_storage
        self.retry_policy = retry_policy or RetryPolicy()

    def collect_snapshot(
        self,
        phase_completed: Callable[[str, int], None] | None = None,
    ) -> Snapshot:
        """
        Discover and persist the current snapshot.
        """

        def discover_with_classification():
            try:
                return self.discovery_provider.discover()
            except Exception as error:
                raise classify_provider_error(error)

        discovery_started_at = perf_counter()
        snapshot = self.retry_policy.execute(discover_with_classification)
        if phase_completed is not None:
            phase_completed(
                "discovery",
                int((perf_counter() - discovery_started_at) * 1000),
            )

        persistence_started_at = perf_counter()
        try:
            self.snapshot_storage.save(snapshot)
        except SnapshotCommittedWithDegradedLatestError as error:
            logger.warning(
                format_log_event(
                    "snapshot_persistence_degraded",
                    latest_reference_maintenance=error.latest_reference_maintenance,
                    operation="snapshot_persistence",
                    phase="latest_reference_update",
                    record_key=error.record_key,
                    snapshot_committed=error.snapshot_committed,
                    **active_execution_log_fields(),
                )
            )
        if phase_completed is not None:
            phase_completed(
                "snapshot_persistence",
                int((perf_counter() - persistence_started_at) * 1000),
            )

        return snapshot

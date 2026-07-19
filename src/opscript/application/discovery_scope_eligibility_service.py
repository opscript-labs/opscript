from platformiq.model import DiscoveryScope

from opscript.models import DiscoveryScopeEligibility
from opscript.storage import SnapshotStorageError


class DiscoveryScopeEligibilityService:
    """
    Application service for scope-local comparison eligibility evidence.
    """

    def qualify(
        self,
        discovery_scope: DiscoveryScope,
        storage,
    ) -> DiscoveryScopeEligibility:
        try:
            history = storage.load_history()
            latest_snapshot = storage.load_latest()
        except SnapshotStorageError as error:
            return DiscoveryScopeEligibility(
                discovery_scope=discovery_scope,
                eligibility_status="ineligible",
                reason=f"snapshot_history_unavailable: {error}",
                snapshot_count=0,
                valid_interval_count=0,
            )

        snapshot_count = len(history)
        valid_interval_count = max(snapshot_count - 1, 0)

        if snapshot_count == 0:
            return DiscoveryScopeEligibility(
                discovery_scope=discovery_scope,
                eligibility_status="ineligible",
                reason="no_snapshot_history",
                snapshot_count=0,
                valid_interval_count=0,
            )

        if latest_snapshot is None:
            return DiscoveryScopeEligibility(
                discovery_scope=discovery_scope,
                eligibility_status="partially_eligible",
                reason="latest_snapshot_unavailable",
                snapshot_count=snapshot_count,
                valid_interval_count=valid_interval_count,
            )

        if snapshot_count == 1:
            return DiscoveryScopeEligibility(
                discovery_scope=discovery_scope,
                eligibility_status="partially_eligible",
                reason="insufficient_comparison_history",
                snapshot_count=snapshot_count,
                valid_interval_count=0,
            )

        return DiscoveryScopeEligibility(
            discovery_scope=discovery_scope,
            eligibility_status="eligible",
            reason="comparison_history_available",
            snapshot_count=snapshot_count,
            valid_interval_count=valid_interval_count,
        )

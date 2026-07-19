from opscript.config import DEFAULT_DISCOVERY_SCOPE
from platformiq.analysis import SnapshotDiffer
from platformiq.core import Identifier
from platformiq.model import Resource, Snapshot

from opscript import AnalysisService, InventoryService


class FakeDiscoveryProvider:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def discover(self):
        return self.snapshot


class FakeSnapshotStorage:
    def __init__(self):
        self.saved_snapshot = None

    def save(self, snapshot):
        self.saved_snapshot = snapshot

    def load_latest(self):
        return self.saved_snapshot


def test_inventory_and_analysis_workflow():
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    previous_snapshot = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
    )

    current_snapshot = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(resource,),
    )

    inventory = InventoryService(
        FakeDiscoveryProvider(current_snapshot),
        FakeSnapshotStorage(),
    )

    analysis = AnalysisService(SnapshotDiffer())

    discovered_snapshot = inventory.collect_snapshot()

    result = analysis.analyze(
        previous_snapshot,
        discovered_snapshot,
    )

    observations = analysis.observe(
        previous_snapshot,
        discovered_snapshot,
    )

    assert result.created == (resource,)

    assert len(observations) == 1
    assert observations[0].subject == resource.external_id
    assert observations[0].type == "resource_created"

from opscript.config import DEFAULT_DISCOVERY_SCOPE
from opscript import InventoryService
from opscript.provider.aws import AWSDiscoveryProvider
from opscript.storage import InMemorySnapshotStorage
from platformiq.model import Snapshot

TEST_SCOPE = DEFAULT_DISCOVERY_SCOPE


class FakeEC2Discovery:
    def discover(self):
        return ()


class FakeLambdaDiscovery:
    def discover(self):
        return ()


class FakeS3Discovery:
    def discover(self):
        return ()


class FakeRDSDiscovery:
    def discover(self):
        return ()


class FakeECRDiscovery:
    def discover(self):
        return ()


class FakeEventBridgeDiscovery:
    def discover(self):
        return ()


class FakeAPIGatewayDiscovery:
    def discover(self):
        return ()


class FakeSQSDiscovery:
    def discover(self):
        return ()


class FakeSNSDiscovery:
    def discover(self):
        return ()


def test_aws_inventory_workflow():

    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        FakeEC2Discovery(),
        FakeLambdaDiscovery(),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )

    storage = InMemorySnapshotStorage(discovery_scope=TEST_SCOPE)

    service = InventoryService(
        provider,
        storage,
    )

    snapshot = service.collect_snapshot()

    assert isinstance(snapshot, Snapshot)
    assert storage.load_latest() == snapshot

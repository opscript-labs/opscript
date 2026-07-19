from platformiq.contracts import DiscoveryProvider
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Snapshot


class FakeDiscoveryProvider(DiscoveryProvider):
    def discover(self) -> Snapshot:
        return Snapshot(
            discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
        )


def test_discovery_provider_returns_snapshot():
    provider = FakeDiscoveryProvider()

    snapshot = provider.discover()

    assert isinstance(snapshot, Snapshot)

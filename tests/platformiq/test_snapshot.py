import pytest
from dataclasses import FrozenInstanceError

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot


def test_discovery_scope_is_immutable():
    scope = DiscoveryScope("scope-001")

    with pytest.raises(FrozenInstanceError):
        scope.value = "scope-002"  # type: ignore[misc]


def test_discovery_scope_rejects_empty_value():
    with pytest.raises(ValueError, match="must not be empty"):
        DiscoveryScope("")


def test_snapshot_requires_discovery_scope():
    with pytest.raises(TypeError):
        Snapshot(id=Identifier.new())  # type: ignore[call-arg]


def test_snapshot_has_identifier():
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )

    assert isinstance(snapshot.id, Identifier)


def test_snapshot_is_empty_by_default():
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )

    assert snapshot.resources == ()
    assert isinstance(snapshot.discovery_scope, DiscoveryScope)


def test_snapshot_is_immutable():
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.discovery_scope = DiscoveryScope("other-scope")  # type: ignore[misc]


def test_snapshot_contains_resources():
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"),
        id=Identifier.new(),
        resources=(resource,),
    )

    assert len(snapshot.resources) == 1
    assert snapshot.resources[0] == resource
    assert snapshot.resources[0].external_id == "resource-001"

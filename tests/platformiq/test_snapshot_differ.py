import pytest

from platformiq.analysis.snapshot_differ import (
    SnapshotDiffer,
    SnapshotScopeMismatchError,
)
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.model.value_objects import ResourceState


def test_compare_returns_empty_diff_result_for_empty_snapshots():
    differ = SnapshotDiffer()

    previous = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )
    current = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )

    result = differ.compare(previous, current)

    assert result.previous_snapshot_id == previous.id
    assert result.current_snapshot_id == current.id
    assert result.created == ()
    assert result.deleted == ()
    assert result.modified == ()


def test_compare_fails_for_different_discovery_scopes():
    differ = SnapshotDiffer()

    previous = Snapshot(
        discovery_scope=DiscoveryScope("previous-scope"),
        id=Identifier.new(),
    )
    current = Snapshot(
        discovery_scope=DiscoveryScope("current-scope"),
        id=Identifier.new(),
    )

    with pytest.raises(SnapshotScopeMismatchError, match="different discovery scopes"):
        differ.compare(previous, current)


def test_compare_detects_created_resource():
    differ = SnapshotDiffer()

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    previous = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )

    current = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"),
        id=Identifier.new(),
        resources=(resource,),
    )

    result = differ.compare(previous, current)

    assert result.previous_snapshot_id == previous.id
    assert result.current_snapshot_id == current.id
    assert result.created == (resource,)


def test_compare_detects_deleted_resource():
    differ = SnapshotDiffer()

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    previous = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"),
        id=Identifier.new(),
        resources=(resource,),
    )

    current = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )

    result = differ.compare(previous, current)

    assert result.previous_snapshot_id == previous.id
    assert result.current_snapshot_id == current.id
    assert result.deleted == (resource,)


def test_compare_detects_modified_resource():
    differ = SnapshotDiffer()

    previous_resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(
            properties={
                "size": "small",
            }
        ),
    )

    current_resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(
            properties={
                "size": "large",
            }
        ),
    )

    previous = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"),
        id=Identifier.new(),
        resources=(previous_resource,),
    )

    current = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"),
        id=Identifier.new(),
        resources=(current_resource,),
    )

    result = differ.compare(previous, current)

    assert result.previous_snapshot_id == previous.id
    assert result.current_snapshot_id == current.id
    assert result.modified == (current_resource,)

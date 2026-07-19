import pytest

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.model.value_objects import ResourceState
from platformiq.serialization import SnapshotSerializer
from platformiq.serialization.snapshot_serializer import SnapshotSerializationError


def test_snapshot_serializer_creates_dict():
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"), id=Identifier.new()
    )

    serializer = SnapshotSerializer()

    result = serializer.serialize(snapshot)

    assert "id" in result
    assert "resources" in result


def test_snapshot_serializer_deserializes_snapshot():
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"),
        id=Identifier.new(),
        resources=(resource,),
    )

    serializer = SnapshotSerializer()

    data = serializer.serialize(snapshot)
    result = serializer.deserialize(data)

    assert result.id == snapshot.id
    assert result.resources[0].id == resource.id
    assert result.resources[0].external_id == "resource-001"


def test_snapshot_serializer_round_trips_resource_state_properties():
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(
            properties={
                "tags": {
                    "Environment": "prod",
                    "Owner": "platform",
                },
                "instance_type": "t3.micro",
            }
        ),
    )
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"),
        id=Identifier.new(),
        resources=(resource,),
    )
    serializer = SnapshotSerializer()

    data = serializer.serialize(snapshot)
    result = serializer.deserialize(data)

    assert data["resources"][0]["state"] == {
        "properties": {
            "tags": {
                "Environment": "prod",
                "Owner": "platform",
            },
            "instance_type": "t3.micro",
        }
    }
    assert result.resources[0].state.properties == resource.state.properties


def test_snapshot_serializer_deserializes_legacy_resource_without_state():
    resource_id = Identifier.new()
    snapshot_id = Identifier.new()
    discovery_scope = DiscoveryScope("legacy-scope")
    serializer = SnapshotSerializer()

    result = serializer.deserialize(
        {
            "id": str(snapshot_id),
            "resources": [
                {
                    "id": str(resource_id),
                    "external_id": "resource-001",
                }
            ],
        },
        discovery_scope=discovery_scope,
    )

    assert result.id == snapshot_id
    assert result.discovery_scope == discovery_scope
    assert result.resources[0].id == resource_id
    assert result.resources[0].external_id == "resource-001"
    assert result.resources[0].state.properties == {}


def test_snapshot_serializer_fails_legacy_snapshot_without_contextual_scope():
    serializer = SnapshotSerializer()

    with pytest.raises(SnapshotSerializationError, match="discovery_scope"):
        serializer.deserialize(
            {
                "id": str(Identifier.new()),
                "resources": [],
            }
        )


def test_snapshot_serializer_preserves_empty_resource_state_properties():
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(properties={}),
    )
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("test-scope"),
        id=Identifier.new(),
        resources=(resource,),
    )
    serializer = SnapshotSerializer()

    data = serializer.serialize(snapshot)
    result = serializer.deserialize(data)

    assert data["resources"][0]["state"] == {"properties": {}}
    assert result.resources[0].state.properties == {}


def test_snapshot_serializer_fails_when_snapshot_id_is_missing():
    serializer = SnapshotSerializer()

    with pytest.raises(SnapshotSerializationError, match="missing required id"):
        serializer.deserialize(
            {
                "resources": [],
            }
        )


def test_snapshot_serializer_fails_when_resources_are_missing():
    serializer = SnapshotSerializer()

    with pytest.raises(SnapshotSerializationError, match="missing required resources"):
        serializer.deserialize(
            {
                "id": str(Identifier.new()),
            }
        )


def test_snapshot_serializer_fails_when_resources_are_not_a_list():
    serializer = SnapshotSerializer()

    with pytest.raises(SnapshotSerializationError, match="resources must be a list"):
        serializer.deserialize(
            {
                "id": str(Identifier.new()),
                "resources": "not-a-list",
            }
        )


def test_snapshot_serializer_fails_when_resource_id_is_missing():
    serializer = SnapshotSerializer()

    with pytest.raises(
        SnapshotSerializationError, match="resource is missing required id"
    ):
        serializer.deserialize(
            {
                "id": str(Identifier.new()),
                "resources": [
                    {
                        "external_id": "resource-001",
                    }
                ],
            }
        )


def test_snapshot_serializer_fails_when_resource_external_id_is_missing():
    serializer = SnapshotSerializer()

    with pytest.raises(
        SnapshotSerializationError,
        match="resource is missing required external_id",
    ):
        serializer.deserialize(
            {
                "id": str(Identifier.new()),
                "resources": [
                    {
                        "id": str(Identifier.new()),
                    }
                ],
            }
        )


def test_snapshot_serializer_fails_on_duplicate_resource_id():
    resource_id = str(Identifier.new())

    serializer = SnapshotSerializer()

    with pytest.raises(SnapshotSerializationError, match="duplicate resource id"):
        serializer.deserialize(
            {
                "id": str(Identifier.new()),
                "resources": [
                    {
                        "id": resource_id,
                        "external_id": "resource-001",
                    },
                    {
                        "id": resource_id,
                        "external_id": "resource-002",
                    },
                ],
            }
        )


def test_snapshot_serializer_fails_on_duplicate_resource_external_id():
    serializer = SnapshotSerializer()

    with pytest.raises(
        SnapshotSerializationError, match="duplicate resource external_id"
    ):
        serializer.deserialize(
            {
                "id": str(Identifier.new()),
                "resources": [
                    {
                        "id": str(Identifier.new()),
                        "external_id": "resource-001",
                    },
                    {
                        "id": str(Identifier.new()),
                        "external_id": "resource-001",
                    },
                ],
            }
        )

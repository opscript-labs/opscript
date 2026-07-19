from __future__ import annotations

from typing import Any

from platformiq.core import Identifier
from platformiq.model import Resource, Snapshot
from platformiq.model.value_objects import DiscoveryScope, ResourceState


class SnapshotSerializationError(Exception):
    """
    Raised when serialized snapshot content is malformed.
    """


class SnapshotSerializer:
    """
    Converts snapshots to and from
    serializable representations.
    """

    def serialize(
        self,
        snapshot: Snapshot,
    ) -> dict:
        return {
            "id": str(snapshot.id),
            "discovery_scope": str(snapshot.discovery_scope),
            "resources": [
                {
                    "id": str(resource.id),
                    "external_id": resource.external_id,
                    "state": {
                        "properties": resource.state.properties,
                    },
                }
                for resource in snapshot.resources
            ],
        }

    def deserialize(
        self,
        data: dict,
        *,
        discovery_scope: DiscoveryScope | None = None,
    ) -> Snapshot:
        self._validate_snapshot_data(data)
        serialized_scope = data.get("discovery_scope")
        if serialized_scope is None:
            if discovery_scope is None:
                raise SnapshotSerializationError(
                    "Snapshot data is missing required discovery_scope."
                )
            snapshot_scope = discovery_scope
        else:
            if not isinstance(serialized_scope, str):
                raise SnapshotSerializationError(
                    "Snapshot discovery_scope must be a string."
                )
            snapshot_scope = DiscoveryScope(serialized_scope)

        return Snapshot(
            id=Identifier.from_string(data["id"]),
            discovery_scope=snapshot_scope,
            resources=tuple(
                Resource(
                    id=Identifier.from_string(resource["id"]),
                    external_id=resource["external_id"],
                    state=ResourceState(
                        properties=resource.get("state", {}).get("properties", {})
                    ),
                )
                for resource in data["resources"]
            ),
        )

    def _validate_snapshot_data(
        self,
        data: Any,
    ) -> None:
        if not isinstance(data, dict):
            raise SnapshotSerializationError("Snapshot data must be an object.")

        if "id" not in data:
            raise SnapshotSerializationError("Snapshot data is missing required id.")

        if "resources" not in data:
            raise SnapshotSerializationError(
                "Snapshot data is missing required resources."
            )

        if not isinstance(data["resources"], list):
            raise SnapshotSerializationError("Snapshot resources must be a list.")

        resource_ids: set[str] = set()
        external_ids: set[str] = set()

        for resource in data["resources"]:
            self._validate_resource_data(resource)

            if resource["id"] in resource_ids:
                raise SnapshotSerializationError(
                    "Snapshot contains duplicate resource id."
                )

            if resource["external_id"] in external_ids:
                raise SnapshotSerializationError(
                    "Snapshot contains duplicate resource external_id."
                )

            resource_ids.add(resource["id"])
            external_ids.add(resource["external_id"])

    def _validate_resource_data(
        self,
        data: Any,
    ) -> None:
        if not isinstance(data, dict):
            raise SnapshotSerializationError("Snapshot resource must be an object.")

        if "id" not in data:
            raise SnapshotSerializationError(
                "Snapshot resource is missing required id."
            )

        if "external_id" not in data:
            raise SnapshotSerializationError(
                "Snapshot resource is missing required external_id."
            )

        if not isinstance(data["id"], str):
            raise SnapshotSerializationError("Snapshot resource id must be a string.")

        if not isinstance(data["external_id"], str):
            raise SnapshotSerializationError(
                "Snapshot resource external_id must be a string."
            )

        if "state" in data:
            if not isinstance(data["state"], dict):
                raise SnapshotSerializationError(
                    "Snapshot resource state must be an object."
                )

            if "properties" in data["state"] and not isinstance(
                data["state"]["properties"], dict
            ):
                raise SnapshotSerializationError(
                    "Snapshot resource state properties must be an object."
                )

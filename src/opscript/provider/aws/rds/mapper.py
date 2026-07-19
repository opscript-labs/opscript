from __future__ import annotations

from platformiq.core import Identifier
from platformiq.model import Resource
from platformiq.model.value_objects import ResourceState


class RDSResourceMapper:
    """
    Converts AWS RDS DB instance representations into PlatformIQ resources.
    """

    def map(
        self,
        db_instance: dict,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=db_instance["DBInstanceIdentifier"],
            state=ResourceState(
                properties={
                    "engine": db_instance.get("Engine"),
                    "engine_version": db_instance.get("EngineVersion"),
                    "instance_class": db_instance.get("DBInstanceClass"),
                    "multi_az": db_instance.get("MultiAZ"),
                    "publicly_accessible": db_instance.get("PubliclyAccessible"),
                    "allocated_storage": db_instance.get("AllocatedStorage"),
                    "storage_type": db_instance.get("StorageType"),
                }
            ),
        )

from __future__ import annotations

from platformiq.core import Identifier
from platformiq.model import Resource
from platformiq.model.value_objects import ResourceState


class EC2ResourceMapper:
    """
    Converts AWS EC2 instance representations
    into PlatformIQ resources.
    """

    def map(
        self,
        instance_id: str,
        tags: list[dict[str, str]] | None = None,
    ) -> Resource:
        return Resource(
            id=Identifier.new(),
            external_id=instance_id,
            state=ResourceState(
                properties={
                    "tags": self._map_tags(tags or []),
                }
            ),
        )

    def _map_tags(
        self,
        tags: list[dict[str, str]],
    ) -> dict[str, str]:
        return {
            tag["Key"]: tag["Value"] for tag in tags if "Key" in tag and "Value" in tag
        }

from __future__ import annotations

from dataclasses import dataclass, field

from platformiq.model.entity import Entity
from platformiq.model.value_objects import ResourceState


@dataclass(frozen=True)
class Resource(Entity):
    """
    Base domain entity representing a cloud resource.

    Attributes:
        id:
            Internal PlatformIQ identifier.

        external_id:
            Stable provider identifier (ARN, Azure Resource ID,
            GCP selfLink, etc.).

        state:
            Observable provider-neutral state used to determine
            whether the resource has changed.
    """

    external_id: str
    state: ResourceState = field(default_factory=ResourceState)

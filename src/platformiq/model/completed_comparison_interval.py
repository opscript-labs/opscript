from __future__ import annotations

from dataclasses import dataclass, field

from platformiq.core import Identifier
from platformiq.model.observation import Observation
from platformiq.model.value_objects.discovery_scope import DiscoveryScope


@dataclass(frozen=True)
class CompletedComparisonInterval:
    """
    Immutable completed comparison interval with associated observations.
    """

    discovery_scope: DiscoveryScope
    previous_snapshot_id: Identifier
    current_snapshot_id: Identifier
    observations: tuple[Observation, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not isinstance(self.discovery_scope, DiscoveryScope):
            raise TypeError("discovery_scope must be a DiscoveryScope.")

        if not isinstance(self.previous_snapshot_id, Identifier):
            raise TypeError("previous_snapshot_id must be an Identifier.")

        if not isinstance(self.current_snapshot_id, Identifier):
            raise TypeError("current_snapshot_id must be an Identifier.")

        object.__setattr__(self, "observations", tuple(self.observations))

        for observation in self.observations:
            if (
                observation.previous_snapshot_id is None
                or observation.current_snapshot_id is None
            ):
                raise ValueError(
                    "Associated observations must include complete comparison "
                    "provenance."
                )

            if observation.previous_snapshot_id != self.previous_snapshot_id:
                raise ValueError(
                    "Associated observation previous_snapshot_id must match "
                    "the interval previous_snapshot_id."
                )

            if observation.current_snapshot_id != self.current_snapshot_id:
                raise ValueError(
                    "Associated observation current_snapshot_id must match "
                    "the interval current_snapshot_id."
                )

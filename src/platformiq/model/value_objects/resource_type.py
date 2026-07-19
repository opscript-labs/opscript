from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceType:
    """
    Provider-neutral resource classification.

    Examples:
        Compute
        Storage
        Network
        Identity
        Database
    """

    name: str

    def __str__(self) -> str:
        return self.name

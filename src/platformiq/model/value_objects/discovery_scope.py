from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryScope:
    """
    Provider-neutral identifier for an authoritative discovery scope.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise TypeError("Discovery scope value must be a string.")

        if not self.value:
            raise ValueError("Discovery scope value must not be empty.")

    def __str__(self) -> str:
        return self.value

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Identifier:
    """
    Immutable base identifier for PlatformIQ entities.

    Wraps a UUID to provide a strongly typed value object.
    """

    value: UUID

    @classmethod
    def new(cls) -> "Identifier":
        """
        Create a new unique identifier.
        """
        return cls(uuid4())

    @classmethod
    def from_string(cls, value: str) -> "Identifier":
        """
        Create an Identifier from an existing UUID string.
        """
        return cls(UUID(value))

    def __str__(self) -> str:
        return str(self.value)

from __future__ import annotations

from dataclasses import dataclass

from platformiq.core import Identifier


@dataclass(frozen=True)
class Entity:
    """
    Base class for all PlatformIQ domain entities.

    Every domain entity has a unique identifier.
    """

    id: Identifier

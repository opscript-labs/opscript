from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResourceState:
    """
    Represents the observable state of a resource.

    The state contains the provider-neutral properties that are
    compared to determine whether a resource has changed.

    Provider-specific discovery code is responsible for producing
    these properties.
    """

    properties: dict[str, Any] = field(default_factory=dict)

from __future__ import annotations

from dataclasses import dataclass, field

from platformiq.core import Identifier
from platformiq.model.resource import Resource


@dataclass(frozen=True)
class DiffResult:
    """
    Represents the result of comparing two infrastructure snapshots.
    """

    previous_snapshot_id: Identifier
    current_snapshot_id: Identifier
    created: tuple[Resource, ...] = field(default_factory=tuple)
    deleted: tuple[Resource, ...] = field(default_factory=tuple)
    modified: tuple[Resource, ...] = field(default_factory=tuple)

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from platformiq.core import Identifier


@dataclass(frozen=True)
class Finding:
    """
    Provider-neutral interpretation of one or more observations.

    A Finding represents what an observation means from a basic
    engineering or operational perspective.
    """

    subject: str
    type: str
    message: str
    timestamp: datetime
    source_observation_type: str
    metadata: Optional[dict[str, Any]] = None
    previous_snapshot_id: Identifier | None = None
    current_snapshot_id: Identifier | None = None

    def __post_init__(self) -> None:
        """
        Require comparison interval identifiers to be both present or both absent.
        """

        previous_is_present = self.previous_snapshot_id is not None
        current_is_present = self.current_snapshot_id is not None

        if previous_is_present != current_is_present:
            raise ValueError(
                "Finding comparison provenance must include both "
                "previous_snapshot_id and current_snapshot_id"
            )

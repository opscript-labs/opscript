from __future__ import annotations

from abc import ABC, abstractmethod

from platformiq.model import Snapshot


class SnapshotStorage(ABC):
    """
    Provider-neutral contract for snapshot persistence.
    """

    @abstractmethod
    def save(self, snapshot: Snapshot) -> None:
        """
        Store a snapshot.
        """
        raise NotImplementedError

    @abstractmethod
    def load_latest(self) -> Snapshot | None:
        """
        Retrieve the latest stored snapshot.
        """
        raise NotImplementedError

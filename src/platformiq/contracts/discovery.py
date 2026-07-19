from __future__ import annotations

from abc import ABC, abstractmethod

from platformiq.model import Snapshot


class DiscoveryProvider(ABC):
    """
    Provider-neutral contract for discovering cloud resources.
    """

    @abstractmethod
    def discover(self) -> Snapshot:
        """
        Collect the current infrastructure state
        and return a PlatformIQ snapshot.
        """
        raise NotImplementedError

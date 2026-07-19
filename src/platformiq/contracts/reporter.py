from __future__ import annotations

from abc import ABC, abstractmethod

from platformiq.model import DiffResult


class Reporter(ABC):
    """
    Provider-neutral contract for presenting analysis results.
    """

    @abstractmethod
    def report(self, result: DiffResult) -> str:
        """
        Convert a diff result into an output representation.
        """
        raise NotImplementedError

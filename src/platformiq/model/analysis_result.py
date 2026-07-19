from __future__ import annotations

from dataclasses import dataclass, field

from platformiq.model.diff_result import DiffResult
from platformiq.model.finding import Finding
from platformiq.model.observation import Observation


@dataclass(frozen=True)
class AnalysisResult:
    """
    Provider-neutral aggregate representing the complete output of
    one infrastructure analysis execution.
    """

    diff: DiffResult
    observations: tuple[Observation, ...] = field(default_factory=tuple)
    findings: tuple[Finding, ...] = field(default_factory=tuple)

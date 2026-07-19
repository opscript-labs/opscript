from dataclasses import dataclass, field

from opscript.application.engineering_knowledge_report_projection import (
    EngineeringKnowledgeReportEntry,
)


@dataclass(frozen=True)
class EngineeringKnowledgeEvolutionUnchangedCondition:
    """
    Preserves both evaluation contexts for one unchanged supported condition.
    """

    evaluation_a: EngineeringKnowledgeReportEntry
    evaluation_b: EngineeringKnowledgeReportEntry


@dataclass(frozen=True)
class EngineeringKnowledgeEvolutionComparison:
    """
    Comparison of two completed Engineering Knowledge evaluations.
    """

    introduced: tuple[EngineeringKnowledgeReportEntry, ...] = field(
        default_factory=tuple
    )
    removed: tuple[EngineeringKnowledgeReportEntry, ...] = field(default_factory=tuple)
    unchanged: tuple[EngineeringKnowledgeEvolutionUnchangedCondition, ...] = field(
        default_factory=tuple
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "introduced", tuple(self.introduced))
        object.__setattr__(self, "removed", tuple(self.removed))
        object.__setattr__(self, "unchanged", tuple(self.unchanged))


class EngineeringKnowledgeEvolutionComparisonService:
    """
    Compares two completed Engineering Knowledge evaluations.
    """

    def compare(
        self,
        evaluation_a: tuple[EngineeringKnowledgeReportEntry, ...],
        evaluation_b: tuple[EngineeringKnowledgeReportEntry, ...],
    ) -> EngineeringKnowledgeEvolutionComparison:
        entries_a = _entries_by_identity(evaluation_a)
        entries_b = _entries_by_identity(evaluation_b)

        identities_a = set(entries_a)
        identities_b = set(entries_b)

        return EngineeringKnowledgeEvolutionComparison(
            introduced=tuple(
                entries_b[identity] for identity in sorted(identities_b - identities_a)
            ),
            removed=tuple(
                entries_a[identity] for identity in sorted(identities_a - identities_b)
            ),
            unchanged=tuple(
                EngineeringKnowledgeEvolutionUnchangedCondition(
                    evaluation_a=entries_a[identity],
                    evaluation_b=entries_b[identity],
                )
                for identity in sorted(identities_a & identities_b)
            ),
        )


def _entries_by_identity(
    evaluation: tuple[EngineeringKnowledgeReportEntry, ...],
) -> dict[tuple[str, str, str], EngineeringKnowledgeReportEntry]:
    entries: dict[tuple[str, str, str], EngineeringKnowledgeReportEntry] = {}

    for entry in evaluation:
        identity = _identity(entry)
        if identity in entries:
            raise ValueError(
                "Engineering Knowledge evaluation contains duplicate identities."
            )
        entries[identity] = entry

    return entries


def _identity(
    entry: EngineeringKnowledgeReportEntry,
) -> tuple[str, str, str]:
    return (
        entry.engineering_condition,
        entry.discovery_scope.value,
        entry.canonical_subject or "",
    )

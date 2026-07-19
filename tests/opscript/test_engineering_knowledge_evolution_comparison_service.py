from dataclasses import FrozenInstanceError

import pytest

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope

from opscript.application.engineering_knowledge_evolution_comparison_service import (
    EngineeringKnowledgeEvolutionComparisonService,
)
from opscript.application.engineering_knowledge_report_projection import (
    EngineeringKnowledgeReportEntry,
)


def test_identical_resource_level_identities_are_unchanged():
    comparison = _service().compare(
        (_entry("frequent_infrastructure_modification", subject="resource-a"),),
        (_entry("frequent_infrastructure_modification", subject="resource-a"),),
    )

    assert comparison.introduced == ()
    assert comparison.removed == ()
    assert len(comparison.unchanged) == 1
    assert (
        comparison.unchanged[0].evaluation_a.engineering_condition
        == "frequent_infrastructure_modification"
    )
    assert comparison.unchanged[0].evaluation_a.canonical_subject == "resource-a"
    assert comparison.unchanged[0].evaluation_b.canonical_subject == "resource-a"


def test_identical_scope_level_identities_are_unchanged():
    comparison = _service().compare(
        (_entry("recurring_infrastructure_removal_activity"),),
        (_entry("recurring_infrastructure_removal_activity"),),
    )

    assert comparison.introduced == ()
    assert comparison.removed == ()
    assert len(comparison.unchanged) == 1
    assert comparison.unchanged[0].evaluation_a.canonical_subject is None
    assert comparison.unchanged[0].evaluation_b.canonical_subject is None


def test_different_subjects_are_removed_and_introduced():
    comparison = _service().compare(
        (_entry("frequent_infrastructure_modification", subject="resource-a"),),
        (_entry("frequent_infrastructure_modification", subject="resource-b"),),
    )

    assert _subjects(comparison.removed) == ("resource-a",)
    assert _subjects(comparison.introduced) == ("resource-b",)
    assert comparison.unchanged == ()


def test_different_discovery_scopes_are_removed_and_introduced():
    comparison = _service().compare(
        (_entry("recurring_infrastructure_removal_activity", scope="scope-a"),),
        (_entry("recurring_infrastructure_removal_activity", scope="scope-b"),),
    )

    assert _scopes(comparison.removed) == ("scope-a",)
    assert _scopes(comparison.introduced) == ("scope-b",)
    assert comparison.unchanged == ()


def test_same_identity_across_different_observation_windows_is_unchanged():
    comparison = _service().compare(
        (
            _entry(
                "frequent_infrastructure_modification",
                subject="resource-a",
                previous_snapshot="a-previous",
                current_snapshot="a-current",
            ),
        ),
        (
            _entry(
                "frequent_infrastructure_modification",
                subject="resource-a",
                previous_snapshot="b-previous",
                current_snapshot="b-current",
            ),
        ),
    )

    unchanged = comparison.unchanged[0]

    assert comparison.introduced == ()
    assert comparison.removed == ()
    assert unchanged.evaluation_a.observation_window_previous_snapshot_id == Identifier(
        "a-previous"
    )
    assert unchanged.evaluation_a.observation_window_current_snapshot_id == Identifier(
        "a-current"
    )
    assert unchanged.evaluation_b.observation_window_previous_snapshot_id == Identifier(
        "b-previous"
    )
    assert unchanged.evaluation_b.observation_window_current_snapshot_id == Identifier(
        "b-current"
    )


def test_introduced_entries_preserve_condition_scope_and_subject():
    comparison = _service().compare(
        (),
        (
            _entry(
                "frequent_infrastructure_modification",
                scope="scope-b",
                subject="resource-b",
            ),
        ),
    )

    introduced = comparison.introduced[0]

    assert introduced.engineering_condition == "frequent_infrastructure_modification"
    assert introduced.discovery_scope == DiscoveryScope("scope-b")
    assert introduced.canonical_subject == "resource-b"


def test_removed_entries_preserve_condition_scope_and_subject():
    comparison = _service().compare(
        (
            _entry(
                "frequent_infrastructure_modification",
                scope="scope-a",
                subject="resource-a",
            ),
        ),
        (),
    )

    removed = comparison.removed[0]

    assert removed.engineering_condition == "frequent_infrastructure_modification"
    assert removed.discovery_scope == DiscoveryScope("scope-a")
    assert removed.canonical_subject == "resource-a"


def test_scope_level_entries_omit_subject():
    comparison = _service().compare(
        (),
        (_entry("recurring_infrastructure_introduction_activity"),),
    )

    assert comparison.introduced[0].canonical_subject is None


def test_duplicate_complete_identity_in_evaluation_a_is_rejected():
    duplicate_a = _entry(
        "frequent_infrastructure_modification",
        subject="resource-a",
        previous_snapshot="a-previous",
        current_snapshot="a-current",
    )
    duplicate_b = _entry(
        "frequent_infrastructure_modification",
        subject="resource-a",
        previous_snapshot="other-previous",
        current_snapshot="other-current",
    )

    with pytest.raises(ValueError, match="duplicate identities"):
        _service().compare((duplicate_a, duplicate_b), ())


def test_duplicate_complete_identity_in_evaluation_b_is_rejected():
    duplicate_a = _entry(
        "recurring_infrastructure_removal_activity",
        previous_snapshot="a-previous",
        current_snapshot="a-current",
    )
    duplicate_b = _entry(
        "recurring_infrastructure_removal_activity",
        previous_snapshot="other-previous",
        current_snapshot="other-current",
    )

    with pytest.raises(ValueError, match="duplicate identities"):
        _service().compare((), (duplicate_a, duplicate_b))


def test_mixed_introduced_removed_and_unchanged_comparison():
    comparison = _service().compare(
        (
            _entry("frequent_infrastructure_modification", subject="resource-a"),
            _entry("recurring_infrastructure_removal_activity", scope="scope-a"),
        ),
        (
            _entry("frequent_infrastructure_modification", subject="resource-a"),
            _entry("recurring_infrastructure_introduction_activity", scope="scope-b"),
        ),
    )

    assert _conditions(comparison.introduced) == (
        "recurring_infrastructure_introduction_activity",
    )
    assert _conditions(comparison.removed) == (
        "recurring_infrastructure_removal_activity",
    )
    assert _conditions(
        tuple(unchanged.evaluation_b for unchanged in comparison.unchanged)
    ) == ("frequent_infrastructure_modification",)


def test_deterministic_ordering_uses_identity_not_window_or_basis():
    comparison = _service().compare(
        (),
        (
            _entry(
                "recurring_infrastructure_removal_activity",
                scope="scope-b",
                previous_snapshot="z-previous",
                recognition_basis="z basis",
            ),
            _entry(
                "frequent_infrastructure_modification",
                scope="scope-b",
                subject="resource-b",
                previous_snapshot="a-previous",
                recognition_basis="a basis",
            ),
            _entry(
                "frequent_infrastructure_modification",
                scope="scope-a",
                subject="resource-c",
                previous_snapshot="m-previous",
                recognition_basis="m basis",
            ),
        ),
    )

    assert _identity_values(comparison.introduced) == (
        ("frequent_infrastructure_modification", "scope-a", "resource-c"),
        ("frequent_infrastructure_modification", "scope-b", "resource-b"),
        ("recurring_infrastructure_removal_activity", "scope-b", None),
    )


def test_repeated_comparison_returns_equal_results():
    evaluation_a = (
        _entry("frequent_infrastructure_modification", subject="resource-a"),
    )
    evaluation_b = (_entry("recurring_infrastructure_removal_activity"),)

    assert _service().compare(evaluation_a, evaluation_b) == _service().compare(
        evaluation_a,
        evaluation_b,
    )


def test_comparison_result_is_immutable():
    comparison = _service().compare(
        (),
        (_entry("frequent_infrastructure_modification", subject="resource-a"),),
    )

    with pytest.raises(FrozenInstanceError):
        comparison.introduced = ()  # type: ignore[misc]


def test_input_evaluations_remain_unchanged():
    evaluation_a = (
        _entry("frequent_infrastructure_modification", subject="resource-a"),
    )
    evaluation_b = (_entry("recurring_infrastructure_removal_activity"),)

    _service().compare(evaluation_a, evaluation_b)

    assert evaluation_a == (
        _entry("frequent_infrastructure_modification", subject="resource-a"),
    )
    assert evaluation_b == (_entry("recurring_infrastructure_removal_activity"),)


def _service() -> EngineeringKnowledgeEvolutionComparisonService:
    return EngineeringKnowledgeEvolutionComparisonService()


def _entry(
    engineering_condition: str,
    *,
    scope: str = "scope-a",
    subject: str | None = None,
    previous_snapshot: str = "snapshot-001",
    current_snapshot: str = "snapshot-002",
    recognition_basis: str = "Recognition basis",
) -> EngineeringKnowledgeReportEntry:
    return EngineeringKnowledgeReportEntry(
        engineering_condition=engineering_condition,
        recognition_outcome="supported",
        discovery_scope=DiscoveryScope(scope),
        canonical_subject=subject,
        recognition_basis=recognition_basis,
        observation_window_previous_snapshot_id=Identifier(previous_snapshot),
        observation_window_current_snapshot_id=Identifier(current_snapshot),
        recognition_threshold=3,
        minimum_completed_interval_count=4,
    )


def _conditions(
    entries: tuple[EngineeringKnowledgeReportEntry, ...],
) -> tuple[str, ...]:
    return tuple(entry.engineering_condition for entry in entries)


def _scopes(
    entries: tuple[EngineeringKnowledgeReportEntry, ...],
) -> tuple[str, ...]:
    return tuple(entry.discovery_scope.value for entry in entries)


def _subjects(
    entries: tuple[EngineeringKnowledgeReportEntry, ...],
) -> tuple[str | None, ...]:
    return tuple(entry.canonical_subject for entry in entries)


def _identity_values(
    entries: tuple[EngineeringKnowledgeReportEntry, ...],
) -> tuple[tuple[str, str, str | None], ...]:
    return tuple(
        (
            entry.engineering_condition,
            entry.discovery_scope.value,
            entry.canonical_subject,
        )
        for entry in entries
    )

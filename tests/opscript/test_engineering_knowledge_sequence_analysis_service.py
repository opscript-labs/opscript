from dataclasses import FrozenInstanceError, replace

import pytest

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope

from opscript.application.engineering_knowledge_report_projection import (
    EngineeringKnowledgeEvaluationContext,
    EngineeringKnowledgeReportEntry,
)
from opscript.application.engineering_knowledge_sequence_analysis_service import (
    ENGINEERING_KNOWLEDGE_SEQUENCE_ANALYSIS_UNAVAILABLE_MESSAGE,
    EngineeringKnowledgeSequenceAnalysisService,
    EngineeringKnowledgeSequenceEvaluation,
)


def test_continuous_support():
    result = _service().analyze(
        (
            _evaluation("snapshot-004", _entry("frequent_infrastructure_modification")),
            _evaluation("snapshot-005", _entry("frequent_infrastructure_modification")),
        )
    )

    analysis = _analysis(result)

    assert analysis.supported_at_sequence_start is True
    assert analysis.supported_at_sequence_end is True
    assert analysis.continuously_supported is True
    assert analysis.newly_supported is False
    assert analysis.no_longer_supported is False
    assert analysis.reappeared is False


def test_newly_supported():
    result = _service().analyze(
        (
            _evaluation("snapshot-004"),
            _evaluation(
                "snapshot-005", _entry("recurring_infrastructure_removal_activity")
            ),
        )
    )

    analysis = _analysis(result)

    assert analysis.supported_at_sequence_start is False
    assert analysis.supported_at_sequence_end is True
    assert analysis.newly_supported is True
    assert analysis.no_longer_supported is False
    assert analysis.reappeared is False


def test_no_longer_supported():
    result = _service().analyze(
        (
            _evaluation(
                "snapshot-004",
                _entry("recurring_infrastructure_introduction_activity"),
            ),
            _evaluation("snapshot-005"),
        )
    )

    analysis = _analysis(result)

    assert analysis.supported_at_sequence_start is True
    assert analysis.supported_at_sequence_end is False
    assert analysis.newly_supported is False
    assert analysis.no_longer_supported is True
    assert analysis.reappeared is False


def test_reappearance():
    result = _service().analyze(
        (
            _evaluation("snapshot-004", _entry("frequent_infrastructure_modification")),
            _evaluation("snapshot-005"),
            _evaluation("snapshot-006", _entry("frequent_infrastructure_modification")),
        )
    )

    analysis = _analysis(result)

    assert analysis.supported_at_sequence_start is True
    assert analysis.supported_at_sequence_end is True
    assert analysis.newly_supported is True
    assert analysis.no_longer_supported is True
    assert analysis.reappeared is True
    assert analysis.continuously_supported is False


def test_sequence_boundaries_and_qualified_evaluation_count():
    result = _service().analyze(
        (
            _evaluation("snapshot-004"),
            _evaluation("snapshot-005", _entry("frequent_infrastructure_modification")),
            _evaluation("snapshot-006", _entry("frequent_infrastructure_modification")),
        )
    )

    analysis = _analysis(result)

    assert analysis.sequence_start_evaluation == _context("snapshot-004")
    assert analysis.sequence_end_evaluation == _context("snapshot-006")
    assert analysis.qualified_evaluation_count == 3


def test_first_deterministic_subject_identity_is_preserved():
    result = _service().analyze(
        (
            _evaluation(
                "snapshot-004",
                _entry("frequent_infrastructure_modification", subject="resource-a"),
                _entry("frequent_infrastructure_modification", subject="resource-b"),
            ),
            _evaluation(
                "snapshot-005",
                _entry("frequent_infrastructure_modification", subject="resource-b"),
            ),
        )
    )

    analysis = _analysis(result)

    assert analysis.canonical_subject == "resource-a"
    assert analysis.no_longer_supported is True


def test_scope_identity_is_preserved():
    result = _service().analyze(
        (
            _evaluation(
                "snapshot-004",
                _entry("recurring_infrastructure_removal_activity", scope="scope-a"),
                scope="scope-a",
            ),
            _evaluation(
                "snapshot-005",
                _entry("recurring_infrastructure_removal_activity", scope="scope-a"),
                scope="scope-a",
            ),
        )
    )

    assert _analysis(result).discovery_scope == DiscoveryScope("scope-a")


def test_incompatible_evaluation_scope_is_rejected():
    with pytest.raises(ValueError, match="share Discovery Scope"):
        _service().analyze(
            (
                _evaluation("snapshot-004", scope="scope-a"),
                _evaluation("snapshot-005", scope="scope-b"),
            )
        )


def test_evaluation_gap_is_rejected():
    with pytest.raises(ValueError, match="share a sequence start"):
        _service().analyze(
            (
                _evaluation("snapshot-004", previous_snapshot="snapshot-001"),
                _evaluation("snapshot-005", previous_snapshot="snapshot-002"),
            )
        )


def test_deterministic_ordering():
    result = _service().analyze(
        (
            _evaluation(
                "snapshot-004",
                _entry("recurring_infrastructure_removal_activity", scope="scope-a"),
                _entry(
                    "frequent_infrastructure_modification",
                    scope="scope-a",
                    subject="resource-b",
                ),
                _entry(
                    "frequent_infrastructure_modification",
                    scope="scope-a",
                    subject="resource-a",
                ),
            ),
            _evaluation("snapshot-005"),
        )
    )

    assert _identity_values(result) == (
        "frequent_infrastructure_modification",
        "scope-a",
        "resource-a",
    )


def test_result_is_immutable():
    analysis = _analysis(
        _service().analyze(
            (
                _evaluation(
                    "snapshot-004", _entry("frequent_infrastructure_modification")
                ),
                _evaluation(
                    "snapshot-005", _entry("frequent_infrastructure_modification")
                ),
            )
        )
    )

    with pytest.raises(FrozenInstanceError):
        analysis.newly_supported = True  # type: ignore[misc]


def test_duplicate_identity_is_rejected():
    with pytest.raises(ValueError, match="duplicate identities"):
        _service().analyze(
            (
                _evaluation(
                    "snapshot-004",
                    _entry(
                        "frequent_infrastructure_modification", subject="resource-a"
                    ),
                    _entry(
                        "frequent_infrastructure_modification", subject="resource-a"
                    ),
                ),
                _evaluation("snapshot-005"),
            )
        )


def test_repeated_execution_is_deterministic():
    evaluations = (
        _evaluation("snapshot-004"),
        _evaluation("snapshot-005", _entry("frequent_infrastructure_modification")),
    )

    assert _service().analyze(evaluations) == _service().analyze(evaluations)


def test_unavailable_when_fewer_than_two_evaluations():
    result = _service().analyze(
        (_evaluation("snapshot-004", _entry("frequent_infrastructure_modification")),)
    )

    assert result.availability == "unavailable"
    assert result.analysis is None
    assert result.message == ENGINEERING_KNOWLEDGE_SEQUENCE_ANALYSIS_UNAVAILABLE_MESSAGE


def test_unavailable_when_no_supported_condition_identity_exists():
    result = _service().analyze(
        (
            _evaluation("snapshot-004"),
            _evaluation("snapshot-005"),
        )
    )

    assert result.availability == "unavailable"
    assert result.analysis is None
    assert result.message == ENGINEERING_KNOWLEDGE_SEQUENCE_ANALYSIS_UNAVAILABLE_MESSAGE


def _service() -> EngineeringKnowledgeSequenceAnalysisService:
    return EngineeringKnowledgeSequenceAnalysisService()


def _evaluation(
    current_snapshot: str,
    *entries: EngineeringKnowledgeReportEntry,
    previous_snapshot: str = "snapshot-001",
    scope: str = "scope-a",
) -> EngineeringKnowledgeSequenceEvaluation:
    context = _context(
        current_snapshot,
        previous_snapshot=previous_snapshot,
        scope=scope,
    )
    return EngineeringKnowledgeSequenceEvaluation(
        report_entries=tuple(
            replace(
                entry,
                observation_window_previous_snapshot_id=(
                    context.observation_window_previous_snapshot_id
                ),
                observation_window_current_snapshot_id=(
                    context.observation_window_current_snapshot_id
                ),
            )
            for entry in entries
        ),
        context=context,
    )


def _context(
    current_snapshot: str,
    *,
    previous_snapshot: str = "snapshot-001",
    scope: str = "scope-a",
) -> EngineeringKnowledgeEvaluationContext:
    return EngineeringKnowledgeEvaluationContext(
        discovery_scope=DiscoveryScope(scope),
        observation_window_previous_snapshot_id=Identifier(previous_snapshot),
        observation_window_current_snapshot_id=Identifier(current_snapshot),
    )


def _entry(
    engineering_condition: str,
    *,
    scope: str = "scope-a",
    subject: str | None = None,
    previous_snapshot: str = "snapshot-001",
    current_snapshot: str = "snapshot-004",
) -> EngineeringKnowledgeReportEntry:
    return EngineeringKnowledgeReportEntry(
        engineering_condition=engineering_condition,
        recognition_outcome="supported",
        discovery_scope=DiscoveryScope(scope),
        canonical_subject=subject,
        recognition_basis="Recognition basis",
        observation_window_previous_snapshot_id=Identifier(previous_snapshot),
        observation_window_current_snapshot_id=Identifier(current_snapshot),
        recognition_threshold=3,
        minimum_completed_interval_count=4,
    )


def _analysis(result):
    assert result.availability == "available"
    assert result.analysis is not None
    assert result.message is None
    return result.analysis


def _identity_values(result):
    analysis = _analysis(result)
    return (
        analysis.engineering_condition,
        analysis.discovery_scope.value,
        analysis.canonical_subject,
    )

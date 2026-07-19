from datetime import UTC, datetime

from platformiq.core import Identifier
from platformiq.model import AnalysisResult, DiffResult, DiscoveryScope, Observation

from opscript.application.qualified_historical_evidence_service import (
    build_qualified_historical_evidence,
    canonical_subject_from_history,
    scope_level_qualified_historical_evidence,
)


def test_builds_qualified_evidence_from_analysis_history():
    scope = DiscoveryScope("scope-a")
    snapshot_ids = _snapshot_ids(3)
    history = (
        _analysis_result(
            snapshot_ids[0],
            snapshot_ids[1],
            _observation(
                "resource-b",
                "resource_modified",
                snapshot_ids[0],
                snapshot_ids[1],
            ),
        ),
        _analysis_result(
            snapshot_ids[1],
            snapshot_ids[2],
            _observation(
                "resource-a",
                "resource_modified",
                snapshot_ids[1],
                snapshot_ids[2],
            ),
        ),
    )

    evidence = build_qualified_historical_evidence(
        history,
        discovery_scope=scope,
        canonical_subject=canonical_subject_from_history(history),
    )

    assert evidence.discovery_scope == scope
    assert evidence.observation_window_previous_snapshot_id == snapshot_ids[0]
    assert evidence.observation_window_current_snapshot_id == snapshot_ids[2]
    assert tuple(
        (
            interval.previous_snapshot_id,
            interval.current_snapshot_id,
        )
        for interval in evidence.completed_intervals
    ) == (
        (snapshot_ids[0], snapshot_ids[1]),
        (snapshot_ids[1], snapshot_ids[2]),
    )
    assert evidence.canonical_subject == "resource-a"


def test_completed_interval_observation_order_is_preserved():
    scope = DiscoveryScope("scope-a")
    previous_snapshot_id, current_snapshot_id = _snapshot_ids(2)
    first = _observation(
        "resource-a",
        "resource_modified",
        previous_snapshot_id,
        current_snapshot_id,
    )
    second = _observation(
        "resource-b",
        "resource_created",
        previous_snapshot_id,
        current_snapshot_id,
    )

    evidence = build_qualified_historical_evidence(
        (
            _analysis_result(
                previous_snapshot_id,
                current_snapshot_id,
                first,
                second,
            ),
        ),
        discovery_scope=scope,
        canonical_subject=None,
    )

    assert evidence.completed_intervals[0].observations == (first, second)


def test_resource_deleted_normalizes_to_resource_removed():
    scope = DiscoveryScope("scope-a")
    previous_snapshot_id, current_snapshot_id = _snapshot_ids(2)
    deleted = _observation(
        "resource-a",
        "resource_deleted",
        previous_snapshot_id,
        current_snapshot_id,
        message="Resource deleted: resource-a",
    )

    evidence = build_qualified_historical_evidence(
        (_analysis_result(previous_snapshot_id, current_snapshot_id, deleted),),
        discovery_scope=scope,
        canonical_subject=None,
    )

    normalized = evidence.completed_intervals[0].observations[0]
    assert normalized is not deleted
    assert normalized.subject == deleted.subject
    assert normalized.type == "resource_removed"
    assert normalized.message == "Resource removed: resource-a"
    assert normalized.timestamp == deleted.timestamp
    assert normalized.previous_snapshot_id == previous_snapshot_id
    assert normalized.current_snapshot_id == current_snapshot_id
    assert normalized.metadata == deleted.metadata


def test_other_observation_types_remain_unchanged():
    scope = DiscoveryScope("scope-a")
    previous_snapshot_id, current_snapshot_id = _snapshot_ids(2)
    modified = _observation(
        "resource-a",
        "resource_modified",
        previous_snapshot_id,
        current_snapshot_id,
    )

    evidence = build_qualified_historical_evidence(
        (_analysis_result(previous_snapshot_id, current_snapshot_id, modified),),
        discovery_scope=scope,
        canonical_subject=None,
    )

    assert evidence.completed_intervals[0].observations[0] is modified


def test_scope_level_evidence_removes_canonical_subject_without_copying_intervals():
    scope = DiscoveryScope("scope-a")
    previous_snapshot_id, current_snapshot_id = _snapshot_ids(2)
    evidence = build_qualified_historical_evidence(
        (
            _analysis_result(
                previous_snapshot_id,
                current_snapshot_id,
                _observation(
                    "resource-a",
                    "resource_modified",
                    previous_snapshot_id,
                    current_snapshot_id,
                ),
            ),
        ),
        discovery_scope=scope,
        canonical_subject="resource-a",
    )

    scope_level = scope_level_qualified_historical_evidence(evidence)

    assert scope_level.discovery_scope == evidence.discovery_scope
    assert scope_level.observation_window_previous_snapshot_id == (
        evidence.observation_window_previous_snapshot_id
    )
    assert scope_level.observation_window_current_snapshot_id == (
        evidence.observation_window_current_snapshot_id
    )
    assert scope_level.completed_intervals is evidence.completed_intervals
    assert scope_level.canonical_subject is None


def test_scope_level_evidence_returns_original_when_no_subject_exists():
    scope = DiscoveryScope("scope-a")
    previous_snapshot_id, current_snapshot_id = _snapshot_ids(2)
    evidence = build_qualified_historical_evidence(
        (_analysis_result(previous_snapshot_id, current_snapshot_id),),
        discovery_scope=scope,
        canonical_subject=None,
    )

    assert scope_level_qualified_historical_evidence(evidence) is evidence


def test_equivalent_input_produces_equal_output():
    scope = DiscoveryScope("scope-a")
    previous_snapshot_id, current_snapshot_id = _snapshot_ids(2)
    history = (_analysis_result(previous_snapshot_id, current_snapshot_id),)

    assert build_qualified_historical_evidence(
        history,
        discovery_scope=scope,
        canonical_subject=None,
    ) == build_qualified_historical_evidence(
        history,
        discovery_scope=scope,
        canonical_subject=None,
    )


def test_input_analysis_history_is_not_mutated():
    scope = DiscoveryScope("scope-a")
    previous_snapshot_id, current_snapshot_id = _snapshot_ids(2)
    history = (
        _analysis_result(
            previous_snapshot_id,
            current_snapshot_id,
            _observation(
                "resource-a",
                "resource_deleted",
                previous_snapshot_id,
                current_snapshot_id,
            ),
        ),
    )
    before = history

    build_qualified_historical_evidence(
        history,
        discovery_scope=scope,
        canonical_subject=None,
    )

    assert history == before


def test_boundary_performs_no_io_storage_recognition_or_projection():
    import opscript.application.qualified_historical_evidence_service as module

    names = set()
    for value in module.__dict__.values():
        code = getattr(value, "__code__", None)
        if code is not None:
            names.update(code.co_names)

    assert "load_history" not in names
    assert "save" not in names
    assert "boto3" not in names
    assert "RecognitionResult" not in names
    assert "RecognizedFinding" not in names
    assert "project_engineering_knowledge_report" not in names


def test_knowledge_review_workflow_delegates_to_shared_boundary(monkeypatch):
    import opscript.application.knowledge_review_workflow as workflow
    import opscript.application.qualified_historical_evidence_service as service

    scope = DiscoveryScope("scope-a")
    history = _contiguous_analysis_history(5)
    calls = []

    def spy_build_qualified_historical_evidence(*args, **kwargs):
        calls.append((args, kwargs))
        return service.build_qualified_historical_evidence(*args, **kwargs)

    monkeypatch.setattr(
        workflow,
        "build_qualified_historical_evidence",
        spy_build_qualified_historical_evidence,
    )

    workflow._engineering_knowledge_evaluation(history, discovery_scope=scope)

    assert len(calls) == 1
    assert calls[0][1]["discovery_scope"] == scope


def test_condition_support_workflow_delegates_to_shared_boundary(monkeypatch):
    import opscript.application.engineering_condition_support_comparison_workflow as workflow
    import opscript.application.qualified_historical_evidence_service as service

    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    history = _contiguous_analysis_history(5)
    calls = []

    def spy_build_qualified_historical_evidence(*args, **kwargs):
        calls.append((args, kwargs))
        return service.build_qualified_historical_evidence(*args, **kwargs)

    class FakeStorage:
        def load_history(self):
            return ()

    class FakeStorageFactory:
        def __call__(self, discovery_scope):
            return FakeStorage()

    class FakeAnalysisService:
        def analyze_history(self, snapshots):
            return history

    monkeypatch.setattr(
        workflow,
        "build_qualified_historical_evidence",
        spy_build_qualified_historical_evidence,
    )

    workflow.EngineeringConditionSupportComparisonWorkflow(
        storage_factory=FakeStorageFactory(),
        analysis_service=FakeAnalysisService(),
    ).run(
        engineering_condition=("recurring_infrastructure_removal_activity"),
        discovery_scopes=(scope_a, scope_b),
    )

    assert [call[1]["discovery_scope"] for call in calls] == [scope_a, scope_b]


def _analysis_result(
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    *observations: Observation,
) -> AnalysisResult:
    return AnalysisResult(
        diff=DiffResult(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        ),
        observations=observations,
    )


def _observation(
    subject: str,
    observation_type: str,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    *,
    message: str | None = None,
) -> Observation:
    return Observation(
        subject=subject,
        type=observation_type,
        message=message or f"{observation_type}: {subject}",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        metadata={"key": "value"},
    )


def _snapshot_ids(count: int) -> tuple[Identifier, ...]:
    return tuple(Identifier.new() for _ in range(count))


def _contiguous_analysis_history(snapshot_count: int) -> tuple[AnalysisResult, ...]:
    snapshot_ids = _snapshot_ids(snapshot_count)
    return tuple(
        _analysis_result(snapshot_ids[index], snapshot_ids[index + 1])
        for index in range(snapshot_count - 1)
    )

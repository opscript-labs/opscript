import pytest

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.model.value_objects import ResourceState

from opscript.application.engineering_condition_support_comparison_workflow import (
    EngineeringConditionSupportComparisonWorkflow,
    EngineeringConditionSupportComparisonWorkflowError,
)
from opscript.models import RecognitionResult


REMOVAL_CONDITION = (
    RecognitionResult.recurring_infrastructure_removal_activity_condition
)
INTRODUCTION_CONDITION = (
    RecognitionResult.recurring_infrastructure_introduction_activity_condition
)
MODIFICATION_CONDITION = (
    RecognitionResult.frequent_infrastructure_modification_condition
)


class FakeWorkflowStorage:
    def __init__(self, history: tuple[Snapshot, ...]):
        self.history = history
        self.load_history_calls = 0
        self.save_calls = 0

    def load_history(self) -> tuple[Snapshot, ...]:
        self.load_history_calls += 1
        return self.history

    def save(self, snapshot: Snapshot) -> None:
        self.save_calls += 1


class FailingStorage:
    def load_history(self) -> tuple[Snapshot, ...]:
        raise RuntimeError("storage unavailable")


class FakeStorageFactory:
    def __init__(self, storages: dict[DiscoveryScope, object]):
        self.storages = storages
        self.requested_scopes: list[DiscoveryScope] = []

    def __call__(self, discovery_scope: DiscoveryScope):
        self.requested_scopes.append(discovery_scope)
        return self.storages[discovery_scope]


class FailingAnalysisService:
    def analyze_history(self, snapshots):
        raise RuntimeError("qualification failed")


def test_workflow_produces_projection_for_two_supported_scopes():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = FakeWorkflowStorage(_removal_supported_history(scope_a))
    storage_b = FakeWorkflowStorage(_removal_supported_history(scope_b))
    factory = FakeStorageFactory({scope_a: storage_a, scope_b: storage_b})

    result = _workflow(factory).run(
        engineering_condition=REMOVAL_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )

    assert result.status == "comparison_produced"
    assert result.reason == "comparison_available"
    assert result.requested_scopes == (scope_a, scope_b)
    assert result.projection is not None
    assert result.projection.classification == "SUPPORTED_IN_ALL_SCOPES"
    assert result.projection.compared_discovery_scopes == (scope_a, scope_b)
    assert result.projection.supported_discovery_scopes == (scope_a, scope_b)
    assert result.projection.not_supported_discovery_scopes == ()
    assert result.eligibility.excluded_evaluations == ()
    assert factory.requested_scopes == [scope_a, scope_b]


def test_workflow_preserves_supported_and_not_supported_outcomes():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = FakeWorkflowStorage(_removal_supported_history(scope_a))
    storage_b = FakeWorkflowStorage(_stable_history(scope_b))

    result = _workflow(
        FakeStorageFactory({scope_a: storage_a, scope_b: storage_b})
    ).run(
        engineering_condition=REMOVAL_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )

    assert result.status == "comparison_produced"
    assert result.projection is not None
    assert result.projection.classification == "SUPPORTED_IN_SOME_SCOPES"
    assert result.projection.supported_discovery_scopes == (scope_a,)
    assert result.projection.not_supported_discovery_scopes == (scope_b,)
    assert tuple(
        evaluation.outcome for evaluation in result.eligibility.eligible_evaluations
    ) == ("supported", "not_supported")


def test_workflow_produces_supported_in_no_scopes():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    result = _workflow(
        FakeStorageFactory(
            {
                scope_a: FakeWorkflowStorage(_stable_history(scope_a)),
                scope_b: FakeWorkflowStorage(_stable_history(scope_b)),
            }
        )
    ).run(
        engineering_condition=REMOVAL_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )

    assert result.status == "comparison_produced"
    assert result.projection is not None
    assert result.projection.classification == "SUPPORTED_IN_NO_SCOPES"
    assert result.projection.supported_discovery_scopes == ()
    assert result.projection.not_supported_discovery_scopes == (scope_a, scope_b)


def test_duplicate_requested_scopes_are_rejected():
    scope = DiscoveryScope("scope-a")

    with pytest.raises(
        EngineeringConditionSupportComparisonWorkflowError,
        match="Duplicate Discovery Scopes",
    ):
        _workflow(FakeStorageFactory({})).run(
            engineering_condition=REMOVAL_CONDITION,
            discovery_scopes=(scope, scope),
        )


def test_requested_order_is_preserved():
    scope_b = DiscoveryScope("scope-b")
    scope_a = DiscoveryScope("scope-a")

    result = _workflow(
        FakeStorageFactory(
            {
                scope_b: FakeWorkflowStorage(_stable_history(scope_b)),
                scope_a: FakeWorkflowStorage(_removal_supported_history(scope_a)),
            }
        )
    ).run(
        engineering_condition=REMOVAL_CONDITION,
        discovery_scopes=(scope_b, scope_a),
    )

    assert result.requested_scopes == (scope_b, scope_a)
    assert result.projection is not None
    assert result.projection.compared_discovery_scopes == (scope_b, scope_a)
    assert result.projection.not_supported_discovery_scopes == (scope_b,)
    assert result.projection.supported_discovery_scopes == (scope_a,)


def test_fewer_than_two_eligible_evaluations_returns_comparison_unavailable():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    result = _workflow(
        FakeStorageFactory(
            {
                scope_a: FakeWorkflowStorage(_modified_history(scope_a)),
                scope_b: FakeWorkflowStorage(_modified_history(scope_b)),
            }
        )
    ).run(
        engineering_condition=MODIFICATION_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )

    assert result.status == "comparison_unavailable"
    assert result.reason == "insufficient_eligible_evaluations"
    assert result.projection is None
    assert result.eligibility.eligible_evaluations == ()
    assert tuple(
        excluded.reason for excluded in result.eligibility.excluded_evaluations
    ) == (
        "unsupported_subject_comparison",
        "unsupported_subject_comparison",
    )


def test_resource_level_engineering_condition_is_excluded():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    result = _workflow(
        FakeStorageFactory(
            {
                scope_a: FakeWorkflowStorage(_modified_history(scope_a)),
                scope_b: FakeWorkflowStorage(_modified_history(scope_b)),
            }
        )
    ).run(
        engineering_condition=MODIFICATION_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )

    assert result.status == "comparison_unavailable"
    assert tuple(
        excluded.evaluation.engineering_condition
        for excluded in result.eligibility.excluded_evaluations
    ) == (MODIFICATION_CONDITION, MODIFICATION_CONDITION)


def test_engineering_condition_mismatch_cannot_be_produced_by_selected_evaluation():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    result = _workflow(
        FakeStorageFactory(
            {
                scope_a: FakeWorkflowStorage(_introduction_supported_history(scope_a)),
                scope_b: FakeWorkflowStorage(_stable_history(scope_b)),
            }
        )
    ).run(
        engineering_condition=INTRODUCTION_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )

    assert result.status == "comparison_produced"
    assert result.eligibility.excluded_evaluations == ()
    assert {
        evaluation.engineering_condition
        for evaluation in result.eligibility.requested_evaluations
    } == {INTRODUCTION_CONDITION}


def test_storage_failure_propagates():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    with pytest.raises(RuntimeError, match="storage unavailable"):
        _workflow(
            FakeStorageFactory(
                {
                    scope_a: FailingStorage(),
                    scope_b: FakeWorkflowStorage(_stable_history(scope_b)),
                }
            )
        ).run(
            engineering_condition=REMOVAL_CONDITION,
            discovery_scopes=(scope_a, scope_b),
        )


def test_recognition_failure_propagates():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    with pytest.raises(ValueError, match="requires at least four completed intervals"):
        _workflow(
            FakeStorageFactory(
                {
                    scope_a: FakeWorkflowStorage(_short_history(scope_a)),
                    scope_b: FakeWorkflowStorage(_stable_history(scope_b)),
                }
            )
        ).run(
            engineering_condition=REMOVAL_CONDITION,
            discovery_scopes=(scope_a, scope_b),
        )


def test_qualification_failure_propagates():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    with pytest.raises(RuntimeError, match="qualification failed"):
        _workflow(
            FakeStorageFactory(
                {
                    scope_a: FakeWorkflowStorage(_stable_history(scope_a)),
                    scope_b: FakeWorkflowStorage(_stable_history(scope_b)),
                }
            ),
            analysis_service=FailingAnalysisService(),
        ).run(
            engineering_condition=REMOVAL_CONDITION,
            discovery_scopes=(scope_a, scope_b),
        )


def test_projection_is_produced_only_for_completed_comparison():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")

    completed = _workflow(
        FakeStorageFactory(
            {
                scope_a: FakeWorkflowStorage(_stable_history(scope_a)),
                scope_b: FakeWorkflowStorage(_stable_history(scope_b)),
            }
        )
    ).run(
        engineering_condition=REMOVAL_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )
    unavailable = _workflow(
        FakeStorageFactory(
            {
                scope_a: FakeWorkflowStorage(_modified_history(scope_a)),
                scope_b: FakeWorkflowStorage(_modified_history(scope_b)),
            }
        )
    ).run(
        engineering_condition=MODIFICATION_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )

    assert completed.status == "comparison_produced"
    assert completed.projection is not None
    assert unavailable.status == "comparison_unavailable"
    assert unavailable.projection is None


def test_workflow_does_not_mutate_storage_or_persist():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = FakeWorkflowStorage(_stable_history(scope_a))
    storage_b = FakeWorkflowStorage(_stable_history(scope_b))
    before = (storage_a.history, storage_b.history)

    _workflow(FakeStorageFactory({scope_a: storage_a, scope_b: storage_b})).run(
        engineering_condition=REMOVAL_CONDITION,
        discovery_scopes=(scope_a, scope_b),
    )

    assert (storage_a.history, storage_b.history) == before
    assert storage_a.save_calls == 0
    assert storage_b.save_calls == 0


def test_workflow_adds_no_cli_json_platformiq_or_telemetry_surface():
    import opscript.application.engineering_condition_support_comparison_workflow as module

    names = set()
    for value in module.__dict__.values():
        code = getattr(value, "__code__", None)
        if code is not None:
            names.update(code.co_names)

    assert "format_output" not in names
    assert "format_engineering_condition_support_comparison" not in names
    assert "format_log_event" not in names
    assert "get_logger" not in names
    assert "save" not in names
    assert "json" not in names


def _workflow(
    storage_factory,
    *,
    analysis_service=None,
) -> EngineeringConditionSupportComparisonWorkflow:
    return EngineeringConditionSupportComparisonWorkflow(
        storage_factory=storage_factory,
        analysis_service=analysis_service,
    )


def _stable_history(scope: DiscoveryScope) -> tuple[Snapshot, ...]:
    return tuple(_snapshot(scope, _resource("stable")) for _ in range(5))


def _short_history(scope: DiscoveryScope) -> tuple[Snapshot, ...]:
    return tuple(_snapshot(scope, _resource("stable")) for _ in range(4))


def _removal_supported_history(scope: DiscoveryScope) -> tuple[Snapshot, ...]:
    return (
        _snapshot(
            scope,
            _resource("removed-1"),
            _resource("removed-2"),
            _resource("removed-3"),
        ),
        _snapshot(scope, _resource("removed-2"), _resource("removed-3")),
        _snapshot(scope, _resource("removed-3")),
        _snapshot(scope),
        _snapshot(scope),
    )


def _introduction_supported_history(scope: DiscoveryScope) -> tuple[Snapshot, ...]:
    return (
        _snapshot(scope),
        _snapshot(scope, _resource("created-1")),
        _snapshot(scope, _resource("created-1"), _resource("created-2")),
        _snapshot(
            scope,
            _resource("created-1"),
            _resource("created-2"),
            _resource("created-3"),
        ),
        _snapshot(
            scope,
            _resource("created-1"),
            _resource("created-2"),
            _resource("created-3"),
        ),
    )


def _modified_history(scope: DiscoveryScope) -> tuple[Snapshot, ...]:
    return tuple(
        _snapshot(scope, _resource("modified", version=str(index)))
        for index in range(5)
    )


def _snapshot(
    discovery_scope: DiscoveryScope,
    *resources: Resource,
) -> Snapshot:
    return Snapshot(
        discovery_scope=discovery_scope,
        id=Identifier.new(),
        resources=resources,
    )


def _resource(
    external_id: str,
    *,
    version: str = "one",
) -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
        state=ResourceState(properties={"version": version}),
    )

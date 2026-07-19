import logging

import pytest

from platformiq.analysis import SnapshotDiffer
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.model.value_objects import ResourceState

from opscript.application import (
    AnalysisService,
    DiscoveryScopeActivityComparisonService,
    DiscoveryScopeActivityFactsService,
    DiscoveryScopeActivityReportService,
    DiscoveryScopeActivityWorkflow,
    DiscoveryScopeActivityWorkflowError,
    DiscoveryScopeEligibilityService,
    DiscoveryScopeEligibilityWorkflow,
)


class FakeWorkflowStorage:
    def __init__(
        self,
        history: tuple[Snapshot, ...],
        latest: Snapshot | None = None,
    ):
        self.history = history
        self.latest = latest if latest is not None else history[-1] if history else None
        self.save_calls = 0
        self.load_history_calls = 0
        self.load_latest_calls = 0

    def save(
        self,
        snapshot: Snapshot,
    ) -> None:
        self.save_calls += 1

    def load_history(self) -> tuple[Snapshot, ...]:
        self.load_history_calls += 1
        return self.history

    def load_latest(self) -> Snapshot | None:
        self.load_latest_calls += 1
        return self.latest


class FakeStorageFactory:
    def __init__(
        self,
        storages: dict[DiscoveryScope, FakeWorkflowStorage],
    ):
        self.storages = storages
        self.requested_scopes: list[DiscoveryScope] = []

    def __call__(
        self,
        discovery_scope: DiscoveryScope,
    ) -> FakeWorkflowStorage:
        self.requested_scopes.append(discovery_scope)
        return self.storages[discovery_scope]


def test_cross_scope_activity_workflow_returns_report_for_two_eligible_scopes():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = _storage(
        _snapshot(scope_a),
        _snapshot(scope_a, _resource("resource-a")),
    )
    storage_b = _storage(
        _snapshot(scope_b),
        _snapshot(scope_b, _resource("resource-b-1"), _resource("resource-b-2")),
    )
    factory = FakeStorageFactory({scope_a: storage_a, scope_b: storage_b})
    workflow = _workflow(factory)

    result = workflow.run((scope_a, scope_b))

    assert result.requested_scopes == (scope_a, scope_b)
    assert result.comparison_status == "comparison_produced"
    assert result.reason == "comparison_available"
    assert result.eligible_scopes == (scope_a, scope_b)
    assert result.excluded_scopes == ()
    assert result.activity_report is not None
    assert result.activity_report.compared_scope_count == 2
    assert result.activity_report.total_endpoint_resources == 3
    assert result.activity_report.total_introduced == 3
    assert result.activity_report.total_modified == 0
    assert result.activity_report.total_removed == 0
    assert result.activity_report.total_represented_changes == 3
    assert tuple(
        scope_report.discovery_scope
        for scope_report in result.activity_report.scope_reports
    ) == (scope_a, scope_b)
    assert factory.requested_scopes == [scope_a, scope_b]


def test_cross_scope_activity_workflow_emits_comparison_phase_lifecycle(caplog):
    workflow, scopes = _two_eligible_scope_workflow()

    with caplog.at_level(logging.INFO, logger="opscript"):
        result = workflow.run(scopes)

    messages = _workflow_phase_messages(caplog)

    assert result.comparison_status == "comparison_produced"
    _assert_phase_order(
        messages,
        ("workflow_phase_started", "scope_qualification"),
        ("workflow_phase_completed", "scope_qualification"),
        ("workflow_phase_started", "activity_fact_derivation"),
        ("workflow_phase_completed", "activity_fact_derivation"),
        ("workflow_phase_started", "cross_scope_comparison"),
        ("workflow_phase_completed", "cross_scope_comparison"),
        ("workflow_phase_started", "activity_report_projection"),
        ("workflow_phase_completed", "activity_report_projection"),
    )
    assert _phase_pair_count(messages, "scope_qualification") == (1, 1, 0)
    assert _phase_pair_count(messages, "activity_fact_derivation") == (1, 1, 0)
    assert _phase_pair_count(messages, "cross_scope_comparison") == (1, 1, 0)
    assert _phase_pair_count(messages, "activity_report_projection") == (1, 1, 0)
    assert _all_phase_events_have_required_fields(messages)
    assert _completed_and_failed_are_mutually_exclusive(messages)
    assert not any("execution_id=" in message for message in messages)


def test_cross_scope_activity_workflow_compares_two_eligible_scopes_and_excludes_one():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    scope_c = DiscoveryScope("scope-c")
    storage_a = _storage(
        _snapshot(scope_a),
        _snapshot(scope_a, _resource("resource-a")),
    )
    storage_b = _storage(
        _snapshot(scope_b),
        _snapshot(scope_b, _resource("resource-b")),
    )
    storage_c = FakeWorkflowStorage(history=(), latest=None)
    workflow = _workflow(
        FakeStorageFactory(
            {
                scope_a: storage_a,
                scope_b: storage_b,
                scope_c: storage_c,
            }
        )
    )

    result = workflow.run((scope_a, scope_b, scope_c))

    assert result.comparison_status == "comparison_produced"
    assert result.eligible_scopes == (scope_a, scope_b)
    assert len(result.excluded_scopes) == 1
    assert result.excluded_scopes[0].discovery_scope == scope_c
    assert result.excluded_scopes[0].eligibility_status == "ineligible"
    assert result.excluded_scopes[0].reason == "no_snapshot_history"
    assert result.activity_report is not None
    assert result.activity_report.compared_scope_count == 2
    assert result.activity_report.total_introduced == 2


def test_cross_scope_activity_workflow_returns_insufficient_outcome_for_one_eligible_scope(
    caplog,
):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = _storage(
        _snapshot(scope_a),
        _snapshot(scope_a, _resource("resource-a")),
    )
    storage_b = FakeWorkflowStorage(history=(), latest=None)
    facts_service = SpyFactsService()
    comparison_service = SpyComparisonService()
    report_service = SpyReportService()
    workflow = _workflow(
        FakeStorageFactory({scope_a: storage_a, scope_b: storage_b}),
        activity_facts_service=facts_service,
        comparison_service=comparison_service,
        report_service=report_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        result = workflow.run((scope_a, scope_b))

    messages = _workflow_phase_messages(caplog)

    assert result.comparison_status == "insufficient_eligible_scopes"
    assert result.reason == (
        "At least two eligible Discovery Scopes are required for comparison."
    )
    assert result.eligible_scopes == (scope_a,)
    assert result.excluded_scopes[0].discovery_scope == scope_b
    assert result.excluded_scopes[0].reason == "no_snapshot_history"
    assert result.activity_report is None
    assert facts_service.calls == 0
    assert comparison_service.calls == 0
    assert report_service.calls == 0
    assert storage_a.save_calls == 0
    assert storage_b.save_calls == 0
    _assert_phase_order(
        messages,
        ("workflow_phase_started", "scope_qualification"),
        ("workflow_phase_completed", "scope_qualification"),
    )
    assert _phase_pair_count(messages, "scope_qualification") == (1, 1, 0)
    assert _all_phase_events_have_required_fields(messages)


def test_cross_scope_activity_workflow_preserves_multiple_excluded_scopes(caplog):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = FakeWorkflowStorage(history=(), latest=None)
    only_snapshot = _snapshot(scope_b, _resource("resource-b"))
    storage_b = FakeWorkflowStorage(history=(only_snapshot,), latest=only_snapshot)
    workflow = _workflow(FakeStorageFactory({scope_a: storage_a, scope_b: storage_b}))

    with caplog.at_level(logging.INFO, logger="opscript"):
        result = workflow.run((scope_a, scope_b))

    messages = _workflow_phase_messages(caplog)

    assert result.comparison_status == "no_eligible_scopes"
    assert result.reason == "No requested Discovery Scopes are eligible for comparison."
    assert result.eligible_scopes == ()
    assert tuple(excluded.discovery_scope for excluded in result.excluded_scopes) == (
        scope_a,
        scope_b,
    )
    assert tuple(
        excluded.eligibility_status for excluded in result.excluded_scopes
    ) == (
        "ineligible",
        "partially_eligible",
    )
    assert tuple(excluded.reason for excluded in result.excluded_scopes) == (
        "no_snapshot_history",
        "insufficient_comparison_history",
    )
    assert result.activity_report is None
    _assert_phase_order(
        messages,
        ("workflow_phase_started", "scope_qualification"),
        ("workflow_phase_completed", "scope_qualification"),
    )
    assert _phase_pair_count(messages, "scope_qualification") == (1, 1, 0)
    assert _all_phase_events_have_required_fields(messages)


def test_cross_scope_activity_workflow_does_not_invoke_comparison_for_zero_eligible_scopes():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    facts_service = SpyFactsService()
    comparison_service = SpyComparisonService()
    report_service = SpyReportService()
    storage_a = FakeWorkflowStorage(history=(), latest=None)
    storage_b = FakeWorkflowStorage(history=(), latest=None)
    workflow = _workflow(
        FakeStorageFactory({scope_a: storage_a, scope_b: storage_b}),
        activity_facts_service=facts_service,
        comparison_service=comparison_service,
        report_service=report_service,
    )

    result = workflow.run((scope_a, scope_b))

    assert result.comparison_status == "no_eligible_scopes"
    assert result.activity_report is None
    assert facts_service.calls == 0
    assert comparison_service.calls == 0
    assert report_service.calls == 0
    assert storage_a.save_calls == 0
    assert storage_b.save_calls == 0


def test_cross_scope_activity_workflow_rejects_duplicate_requested_scopes():
    scope_a = DiscoveryScope("scope-a")
    workflow = _workflow(FakeStorageFactory({scope_a: FakeWorkflowStorage(history=())}))

    with pytest.raises(
        DiscoveryScopeActivityWorkflowError,
        match="Duplicate Discovery Scopes are not allowed.",
    ):
        workflow.run((scope_a, scope_a))


@pytest.mark.parametrize(
    "requested_scopes",
    [
        (),
        (DiscoveryScope("scope-a"),),
    ],
)
def test_cross_scope_activity_workflow_rejects_fewer_than_two_scopes(
    requested_scopes: tuple[DiscoveryScope, ...],
):
    workflow = _workflow(FakeStorageFactory({}))

    with pytest.raises(
        DiscoveryScopeActivityWorkflowError,
        match="At least two Discovery Scopes are required.",
    ):
        workflow.run(requested_scopes)


def test_cross_scope_activity_workflow_is_deterministic():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storages = {
        scope_a: _storage(_snapshot(scope_a), _snapshot(scope_a, _resource("a"))),
        scope_b: _storage(_snapshot(scope_b), _snapshot(scope_b, _resource("b"))),
    }
    workflow = _workflow(FakeStorageFactory(storages))

    first = workflow.run((scope_a, scope_b))
    second = workflow.run((scope_a, scope_b))

    assert first == second


def test_cross_scope_activity_workflow_does_not_mutate_storage():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = _storage(_snapshot(scope_a), _snapshot(scope_a, _resource("a")))
    storage_b = _storage(_snapshot(scope_b), _snapshot(scope_b, _resource("b")))
    workflow = _workflow(FakeStorageFactory({scope_a: storage_a, scope_b: storage_b}))

    workflow.run((scope_a, scope_b))

    assert storage_a.save_calls == 0
    assert storage_b.save_calls == 0


def test_cross_scope_activity_workflow_preserves_requested_scope_order():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storages = {
        scope_a: _storage(_snapshot(scope_a), _snapshot(scope_a, _resource("a"))),
        scope_b: _storage(_snapshot(scope_b), _snapshot(scope_b, _resource("b"))),
    }
    workflow = _workflow(FakeStorageFactory(storages))

    result = workflow.run((scope_b, scope_a))

    assert result.requested_scopes == (scope_b, scope_a)
    assert result.eligible_scopes == (scope_b, scope_a)
    assert result.activity_report is not None
    assert tuple(
        scope_report.discovery_scope
        for scope_report in result.activity_report.scope_reports
    ) == (scope_b, scope_a)


@pytest.mark.parametrize(
    (
        "failing_service",
        "failed_phase",
        "raw_error_text",
        "expected_order",
    ),
    [
        (
            "facts",
            "activity_fact_derivation",
            "synthetic fact failure",
            (
                ("workflow_phase_started", "scope_qualification"),
                ("workflow_phase_completed", "scope_qualification"),
                ("workflow_phase_started", "activity_fact_derivation"),
                ("workflow_phase_failed", "activity_fact_derivation"),
            ),
        ),
        (
            "comparison",
            "cross_scope_comparison",
            "synthetic comparison failure",
            (
                ("workflow_phase_started", "scope_qualification"),
                ("workflow_phase_completed", "scope_qualification"),
                ("workflow_phase_started", "activity_fact_derivation"),
                ("workflow_phase_completed", "activity_fact_derivation"),
                ("workflow_phase_started", "cross_scope_comparison"),
                ("workflow_phase_failed", "cross_scope_comparison"),
            ),
        ),
        (
            "projection",
            "activity_report_projection",
            "synthetic projection failure",
            (
                ("workflow_phase_started", "scope_qualification"),
                ("workflow_phase_completed", "scope_qualification"),
                ("workflow_phase_started", "activity_fact_derivation"),
                ("workflow_phase_completed", "activity_fact_derivation"),
                ("workflow_phase_started", "cross_scope_comparison"),
                ("workflow_phase_completed", "cross_scope_comparison"),
                ("workflow_phase_started", "activity_report_projection"),
                ("workflow_phase_failed", "activity_report_projection"),
            ),
        ),
    ],
)
def test_cross_scope_activity_workflow_emits_phase_failure(
    caplog,
    failing_service,
    failed_phase,
    raw_error_text,
    expected_order,
):
    service_overrides = _failing_service_overrides(failing_service)
    workflow, scopes = _two_eligible_scope_workflow(**service_overrides)

    with (
        caplog.at_level(logging.INFO, logger="opscript"),
        pytest.raises(DiscoveryScopeActivityWorkflowError),
    ):
        workflow.run(scopes)

    messages = _workflow_phase_messages(caplog)

    _assert_phase_order(messages, *expected_order)
    assert _phase_pair_count(messages, failed_phase) == (1, 0, 1)
    assert _all_phase_events_have_required_fields(messages)
    assert _completed_and_failed_are_mutually_exclusive(messages)
    assert f"reason={failed_phase}_failed" in messages[-1]
    assert raw_error_text not in messages[-1]


class SpyFactsService:
    def __init__(self):
        self.delegate = _activity_facts_service()
        self.calls = 0

    def derive(self, eligibility, history):
        self.calls += 1
        return self.delegate.derive(eligibility, history)


class FailingFactsService:
    def derive(self, eligibility, history):
        raise DiscoveryScopeActivityWorkflowError("synthetic fact failure")


class SpyComparisonService:
    def __init__(self):
        self.delegate = DiscoveryScopeActivityComparisonService()
        self.calls = 0

    def compare(self, facts):
        self.calls += 1
        return self.delegate.compare(facts)


class FailingComparisonService:
    def compare(self, facts):
        raise DiscoveryScopeActivityWorkflowError("synthetic comparison failure")


class SpyReportService:
    def __init__(self):
        self.delegate = DiscoveryScopeActivityReportService()
        self.calls = 0

    def project(self, comparison):
        self.calls += 1
        return self.delegate.project(comparison)


class FailingReportService:
    def project(self, comparison):
        raise DiscoveryScopeActivityWorkflowError("synthetic projection failure")


def _failing_service_overrides(failing_service: str):
    if failing_service == "facts":
        return {
            "activity_facts_service": FailingFactsService(),
            "comparison_service": SpyComparisonService(),
            "report_service": SpyReportService(),
        }
    if failing_service == "comparison":
        return {
            "comparison_service": FailingComparisonService(),
            "report_service": SpyReportService(),
        }
    return {"report_service": FailingReportService()}


def _workflow(
    storage_factory: FakeStorageFactory,
    activity_facts_service=None,
    comparison_service=None,
    report_service=None,
) -> DiscoveryScopeActivityWorkflow:
    return DiscoveryScopeActivityWorkflow(
        eligibility_workflow=DiscoveryScopeEligibilityWorkflow(
            eligibility_service=DiscoveryScopeEligibilityService()
        ),
        activity_facts_service=activity_facts_service or _activity_facts_service(),
        comparison_service=comparison_service
        or DiscoveryScopeActivityComparisonService(),
        report_service=report_service or DiscoveryScopeActivityReportService(),
        storage_factory=storage_factory,
    )


def _two_eligible_scope_workflow(
    activity_facts_service=None,
    comparison_service=None,
    report_service=None,
) -> tuple[DiscoveryScopeActivityWorkflow, tuple[DiscoveryScope, DiscoveryScope]]:
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    workflow = _workflow(
        FakeStorageFactory(
            {
                scope_a: _storage(
                    _snapshot(scope_a),
                    _snapshot(scope_a, _resource("resource-a")),
                ),
                scope_b: _storage(
                    _snapshot(scope_b),
                    _snapshot(scope_b, _resource("resource-b")),
                ),
            }
        ),
        activity_facts_service=activity_facts_service,
        comparison_service=comparison_service,
        report_service=report_service,
    )
    return workflow, (scope_a, scope_b)


def _activity_facts_service() -> DiscoveryScopeActivityFactsService:
    return DiscoveryScopeActivityFactsService(
        analysis_service=AnalysisService(SnapshotDiffer())
    )


def _storage(
    *history: Snapshot,
) -> FakeWorkflowStorage:
    return FakeWorkflowStorage(history=history)


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
    version: str = "one",
) -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
        state=ResourceState(properties={"version": version}),
    )


def _workflow_phase_messages(caplog) -> tuple[str, ...]:
    return tuple(
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=cross_scope_activity" in record.message
    )


def _phase_event_order(messages: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (_field(message, "event"), _field(message, "phase")) for message in messages
    )


def _assert_phase_order(
    messages: tuple[str, ...],
    *expected: tuple[str, str],
) -> None:
    assert _phase_event_order(messages) == expected


def _phase_pair_count(
    messages: tuple[str, ...],
    phase: str,
) -> tuple[int, int, int]:
    phase_messages = tuple(
        message for message in messages if _field(message, "phase") == phase
    )
    return (
        sum(
            1
            for message in phase_messages
            if _field(message, "event") == "workflow_phase_started"
        ),
        sum(
            1
            for message in phase_messages
            if _field(message, "event") == "workflow_phase_completed"
        ),
        sum(
            1
            for message in phase_messages
            if _field(message, "event") == "workflow_phase_failed"
        ),
    )


def _all_phase_events_have_required_fields(messages: tuple[str, ...]) -> bool:
    for message in messages:
        if _field(message, "workflow") != "cross_scope_activity":
            return False
        if _field(message, "phase") == "":
            return False
        event = _field(message, "event")
        if event in {"workflow_phase_completed", "workflow_phase_failed"}:
            duration = _field(message, "duration_ms")
            if not duration.isdigit():
                return False
        if event == "workflow_phase_failed" and _field(message, "reason") == "":
            return False

    return True


def _completed_and_failed_are_mutually_exclusive(messages: tuple[str, ...]) -> bool:
    phases = {_field(message, "phase") for message in messages}
    for phase in phases:
        completed = any(
            _field(message, "phase") == phase
            and _field(message, "event") == "workflow_phase_completed"
            for message in messages
        )
        failed = any(
            _field(message, "phase") == phase
            and _field(message, "event") == "workflow_phase_failed"
            for message in messages
        )
        if completed and failed:
            return False
    return True


def _field(message: str, field_name: str) -> str:
    prefix = f"{field_name}="
    for part in message.split():
        if part.startswith(prefix):
            return part.removeprefix(prefix)
    return ""

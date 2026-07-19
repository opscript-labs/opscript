from opscript.config import DEFAULT_DISCOVERY_SCOPE
import logging

import pytest
from platformiq.core import Identifier
from platformiq.errors.provider import ProviderError
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.model.value_objects import ResourceState

from opscript.application import WorkflowOutcome
from opscript.commands import (
    run_churn_workflow,
    run_churn_workflow_outcome,
    run_activity_workflow,
    run_activity_workflow_outcome,
    run_change_frequency_workflow,
    run_change_frequency_workflow_outcome,
    run_environment_evolution_workflow,
    run_environment_evolution_workflow_outcome,
    run_instability_workflow,
    run_instability_workflow_outcome,
    run_inventory_history_workflow,
    run_inventory_history_workflow_outcome,
    run_metadata_grouping_workflow,
    run_metadata_grouping_workflow_outcome,
    run_observation_history_workflow,
    run_observation_history_workflow_outcome,
    run_observation_workflow,
    run_observation_workflow_outcome,
    run_resource_evolution_workflow,
    run_resource_evolution_workflow_outcome,
    run_stability_workflow,
    run_stability_workflow_outcome,
)
from opscript.errors import OpscriptProviderError, FailureCategory
from opscript.storage import (
    SnapshotCommittedWithDegradedLatestError,
    SnapshotStorageError,
)
from opscript.storage.memory import InMemorySnapshotStorage


class StableDiscoveryProvider:
    def discover(self):
        return Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(
                Resource(
                    id=Identifier.new(),
                    external_id="resource-001",
                    state=ResourceState(),
                ),
            ),
        )


class ScopedDiscoveryProvider:
    def __init__(self, discovery_scope):
        self.discovery_scope = discovery_scope

    def discover(self):
        return Snapshot(
            discovery_scope=self.discovery_scope,
            id=Identifier.new(),
            resources=(
                Resource(
                    id=Identifier.new(),
                    external_id="resource-001",
                    state=ResourceState(),
                ),
            ),
        )


class FailingDiscoveryProvider:
    def discover(self):
        raise ProviderError("discovery provider unavailable")


class ClassifiedFailingDiscoveryProvider:
    def discover(self):
        raise OpscriptProviderError(
            "provider timed out",
            FailureCategory.TIMEOUT,
        )


class FailingSnapshotHistoryStorage:
    def load_history(self):
        raise SnapshotStorageError("snapshot history is unavailable")


class FailingLatestSnapshotStorage:
    def __init__(self):
        self.save_called = False

    def load_latest(self):
        raise SnapshotStorageError("latest snapshot is unavailable")

    def save(self, snapshot):
        self.save_called = True


class FailingSnapshotSaveStorage:
    def load_latest(self):
        return None

    def save(self, snapshot):
        raise SnapshotStorageError("snapshot save is unavailable")


class DegradedLatestSnapshotStorage:
    def __init__(self):
        self.save_calls = 0

    def load_latest(self):
        return None

    def save(self, snapshot):
        self.save_calls += 1
        raise SnapshotCommittedWithDegradedLatestError(
            "Snapshot record committed, but latest reference maintenance failed",
            record_key="snapshots/records/0001.json",
            original_exception=RuntimeError("latest reference unavailable"),
        )


class UnscopedEmptyStorage:
    def __init__(self):
        self.saved_snapshot = None

    def load_latest(self):
        return None

    def save(self, snapshot):
        self.saved_snapshot = snapshot


class FailingAnalysisService:
    def analyze_full(self, previous_snapshot, current_snapshot):
        raise RuntimeError("analysis failed")


class FailingReportingService:
    def generate_infrastructure_change_summary_report(self, summary):
        raise RuntimeError("reporting failed")


class FailingResourceEvolutionAnalysisService:
    def analyze_history(self, snapshots):
        raise RuntimeError("resource evolution analysis failed")


class FailingEnvironmentEvolutionAnalysisService:
    def analyze_history(self, snapshots):
        raise RuntimeError("environment evolution analysis failed")


class FailingInventoryHistoryAnalysisService:
    def analyze_historical_inventory_timeline(self, snapshots):
        raise RuntimeError("inventory history analysis failed")


class FailingChangeFrequencyAnalysisService:
    def analyze_resource_change_frequency(self, snapshots):
        raise RuntimeError("change frequency analysis failed")


class FailingChurnAnalysisService:
    def analyze_history(self, snapshots):
        raise RuntimeError("churn analysis failed")


class FailingInstabilityAnalysisService:
    def analyze_history(self, snapshots):
        raise RuntimeError("instability analysis failed")


class FailingActivityAnalysisService:
    def analyze_history(self, snapshots):
        raise RuntimeError("activity analysis failed")


class FailingStabilityAnalysisService:
    def analyze_history(self, snapshots):
        raise RuntimeError("stability analysis failed")


class FailingMetadataGroupingAnalysisService:
    def analyze_resource_metadata_groups(self, snapshots, metadata_path):
        raise RuntimeError("metadata grouping analysis failed")


class FailingObservationHistoryAnalysisService:
    def analyze_resource_observation_history(self, snapshots):
        raise RuntimeError("observation history analysis failed")


class RecordingMetadataGroupingAnalysisService:
    def __init__(self):
        self.metadata_path = None

    def analyze_resource_metadata_groups(self, snapshots, metadata_path):
        self.metadata_path = metadata_path
        return ()


class FailingResourceEvolutionReportingService:
    def generate_resource_evolution_report(
        self,
        resource_external_id,
        filtered_history,
        change_history,
    ):
        raise RuntimeError("resource evolution report failed")


class FailingEnvironmentEvolutionReportingService:
    def generate_environment_evolution_report(
        self,
        history,
        latest_change_index,
    ):
        raise RuntimeError("environment evolution report failed")


class FailingInventoryHistoryReportingService:
    def generate_historical_inventory_timeline_report(self, observations):
        raise RuntimeError("inventory history report failed")


class FailingChangeFrequencyReportingService:
    def generate_resource_change_frequency_report(self, summary):
        raise RuntimeError("change frequency report failed")


class FailingChurnReportingService:
    def generate_resource_churn_trend_report(self, summary, limit=None):
        raise RuntimeError("churn report failed")


class FailingInstabilityReportingService:
    def generate_instability_concentration_report(self, summary):
        raise RuntimeError("instability report failed")


class FailingActivityReportingService:
    def generate_operational_activity_dominance_report(self, summary):
        raise RuntimeError("activity report failed")


class FailingStabilityReportingService:
    def generate_environment_stability_trend_report(self, trend):
        raise RuntimeError("stability report failed")


class FailingMetadataGroupingReportingService:
    def generate_resource_metadata_grouping_report(self, groups):
        raise RuntimeError("metadata grouping report failed")


class FailingObservationHistoryReportingService:
    def generate_resource_observation_history_report(self, summaries):
        raise RuntimeError("observation history report failed")


def _environment_evolution_storage_with_history() -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    return storage


def _inventory_history_storage_with_history() -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(
                Resource(
                    id=Identifier.new(),
                    external_id="resource-001",
                    state=ResourceState(),
                ),
            ),
        )
    )
    return storage


def _change_frequency_storage_with_history() -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    return storage


def _churn_storage_with_history(
    resource_count: int = 2,
) -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    resources = tuple(
        Resource(
            id=Identifier.new(),
            external_id=f"resource-{index:03}",
            state=ResourceState(),
        )
        for index in range(1, resource_count + 1)
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=resources,
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    return storage


def _instability_storage_with_history() -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    return storage


def _activity_storage_with_history() -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    return storage


def _stability_storage_with_history() -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    return storage


def _metadata_grouping_storage_with_history() -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(properties={"tags": {"Environment": "prod"}}),
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    return storage


def _observation_history_storage_with_history() -> InMemorySnapshotStorage:
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    resource_001 = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )
    resource_002 = Resource(
        id=Identifier.new(),
        external_id="resource-002",
        state=ResourceState(),
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource_001, resource_002),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource_001,),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource_001, resource_002),
        )
    )
    return storage


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


def _workflow_phase_messages(caplog) -> tuple[str, ...]:
    return _workflow_phase_messages_for(caplog, "observation")


def _workflow_phase_messages_for(
    caplog,
    workflow: str,
) -> tuple[str, ...]:
    return tuple(
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and f"workflow={workflow}" in record.message
    )


def _log_field(
    message: str,
    field: str,
) -> str:
    prefix = f"{field}="
    for part in message.split():
        if part.startswith(prefix):
            return part.removeprefix(prefix)
    return ""


def _phase_events(messages: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (_log_field(message, "event"), _log_field(message, "phase"))
        for message in messages
    )


HISTORICAL_SUCCESS_PHASE_EVENTS = (
    ("workflow_phase_started", "historical_evidence_loading"),
    ("workflow_phase_completed", "historical_evidence_loading"),
    ("workflow_phase_started", "historical_evidence_validation"),
    ("workflow_phase_completed", "historical_evidence_validation"),
    ("workflow_phase_started", "historical_analysis"),
    ("workflow_phase_completed", "historical_analysis"),
    ("workflow_phase_started", "historical_report_projection"),
    ("workflow_phase_completed", "historical_report_projection"),
)


def _assert_terminal_phase_durations(messages: tuple[str, ...]) -> None:
    for message in messages:
        if "event=workflow_phase_completed" in message or (
            "event=workflow_phase_failed" in message
        ):
            duration = _log_field(message, "duration_ms")
            assert duration.isdigit()
            assert int(duration) >= 0


def _assert_phase_lifecycle_is_exclusive(messages: tuple[str, ...]) -> None:
    phases = tuple(_log_field(message, "phase") for message in messages)
    for phase in set(phases):
        phase_messages = [
            message for message in messages if _log_field(message, "phase") == phase
        ]
        assert (
            len(
                [
                    message
                    for message in phase_messages
                    if "event=workflow_phase_started" in message
                ]
            )
            == 1
        )
        terminal_events = [
            message
            for message in phase_messages
            if "event=workflow_phase_completed" in message
            or "event=workflow_phase_failed" in message
        ]
        assert len(terminal_events) == 1


def _assert_one_workflow_failure(
    messages: list[str],
    workflow: str,
    phase: str,
    reason: str,
) -> None:
    workflow_events = _workflow_events_for(messages, workflow)
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_failed" in message
            ]
        )
        == 1
    )
    assert_log_contains_all(
        list(workflow_events),
        "event=workflow_failed",
        "duration_ms=",
        f"phase={phase}",
        f"reason={reason}",
        f"workflow={workflow}",
    )
    assert not any("event=workflow_completed" in message for message in messages)


def _assert_no_legacy_observation_phases(messages: tuple[str, ...]) -> None:
    legacy_phases = (
        "load_latest",
        "discovery",
        "snapshot_persistence",
        "analysis",
        "reporting",
        "total_workflow",
    )
    assert not any(
        _log_field(message, "phase") in legacy_phases for message in messages
    )


def _workflow_events_for(
    messages: list[str],
    workflow: str,
) -> tuple[str, ...]:
    return tuple(
        message
        for message in messages
        if f"workflow={workflow}" in message
        and (
            "event=workflow_started" in message
            or "event=workflow_completed" in message
            or "event=workflow_failed" in message
        )
        and "event=workflow_phase_" not in message
    )


def test_observation_workflow_uses_previous_snapshot_history():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    discovery = StableDiscoveryProvider()

    first_output = run_observation_workflow(
        discovery_provider=discovery,
        snapshot_storage=storage,
    )

    second_output = run_observation_workflow(
        discovery_provider=discovery,
        snapshot_storage=storage,
    )

    assert "Resource created: resource-001" in first_output
    assert second_output == "No observations."


def test_observation_workflow_returns_outcome():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    discovery = StableDiscoveryProvider()
    previous_snapshot = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()
    )
    storage.save(previous_snapshot)

    outcome = run_observation_workflow_outcome(
        discovery_provider=discovery,
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Resource created: resource-001" in outcome.report
    assert outcome.analysis_result is not None
    assert outcome.analysis_result.diff.previous_snapshot_id == previous_snapshot.id
    assert (
        outcome.analysis_result.diff.current_snapshot_id == outcome.execution.value.id
    )
    assert outcome.analysis_result.findings
    assert outcome.metrics.workflow_name == "observation"
    assert outcome.metrics.measurements["resources"] == 1
    assert outcome.metrics.measurements["observations"] == 1
    assert outcome.metrics.measurements["findings"] == 1


def test_observation_workflow_empty_previous_snapshot_uses_discovered_scope():
    discovery_scope = DiscoveryScope("explicit-observation-scope")
    storage = UnscopedEmptyStorage()

    outcome = run_observation_workflow_outcome(
        discovery_provider=ScopedDiscoveryProvider(discovery_scope),
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert outcome.analysis_result is not None
    assert outcome.analysis_result.diff.created[0].external_id == "resource-001"
    assert storage.saved_snapshot is outcome.execution.value
    assert outcome.execution.value.discovery_scope == discovery_scope


def test_observation_workflow_logs_start_and_completion(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    discovery = StableDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_observation_workflow(
            discovery_provider=discovery,
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]

    assert "event=workflow_started workflow=observation" in messages
    assert_log_contains_all(
        messages,
        "event=workflow_completed",
        "duration_ms=",
        "findings=1",
        "observations=1",
        "resources=1",
        "workflow=observation",
    )
    assert not any("execution_id=" in message for message in messages)


def test_observation_workflow_logs_phase_lifecycle(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    discovery = StableDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_observation_workflow(
            discovery_provider=discovery,
            snapshot_storage=storage,
        )

    messages = _workflow_phase_messages(caplog)

    assert _phase_events(messages) == (
        ("workflow_phase_started", "latest_snapshot_loading"),
        ("workflow_phase_completed", "latest_snapshot_loading"),
        ("workflow_phase_started", "current_snapshot_collection"),
        ("workflow_phase_completed", "current_snapshot_collection"),
        ("workflow_phase_started", "change_analysis"),
        ("workflow_phase_completed", "change_analysis"),
        ("workflow_phase_started", "change_report_projection"),
        ("workflow_phase_completed", "change_report_projection"),
    )
    _assert_terminal_phase_durations(messages)
    _assert_no_legacy_observation_phases(messages)


def test_observation_workflow_missing_latest_completes_latest_phase(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_workflow(
            discovery_provider=StableDiscoveryProvider(),
            snapshot_storage=storage,
        )

    messages = _workflow_phase_messages(caplog)

    assert "Resource created: resource-001" in output
    assert (
        "workflow_phase_completed",
        "latest_snapshot_loading",
    ) in _phase_events(messages)
    assert (
        "workflow_phase_started",
        "current_snapshot_collection",
    ) in _phase_events(messages)


def test_observation_workflow_phase_timing_does_not_change_output():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    discovery = StableDiscoveryProvider()

    output = run_observation_workflow(
        discovery_provider=discovery,
        snapshot_storage=storage,
    )

    assert "Resource created: resource-001" in output


def test_observation_workflow_handles_discovery_provider_failure():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    output = run_observation_workflow(
        discovery_provider=FailingDiscoveryProvider(),
        snapshot_storage=storage,
    )

    assert output == "Infrastructure observation failed: discovery provider unavailable"


def test_observation_workflow_outcome_handles_discovery_provider_failure():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    output = run_observation_workflow_outcome(
        discovery_provider=FailingDiscoveryProvider(),
        snapshot_storage=storage,
    )

    assert output == "Infrastructure observation failed: discovery provider unavailable"


def test_observation_workflow_logs_discovery_provider_failure(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_observation_workflow(
            discovery_provider=FailingDiscoveryProvider(),
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages(caplog)

    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "latest_snapshot_loading"),
        ("workflow_phase_completed", "latest_snapshot_loading"),
        ("workflow_phase_started", "current_snapshot_collection"),
        ("workflow_phase_failed", "current_snapshot_collection"),
    )
    assert "discovery provider unavailable" not in phase_messages[-1]
    assert any(
        "event=workflow_failed" in message
        and "duration_ms=" in message
        and "failure_category=INTERNAL_DEFECT" in message
        and "phase=current_snapshot_collection" in message
        and "reason=provider_error" in message
        and "workflow=observation" in message
        for message in messages
    )


def test_observation_workflow_logs_classified_provider_failure_category(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_observation_workflow(
            discovery_provider=ClassifiedFailingDiscoveryProvider(),
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]

    assert any(
        "event=workflow_failed" in message
        and "duration_ms=" in message
        and "failure_category=TIMEOUT" in message
        and "phase=current_snapshot_collection" in message
        and "reason=provider_error" in message
        and "workflow=observation" in message
        for message in messages
    )


def test_observation_workflow_handles_load_latest_storage_failure(caplog):
    storage = FailingLatestSnapshotStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_workflow(
            discovery_provider=StableDiscoveryProvider(),
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages(caplog)

    assert output == "Infrastructure observation failed: latest snapshot is unavailable"
    assert storage.save_called is False
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "latest_snapshot_loading"),
        ("workflow_phase_failed", "latest_snapshot_loading"),
    )
    assert "latest snapshot is unavailable" not in phase_messages[-1]
    assert_log_contains_all(
        messages,
        "event=workflow_failed",
        "phase=latest_snapshot_loading",
        "reason=snapshot_storage_error",
        "workflow=observation",
        "error=latest snapshot is unavailable",
    )


def test_observation_workflow_outcome_handles_load_latest_storage_failure():
    output = run_observation_workflow_outcome(
        discovery_provider=StableDiscoveryProvider(),
        snapshot_storage=FailingLatestSnapshotStorage(),
    )

    assert output == "Infrastructure observation failed: latest snapshot is unavailable"


def test_observation_workflow_logs_snapshot_persistence_failure(caplog):
    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_workflow(
            discovery_provider=StableDiscoveryProvider(),
            snapshot_storage=FailingSnapshotSaveStorage(),
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages(caplog)

    assert output == "Infrastructure observation failed: snapshot save is unavailable"
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "latest_snapshot_loading"),
        ("workflow_phase_completed", "latest_snapshot_loading"),
        ("workflow_phase_started", "current_snapshot_collection"),
        ("workflow_phase_failed", "current_snapshot_collection"),
    )
    assert_log_contains_all(
        messages,
        "event=workflow_failed",
        "phase=current_snapshot_collection",
        "reason=snapshot_storage_error",
        "workflow=observation",
        "error=snapshot save is unavailable",
    )


def test_observation_workflow_degraded_latest_completes_collection_phase(caplog):
    storage = DegradedLatestSnapshotStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_workflow(
            discovery_provider=StableDiscoveryProvider(),
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages(caplog)

    assert "Resource created: resource-001" in output
    assert storage.save_calls == 1
    assert (
        "workflow_phase_completed",
        "current_snapshot_collection",
    ) in _phase_events(phase_messages)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_persistence_degraded",
        "latest_reference_maintenance=failed",
        "snapshot_committed=True",
    )


def test_observation_workflow_logs_analysis_failure(caplog, monkeypatch):
    monkeypatch.setattr(
        "opscript.commands.build_analysis_service",
        lambda *args, **kwargs: FailingAnalysisService(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_workflow(
            discovery_provider=StableDiscoveryProvider(),
            snapshot_storage=InMemorySnapshotStorage(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE
            ),
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages(caplog)

    assert output == "Infrastructure observation failed: analysis failed"
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "latest_snapshot_loading"),
        ("workflow_phase_completed", "latest_snapshot_loading"),
        ("workflow_phase_started", "current_snapshot_collection"),
        ("workflow_phase_completed", "current_snapshot_collection"),
        ("workflow_phase_started", "change_analysis"),
        ("workflow_phase_failed", "change_analysis"),
    )
    assert_log_contains_all(
        messages,
        "event=workflow_failed",
        "phase=change_analysis",
        "reason=internal_error",
        "workflow=observation",
        "error=analysis failed",
    )


def test_observation_workflow_logs_reporting_failure(caplog, monkeypatch):
    monkeypatch.setattr(
        "opscript.commands.build_reporting_service",
        lambda *args, **kwargs: FailingReportingService(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_workflow(
            discovery_provider=StableDiscoveryProvider(),
            snapshot_storage=InMemorySnapshotStorage(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE
            ),
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages(caplog)

    assert output == "Infrastructure observation failed: reporting failed"
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "latest_snapshot_loading"),
        ("workflow_phase_completed", "latest_snapshot_loading"),
        ("workflow_phase_started", "current_snapshot_collection"),
        ("workflow_phase_completed", "current_snapshot_collection"),
        ("workflow_phase_started", "change_analysis"),
        ("workflow_phase_completed", "change_analysis"),
        ("workflow_phase_started", "change_report_projection"),
        ("workflow_phase_failed", "change_report_projection"),
    )
    assert_log_contains_all(
        messages,
        "event=workflow_failed",
        "phase=change_report_projection",
        "reason=internal_error",
        "workflow=observation",
        "error=reporting failed",
    )


def test_resource_evolution_workflow_uses_snapshot_history():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )

    output = run_resource_evolution_workflow(
        "resource-001",
        snapshot_storage=storage,
    )

    assert "Resource Evolution: resource-001" in output
    assert "Resource created: resource-001" in output
    assert "New infrastructure introduced: resource-001" in output


def test_resource_evolution_workflow_returns_outcome():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )

    outcome = run_resource_evolution_workflow_outcome(
        "resource-001",
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Resource Evolution: resource-001" in outcome.report
    assert outcome.metrics.workflow_name == "resource_evolution"
    assert outcome.metrics.measurements["snapshots"] == 2
    assert outcome.metrics.measurements["comparisons"] == 1
    assert outcome.metrics.measurements["matched_comparisons"] == 1


def test_resource_evolution_workflow_logs_start_and_completion(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_resource_evolution_workflow(
            "resource-001",
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]

    assert (
        "event=workflow_started resource=resource-001 workflow=resource_evolution"
    ) in messages
    assert_log_contains_all(
        messages,
        "event=workflow_completed",
        "comparisons=1",
        "duration_ms=",
        "matched_comparisons=1",
        "resource=resource-001",
        "snapshots=2",
        "workflow=resource_evolution",
    )


def test_resource_evolution_workflow_logs_phase_lifecycle(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_resource_evolution_workflow(
            "resource-001",
            snapshot_storage=storage,
        )

    messages = _workflow_phase_messages_for(caplog, "resource_evolution")

    assert _phase_events(messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_completed", "historical_evidence_validation"),
        ("workflow_phase_started", "historical_analysis"),
        ("workflow_phase_completed", "historical_analysis"),
        ("workflow_phase_started", "historical_report_projection"),
        ("workflow_phase_completed", "historical_report_projection"),
    )
    _assert_terminal_phase_durations(messages)


def test_resource_evolution_workflow_handles_missing_resource_history():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    output = run_resource_evolution_workflow(
        "resource-999",
        snapshot_storage=storage,
    )

    assert output == "No history found for resource: resource-999"


def test_resource_evolution_workflow_no_matching_resource_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_resource_evolution_workflow(
            "resource-999",
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "resource_evolution")

    assert output == "No history found for resource: resource-999"
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_completed", "historical_evidence_validation"),
        ("workflow_phase_started", "historical_analysis"),
        ("workflow_phase_completed", "historical_analysis"),
        ("workflow_phase_started", "historical_report_projection"),
        ("workflow_phase_completed", "historical_report_projection"),
    )
    assert_log_contains_all(
        messages,
        "event=workflow_completed",
        "workflow=resource_evolution",
    )
    assert not any("event=workflow_failed" in message for message in messages)
    assert not any("event=workflow_phase_failed" in message for message in messages)


def test_resource_evolution_workflow_handles_snapshot_storage_failure():
    storage = FailingSnapshotHistoryStorage()

    output = run_resource_evolution_workflow(
        "resource-001",
        snapshot_storage=storage,
    )

    assert output == "Resource evolution failed: snapshot history is unavailable"


def test_resource_evolution_workflow_outcome_handles_snapshot_storage_failure():
    storage = FailingSnapshotHistoryStorage()

    output = run_resource_evolution_workflow_outcome(
        "resource-001",
        snapshot_storage=storage,
    )

    assert output == "Resource evolution failed: snapshot history is unavailable"


def test_resource_evolution_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_resource_evolution_workflow(
            "resource-001",
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "resource_evolution")

    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    assert "snapshot history is unavailable" not in phase_messages[-1]
    workflow_events = _workflow_events_for(messages, "resource_evolution")
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_failed" in message
            ]
        )
        == 1
    )
    assert_log_contains_all(
        list(workflow_events),
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_loading",
        "reason=snapshot_storage_error",
        "workflow=resource_evolution",
    )


def test_resource_evolution_workflow_logs_analysis_failure_without_changing_behavior(
    caplog,
    monkeypatch,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    monkeypatch.setattr(
        "opscript.commands.build_analysis_service",
        lambda *args, **kwargs: FailingResourceEvolutionAnalysisService(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match="resource evolution analysis failed"):
            run_resource_evolution_workflow(
                "resource-001",
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "resource_evolution")

    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_completed", "historical_evidence_validation"),
        ("workflow_phase_started", "historical_analysis"),
        ("workflow_phase_failed", "historical_analysis"),
    )
    assert "resource evolution analysis failed" not in phase_messages[-1]
    workflow_events = _workflow_events_for(messages, "resource_evolution")
    assert workflow_events[-1].startswith("event=workflow_failed")
    assert_log_contains_all(
        list(workflow_events),
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_analysis",
        "reason=analysis_error",
        "workflow=resource_evolution",
    )
    assert not any("event=workflow_completed" in message for message in messages)
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_failed" in message
            ]
        )
        == 1
    )


def test_resource_evolution_workflow_logs_projection_failure_without_changing_behavior(
    caplog,
    monkeypatch,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    monkeypatch.setattr(
        "opscript.commands.build_reporting_service",
        lambda *args, **kwargs: FailingResourceEvolutionReportingService(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match="resource evolution report failed"):
            run_resource_evolution_workflow(
                "resource-001",
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "resource_evolution")

    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_completed", "historical_evidence_validation"),
        ("workflow_phase_started", "historical_analysis"),
        ("workflow_phase_completed", "historical_analysis"),
        ("workflow_phase_started", "historical_report_projection"),
        ("workflow_phase_failed", "historical_report_projection"),
    )
    assert "resource evolution report failed" not in phase_messages[-1]
    workflow_events = _workflow_events_for(messages, "resource_evolution")
    assert workflow_events[-1].startswith("event=workflow_failed")
    assert_log_contains_all(
        list(workflow_events),
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_report_projection",
        "reason=report_projection_error",
        "workflow=resource_evolution",
    )
    assert not any("event=workflow_completed" in message for message in messages)
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_failed" in message
            ]
        )
        == 1
    )


def test_environment_evolution_workflow_uses_snapshot_history():
    storage = _environment_evolution_storage_with_history()

    output = run_environment_evolution_workflow(
        snapshot_storage=storage,
    )

    assert "Environment Evolution" in output
    assert "Comparisons analyzed: 1" in output
    assert "Resources introduced: 1" in output
    assert "resource-001" in output


def test_environment_evolution_workflow_returns_outcome():
    storage = _environment_evolution_storage_with_history()

    outcome = run_environment_evolution_workflow_outcome(
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Environment Evolution" in outcome.report
    assert outcome.metrics.workflow_name == "environment_evolution"
    assert outcome.metrics.measurements["snapshots"] == 2
    assert outcome.metrics.measurements["comparisons"] == 1


def test_environment_evolution_workflow_logs_start_and_completion(caplog):
    storage = _environment_evolution_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_environment_evolution_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]

    assert "event=workflow_started workflow=environment_evolution" in messages
    assert_log_contains_all(
        messages,
        "event=workflow_completed",
        "comparisons=1",
        "duration_ms=",
        "snapshots=2",
        "workflow=environment_evolution",
    )


def test_environment_evolution_workflow_logs_phase_lifecycle(caplog):
    storage = _environment_evolution_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_environment_evolution_workflow(
            snapshot_storage=storage,
        )

    messages = _workflow_phase_messages_for(caplog, "environment_evolution")

    assert _phase_events(messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_completed", "historical_evidence_validation"),
        ("workflow_phase_started", "historical_analysis"),
        ("workflow_phase_completed", "historical_analysis"),
        ("workflow_phase_started", "historical_report_projection"),
        ("workflow_phase_completed", "historical_report_projection"),
    )
    assert all("workflow=environment_evolution" in message for message in messages)
    assert all(_log_field(message, "phase") for message in messages)
    _assert_terminal_phase_durations(messages)
    _assert_phase_lifecycle_is_exclusive(messages)
    assert not any("event=workflow_phase_failed" in message for message in messages)


def test_environment_evolution_workflow_handles_empty_history():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    output = run_environment_evolution_workflow(
        snapshot_storage=storage,
    )

    assert output == "No environment history."


def test_environment_evolution_workflow_empty_history_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_environment_evolution_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "environment_evolution")
    workflow_events = _workflow_events_for(messages, "environment_evolution")

    assert output == "No environment history."
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_completed", "historical_evidence_validation"),
        ("workflow_phase_started", "historical_analysis"),
        ("workflow_phase_completed", "historical_analysis"),
        ("workflow_phase_started", "historical_report_projection"),
        ("workflow_phase_completed", "historical_report_projection"),
    )
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )


def test_environment_evolution_workflow_handles_snapshot_storage_failure():
    storage = FailingSnapshotHistoryStorage()

    output = run_environment_evolution_workflow(
        snapshot_storage=storage,
    )

    assert output == "Environment evolution failed: snapshot history is unavailable"


def test_environment_evolution_workflow_outcome_handles_snapshot_storage_failure():
    storage = FailingSnapshotHistoryStorage()

    output = run_environment_evolution_workflow_outcome(
        snapshot_storage=storage,
    )

    assert output == "Environment evolution failed: snapshot history is unavailable"


def test_environment_evolution_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_environment_evolution_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "environment_evolution")
    workflow_events = _workflow_events_for(messages, "environment_evolution")

    assert output == "Environment evolution failed: snapshot history is unavailable"
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_failed" in message
            ]
        )
        == 1
    )
    assert_log_contains_all(
        list(workflow_events),
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_loading",
        "reason=snapshot_storage_error",
        "workflow=environment_evolution",
    )
    assert not any("event=workflow_completed" in message for message in messages)


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingEnvironmentEvolutionAnalysisService(),
            "environment evolution analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingEnvironmentEvolutionReportingService(),
            "environment evolution report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_environment_evolution_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_environment_evolution_workflow(
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "environment_evolution")
    workflow_events = _workflow_events_for(messages, "environment_evolution")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_failed" in message
            ]
        )
        == 1
    )
    assert_log_contains_all(
        list(workflow_events),
        "event=workflow_failed",
        "duration_ms=",
        f"phase={expected_failed_phase}",
        f"reason={expected_reason}",
        "workflow=environment_evolution",
    )
    assert not any("event=workflow_completed" in message for message in messages)


def test_resource_evolution_workflow_includes_change_history():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )

    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )

    output = run_resource_evolution_workflow(
        "resource-001",
        snapshot_storage=storage,
    )

    assert "Resource Change History: resource-001" in output
    assert "First recorded change: Comparison 1" in output
    assert "Most recent recorded change: Comparison 3" in output
    assert "Recorded change count: 2" in output
    assert "Recorded change span: Comparison 1 -> Comparison 3" in output
    assert "Comparisons containing recorded changes:" in output
    assert "- Comparison 1" in output
    assert "- Comparison 3" in output


def test_environment_evolution_workflow_includes_latest_change_index():
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(),
    )

    # 1. Start empty
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )
    )
    # 2. Change 1: introduce resource-001 (Comparison 1)
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    # 3. Change 2: no changes (Comparison 2)
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(resource,),
        )
    )
    # 4. Change 3: modify state properties (Comparison 3)
    modified_resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(properties={"size": "large"}),
    )
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(modified_resource,),
        )
    )
    # 5. Change 4: no changes (Comparison 4)
    storage.save(
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(modified_resource,),
        )
    )

    output = run_environment_evolution_workflow(
        snapshot_storage=storage,
    )

    assert "Latest comparison containing recorded changes: Comparison 3" in output


def test_instability_workflow_returns_outcome_with_existing_metrics():
    storage = _instability_storage_with_history()

    outcome = run_instability_workflow_outcome(
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Operational Instability Concentration" in outcome.report
    assert outcome.metrics.workflow_name == "instability"
    assert outcome.metrics.measurements["snapshots"] == 2
    assert outcome.metrics.measurements["comparisons"] == 1
    assert outcome.metrics.measurements["resources"] == 1


def test_instability_workflow_logs_phase_lifecycle(caplog):
    storage = _instability_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_instability_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "instability")
    workflow_events = _workflow_events_for(messages, "instability")

    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    assert all("workflow=instability" in message for message in phase_messages)
    assert all(_log_field(message, "phase") for message in phase_messages)
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert not any("event=workflow_phase_failed" in message for message in messages)
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_completed" in message
            ]
        )
        == 1
    )
    assert not any("event=workflow_failed" in message for message in workflow_events)


def test_instability_workflow_empty_history_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_instability_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "instability")
    workflow_events = _workflow_events_for(messages, "instability")

    assert (
        output == "Operational Instability Concentration\n\n"
        "No recorded infrastructure activity found."
    )
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )


def test_instability_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_instability_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "instability")

    assert output == "Instability concentration failed: snapshot history is unavailable"
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "instability",
        "historical_evidence_loading",
        "snapshot_storage_error",
    )


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingInstabilityAnalysisService(),
            "instability analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingInstabilityReportingService(),
            "instability report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_instability_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_instability_workflow(
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "instability")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "instability",
        expected_failed_phase,
        expected_reason,
    )


def test_activity_workflow_returns_outcome_with_existing_metrics():
    storage = _activity_storage_with_history()

    outcome = run_activity_workflow_outcome(
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Operational Activity Dominance" in outcome.report
    assert outcome.metrics.workflow_name == "activity"
    assert outcome.metrics.measurements["snapshots"] == 2
    assert outcome.metrics.measurements["comparisons"] == 1
    assert outcome.metrics.measurements["activities"] == 3


def test_activity_workflow_logs_phase_lifecycle(caplog):
    storage = _activity_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_activity_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "activity")
    workflow_events = _workflow_events_for(messages, "activity")

    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    assert all("workflow=activity" in message for message in phase_messages)
    assert all(_log_field(message, "phase") for message in phase_messages)
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert not any("event=workflow_phase_failed" in message for message in messages)
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_completed" in message
            ]
        )
        == 1
    )
    assert not any("event=workflow_failed" in message for message in workflow_events)


def test_activity_workflow_empty_history_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_activity_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "activity")
    workflow_events = _workflow_events_for(messages, "activity")

    assert (
        output
        == "Operational Activity Dominance\n\nNo recorded operational activity found."
    )
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )


def test_activity_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_activity_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "activity")

    assert (
        output
        == "Operational activity dominance failed: snapshot history is unavailable"
    )
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "activity",
        "historical_evidence_loading",
        "snapshot_storage_error",
    )


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingActivityAnalysisService(),
            "activity analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingActivityReportingService(),
            "activity report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_activity_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_activity_workflow(
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "activity")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "activity",
        expected_failed_phase,
        expected_reason,
    )


def test_stability_workflow_returns_outcome_with_existing_metrics():
    storage = _stability_storage_with_history()

    outcome = run_stability_workflow_outcome(
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Environment Stability Trend" in outcome.report
    assert outcome.metrics.workflow_name == "stability"
    assert outcome.metrics.measurements["snapshots"] == 3
    assert outcome.metrics.measurements["comparisons"] == 2


def test_stability_workflow_logs_phase_lifecycle(caplog):
    storage = _stability_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_stability_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "stability")
    workflow_events = _workflow_events_for(messages, "stability")

    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    assert all("workflow=stability" in message for message in phase_messages)
    assert all(_log_field(message, "phase") for message in phase_messages)
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert not any("event=workflow_phase_failed" in message for message in messages)
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_completed" in message
            ]
        )
        == 1
    )
    assert not any("event=workflow_failed" in message for message in workflow_events)


def test_stability_workflow_insufficient_history_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_stability_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "stability")
    workflow_events = _workflow_events_for(messages, "stability")

    assert (
        output == "Environment Stability Trend\n\n"
        "Insufficient history to determine activity direction."
    )
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )


def test_stability_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_stability_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "stability")

    assert (
        output == "Environment stability trend failed: snapshot history is unavailable"
    )
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "stability",
        "historical_evidence_loading",
        "snapshot_storage_error",
    )


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingStabilityAnalysisService(),
            "stability analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingStabilityReportingService(),
            "stability report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_stability_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_stability_workflow(
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "stability")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "stability",
        expected_failed_phase,
        expected_reason,
    )


def test_change_frequency_workflow_returns_outcome_with_existing_metrics():
    storage = _change_frequency_storage_with_history()

    outcome = run_change_frequency_workflow_outcome(
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Resource Change Frequency" in outcome.report
    assert outcome.metrics.workflow_name == "change_frequency"
    assert outcome.metrics.measurements["snapshots"] == 2
    assert outcome.metrics.measurements["resources"] == 1


def test_change_frequency_workflow_logs_phase_lifecycle(caplog):
    storage = _change_frequency_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_change_frequency_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "change_frequency")
    workflow_events = _workflow_events_for(messages, "change_frequency")

    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    assert all("workflow=change_frequency" in message for message in phase_messages)
    assert all(_log_field(message, "phase") for message in phase_messages)
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert not any("event=workflow_phase_failed" in message for message in messages)
    assert (
        len(
            [
                message
                for message in workflow_events
                if "event=workflow_completed" in message
            ]
        )
        == 1
    )
    assert not any("event=workflow_failed" in message for message in workflow_events)


def test_change_frequency_workflow_empty_history_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_change_frequency_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "change_frequency")
    workflow_events = _workflow_events_for(messages, "change_frequency")

    assert output == "Resource Change Frequency\n\nNo observed resources found."
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )


def test_change_frequency_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_change_frequency_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "change_frequency")

    assert output == "Resource change frequency failed: snapshot history is unavailable"
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "change_frequency",
        "historical_evidence_loading",
        "snapshot_storage_error",
    )


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingChangeFrequencyAnalysisService(),
            "change frequency analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingChangeFrequencyReportingService(),
            "change frequency report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_change_frequency_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_change_frequency_workflow(
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "change_frequency")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "change_frequency",
        expected_failed_phase,
        expected_reason,
    )


def test_inventory_history_workflow_returns_outcome():
    storage = _inventory_history_storage_with_history()

    outcome = run_inventory_history_workflow_outcome(
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Historical Inventory Timeline" in outcome.report
    assert outcome.metrics.workflow_name == "inventory_history"
    assert outcome.metrics.measurements["snapshots"] == 2
    assert outcome.metrics.measurements["observations"] == 2


def test_inventory_history_workflow_logs_phase_lifecycle(caplog):
    storage = _inventory_history_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        run_inventory_history_workflow(
            snapshot_storage=storage,
        )

    messages = _workflow_phase_messages_for(caplog, "inventory_history")

    assert _phase_events(messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    assert all("workflow=inventory_history" in message for message in messages)
    assert all(_log_field(message, "phase") for message in messages)
    _assert_terminal_phase_durations(messages)
    _assert_phase_lifecycle_is_exclusive(messages)
    assert not any("event=workflow_phase_failed" in message for message in messages)


def test_inventory_history_workflow_empty_history_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_inventory_history_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "inventory_history")
    workflow_events = _workflow_events_for(messages, "inventory_history")

    assert (
        output
        == "Historical Inventory Timeline\n\nNo historical inventory observations found."
    )
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )


def test_inventory_history_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_inventory_history_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "inventory_history")

    assert (
        output
        == "Historical inventory timeline failed: snapshot history is unavailable"
    )
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "inventory_history",
        "historical_evidence_loading",
        "snapshot_storage_error",
    )


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingInventoryHistoryAnalysisService(),
            "inventory history analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingInventoryHistoryReportingService(),
            "inventory history report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_inventory_history_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_inventory_history_workflow(
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "inventory_history")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "inventory_history",
        expected_failed_phase,
        expected_reason,
    )


def test_metadata_grouping_workflow_returns_outcome_with_existing_metrics():
    storage = _metadata_grouping_storage_with_history()

    outcome = run_metadata_grouping_workflow_outcome(
        "tags.Environment",
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Resource Metadata Grouping" in outcome.report
    assert "Metadata: tags.Environment" in outcome.report
    assert outcome.metrics.workflow_name == "metadata_grouping"
    assert outcome.metrics.measurements == {
        "snapshots": 2,
        "groups": 1,
    }


def test_metadata_grouping_workflow_logs_phase_lifecycle(caplog):
    storage = _metadata_grouping_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_metadata_grouping_workflow(
            "tags.Environment",
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "metadata_grouping")
    workflow_events = _workflow_events_for(messages, "metadata_grouping")

    assert "Resource Metadata Grouping" in output
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_started" in message for message in workflow_events)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )
    assert not any("tags.Environment" in message for message in phase_messages)


def test_metadata_grouping_workflow_empty_history_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_metadata_grouping_workflow(
            "tags.Environment",
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "metadata_grouping")
    workflow_events = _workflow_events_for(messages, "metadata_grouping")

    assert output == (
        "Resource Metadata Grouping\n\nNo recorded metadata groups found."
    )
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )


def test_metadata_grouping_workflow_passes_metadata_path_unchanged(
    caplog,
    monkeypatch,
):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    analysis_service = RecordingMetadataGroupingAnalysisService()

    monkeypatch.setattr(
        "opscript.commands.build_analysis_service",
        lambda *args, **kwargs: analysis_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_metadata_grouping_workflow(
            "tags.Environment",
            snapshot_storage=storage,
        )

    phase_messages = _workflow_phase_messages_for(caplog, "metadata_grouping")

    assert output == (
        "Resource Metadata Grouping\n\nNo recorded metadata groups found."
    )
    assert analysis_service.metadata_path == "tags.Environment"
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    assert not any("tags.Environment" in message for message in phase_messages)


def test_metadata_grouping_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_metadata_grouping_workflow(
            "tags.Environment",
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "metadata_grouping")

    assert (
        output == "Resource metadata grouping failed: snapshot history is unavailable"
    )
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "metadata_grouping",
        "historical_evidence_loading",
        "snapshot_storage_error",
    )


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingMetadataGroupingAnalysisService(),
            "metadata grouping analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingMetadataGroupingReportingService(),
            "metadata grouping report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_metadata_grouping_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = _metadata_grouping_storage_with_history()

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_metadata_grouping_workflow(
                "tags.Environment",
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "metadata_grouping")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    assert not any("tags.Environment" in message for message in phase_messages)
    _assert_one_workflow_failure(
        messages,
        "metadata_grouping",
        expected_failed_phase,
        expected_reason,
    )


def test_observation_history_workflow_returns_outcome_with_existing_metrics():
    storage = _observation_history_storage_with_history()

    outcome = run_observation_history_workflow_outcome(
        snapshot_storage=storage,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Resource Observation History" in outcome.report
    assert outcome.metrics.workflow_name == "observation_history"
    assert outcome.metrics.measurements == {
        "snapshots": 3,
        "resources": 2,
    }


@pytest.mark.parametrize(
    ("resource_external_id", "expected_present", "expected_absent"),
    (
        (None, "Resource: resource-001", None),
        ("resource-002", "Resource: resource-002", "Resource: resource-001"),
    ),
)
def test_observation_history_workflow_logs_phase_lifecycle(
    caplog,
    resource_external_id,
    expected_present,
    expected_absent,
):
    storage = _observation_history_storage_with_history()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_history_workflow(
            resource_external_id=resource_external_id,
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "observation_history")
    workflow_events = _workflow_events_for(messages, "observation_history")

    assert "Resource Observation History" in output
    assert expected_present in output
    if expected_absent is not None:
        assert expected_absent not in output
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_started" in message for message in workflow_events)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )
    assert not any("resource-002" in message for message in phase_messages)
    assert not any("Resource:" in message for message in phase_messages)


@pytest.mark.parametrize(
    ("storage", "resource_external_id"),
    (
        (InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE), None),
        (_observation_history_storage_with_history(), "missing-resource"),
    ),
)
def test_observation_history_workflow_empty_or_no_match_completes_all_phases(
    caplog,
    storage,
    resource_external_id,
):
    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_history_workflow(
            resource_external_id=resource_external_id,
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "observation_history")
    workflow_events = _workflow_events_for(messages, "observation_history")

    assert output == (
        "Resource Observation History\n\nNo resource observation history found."
    )
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )
    assert not any("missing-resource" in message for message in phase_messages)


def test_observation_history_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_observation_history_workflow(
            snapshot_storage=storage,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "observation_history")

    assert (
        output == "Resource observation history failed: snapshot history is unavailable"
    )
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "observation_history",
        "historical_evidence_loading",
        "snapshot_storage_error",
    )


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingObservationHistoryAnalysisService(),
            "observation history analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingObservationHistoryReportingService(),
            "observation history report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_observation_history_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = _observation_history_storage_with_history()

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_observation_history_workflow(
                resource_external_id="resource-002",
                snapshot_storage=storage,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "observation_history")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    assert not any("resource-002" in message for message in phase_messages)
    _assert_one_workflow_failure(
        messages,
        "observation_history",
        expected_failed_phase,
        expected_reason,
    )


def test_churn_workflow_returns_outcome_with_existing_metrics():
    storage = _churn_storage_with_history()

    outcome = run_churn_workflow_outcome(
        snapshot_storage=storage,
        report_limit=20,
    )

    assert isinstance(outcome, WorkflowOutcome)
    assert "Resource Churn Trend" in outcome.report
    assert outcome.metrics.workflow_name == "churn"
    assert outcome.metrics.measurements == {
        "snapshots": 3,
        "comparisons": 2,
        "resources": 2,
    }


@pytest.mark.parametrize(
    ("report_limit", "expected_present", "expected_absent", "expected_omission"),
    (
        (
            20,
            "Resource: resource-020",
            "Resource: resource-021",
            "Showing 20 of 21 resource trends. "
            "1 omitted. Use --all to show the complete report.",
        ),
        (None, "Resource: resource-021", None, None),
    ),
)
def test_churn_workflow_logs_phase_lifecycle_for_default_and_all_modes(
    caplog,
    report_limit,
    expected_present,
    expected_absent,
    expected_omission,
):
    storage = _churn_storage_with_history(resource_count=21)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_churn_workflow(
            snapshot_storage=storage,
            report_limit=report_limit,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "churn")
    workflow_events = _workflow_events_for(messages, "churn")

    assert "Resource Churn Trend" in output
    assert expected_present in output
    if expected_absent is not None:
        assert expected_absent not in output
    if expected_omission is not None:
        assert expected_omission in output
    else:
        assert "omitted. Use --all to show the complete report." not in output
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_started" in message for message in workflow_events)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )
    assert not any("resource-001" in message for message in phase_messages)
    assert not any("limit=" in message for message in phase_messages)


def test_churn_workflow_empty_history_completes_all_phases(caplog):
    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_churn_workflow(
            snapshot_storage=storage,
            report_limit=20,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "churn")
    workflow_events = _workflow_events_for(messages, "churn")

    assert output == "Resource Churn Trend\n\nNo recorded resource activity found."
    assert _phase_events(phase_messages) == HISTORICAL_SUCCESS_PHASE_EVENTS
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert any("event=workflow_completed" in message for message in workflow_events)
    assert not any("event=workflow_failed" in message for message in workflow_events)
    assert not any(
        "event=workflow_phase_failed" in message for message in phase_messages
    )


def test_churn_workflow_logs_snapshot_storage_failure(caplog):
    storage = FailingSnapshotHistoryStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        output = run_churn_workflow(
            snapshot_storage=storage,
            report_limit=20,
        )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "churn")

    assert output == "Resource churn trend failed: snapshot history is unavailable"
    assert _phase_events(phase_messages) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_failed", "historical_evidence_loading"),
    )
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert "snapshot history is unavailable" not in phase_messages[-1]
    _assert_one_workflow_failure(
        messages,
        "churn",
        "historical_evidence_loading",
        "snapshot_storage_error",
    )


@pytest.mark.parametrize(
    (
        "patch_target",
        "failing_service",
        "expected_error",
        "expected_events",
        "expected_failed_phase",
        "expected_reason",
    ),
    (
        (
            "opscript.commands.build_analysis_service",
            FailingChurnAnalysisService(),
            "churn analysis failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_failed", "historical_analysis"),
            ),
            "historical_analysis",
            "analysis_error",
        ),
        (
            "opscript.commands.build_reporting_service",
            FailingChurnReportingService(),
            "churn report failed",
            (
                ("workflow_phase_started", "historical_evidence_loading"),
                ("workflow_phase_completed", "historical_evidence_loading"),
                ("workflow_phase_started", "historical_evidence_validation"),
                ("workflow_phase_completed", "historical_evidence_validation"),
                ("workflow_phase_started", "historical_analysis"),
                ("workflow_phase_completed", "historical_analysis"),
                ("workflow_phase_started", "historical_report_projection"),
                ("workflow_phase_failed", "historical_report_projection"),
            ),
            "historical_report_projection",
            "report_projection_error",
        ),
    ),
)
def test_churn_workflow_logs_uncontrolled_failure_without_changing_behavior(
    caplog,
    monkeypatch,
    patch_target,
    failing_service,
    expected_error,
    expected_events,
    expected_failed_phase,
    expected_reason,
):
    storage = _churn_storage_with_history()

    monkeypatch.setattr(
        patch_target,
        lambda *args, **kwargs: failing_service,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match=expected_error):
            run_churn_workflow(
                snapshot_storage=storage,
                report_limit=20,
            )

    messages = [record.message for record in caplog.records]
    phase_messages = _workflow_phase_messages_for(caplog, "churn")

    assert _phase_events(phase_messages) == expected_events
    _assert_terminal_phase_durations(phase_messages)
    _assert_phase_lifecycle_is_exclusive(phase_messages)
    assert expected_error not in phase_messages[-1]
    assert not any("resource-001" in message for message in phase_messages)
    assert not any("limit=" in message for message in phase_messages)
    _assert_one_workflow_failure(
        messages,
        "churn",
        expected_failed_phase,
        expected_reason,
    )

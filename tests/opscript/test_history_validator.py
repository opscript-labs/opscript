from opscript.config import DEFAULT_DISCOVERY_SCOPE
import pytest
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot

from opscript.application import HistoryValidator, HistoryValidationError
from opscript.commands import (
    run_churn_workflow_outcome,
    run_activity_workflow_outcome,
    run_change_frequency_workflow_outcome,
    run_environment_evolution_workflow_outcome,
    run_instability_workflow_outcome,
    run_inventory_history_workflow_outcome,
    run_metadata_grouping_workflow_outcome,
    run_observation_history_workflow_outcome,
    run_resource_evolution_workflow_outcome,
    run_stability_workflow_outcome,
)
from opscript.storage.memory import InMemorySnapshotStorage


def test_history_validator_accepts_empty_history():
    validator = HistoryValidator()
    validator.validate(())


def test_history_validator_accepts_single_snapshot():
    validator = HistoryValidator()
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    validator.validate((snapshot,))


def test_history_validator_accepts_multiple_valid_snapshots():
    validator = HistoryValidator()
    res1 = Resource(id=Identifier.new(), external_id="res-001")
    res2 = Resource(id=Identifier.new(), external_id="res-002")

    snap1 = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(res1,),
    )
    snap2 = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(res1, res2),
    )

    validator.validate((snap1, snap2))


def test_history_validator_rejects_non_tuple():
    validator = HistoryValidator()
    with pytest.raises(HistoryValidationError) as excinfo:
        validator.validate([])  # type: ignore
    assert "Snapshot history must be a tuple" in str(excinfo.value)


def test_history_validator_rejects_duplicate_snapshot_ids():
    validator = HistoryValidator()
    snap_id = Identifier.new()
    snap1 = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id)
    snap2 = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id)
    with pytest.raises(HistoryValidationError) as excinfo:
        validator.validate((snap1, snap2))
    assert "Duplicate snapshot ID detected in history" in str(excinfo.value)


def test_history_validator_rejects_mixed_discovery_scopes():
    validator = HistoryValidator()
    snap1 = Snapshot(
        discovery_scope=DiscoveryScope("scope-001"),
        id=Identifier.new(),
    )
    snap2 = Snapshot(
        discovery_scope=DiscoveryScope("scope-002"),
        id=Identifier.new(),
    )

    with pytest.raises(HistoryValidationError) as excinfo:
        validator.validate((snap1, snap2))

    assert "multiple discovery scopes" in str(excinfo.value)


def test_resource_evolution_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    # Save duplicate snapshot IDs in history
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_resource_evolution_workflow_outcome(
            resource_external_id="res-001",
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Resource evolution failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=resource_evolution" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message
        and "workflow=resource_evolution" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=resource_evolution",
    )


def test_environment_evolution_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    # Save duplicate snapshot IDs in history
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.ERROR, logger="opscript"):
        outcome = run_environment_evolution_workflow_outcome(
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Environment evolution failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    assert any(
        "event=workflow_failed" in message
        and "duration_ms=" in message
        and "phase=historical_evidence_validation" in message
        and "reason=validation_error" in message
        and "workflow=environment_evolution" in message
        for message in messages
    )


def test_inventory_history_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_inventory_history_workflow_outcome(
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Historical inventory timeline failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=inventory_history" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message
        and "workflow=inventory_history" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=inventory_history",
    )


def test_change_frequency_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_change_frequency_workflow_outcome(
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Resource change frequency failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=change_frequency" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message and "workflow=change_frequency" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=change_frequency",
    )


def test_instability_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_instability_workflow_outcome(
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Instability concentration failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=instability" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message and "workflow=instability" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=instability",
    )


def test_activity_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_activity_workflow_outcome(
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Operational activity dominance failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=activity" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message and "workflow=activity" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=activity",
    )


def test_stability_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_stability_workflow_outcome(
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Environment stability trend failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=stability" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message and "workflow=stability" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=stability",
    )


def test_metadata_grouping_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_metadata_grouping_workflow_outcome(
            "tags.Environment",
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Resource metadata grouping failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=metadata_grouping" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message
        and "workflow=metadata_grouping" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=metadata_grouping",
    )


def test_observation_history_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_observation_history_workflow_outcome(
            snapshot_storage=storage,
        )

    assert isinstance(outcome, str)
    assert "Resource observation history failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=observation_history" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message
        and "workflow=observation_history" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=observation_history",
    )


def test_churn_workflow_fails_when_validation_fails(caplog):
    import logging

    storage = InMemorySnapshotStorage(discovery_scope=DEFAULT_DISCOVERY_SCOPE)
    snap_id = Identifier.new()

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=snap_id))

    with caplog.at_level(logging.INFO, logger="opscript"):
        outcome = run_churn_workflow_outcome(
            snapshot_storage=storage,
            report_limit=20,
        )

    assert isinstance(outcome, str)
    assert "Resource churn trend failed" in outcome
    assert "Duplicate snapshot ID detected in history" in outcome

    messages = [record.message for record in caplog.records]
    phase_messages = [
        record.message
        for record in caplog.records
        if "event=workflow_phase_" in record.message
        and "workflow=churn" in record.message
    ]
    assert tuple(
        (
            _log_field(message, "event"),
            _log_field(message, "phase"),
        )
        for message in phase_messages
    ) == (
        ("workflow_phase_started", "historical_evidence_loading"),
        ("workflow_phase_completed", "historical_evidence_loading"),
        ("workflow_phase_started", "historical_evidence_validation"),
        ("workflow_phase_failed", "historical_evidence_validation"),
    )
    assert "Duplicate snapshot ID detected" not in phase_messages[-1]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message and "workflow=churn" in message
    ]
    assert len(workflow_failed) == 1
    assert_log_contains_all(
        workflow_failed,
        "event=workflow_failed",
        "duration_ms=",
        "phase=historical_evidence_validation",
        "reason=validation_error",
        "workflow=churn",
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


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)

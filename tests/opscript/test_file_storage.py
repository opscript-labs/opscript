from opscript.config import DEFAULT_DISCOVERY_SCOPE
import json
import logging
from pathlib import Path

import pytest

from opscript.storage import FileSnapshotStorage, SnapshotStorageError
from opscript.execution import activate_execution, create_execution
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.serialization import SnapshotSerializer


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


def assert_log_count(
    messages: list[str],
    event: str,
    expected_count: int,
) -> None:
    assert (
        sum(1 for message in messages if f"event={event}" in message) == expected_count
    )


def assert_no_execution_id(
    messages: list[str],
) -> None:
    assert not any("execution_id=" in message for message in messages)


def assert_all_storage_logs_have_execution_id(
    messages: list[str],
    execution_id: str,
) -> None:
    storage_messages = [
        message for message in messages if message.startswith("event=snapshot_storage_")
    ]
    assert storage_messages
    assert all(
        f"execution_id={execution_id}" in message for message in storage_messages
    )


def snapshot_with_resource(
    discovery_scope: DiscoveryScope,
    resource_external_id: str,
) -> Snapshot:
    return Snapshot(
        discovery_scope=discovery_scope,
        id=Identifier.new(),
        resources=(
            Resource(
                id=Identifier.new(),
                external_id=resource_external_id,
            ),
        ),
    )


def test_file_storage_saves_snapshot(tmp_path):
    file_path = tmp_path / "snapshots"

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(snapshot)

    loaded = storage.load_latest()

    assert isinstance(loaded, Snapshot)
    assert loaded.id == snapshot.id
    assert loaded.discovery_scope == DEFAULT_DISCOVERY_SCOPE


def test_file_storage_rejects_mismatched_scope_save(tmp_path):
    storage = FileSnapshotStorage(
        str(tmp_path / "snapshots"),
        SnapshotSerializer(),
        discovery_scope=DiscoveryScope("scope-001"),
    )
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("scope-002"),
        id=Identifier.new(),
    )

    with pytest.raises(SnapshotStorageError, match="discovery scope"):
        storage.save(snapshot)


def test_file_storage_isolates_histories_by_path_and_scope(tmp_path):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    path_a = tmp_path / "scope-a"
    path_b = tmp_path / "scope-b"
    storage_a = FileSnapshotStorage(
        str(path_a),
        SnapshotSerializer(),
        discovery_scope=scope_a,
    )
    storage_b = FileSnapshotStorage(
        str(path_b),
        SnapshotSerializer(),
        discovery_scope=scope_b,
    )
    first_a = snapshot_with_resource(scope_a, "resource-a-001")
    second_a = snapshot_with_resource(scope_a, "resource-a-002")
    only_b = snapshot_with_resource(scope_b, "resource-b-001")

    storage_a.save(first_a)
    storage_b.save(only_b)
    storage_a.save(second_a)

    assert tuple(snapshot.id for snapshot in storage_a.load_history()) == (
        first_a.id,
        second_a.id,
    )
    assert tuple(snapshot.id for snapshot in storage_b.load_history()) == (only_b.id,)
    assert storage_a.load_latest().id == second_a.id
    assert storage_b.load_latest().id == only_b.id
    assert len(tuple(path_a.glob("*.json"))) == 2
    assert len(tuple(path_b.glob("*.json"))) == 1


def test_file_storage_does_not_scan_sibling_scope_paths(tmp_path):
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = FileSnapshotStorage(
        str(tmp_path / "scope-a"),
        SnapshotSerializer(),
        discovery_scope=scope_a,
    )
    storage_b = FileSnapshotStorage(
        str(tmp_path / "scope-b"),
        SnapshotSerializer(),
        discovery_scope=scope_b,
    )
    snapshot_a = snapshot_with_resource(scope_a, "resource-a")
    snapshot_b = snapshot_with_resource(scope_b, "resource-b")

    storage_a.save(snapshot_a)
    storage_b.save(snapshot_b)

    history_a = storage_a.load_history()

    assert tuple(snapshot.id for snapshot in history_a) == (snapshot_a.id,)
    assert all(snapshot.discovery_scope == scope_a for snapshot in history_a)


def test_file_storage_reusing_path_with_mismatched_scope_fails(tmp_path):
    path = tmp_path / "shared-scope-path"
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = FileSnapshotStorage(
        str(path),
        SnapshotSerializer(),
        discovery_scope=scope_a,
    )
    storage_b = FileSnapshotStorage(
        str(path),
        SnapshotSerializer(),
        discovery_scope=scope_b,
    )
    storage_a.save(snapshot_with_resource(scope_a, "resource-a"))

    with pytest.raises(SnapshotStorageError, match="discovery scope"):
        storage_b.load_history()


def test_file_storage_assigns_contextual_scope_to_legacy_record(tmp_path):
    file_path = tmp_path / "snapshot.json"
    snapshot_id = Identifier.new()
    file_path.write_text(
        json.dumps(
            {
                "id": str(snapshot_id),
                "resources": [],
            }
        )
    )

    storage = FileSnapshotStorage(
        str(file_path),
        SnapshotSerializer(),
        discovery_scope=DiscoveryScope("legacy-scope"),
    )

    history = storage.load_history()

    assert history[0].id == snapshot_id
    assert history[0].discovery_scope == DiscoveryScope("legacy-scope")


def test_file_storage_logs_save_events(tmp_path, caplog):
    file_path = tmp_path / "snapshots"

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_save_started",
        "backend=file",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "operation=save",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_started",
        "backend=file",
        "operation=save",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_record_write_completed",
        "backend=file",
        "operation=save",
        "phase=record_write",
        "record_name=",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_update_completed",
        "backend=file",
        "operation=save",
        "phase=latest_reference_update",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_completed",
        "backend=file",
        "duration_ms=",
        "operation=save",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_save_completed",
        "backend=file",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "duration_ms=",
        "operation=save",
        "record_name=",
    )
    assert_log_count(messages, "snapshot_storage_save_started", 1)
    assert_log_count(messages, "snapshot_storage_save_completed", 1)
    assert_no_execution_id(messages)


def test_file_storage_save_logs_active_execution_identity(tmp_path, caplog):
    file_path = tmp_path / "snapshots"
    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        storage.save(snapshot)

    messages = [record.message for record in caplog.records]
    record_files = sorted(file_path.glob("*.json"))

    assert_all_storage_logs_have_execution_id(messages, execution.identity)
    assert len(record_files) == 1
    assert execution.identity not in record_files[0].name
    assert execution.identity not in record_files[0].read_text()
    assert execution.identity not in (file_path / "latest").read_text()


def test_file_storage_load_latest_reads_valid_latest_reference(tmp_path):
    file_path = tmp_path / "snapshots"
    file_path.mkdir()
    serializer = SnapshotSerializer()
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    corrupt_record = file_path / "0001.json"
    corrupt_record.write_text("{not-valid-json")
    latest_record = file_path / "0002.json"
    latest_record.write_text(json.dumps(serializer.serialize(second)))
    (file_path / "latest").write_text(latest_record.name)

    storage = FileSnapshotStorage(
        str(file_path), serializer, discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    latest = storage.load_latest()

    assert isinstance(latest, Snapshot)
    assert latest.id == second.id


def test_file_storage_logs_load_latest_fast_path(tmp_path, caplog):
    file_path = tmp_path / "snapshots"
    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.load_latest()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_started",
        "backend=file",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "operation=load_latest",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_hit",
        "backend=file",
        "operation=load_latest",
        "phase=latest_reference",
        "record_name=",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_completed",
        "backend=file",
        "duration_ms=",
        "operation=load_latest",
        "phase=latest_reference",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_completed",
        "backend=file",
        "fallback_used=False",
        "operation=load_latest",
        "phase=latest_reference",
        "record_name=",
    )
    assert_log_count(messages, "snapshot_storage_load_latest_started", 1)
    assert_log_count(messages, "snapshot_storage_load_latest_completed", 1)
    assert_no_execution_id(messages)


def test_file_storage_load_latest_logs_active_execution_identity(tmp_path, caplog):
    file_path = tmp_path / "snapshots"
    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    storage.save(snapshot)
    execution = create_execution()

    caplog.clear()
    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        latest = storage.load_latest()

    messages = [record.message for record in caplog.records]

    assert latest is not None
    assert latest.id == snapshot.id
    assert_all_storage_logs_have_execution_id(messages, execution.identity)


def test_file_storage_loads_snapshot_history_in_save_order(tmp_path):
    file_path = tmp_path / "snapshots"

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(first)
    storage.save(second)

    history = storage.load_history()

    assert history[0].id == first.id
    assert history[1].id == second.id


def test_file_storage_load_latest_falls_back_when_latest_reference_is_missing(
    tmp_path,
):
    file_path = tmp_path / "snapshots"

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(first)
    storage.save(second)
    (file_path / "latest").unlink()

    latest = storage.load_latest()

    assert isinstance(latest, Snapshot)
    assert latest.id == second.id


def test_file_storage_logs_load_latest_fallback_path(tmp_path, caplog):
    file_path = tmp_path / "snapshots"
    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))
    (file_path / "latest").unlink()

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.load_latest()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_started",
        "backend=file",
        "operation=load_latest",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_missing",
        "backend=file",
        "operation=load_latest",
        "phase=latest_reference",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_completed",
        "backend=file",
        "history_count=1",
        "operation=load_latest",
        "phase=history_fallback",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_completed",
        "backend=file",
        "fallback_used=True",
        "history_count=1",
        "operation=load_latest",
        "phase=history_fallback",
    )
    assert_log_count(messages, "snapshot_storage_load_latest_started", 1)
    assert_log_count(messages, "snapshot_storage_load_latest_completed", 1)


def test_file_storage_latest_reference_to_missing_record_fails(tmp_path):
    file_path = tmp_path / "snapshots"
    file_path.mkdir()
    (file_path / "latest").write_text("missing.json")

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    with pytest.raises(
        SnapshotStorageError,
        match="Latest snapshot reference points to missing record",
    ):
        storage.load_latest()


def test_file_storage_logs_latest_reference_failure(tmp_path, caplog):
    file_path = tmp_path / "snapshots"
    file_path.mkdir()
    (file_path / "latest").write_text("missing.json")

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(SnapshotStorageError):
            storage.load_latest()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_failed",
        "backend=file",
        "operation=load_latest",
        "phase=latest_reference",
        "reason=missing_record",
        "record_name=missing.json",
    )


def test_file_storage_latest_reference_to_malformed_record_fails(tmp_path):
    file_path = tmp_path / "snapshots"
    file_path.mkdir()
    record_path = file_path / "0001.json"
    record_path.write_text("{not-valid-json")
    (file_path / "latest").write_text(record_path.name)

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    with pytest.raises(SnapshotStorageError, match="Malformed snapshot history file"):
        storage.load_latest()


def test_file_storage_latest_reference_to_invalid_snapshot_record_fails(tmp_path):
    file_path = tmp_path / "snapshots"
    file_path.mkdir()
    record_path = file_path / "0001.json"
    record_path.write_text('"not-a-snapshot"')
    (file_path / "latest").write_text(record_path.name)

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    with pytest.raises(
        SnapshotStorageError,
        match="Malformed snapshot history record",
    ):
        storage.load_latest()


def test_file_storage_save_writes_record_before_latest_reference(tmp_path, monkeypatch):
    file_path = tmp_path / "snapshots"
    writes: list[str] = []
    original_write_text = Path.write_text

    def tracked_write_text(self, data, *args, **kwargs):
        writes.append(self.name)
        return original_write_text(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", tracked_write_text)

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))

    assert writes[0].endswith(".json")
    assert writes[1] == "latest"


def test_file_storage_saves_each_snapshot_as_distinct_record(tmp_path):
    file_path = tmp_path / "snapshots"

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(snapshot)
    first_records = sorted(file_path.glob("*.json"))
    first_record_content = first_records[0].read_text()

    storage.save(snapshot)
    records = sorted(file_path.glob("*.json"))

    assert len(records) == 2
    assert records[0].read_text() == first_record_content


def test_file_storage_identical_snapshot_content_creates_distinct_records(tmp_path):
    file_path = tmp_path / "snapshots"

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(snapshot)
    storage.save(snapshot)

    records = sorted(file_path.glob("*.json"))

    assert len(records) == 2
    assert records[0].name != records[1].name


def test_file_storage_returns_empty_history_when_file_does_not_exist(tmp_path):
    file_path = tmp_path / "snapshots"

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    assert storage.load_history() == ()


def test_file_storage_logs_load_history(tmp_path, caplog):
    file_path = tmp_path / "snapshots"
    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.load_history()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_history_load_started",
        "backend=file",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "operation=load_history",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_started",
        "backend=file",
        "operation=load_history",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_completed",
        "backend=file",
        "duration_ms=",
        "history_count=1",
        "operation=load_history",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_history_load_completed",
        "backend=file",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "duration_ms=",
        "history_count=1",
        "operation=load_history",
    )
    assert_log_count(messages, "snapshot_storage_history_load_started", 1)
    assert_log_count(messages, "snapshot_storage_history_load_completed", 1)
    assert_no_execution_id(messages)


def test_file_storage_load_history_logs_active_execution_identity(tmp_path, caplog):
    file_path = tmp_path / "snapshots"
    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    storage.save(snapshot)
    execution = create_execution()

    caplog.clear()
    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        history = storage.load_history()

    messages = [record.message for record in caplog.records]

    assert tuple(item.id for item in history) == (snapshot.id,)
    assert_all_storage_logs_have_execution_id(messages, execution.identity)


def test_file_storage_loads_legacy_history_list_file(tmp_path):
    file_path = tmp_path / "snapshot.json"
    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    serializer = SnapshotSerializer()
    file_path.write_text(
        json.dumps(
            [
                serializer.serialize(first),
                serializer.serialize(second),
            ]
        )
    )

    storage = FileSnapshotStorage(
        str(file_path), serializer, discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    history = storage.load_history()

    assert isinstance(history[0], Snapshot)
    assert history[0].id == first.id
    assert history[1].id == second.id


def test_file_storage_loads_legacy_single_snapshot_file(tmp_path):
    file_path = tmp_path / "snapshot.json"
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    serializer = SnapshotSerializer()
    file_path.write_text(json.dumps(serializer.serialize(snapshot)))

    storage = FileSnapshotStorage(
        str(file_path), serializer, discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    history = storage.load_history()

    assert isinstance(history[0], Snapshot)
    assert history[0].id == snapshot.id


def test_file_storage_load_latest_still_supports_legacy_single_snapshot_file(tmp_path):
    file_path = tmp_path / "snapshot.json"
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    serializer = SnapshotSerializer()
    file_path.write_text(json.dumps(serializer.serialize(snapshot)))

    storage = FileSnapshotStorage(
        str(file_path), serializer, discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    latest = storage.load_latest()

    assert isinstance(latest, Snapshot)
    assert latest.id == snapshot.id


def test_file_storage_save_fails_when_path_is_legacy_file(tmp_path):
    file_path = tmp_path / "snapshot.json"
    file_path.write_text("[]")

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    with pytest.raises(
        SnapshotStorageError,
        match="Append-only snapshot storage requires a directory or migration",
    ):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )


def test_file_storage_fails_fast_on_malformed_history(tmp_path):
    file_path = tmp_path / "snapshots"
    file_path.mkdir()
    record_path = file_path / "0001.json"
    record_path.write_text("{not-valid-json")

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    with pytest.raises(SnapshotStorageError, match="Malformed snapshot history file"):
        storage.load_history()


def test_file_storage_fails_fast_on_invalid_history_shape(tmp_path):
    file_path = tmp_path / "snapshots"
    file_path.mkdir()
    record_path = file_path / "0001.json"
    record_path.write_text('"not-a-history"')

    storage = FileSnapshotStorage(
        str(file_path), SnapshotSerializer(), discovery_scope=DEFAULT_DISCOVERY_SCOPE
    )

    with pytest.raises(
        SnapshotStorageError,
        match="Malformed snapshot history record",
    ):
        storage.load_history()

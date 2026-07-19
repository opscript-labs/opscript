from opscript.config import DEFAULT_DISCOVERY_SCOPE
import json
import logging

import pytest
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from opscript.storage import (
    S3SnapshotStorage,
    SnapshotCommittedWithDegradedLatestError,
    SnapshotStorageError,
)
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


class FakeS3:
    def __init__(self, data=None, error_code=None):
        self.objects = {}
        self.put_keys = []
        self.get_keys = []
        self.list_calls = 0
        if data is not None:
            self.objects["snapshot.json"] = data
        self.error_code = error_code

    def put_object(
        self,
        Bucket,
        Key,
        Body,
    ):
        self.put_keys.append(Key)
        self.objects[Key] = Body

    def get_object(
        self,
        Bucket,
        Key,
    ):
        self.get_keys.append(Key)
        if self.error_code is not None:
            raise ClientError(
                {"Error": {"Code": self.error_code, "Message": "S3 error"}},
                "GetObject",
            )
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
                "GetObject",
            )
        return {"Body": FakeBody(self.objects[Key])}

    def list_objects_v2(
        self,
        Bucket,
        Prefix,
    ):
        self.list_calls += 1
        contents = [{"Key": key} for key in self.objects if key.startswith(Prefix)]

        if not contents:
            return {}

        return {"Contents": contents}


def client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": f"{code} error"}},
        "S3Operation",
    )


def record_keys(client: FakeS3) -> list[str]:
    return sorted(key for key in client.objects if key.endswith(".json"))


def latest_reference_key() -> str:
    return "snapshot.json/latest"


def scoped_latest_reference_key(namespace: str) -> str:
    return f"{namespace}/latest"


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


class FailingS3(FakeS3):
    def __init__(
        self,
        list_error=None,
        get_error=None,
        put_error=None,
    ):
        super().__init__()
        self.list_error = list_error
        self.get_error = get_error
        self.put_error = put_error
        self.put_calls = 0

    def put_object(
        self,
        Bucket,
        Key,
        Body,
    ):
        self.put_calls += 1
        if self.put_error is not None:
            raise self.put_error
        super().put_object(Bucket=Bucket, Key=Key, Body=Body)

    def get_object(
        self,
        Bucket,
        Key,
    ):
        if self.get_error is not None:
            raise self.get_error
        return super().get_object(Bucket=Bucket, Key=Key)

    def list_objects_v2(
        self,
        Bucket,
        Prefix,
    ):
        if self.list_error is not None:
            raise self.list_error
        return super().list_objects_v2(Bucket=Bucket, Prefix=Prefix)


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(
        self,
        Bucket,
        Prefix,
    ):
        return self.pages


class FakePaginatedS3(FakeS3):
    def __init__(self, pages):
        super().__init__()
        self.pages = pages

    def get_paginator(self, operation_name):
        assert operation_name == "list_objects_v2"
        return FakePaginator(self.pages)


class FakeBody:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


def test_s3_storage_saves_snapshot():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(snapshot)

    loaded = storage.load_latest()

    assert isinstance(loaded, Snapshot)
    assert loaded.id == snapshot.id
    assert loaded.discovery_scope == DEFAULT_DISCOVERY_SCOPE


def test_s3_storage_rejects_mismatched_scope_save():
    storage = S3SnapshotStorage(
        FakeS3(),
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DiscoveryScope("scope-001"),
    )
    snapshot = Snapshot(
        discovery_scope=DiscoveryScope("scope-002"),
        id=Identifier.new(),
    )

    with pytest.raises(SnapshotStorageError, match="discovery scope"):
        storage.save(snapshot)


def test_s3_storage_assigns_contextual_scope_to_legacy_record():
    snapshot_id = Identifier.new()
    client = FakeS3(
        data=json.dumps(
            {
                "id": str(snapshot_id),
                "resources": [],
            }
        )
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DiscoveryScope("legacy-scope"),
    )

    history = storage.load_history()

    assert history[0].id == snapshot_id
    assert history[0].discovery_scope == DiscoveryScope("legacy-scope")


def test_s3_storage_rejects_mixed_scope_records():
    serializer = SnapshotSerializer()
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(
        serializer.serialize(
            Snapshot(
                discovery_scope=DiscoveryScope("scope-001"),
                id=Identifier.new(),
            )
        )
    )
    client.objects["snapshot.json/0002.json"] = json.dumps(
        serializer.serialize(
            Snapshot(
                discovery_scope=DiscoveryScope("scope-002"),
                id=Identifier.new(),
            )
        )
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DiscoveryScope("scope-001"),
    )

    with pytest.raises(SnapshotStorageError, match="discovery scope"):
        storage.load_history()


def test_s3_storage_isolates_histories_latest_and_append_only_records_by_namespace():
    client = FakeS3()
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    namespace_a = "root/discovery-scopes/scope-a"
    namespace_b = "root/discovery-scopes/scope-b"
    storage_a = S3SnapshotStorage(
        client,
        "bucket",
        namespace_a,
        SnapshotSerializer(),
        discovery_scope=scope_a,
    )
    storage_b = S3SnapshotStorage(
        client,
        "bucket",
        namespace_b,
        SnapshotSerializer(),
        discovery_scope=scope_b,
    )
    first_a = snapshot_with_resource(scope_a, "resource-a-001")
    only_b = snapshot_with_resource(scope_b, "resource-b-001")
    second_a = snapshot_with_resource(scope_a, "resource-a-002")

    storage_a.save(first_a)
    storage_b.save(only_b)
    storage_a.save(second_a)

    history_a = storage_a.load_history()
    history_b = storage_b.load_history()
    latest_a = storage_a.load_latest()
    latest_b = storage_b.load_latest()
    records_a = [
        key for key in record_keys(client) if key.startswith(f"{namespace_a}/")
    ]
    records_b = [
        key for key in record_keys(client) if key.startswith(f"{namespace_b}/")
    ]

    assert tuple(snapshot.id for snapshot in history_a) == (first_a.id, second_a.id)
    assert tuple(snapshot.id for snapshot in history_b) == (only_b.id,)
    assert latest_a.id == second_a.id
    assert latest_b.id == only_b.id
    assert len(records_a) == 2
    assert len(records_b) == 1
    assert client.objects[scoped_latest_reference_key(namespace_a)] in records_a
    assert client.objects[scoped_latest_reference_key(namespace_b)] in records_b
    assert client.objects[scoped_latest_reference_key(namespace_a)] not in records_b
    assert client.objects[scoped_latest_reference_key(namespace_b)] not in records_a
    assert all(key.startswith(f"{namespace_a}/") for key in records_a)
    assert all(key.startswith(f"{namespace_b}/") for key in records_b)


def test_s3_storage_prefix_listing_does_not_enumerate_sibling_scope_records():
    client = FakeS3()
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    namespace_a = "root/discovery-scopes/scope-a"
    namespace_b = "root/discovery-scopes/scope-b"
    storage_a = S3SnapshotStorage(
        client,
        "bucket",
        namespace_a,
        SnapshotSerializer(),
        discovery_scope=scope_a,
    )
    storage_b = S3SnapshotStorage(
        client,
        "bucket",
        namespace_b,
        SnapshotSerializer(),
        discovery_scope=scope_b,
    )
    snapshot_a = snapshot_with_resource(scope_a, "resource-a")
    snapshot_b = snapshot_with_resource(scope_b, "resource-b")

    storage_a.save(snapshot_a)
    storage_b.save(snapshot_b)

    listed_for_a = storage_a._list_record_keys()

    assert listed_for_a == [
        key for key in record_keys(client) if key.startswith(f"{namespace_a}/")
    ]
    assert all(namespace_b not in key for key in listed_for_a)


def test_s3_storage_parent_load_history_ignores_nested_scope_records():
    serializer = SnapshotSerializer()
    client = FakeS3()
    parent_scope = DEFAULT_DISCOVERY_SCOPE
    nested_scope = DiscoveryScope("scope-a")
    parent_first = Snapshot(discovery_scope=parent_scope, id=Identifier.new())
    parent_second = Snapshot(discovery_scope=parent_scope, id=Identifier.new())
    nested = Snapshot(discovery_scope=nested_scope, id=Identifier.new())
    client.objects["root/0001.json"] = json.dumps(serializer.serialize(parent_first))
    client.objects["root/0002.json"] = json.dumps(serializer.serialize(parent_second))
    client.objects["root/latest"] = "root/0002.json"
    client.objects["root/discovery-scopes/scope-a/0003.json"] = json.dumps(
        serializer.serialize(nested)
    )
    client.objects["root/discovery-scopes/scope-a/latest"] = (
        "root/discovery-scopes/scope-a/0003.json"
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "root",
        serializer,
        discovery_scope=parent_scope,
    )

    history = storage.load_history()

    assert tuple(snapshot.id for snapshot in history) == (
        parent_first.id,
        parent_second.id,
    )
    assert "root/discovery-scopes/scope-a/0003.json" not in client.get_keys


def test_s3_storage_custom_scope_load_history_ignores_nested_descendants():
    serializer = SnapshotSerializer()
    client = FakeS3()
    scope = DiscoveryScope("scope-a")
    direct = Snapshot(discovery_scope=scope, id=Identifier.new())
    client.objects["root/discovery-scopes/scope-a/0001.json"] = json.dumps(
        serializer.serialize(direct)
    )
    client.objects["root/discovery-scopes/scope-a/nested/0002.json"] = "{not-json"
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "root/discovery-scopes/scope-a",
        serializer,
        discovery_scope=scope,
    )

    history = storage.load_history()

    assert tuple(snapshot.id for snapshot in history) == (direct.id,)
    assert "root/discovery-scopes/scope-a/nested/0002.json" not in client.get_keys


def test_s3_storage_parent_and_custom_latest_references_are_isolated():
    serializer = SnapshotSerializer()
    client = FakeS3()
    parent_scope = DEFAULT_DISCOVERY_SCOPE
    nested_scope = DiscoveryScope("scope-a")
    parent = Snapshot(discovery_scope=parent_scope, id=Identifier.new())
    nested = Snapshot(discovery_scope=nested_scope, id=Identifier.new())
    client.objects["root/0001.json"] = json.dumps(serializer.serialize(parent))
    client.objects["root/latest"] = "root/0001.json"
    client.objects["root/discovery-scopes/scope-a/0001.json"] = json.dumps(
        serializer.serialize(nested)
    )
    client.objects["root/discovery-scopes/scope-a/latest"] = (
        "root/discovery-scopes/scope-a/0001.json"
    )
    parent_storage = S3SnapshotStorage(
        client,
        "bucket",
        "root",
        serializer,
        discovery_scope=parent_scope,
    )
    nested_storage = S3SnapshotStorage(
        client,
        "bucket",
        "root/discovery-scopes/scope-a",
        serializer,
        discovery_scope=nested_scope,
    )

    parent_latest = parent_storage.load_latest()
    nested_latest = nested_storage.load_latest()

    assert parent_latest.id == parent.id
    assert nested_latest.id == nested.id


def test_s3_storage_parent_latest_reference_to_nested_record_falls_back():
    serializer = SnapshotSerializer()
    client = FakeS3()
    parent = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    nested = Snapshot(discovery_scope=DiscoveryScope("scope-a"), id=Identifier.new())
    client.objects["root/0001.json"] = json.dumps(serializer.serialize(parent))
    client.objects["root/discovery-scopes/scope-a/0001.json"] = json.dumps(
        serializer.serialize(nested)
    )
    client.objects["root/latest"] = "root/discovery-scopes/scope-a/0001.json"
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "root",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    latest = storage.load_latest()

    assert latest.id == parent.id
    assert client.objects["root/latest"] == "root/discovery-scopes/scope-a/0001.json"


def test_s3_storage_parent_latest_fallback_ignores_nested_records():
    serializer = SnapshotSerializer()
    client = FakeS3()
    nested = Snapshot(discovery_scope=DiscoveryScope("scope-a"), id=Identifier.new())
    client.objects["root/discovery-scopes/scope-a/0001.json"] = json.dumps(
        serializer.serialize(nested)
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "root",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    assert storage.load_latest() is None
    assert "root/discovery-scopes/scope-a/0001.json" not in client.get_keys


def test_s3_storage_nested_foreign_scope_record_is_ignored_but_direct_foreign_fails():
    serializer = SnapshotSerializer()
    client = FakeS3()
    parent = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    direct_foreign = Snapshot(
        discovery_scope=DiscoveryScope("scope-b"), id=Identifier.new()
    )
    nested_foreign = Snapshot(
        discovery_scope=DiscoveryScope("scope-a"), id=Identifier.new()
    )
    client.objects["root/0001.json"] = json.dumps(serializer.serialize(parent))
    client.objects["root/discovery-scopes/scope-a/0002.json"] = json.dumps(
        serializer.serialize(nested_foreign)
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "root",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    assert tuple(snapshot.id for snapshot in storage.load_history()) == (parent.id,)

    client.objects["root/0003.json"] = json.dumps(serializer.serialize(direct_foreign))

    with pytest.raises(SnapshotStorageError, match="discovery scope"):
        storage.load_history()


def test_s3_storage_parent_namespace_with_only_nested_histories_is_empty():
    serializer = SnapshotSerializer()
    client = FakeS3()
    nested = Snapshot(discovery_scope=DiscoveryScope("scope-a"), id=Identifier.new())
    client.objects["root/discovery-scopes/scope-a/0001.json"] = json.dumps(
        serializer.serialize(nested)
    )
    client.objects["root/discovery-scopes/scope-a/latest"] = (
        "root/discovery-scopes/scope-a/0001.json"
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "root",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    assert storage.load_history() == ()


def test_s3_storage_direct_legacy_object_is_preserved_while_nested_legacy_is_ignored():
    serializer = SnapshotSerializer()
    client = FakeS3()
    parent = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    nested = Snapshot(discovery_scope=DiscoveryScope("scope-a"), id=Identifier.new())
    client.objects["root"] = json.dumps(serializer.serialize(parent))
    client.objects["root/discovery-scopes/scope-a"] = json.dumps(
        serializer.serialize(nested)
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "root",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    history = storage.load_history()

    assert tuple(snapshot.id for snapshot in history) == (parent.id,)
    assert "root/discovery-scopes/scope-a" not in client.get_keys


def test_s3_storage_nested_legacy_object_is_ignored_without_parent_legacy():
    serializer = SnapshotSerializer()
    client = FakeS3()
    nested = Snapshot(discovery_scope=DiscoveryScope("scope-a"), id=Identifier.new())
    client.objects["root/discovery-scopes/scope-a"] = json.dumps(
        serializer.serialize(nested)
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "root",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    assert storage.load_history() == ()


def test_s3_storage_runtime_v1_parent_history_ignores_nested_custom_scope_history():
    serializer = SnapshotSerializer()
    client = FakeS3()
    parent_scope = DEFAULT_DISCOVERY_SCOPE
    custom_scope = DiscoveryScope("scope-a")
    parent = Snapshot(discovery_scope=parent_scope, id=Identifier.new())
    custom = Snapshot(discovery_scope=custom_scope, id=Identifier.new())
    client.objects["environments/prod/snapshots/0001.json"] = json.dumps(
        serializer.serialize(parent)
    )
    client.objects["environments/prod/snapshots/latest"] = (
        "environments/prod/snapshots/0001.json"
    )
    client.objects["environments/prod/snapshots/discovery-scopes/scope-a/0001.json"] = (
        json.dumps(serializer.serialize(custom))
    )
    client.objects["environments/prod/snapshots/discovery-scopes/scope-a/latest"] = (
        "environments/prod/snapshots/discovery-scopes/scope-a/0001.json"
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "environments/prod/snapshots",
        serializer,
        discovery_scope=parent_scope,
    )

    history = storage.load_history()

    assert tuple(snapshot.id for snapshot in history) == (parent.id,)


def test_s3_storage_custom_scope_history_ignores_parent_and_sibling_histories():
    serializer = SnapshotSerializer()
    client = FakeS3()
    parent_scope = DEFAULT_DISCOVERY_SCOPE
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    parent = Snapshot(discovery_scope=parent_scope, id=Identifier.new())
    custom_a = Snapshot(discovery_scope=scope_a, id=Identifier.new())
    custom_b = Snapshot(discovery_scope=scope_b, id=Identifier.new())
    client.objects["environments/prod/snapshots/0001.json"] = json.dumps(
        serializer.serialize(parent)
    )
    client.objects["environments/prod/snapshots/discovery-scopes/scope-a/0001.json"] = (
        json.dumps(serializer.serialize(custom_a))
    )
    client.objects["environments/prod/snapshots/discovery-scopes/scope-b/0001.json"] = (
        json.dumps(serializer.serialize(custom_b))
    )
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "environments/prod/snapshots/discovery-scopes/scope-a",
        serializer,
        discovery_scope=scope_a,
    )

    history = storage.load_history()

    assert tuple(snapshot.id for snapshot in history) == (custom_a.id,)


def test_s3_storage_reusing_namespace_with_mismatched_scope_fails():
    client = FakeS3()
    namespace = "root/shared-scope"
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    storage_a = S3SnapshotStorage(
        client,
        "bucket",
        namespace,
        SnapshotSerializer(),
        discovery_scope=scope_a,
    )
    storage_b = S3SnapshotStorage(
        client,
        "bucket",
        namespace,
        SnapshotSerializer(),
        discovery_scope=scope_b,
    )
    storage_a.save(snapshot_with_resource(scope_a, "resource-a"))

    with pytest.raises(SnapshotStorageError, match="discovery scope"):
        storage_b.load_history()


def test_s3_storage_logs_save_events(caplog):
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_save_started",
        "backend=s3",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "operation=save",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_started",
        "backend=s3",
        "bucket=bucket",
        "key=snapshot.json",
        "operation=save",
        "prefix=snapshot.json/",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_record_write_completed",
        "backend=s3",
        "operation=save",
        "phase=record_write",
        "record_key=",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_update_completed",
        "backend=s3",
        "operation=save",
        "phase=latest_reference_update",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_completed",
        "backend=s3",
        "duration_ms=",
        "operation=save",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_save_completed",
        "backend=s3",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "duration_ms=",
        "operation=save",
        "record_key=",
    )
    assert_log_count(messages, "snapshot_storage_save_started", 1)
    assert_log_count(messages, "snapshot_storage_save_completed", 1)
    assert_no_execution_id(messages)


def test_s3_storage_save_logs_active_execution_identity(caplog):
    client = FakeS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        storage.save(snapshot)

    messages = [record.message for record in caplog.records]

    assert_all_storage_logs_have_execution_id(messages, execution.identity)
    assert all(execution.identity not in key for key in client.objects)
    assert all(execution.identity not in str(body) for body in client.objects.values())


def test_s3_storage_loads_snapshot_history_in_save_order():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(first)
    storage.save(second)

    history = storage.load_history()

    assert history[0].id == first.id
    assert history[1].id == second.id


def test_s3_storage_load_latest_reads_valid_latest_reference():
    serializer = SnapshotSerializer()
    latest = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = "{not-valid-json"
    client.objects["snapshot.json/0002.json"] = json.dumps(serializer.serialize(latest))
    client.objects[latest_reference_key()] = "snapshot.json/0002.json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    loaded = storage.load_latest()

    assert isinstance(loaded, Snapshot)
    assert loaded.id == latest.id
    assert client.list_calls == 0


def test_s3_storage_load_latest_decodes_bytes_latest_reference():
    serializer = SnapshotSerializer()
    latest = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(latest))
    client.objects[latest_reference_key()] = b"snapshot.json/0001.json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    loaded = storage.load_latest()

    assert isinstance(loaded, Snapshot)
    assert loaded.id == latest.id


def test_s3_storage_logs_load_latest_fast_path(caplog):
    client = FakeS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.load_latest()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_started",
        "backend=s3",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "operation=load_latest",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_hit",
        "backend=s3",
        "operation=load_latest",
        "phase=latest_reference",
        "record_key=",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_completed",
        "backend=s3",
        "duration_ms=",
        "operation=load_latest",
        "phase=latest_reference",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_completed",
        "backend=s3",
        "fallback_used=False",
        "operation=load_latest",
        "phase=latest_reference",
        "record_key=",
    )
    assert_log_count(messages, "snapshot_storage_load_latest_started", 1)
    assert_log_count(messages, "snapshot_storage_load_latest_completed", 1)
    assert_no_execution_id(messages)


def test_s3_storage_load_latest_logs_active_execution_identity(caplog):
    client = FakeS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
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


def test_s3_storage_load_latest_falls_back_when_latest_reference_is_missing():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(first)
    storage.save(second)
    del client.objects[latest_reference_key()]

    latest = storage.load_latest()

    assert isinstance(latest, Snapshot)
    assert latest.id == second.id


def test_s3_storage_load_latest_missing_reference_with_no_history_returns_none():
    client = FakeS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    latest = storage.load_latest()

    assert latest is None


def test_s3_storage_load_latest_empty_reference_falls_back_to_history():
    serializer = SnapshotSerializer()
    latest = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(latest))
    client.objects[latest_reference_key()] = ""
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    loaded = storage.load_latest()

    assert loaded.id == latest.id
    assert client.objects[latest_reference_key()] == ""


def test_s3_storage_load_latest_malformed_reference_falls_back_to_history():
    serializer = SnapshotSerializer()
    latest = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(latest))
    client.objects[latest_reference_key()] = "not-a-record-key"
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    loaded = storage.load_latest()

    assert loaded.id == latest.id
    assert client.objects[latest_reference_key()] == "not-a-record-key"


def test_s3_storage_load_latest_invalid_text_reference_falls_back_to_history():
    serializer = SnapshotSerializer()
    latest = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(latest))
    client.objects[latest_reference_key()] = b"\xff"
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    loaded = storage.load_latest()

    assert loaded.id == latest.id
    assert client.objects[latest_reference_key()] == b"\xff"


def test_s3_storage_load_latest_outside_reference_falls_back_to_history():
    serializer = SnapshotSerializer()
    latest = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(latest))
    client.objects["other/0002.json"] = json.dumps(
        serializer.serialize(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )
    )
    client.objects[latest_reference_key()] = "other/0002.json"
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    loaded = storage.load_latest()

    assert loaded.id == latest.id
    assert client.objects[latest_reference_key()] == "other/0002.json"


def test_s3_storage_load_latest_fallback_returns_newest_record_by_key_order():
    serializer = SnapshotSerializer()
    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0002.json"] = json.dumps(serializer.serialize(second))
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(first))
    client.objects[latest_reference_key()] = ""
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    latest = storage.load_latest()

    assert latest.id == second.id


def test_s3_storage_load_latest_fallback_is_read_only():
    serializer = SnapshotSerializer()
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(
        serializer.serialize(snapshot)
    )
    client.objects[latest_reference_key()] = ""
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    before_objects = dict(client.objects)
    latest = storage.load_latest()

    assert latest.id == snapshot.id
    assert client.objects == before_objects
    assert client.put_keys == []


def test_s3_storage_stale_but_valid_latest_returns_fast_path_without_history_listing():
    serializer = SnapshotSerializer()
    older = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    newer = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(older))
    client.objects["snapshot.json/0002.json"] = json.dumps(serializer.serialize(newer))
    client.objects[latest_reference_key()] = "snapshot.json/0001.json"
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    latest = storage.load_latest()

    assert latest.id == older.id
    assert client.list_calls == 0


def test_s3_storage_load_latest_normalizes_latest_reference_client_error(caplog):
    client = FailingS3(get_error=client_error("NoSuchBucket"))

    storage = S3SnapshotStorage(
        client,
        "missing-bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(
            SnapshotStorageError,
            match="Failed to load latest snapshot reference",
        ):
            storage.load_latest()

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_failed",
        "operation=load_latest",
        "phase=latest_reference_read",
        "reason=snapshot_storage_error",
    )


def test_s3_storage_load_latest_fallback_history_list_access_denied_raises():
    client = FailingS3(list_error=client_error("AccessDenied"))
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(SnapshotStorageError, match="Failed to list S3 snapshot"):
        storage.load_latest()


def test_s3_storage_logs_load_latest_fallback_path(caplog):
    client = FakeS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))
    del client.objects[latest_reference_key()]

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.load_latest()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_started",
        "backend=s3",
        "operation=load_latest",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_missing",
        "backend=s3",
        "operation=load_latest",
        "phase=latest_reference",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_completed",
        "backend=s3",
        "history_count=1",
        "operation=load_latest",
        "phase=history_fallback",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_completed",
        "backend=s3",
        "fallback_used=True",
        "history_count=1",
        "latest_reference_state=missing",
        "operation=load_latest",
        "phase=history_fallback",
    )
    assert_log_count(messages, "snapshot_storage_load_latest_started", 1)
    assert_log_count(messages, "snapshot_storage_load_latest_completed", 1)


def test_s3_storage_latest_reference_to_missing_record_falls_back_to_history():
    serializer = SnapshotSerializer()
    latest = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(latest))
    client.objects[latest_reference_key()] = "snapshot.json/missing.json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    loaded = storage.load_latest()

    assert loaded.id == latest.id
    assert client.objects[latest_reference_key()] == "snapshot.json/missing.json"


def test_s3_storage_latest_reference_missing_target_with_no_history_returns_none():
    client = FakeS3()
    client.objects[latest_reference_key()] = "snapshot.json/missing.json"
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    assert storage.load_latest() is None


def test_s3_storage_latest_reference_to_unreadable_record_fails(caplog):
    class LatestRecordAccessDeniedS3(FakeS3):
        def get_object(
            self,
            Bucket,
            Key,
        ):
            if Key == "snapshot.json/0002.json":
                raise client_error("AccessDenied")
            return super().get_object(Bucket=Bucket, Key=Key)

    serializer = SnapshotSerializer()
    older = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = LatestRecordAccessDeniedS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(older))
    client.objects["snapshot.json/0002.json"] = json.dumps(
        serializer.serialize(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )
    )
    client.objects[latest_reference_key()] = "snapshot.json/0002.json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(SnapshotStorageError, match="snapshot.json/0002.json"):
            storage.load_latest()

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_failed",
        "operation=load_latest",
        "phase=record_read",
        "record_key=snapshot.json/0002.json",
        "reason=snapshot_storage_error",
    )


def test_s3_storage_logs_latest_reference_fallback_for_missing_target(caplog):
    serializer = SnapshotSerializer()
    latest = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(latest))
    client.objects[latest_reference_key()] = "snapshot.json/missing.json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.load_latest()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_failed",
        "backend=s3",
        "operation=load_latest",
        "phase=latest_reference",
        "reason=missing_record",
        "record_key=snapshot.json/missing.json",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_fallback_started",
        "fallback_used=True",
        "latest_reference_state=missing_target",
        "phase=history_fallback",
        "record_key=snapshot.json/missing.json",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_load_latest_completed",
        "fallback_used=True",
        "latest_reference_state=missing_target",
        "phase=history_fallback",
    )
    assert_log_count(messages, "snapshot_storage_load_latest_completed", 1)


def test_s3_storage_latest_reference_to_malformed_record_fails():
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = "{not-valid-json"
    client.objects[latest_reference_key()] = "snapshot.json/0001.json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(SnapshotStorageError, match="Malformed snapshot history object"):
        storage.load_latest()


def test_s3_storage_fallback_preserves_malformed_authoritative_history_failure():
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = "{not-valid-json"
    client.objects[latest_reference_key()] = ""
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(SnapshotStorageError, match="Malformed snapshot history object"):
        storage.load_latest()


def test_s3_storage_latest_reference_to_invalid_snapshot_record_fails():
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = '"not-a-snapshot"'
    client.objects[latest_reference_key()] = "snapshot.json/0001.json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(
        SnapshotStorageError,
        match="Malformed snapshot history record",
    ):
        storage.load_latest()


def test_s3_storage_returns_empty_history_when_no_snapshots_exist():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    assert storage.load_history() == ()


def test_s3_storage_logs_load_history(caplog):
    client = FakeS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="opscript"):
        storage.load_history()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=snapshot_storage_history_load_started",
        "backend=s3",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "operation=load_history",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_started",
        "backend=s3",
        "operation=load_history",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_completed",
        "backend=s3",
        "duration_ms=",
        "history_count=1",
        "operation=load_history",
    )
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_history_load_completed",
        "backend=s3",
        f"discovery_scope={DEFAULT_DISCOVERY_SCOPE}",
        "duration_ms=",
        "history_count=1",
        "operation=load_history",
    )
    assert_log_count(messages, "snapshot_storage_history_load_started", 1)
    assert_log_count(messages, "snapshot_storage_history_load_completed", 1)
    assert_no_execution_id(messages)


def test_s3_storage_load_history_logs_active_execution_identity(caplog):
    client = FakeS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
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


def test_s3_storage_saves_snapshot_when_object_does_not_exist():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(snapshot)

    loaded = storage.load_latest()

    assert isinstance(loaded, Snapshot)
    assert loaded.id == snapshot.id


def test_s3_storage_save_writes_serialized_history():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(snapshot)

    records = record_keys(client)
    data = json.loads(client.objects[records[0]])

    assert len(records) == 1
    assert records[0].startswith("snapshot.json/")
    assert data["id"] == str(snapshot.id)
    assert client.objects[latest_reference_key()] == records[0]


def test_s3_storage_save_writes_record_before_latest_reference():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))

    assert client.put_keys[0].endswith(".json")
    assert client.put_keys[1] == latest_reference_key()


def test_s3_storage_repeated_saves_create_distinct_record_objects():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(first)
    storage.save(second)

    records = record_keys(client)

    assert len(records) == 2
    assert all(key.startswith("snapshot.json/") for key in records)
    assert client.objects[latest_reference_key()] == records[-1]


def test_s3_storage_does_not_rewrite_existing_record_objects():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))
    first_key = record_keys(client)[0]
    first_content = client.objects[first_key]

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))

    assert client.objects[first_key] == first_content


def test_s3_storage_orders_history_by_record_key():
    serializer = SnapshotSerializer()
    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3()
    client.objects["snapshot.json/0002.json"] = json.dumps(serializer.serialize(second))
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(first))

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    history = storage.load_history()

    assert history[0].id == first.id
    assert history[1].id == second.id


def test_s3_storage_loads_record_keys_across_multiple_pages():
    serializer = SnapshotSerializer()
    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakePaginatedS3(
        (
            {"Contents": [{"Key": "snapshot.json/0002.json"}]},
            {"Contents": [{"Key": "snapshot.json/0001.json"}]},
        )
    )
    client.objects["snapshot.json/0001.json"] = json.dumps(serializer.serialize(first))
    client.objects["snapshot.json/0002.json"] = json.dumps(serializer.serialize(second))

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    history = storage.load_history()

    assert history[0].id == first.id
    assert history[1].id == second.id


def test_s3_storage_identical_snapshot_content_creates_distinct_records():
    client = FakeS3()

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())

    storage.save(snapshot)
    storage.save(snapshot)

    records = record_keys(client)

    assert len(records) == 2
    assert records[0] != records[1]


def test_s3_storage_normalizes_legacy_read_access_denied(caplog):
    client = FakeS3(error_code="AccessDenied")

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(SnapshotStorageError, match="AccessDenied"):
            storage.load_history()

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_failed",
        "operation=load_history",
        "phase=legacy_read",
        "reason=snapshot_storage_error",
    )


@pytest.mark.parametrize(
    "error",
    (
        client_error("AccessDenied"),
        client_error("Throttling"),
        client_error("ThrottlingException"),
        client_error("UnexpectedClientError"),
        BotoCoreError(error="network unavailable"),
        EndpointConnectionError(endpoint_url="https://s3.example.com"),
        ConnectTimeoutError(endpoint_url="https://s3.example.com"),
        ReadTimeoutError(endpoint_url="https://s3.example.com"),
    ),
)
def test_s3_storage_normalizes_list_objects_failures(error, caplog):
    client = FailingS3(list_error=error)

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(SnapshotStorageError) as error_info:
            storage.load_history()

    if isinstance(error, ClientError):
        assert error.response["Error"]["Code"] in str(error_info.value)

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_failed",
        "operation=load_history",
        "phase=record_discovery",
        "reason=snapshot_storage_error",
    )


@pytest.mark.parametrize(
    "error",
    (
        client_error("AccessDenied"),
        client_error("Throttling"),
        client_error("ThrottlingException"),
        client_error("UnexpectedClientError"),
        BotoCoreError(error="network unavailable"),
        EndpointConnectionError(endpoint_url="https://s3.example.com"),
        ConnectTimeoutError(endpoint_url="https://s3.example.com"),
        ReadTimeoutError(endpoint_url="https://s3.example.com"),
    ),
)
def test_s3_storage_normalizes_append_only_get_object_failures(error, caplog):
    serializer = SnapshotSerializer()
    client = FailingS3(get_error=error)
    client.objects["snapshot.json/0001.json"] = json.dumps(
        serializer.serialize(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )
    )

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(
            SnapshotStorageError,
            match="snapshot.json/0001.json",
        ) as error_info:
            storage.load_history()

    if isinstance(error, ClientError):
        assert error.response["Error"]["Code"] in str(error_info.value)

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_failed",
        "operation=load_history",
        "phase=record_read",
        "record_key=snapshot.json/0001.json",
        "reason=snapshot_storage_error",
    )


@pytest.mark.parametrize(
    "error",
    (
        client_error("AccessDenied"),
        client_error("Throttling"),
        client_error("ThrottlingException"),
        client_error("UnexpectedClientError"),
        EndpointConnectionError(endpoint_url="https://s3.example.com"),
        ConnectTimeoutError(endpoint_url="https://s3.example.com"),
        ReadTimeoutError(endpoint_url="https://s3.example.com"),
    ),
)
def test_s3_storage_propagates_put_object_failures_without_partial_record(error):
    client = FailingS3(put_error=error)

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(SnapshotStorageError):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )

    assert client.objects == {}
    assert latest_reference_key() not in client.objects


@pytest.mark.parametrize(
    "error",
    (
        client_error("AccessDenied"),
        client_error("Throttling"),
        client_error("ThrottlingException"),
        client_error("UnexpectedClientError"),
        EndpointConnectionError(endpoint_url="https://s3.example.com"),
        ConnectTimeoutError(endpoint_url="https://s3.example.com"),
        ReadTimeoutError(endpoint_url="https://s3.example.com"),
    ),
)
def test_s3_storage_save_stops_before_write_when_list_fails(error):
    client = FailingS3(list_error=error)

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(SnapshotStorageError):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )

    assert client.objects == {}
    assert client.put_calls == 0


@pytest.mark.parametrize(
    "error",
    (
        client_error("AccessDenied"),
        client_error("Throttling"),
        client_error("ThrottlingException"),
        client_error("UnexpectedClientError"),
        EndpointConnectionError(endpoint_url="https://s3.example.com"),
        ConnectTimeoutError(endpoint_url="https://s3.example.com"),
        ReadTimeoutError(endpoint_url="https://s3.example.com"),
    ),
)
def test_s3_storage_save_stops_before_write_when_legacy_get_fails(error):
    client = FailingS3(get_error=error)

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(SnapshotStorageError):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )

    assert client.objects == {}
    assert client.put_calls == 0


def test_s3_storage_treats_legacy_nosuchkey_as_empty_history_only():
    client = FailingS3(get_error=client_error("NoSuchKey"))

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    assert storage.load_history() == ()


def test_s3_storage_save_writes_after_legacy_nosuchkey():
    client = FailingS3(get_error=client_error("NoSuchKey"))

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))

    assert len(record_keys(client)) == 1


def test_s3_storage_fails_fast_on_malformed_history():
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = "{not-valid-json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(SnapshotStorageError, match="Malformed snapshot history object"):
        storage.load_history()


def test_s3_storage_fails_fast_on_invalid_history_shape():
    client = FakeS3()
    client.objects["snapshot.json/0001.json"] = '"not-a-history"'

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(
        SnapshotStorageError,
        match="Malformed snapshot history record",
    ):
        storage.load_history()


def test_s3_storage_loads_legacy_history_list_when_no_records_exist():
    serializer = SnapshotSerializer()
    first = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    second = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3(
        data=json.dumps(
            [
                serializer.serialize(first),
                serializer.serialize(second),
            ]
        )
    )

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    history = storage.load_history()

    assert history[0].id == first.id
    assert history[1].id == second.id


def test_s3_storage_loads_legacy_single_snapshot_when_no_records_exist():
    serializer = SnapshotSerializer()
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3(data=json.dumps(serializer.serialize(snapshot)))

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    history = storage.load_history()

    assert history[0].id == snapshot.id


def test_s3_storage_save_fails_when_only_legacy_object_exists():
    client = FakeS3(data="[]")

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    with pytest.raises(
        SnapshotStorageError,
        match="requires explicit migration",
    ):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )


def test_s3_storage_reads_append_only_records_when_legacy_object_also_exists():
    serializer = SnapshotSerializer()
    legacy = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    current = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3(data=json.dumps([serializer.serialize(legacy)]))
    client.objects["snapshot.json/0001.json"] = json.dumps(
        serializer.serialize(current)
    )

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    history = storage.load_history()

    assert len(history) == 1
    assert history[0].id == current.id


def test_s3_storage_load_latest_uses_append_only_latest_when_legacy_object_exists():
    serializer = SnapshotSerializer()
    legacy = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    current = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FakeS3(data=json.dumps([serializer.serialize(legacy)]))
    client.objects["snapshot.json/0001.json"] = json.dumps(
        serializer.serialize(current)
    )
    client.objects[latest_reference_key()] = "snapshot.json/0001.json"

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    latest = storage.load_latest()

    assert isinstance(latest, Snapshot)
    assert latest.id == current.id


def test_s3_storage_save_record_put_access_denied():
    client = FailingS3(put_error=client_error("AccessDenied"))
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    with pytest.raises(SnapshotStorageError, match="AccessDenied"):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )
    assert client.put_calls == 1
    assert client.objects == {}


def test_s3_storage_save_record_put_no_such_bucket():
    client = FailingS3(put_error=client_error("NoSuchBucket"))
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    with pytest.raises(SnapshotStorageError, match="NoSuchBucket"):
        storage.save(
            Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
        )
    assert client.put_calls == 1
    assert client.objects == {}


def test_s3_storage_save_latest_reference_put_access_denied_commits_record():
    class PartialFailingS3(FakeS3):
        def __init__(self):
            super().__init__()
            self.put_calls = 0

        def put_object(self, Bucket, Key, Body):
            self.put_calls += 1
            if self.put_calls == 2:
                raise client_error("AccessDenied")
            super().put_object(Bucket=Bucket, Key=Key, Body=Body)

    client = PartialFailingS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    with pytest.raises(
        SnapshotCommittedWithDegradedLatestError,
        match="Snapshot record committed",
    ) as exc_info:
        storage.save(snapshot)

    records = record_keys(client)
    assert len(records) == 1
    assert latest_reference_key() not in client.objects
    assert client.put_calls == 2
    assert exc_info.value.snapshot_committed is True
    assert exc_info.value.latest_reference_maintenance == "failed"
    assert exc_info.value.record_key == records[0]
    assert isinstance(exc_info.value, SnapshotStorageError)
    assert isinstance(exc_info.value.__cause__, ClientError)
    assert storage.load_history() == (snapshot,)


def test_s3_storage_save_with_existing_records_short_circuits_legacy_check():
    serializer = SnapshotSerializer()
    current = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    client = FailingS3(get_error=client_error("AccessDenied"))
    client.objects["snapshot.json/0001.json"] = json.dumps(
        serializer.serialize(current)
    )

    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        serializer,
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

    storage.save(Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()))
    assert len(record_keys(client)) == 2


def test_s3_storage_save_list_failure_logs_phase(caplog):
    client = FailingS3(list_error=client_error("AccessDenied"))
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(SnapshotStorageError):
            storage.save(
                Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
            )

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_failed",
        "phase=record_discovery",
        "reason=snapshot_storage_error",
    )
    assert client.put_calls == 0


def test_s3_storage_save_legacy_check_failure_logs_phase(caplog):
    client = FailingS3(get_error=client_error("AccessDenied"))
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(SnapshotStorageError):
            storage.save(
                Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
            )

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_failed",
        "phase=legacy_check",
        "reason=snapshot_storage_error",
    )
    assert client.put_calls == 0


def test_s3_storage_save_record_write_failure_logs_phase(caplog):
    client = FailingS3(put_error=client_error("AccessDenied"))
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(SnapshotStorageError):
            storage.save(
                Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
            )

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_operation_failed",
        "phase=record_write",
        "reason=snapshot_storage_error",
    )


def test_s3_storage_save_latest_reference_update_failure_logs_degraded_state(caplog):
    class PartialFailingS3(FakeS3):
        def __init__(self):
            super().__init__()
            self.put_calls = 0

        def put_object(self, Bucket, Key, Body):
            self.put_calls += 1
            if self.put_calls == 2:
                raise client_error("AccessDenied")
            super().put_object(Bucket=Bucket, Key=Key, Body=Body)

    client = PartialFailingS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(SnapshotStorageError):
            storage.save(
                Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
            )

    messages = [record.message for record in caplog.records]
    assert_log_contains_all(
        messages,
        "event=snapshot_storage_latest_reference_maintenance_failed",
        "phase=latest_reference_update",
        "reason=latest_reference_maintenance_failed",
        "snapshot_committed=True",
        "latest_reference_maintenance=failed",
    )
    assert_log_count(messages, "snapshot_storage_save_started", 1)
    assert_log_count(messages, "snapshot_storage_save_completed", 0)


def test_s3_storage_degraded_latest_logs_active_execution_identity(caplog):
    class PartialFailingS3(FakeS3):
        def __init__(self):
            super().__init__()
            self.put_calls = 0

        def put_object(self, Bucket, Key, Body):
            self.put_calls += 1
            if self.put_calls == 2:
                raise client_error("AccessDenied")
            super().put_object(Bucket=Bucket, Key=Key, Body=Body)

    client = PartialFailingS3()
    storage = S3SnapshotStorage(
        client,
        "bucket",
        "snapshot.json",
        SnapshotSerializer(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )
    snapshot = Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
        pytest.raises(SnapshotStorageError),
    ):
        storage.save(snapshot)

    messages = [record.message for record in caplog.records]

    assert_all_storage_logs_have_execution_id(messages, execution.identity)
    assert_log_count(messages, "snapshot_storage_save_started", 1)
    assert_log_count(messages, "snapshot_storage_save_completed", 0)

from dataclasses import FrozenInstanceError
import logging

import pytest

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Snapshot
from platformiq.serialization import SnapshotSerializer

from opscript.execution import (
    Execution,
    activate_execution,
    active_execution_log_fields,
    create_execution,
    get_active_execution,
)
from opscript.application.retry_policy import RetryPolicy
from opscript.errors import OpscriptProviderError, FailureCategory
from opscript.provider.aws.ec2.discovery import EC2Discovery
from opscript.provider.aws.ec2.mapper import EC2ResourceMapper
from opscript.runtime import run_accepted_runtime_operation
from opscript.storage.file import FileSnapshotStorage


class EmptyEC2Client:
    def describe_instances(self):
        return {"Reservations": []}


def test_execution_identity_is_immutable():
    execution = create_execution()

    with pytest.raises(FrozenInstanceError):
        execution.identity = "replacement"


def test_separate_executions_have_distinct_identities():
    first = create_execution()
    second = create_execution()

    assert first.identity != second.identity


def test_execution_identity_is_opaque_and_non_semantic():
    execution = create_execution()

    assert isinstance(execution.identity, str)
    assert execution.identity
    assert "run" not in execution.identity
    assert "prod" not in execution.identity


def test_activation_exposes_active_execution():
    execution = create_execution()

    with activate_execution(execution):
        assert get_active_execution() is execution


def test_active_execution_log_fields_are_empty_without_active_execution():
    assert active_execution_log_fields() == {}


def test_active_execution_log_fields_return_active_execution_identity():
    execution = Execution(identity="execution-123")

    with activate_execution(execution):
        assert active_execution_log_fields() == {"execution_id": "execution-123"}

    assert active_execution_log_fields() == {}


def test_activation_clears_context_after_completion():
    execution = create_execution()

    with activate_execution(execution):
        pass

    assert get_active_execution() is None


def test_activation_restores_previous_context_after_completion():
    outer = Execution(identity="outer")
    inner = Execution(identity="inner")

    with activate_execution(outer):
        with activate_execution(inner):
            assert get_active_execution() is inner
        assert get_active_execution() is outer

    assert get_active_execution() is None


def test_activation_clears_context_after_exception():
    execution = create_execution()

    with pytest.raises(RuntimeError, match="boom"):
        with activate_execution(execution):
            raise RuntimeError("boom")

    assert get_active_execution() is None


def test_runtime_operation_clears_context_after_success():
    result = run_accepted_runtime_operation(
        lambda: "ok",
        terminal_status=lambda _: "completed",
    )

    assert result == "ok"
    assert get_active_execution() is None


def test_runtime_operation_clears_context_after_failure_result():
    result = run_accepted_runtime_operation(
        lambda: "failed",
        terminal_status=lambda _: "failed",
    )

    assert result == "failed"
    assert get_active_execution() is None


def test_runtime_operation_clears_context_after_uncaught_exception():
    with pytest.raises(RuntimeError, match="boom"):
        run_accepted_runtime_operation(
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            terminal_status=lambda _: "completed",
        )

    assert get_active_execution() is None


def test_snapshot_serialization_contains_no_execution_identity():
    execution = create_execution()
    snapshot = Snapshot(
        id=Identifier.new(),
        discovery_scope=DiscoveryScope("scope-a"),
        resources=(),
    )

    with activate_execution(execution):
        data = SnapshotSerializer().serialize(snapshot)

    assert execution.identity not in str(data)
    assert "execution" not in data
    assert get_active_execution() is None


def test_storage_lifecycle_reads_active_execution_identity(tmp_path, caplog):
    storage = FileSnapshotStorage(
        path=str(tmp_path),
        serializer=SnapshotSerializer(),
        discovery_scope=DiscoveryScope("scope-a"),
    )
    execution = create_execution()

    with activate_execution(execution), caplog.at_level(logging.INFO):
        storage.load_history()

    assert caplog.messages
    assert all(
        f"execution_id={execution.identity}" in message for message in caplog.messages
    )
    assert get_active_execution() is None


def test_provider_lifecycle_reads_active_execution_identity(caplog):
    discovery = EC2Discovery(
        client=EmptyEC2Client(),
        mapper=EC2ResourceMapper(),
    )
    execution = create_execution()

    with activate_execution(execution), caplog.at_level(logging.INFO):
        discovery.discover()

    assert any(
        "event=aws_discovery_service_started" in message for message in caplog.messages
    )
    assert any(
        "event=aws_discovery_service_completed" in message
        for message in caplog.messages
    )
    assert all(
        f"execution_id={execution.identity}" in message for message in caplog.messages
    )
    assert get_active_execution() is None


def test_retry_lifecycle_reads_active_execution_identity(caplog):
    policy = RetryPolicy(max_attempts=2)
    execution = create_execution()

    def fail():
        raise OpscriptProviderError(
            "network unavailable",
            category=FailureCategory.NETWORK,
        )

    with (
        activate_execution(execution),
        caplog.at_level(logging.WARNING),
        pytest.raises(OpscriptProviderError),
    ):
        policy.execute(fail)

    assert any("event=retry_attempt" in message for message in caplog.messages)
    assert any("event=retry_exhausted" in message for message in caplog.messages)
    assert all(
        f"execution_id={execution.identity}" in message for message in caplog.messages
    )
    assert get_active_execution() is None

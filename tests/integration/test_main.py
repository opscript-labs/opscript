import json
import logging
import os
import subprocess
import sys
import textwrap
import types
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError
from platformiq.core import Identifier
from platformiq.errors.provider import ProviderError
from platformiq.model import DiscoveryScope, Resource, Snapshot
from platformiq.model.value_objects import ResourceState

from opscript.application import FindingExplanationError
from opscript.cli import build_parser, main
from opscript.command_registry import COMMANDS
from opscript.commands import explain_command
from opscript.config import (
    DEFAULT_DISCOVERY_SCOPE,
    DEFAULT_LOCAL_DISCOVERY_SCOPE,
    OpscriptConfig,
    ConfigurationError,
)
from opscript.execution import get_active_execution
from opscript.models import Failure, ServiceResult, Success
from opscript.storage import (
    FileSnapshotStorage,
    S3SnapshotStorage,
    SnapshotStorageError,
)
from platformiq.serialization import SnapshotSerializer


def _json_from_entire_stdout(captured):
    assert "Opscript run started" not in captured.out
    return json.loads(captured.out)


def _execution_events(messages):
    return [message for message in messages if "event=execution_" in message]


def _field(message: str, name: str) -> str | None:
    prefix = f"{name}="
    for part in message.split():
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


class FakeDiscoveryProvider:
    def discover(self):
        return Snapshot(
            discovery_scope=DEFAULT_LOCAL_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(
                Resource(
                    id=Identifier.new(),
                    external_id="resource-001",
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
                ),
            ),
        )


class EmptyDiscoveryProvider:
    def discover(self):
        return Snapshot(
            discovery_scope=DEFAULT_LOCAL_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        )


def test_successful_recognized_cli_invocation_emits_execution_lifecycle(
    monkeypatch,
    caplog,
    capsys,
):
    def successful_command(args):
        return Success(ServiceResult("completed")), "completed"

    monkeypatch.setitem(COMMANDS, "version", successful_command)

    with caplog.at_level(logging.INFO):
        exit_code = main(["version"])

    captured = capsys.readouterr()
    events = _execution_events(caplog.messages)
    started = [message for message in events if "event=execution_started" in message]
    completed = [
        message for message in events if "event=execution_completed" in message
    ]
    failed = [message for message in events if "event=execution_failed" in message]

    assert exit_code == 0
    assert captured.out.splitlines()[-1] == "completed"
    assert len(started) == 1
    assert len(completed) == 1
    assert failed == []
    assert _field(started[0], "execution_id") == _field(completed[0], "execution_id")
    assert _field(completed[0], "terminal_status") == "completed"
    assert int(_field(completed[0], "duration_ms")) >= 0
    assert get_active_execution() is None


def test_controlled_cli_failure_emits_execution_failure(caplog, capsys):
    with caplog.at_level(logging.INFO):
        exit_code = main(["run", "--fail"])

    captured = capsys.readouterr()
    events = _execution_events(caplog.messages)
    started = [message for message in events if "event=execution_started" in message]
    completed = [
        message for message in events if "event=execution_completed" in message
    ]
    failed = [message for message in events if "event=execution_failed" in message]

    assert exit_code == 1
    assert captured.out.splitlines()[-1] == "Opscript run failed"
    assert len(started) == 1
    assert completed == []
    assert len(failed) == 1
    assert _field(started[0], "execution_id") == _field(failed[0], "execution_id")
    assert _field(failed[0], "terminal_status") == "failed"
    assert _field(failed[0], "reason") == "failure_result"
    assert int(_field(failed[0], "duration_ms")) >= 0
    assert get_active_execution() is None


def test_invalid_runtime_configuration_emits_execution_failure(
    monkeypatch,
    caplog,
    capsys,
):
    monkeypatch.setenv("OPSCRIPT_ENVIRONMENT", "prod")
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "memory")

    with caplog.at_level(logging.INFO):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    events = _execution_events(caplog.messages)
    started = [message for message in events if "event=execution_started" in message]
    completed = [
        message for message in events if "event=execution_completed" in message
    ]
    failed = [message for message in events if "event=execution_failed" in message]
    configuration_failed = [
        message
        for message in caplog.messages
        if message.startswith("event=configuration_validation_failed ")
    ]

    assert exit_code == 1
    assert captured.out.startswith("Configuration error: ")
    assert len(started) == 1
    assert completed == []
    assert len(failed) == 1
    assert _field(started[0], "execution_id") == _field(failed[0], "execution_id")
    assert len(configuration_failed) == 1
    assert _field(configuration_failed[0], "execution_id") == _field(
        started[0], "execution_id"
    )
    assert _field(configuration_failed[0], "command") == "run"
    assert _field(configuration_failed[0], "reason") == "configuration_error"
    assert "execution_id" not in captured.out
    assert get_active_execution() is None


def test_invalid_parser_input_emits_no_execution_lifecycle(caplog):
    with caplog.at_level(logging.INFO), pytest.raises(SystemExit):
        main(["resource-evolution"])

    assert _execution_events(caplog.messages) == []
    assert get_active_execution() is None


def test_uncaught_cli_exception_emits_execution_failure(monkeypatch, caplog):
    def failing_version_command(args):
        raise RuntimeError("boom")

    monkeypatch.setitem(COMMANDS, "version", failing_version_command)

    with caplog.at_level(logging.INFO), pytest.raises(RuntimeError, match="boom"):
        main(["version"])

    events = _execution_events(caplog.messages)
    started = [message for message in events if "event=execution_started" in message]
    completed = [
        message for message in events if "event=execution_completed" in message
    ]
    failed = [message for message in events if "event=execution_failed" in message]

    assert len(started) == 1
    assert completed == []
    assert len(failed) == 1
    assert _field(started[0], "execution_id") == _field(failed[0], "execution_id")
    assert _field(failed[0], "reason") == "uncaught_exception"
    assert "boom" not in failed[0]
    assert get_active_execution() is None


def test_sequential_cli_invocations_have_distinct_execution_identities(
    monkeypatch,
    caplog,
    capsys,
):
    def successful_command(args):
        return Success(ServiceResult("completed")), "completed"

    monkeypatch.setitem(COMMANDS, "version", successful_command)

    with caplog.at_level(logging.INFO):
        assert main(["version"]) == 0
        assert main(["version"]) == 0

    capsys.readouterr()
    started = [
        message
        for message in _execution_events(caplog.messages)
        if "event=execution_started" in message
    ]

    assert len(started) == 2
    assert _field(started[0], "execution_id") != _field(started[1], "execution_id")
    assert get_active_execution() is None


def test_execution_identity_does_not_contaminate_json_stdout(capsys, caplog):
    with caplog.at_level(logging.INFO):
        exit_code = main(["run", "--fail", "--json"])

    captured = capsys.readouterr()
    output = _json_from_entire_stdout(captured)

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Opscript run failed",
    }
    assert "execution_id" not in captured.out
    assert any(
        "execution_id=" in message for message in _execution_events(caplog.messages)
    )


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_workflow_lifecycle_uses_cli_execution_identity(
    default_provider,
    capsys,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message for message in messages if "event=execution_started" in message
    ]
    workflow_started = [
        message
        for message in messages
        if "event=workflow_started" in message and "workflow=observation" in message
    ]
    workflow_completed = [
        message
        for message in messages
        if "event=workflow_completed" in message and "workflow=observation" in message
    ]
    phase_events = [
        message for message in messages if "event=workflow_phase_" in message
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 0
    assert "Infrastructure Change Summary" in captured.out
    assert len(execution_started) == 1
    assert len(workflow_started) == 1
    assert len(workflow_completed) == 1
    assert _field(workflow_started[0], "execution_id") == execution_id
    assert _field(workflow_completed[0], "execution_id") == execution_id
    assert phase_events
    assert all(
        _field(message, "execution_id") == execution_id for message in phase_events
    )


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_aggregate_discovery_lifecycle_uses_cli_execution_identity(
    default_provider,
    capsys,
    caplog,
):
    from opscript.provider.aws import AWSDiscoveryProvider

    class EmptyServiceDiscovery:
        def discover(self):
            return ()

    class ResourceServiceDiscovery:
        def discover(self):
            return (
                Resource(
                    id=Identifier.new(),
                    external_id="resource-001",
                ),
            )

    default_provider.return_value = AWSDiscoveryProvider(
        DEFAULT_LOCAL_DISCOVERY_SCOPE,
        ResourceServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message for message in messages if "event=execution_started" in message
    ]
    workflow_events = [
        message
        for message in messages
        if (
            "event=workflow_started" in message
            or "event=workflow_completed" in message
            or "event=workflow_phase_" in message
        )
        and "workflow=observation" in message
    ]
    aggregate_discovery = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_started ")
        or message.startswith("event=aws_discovery_completed ")
    ]
    service_discovery = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_service_")
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 0
    assert "Infrastructure Change Summary" in captured.out
    assert len(execution_started) == 1
    assert len(aggregate_discovery) == 2
    assert all(
        _field(message, "execution_id") == execution_id for message in workflow_events
    )
    assert all(
        _field(message, "execution_id") == execution_id
        for message in aggregate_discovery
    )
    assert all("execution_id=" not in message for message in service_discovery)
    assert "resource_count=1" in aggregate_discovery[-1]
    assert "service_count=9" in aggregate_discovery[-1]
    assert "execution_id" not in captured.out


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_aggregate_discovery_failure_uses_cli_execution_identity(
    default_provider,
    capsys,
    caplog,
):
    from opscript.provider.aws import AWSDiscoveryProvider

    class EmptyServiceDiscovery:
        def discover(self):
            return ()

    class FailingServiceDiscovery:
        def discover(self):
            raise ProviderError("provider payload should stay out of lifecycle logs")

    default_provider.return_value = AWSDiscoveryProvider(
        DEFAULT_LOCAL_DISCOVERY_SCOPE,
        FailingServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message for message in messages if "event=execution_started" in message
    ]
    execution_failed = [
        message for message in messages if "event=execution_failed" in message
    ]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message and "workflow=observation" in message
    ]
    phase_failed = [
        message
        for message in messages
        if "event=workflow_phase_failed" in message
        and "workflow=observation" in message
    ]
    aggregate_started = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_started ")
    ]
    aggregate_failed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_failed ")
    ]
    aggregate_completed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_completed ")
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 1
    assert "Infrastructure observation failed:" in captured.out
    assert len(aggregate_started) == 1
    assert len(aggregate_failed) == 1
    assert aggregate_completed == []
    assert _field(aggregate_started[0], "execution_id") == execution_id
    assert _field(aggregate_failed[0], "execution_id") == execution_id
    assert _field(phase_failed[0], "execution_id") == execution_id
    assert _field(workflow_failed[0], "execution_id") == execution_id
    assert _field(execution_failed[0], "execution_id") == execution_id
    assert (
        "provider payload should stay out of lifecycle logs" not in aggregate_failed[0]
    )


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_retry_lifecycle_uses_cli_execution_identity_on_recovery(
    default_provider,
    capsys,
    caplog,
):
    from opscript.errors import OpscriptProviderError, FailureCategory
    from opscript.execution import active_execution_log_fields
    from opscript.logger import format_log_event
    from opscript.provider.aws import AWSDiscoveryProvider

    class EmptyServiceDiscovery:
        def discover(self):
            return ()

    class TransientServiceDiscovery:
        def __init__(self):
            self.attempts = 0

        def discover(self):
            self.attempts += 1
            logging.getLogger("opscript").info(
                format_log_event(
                    "aws_discovery_service_started",
                    provider="aws",
                    service="fake_retrying",
                    **active_execution_log_fields(),
                )
            )
            if self.attempts == 1:
                logging.getLogger("opscript").error(
                    format_log_event(
                        "aws_discovery_service_failed",
                        provider="aws",
                        service="fake_retrying",
                        page_count=0,
                        duration_ms=0,
                        **active_execution_log_fields(),
                    )
                )
                raise OpscriptProviderError(
                    "retry payload should stay out of lifecycle logs",
                    FailureCategory.NETWORK,
                )
            logging.getLogger("opscript").info(
                format_log_event(
                    "aws_discovery_service_completed",
                    provider="aws",
                    service="fake_retrying",
                    resource_count=0,
                    page_count=1,
                    duration_ms=0,
                    **active_execution_log_fields(),
                )
            )
            return ()

    retrying = TransientServiceDiscovery()
    default_provider.return_value = AWSDiscoveryProvider(
        DEFAULT_LOCAL_DISCOVERY_SCOPE,
        retrying,
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    retry_attempts = [
        message for message in messages if message.startswith("event=retry_attempt ")
    ]
    retry_exhausted = [
        message for message in messages if message.startswith("event=retry_exhausted ")
    ]
    aggregate_started = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_started ")
    ]
    aggregate_completed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_completed ")
    ]
    aggregate_failed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_failed ")
    ]
    provider_events = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_service_")
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 0
    assert retrying.attempts == 2
    assert "execution_id" not in captured.out
    assert len(retry_attempts) == 1
    assert retry_exhausted == []
    assert len(aggregate_started) == 2
    assert len(aggregate_failed) == 1
    assert len(aggregate_completed) == 1
    assert _field(retry_attempts[0], "attempt") == "1"
    assert _field(retry_attempts[0], "execution_id") == execution_id
    assert all(
        _field(message, "execution_id") == execution_id for message in provider_events
    )
    assert all(
        _field(message, "execution_id") == execution_id
        for message in aggregate_started + aggregate_failed + aggregate_completed
    )
    assert "retry payload should stay out of lifecycle logs" not in retry_attempts[0]
    assert "retry payload should stay out of lifecycle logs" not in aggregate_failed[0]
    assert get_active_execution() is None


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_retry_lifecycle_uses_cli_execution_identity_on_exhaustion(
    default_provider,
    capsys,
    caplog,
):
    from opscript.errors import OpscriptProviderError, FailureCategory
    from opscript.execution import active_execution_log_fields
    from opscript.logger import format_log_event
    from opscript.provider.aws import AWSDiscoveryProvider

    class EmptyServiceDiscovery:
        def discover(self):
            return ()

    class ExhaustingServiceDiscovery:
        def __init__(self):
            self.attempts = 0

        def discover(self):
            self.attempts += 1
            logging.getLogger("opscript").info(
                format_log_event(
                    "aws_discovery_service_started",
                    provider="aws",
                    service="fake_retrying",
                    **active_execution_log_fields(),
                )
            )
            logging.getLogger("opscript").error(
                format_log_event(
                    "aws_discovery_service_failed",
                    provider="aws",
                    service="fake_retrying",
                    page_count=0,
                    duration_ms=0,
                    **active_execution_log_fields(),
                )
            )
            raise OpscriptProviderError(
                "retry payload should stay out of lifecycle logs",
                FailureCategory.NETWORK,
            )

    retrying = ExhaustingServiceDiscovery()
    default_provider.return_value = AWSDiscoveryProvider(
        DEFAULT_LOCAL_DISCOVERY_SCOPE,
        retrying,
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
        EmptyServiceDiscovery(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    execution_failed = [
        message for message in messages if message.startswith("event=execution_failed ")
    ]
    retry_attempts = [
        message for message in messages if message.startswith("event=retry_attempt ")
    ]
    retry_exhausted = [
        message for message in messages if message.startswith("event=retry_exhausted ")
    ]
    aggregate_failed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_failed ")
    ]
    provider_failed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_service_failed ")
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 1
    assert retrying.attempts == 3
    assert "execution_id" not in captured.out
    assert len(retry_attempts) == 2
    assert len(retry_exhausted) == 1
    assert [_field(message, "attempt") for message in retry_attempts] == ["1", "2"]
    assert _field(retry_exhausted[0], "attempt") == "3"
    assert all(
        _field(message, "execution_id") == execution_id for message in retry_attempts
    )
    assert _field(retry_exhausted[0], "execution_id") == execution_id
    assert all(
        _field(message, "execution_id") == execution_id for message in provider_failed
    )
    assert all(
        _field(message, "execution_id") == execution_id for message in aggregate_failed
    )
    assert _field(execution_failed[0], "execution_id") == execution_id
    assert "retry payload should stay out of lifecycle logs" not in retry_exhausted[0]
    assert get_active_execution() is None


class FakeSnapshotHistoryStorage:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def load_history(self):
        return self.snapshots


class SharedFakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(
        self,
        Bucket,
        Key,
        Body,
    ):
        self.objects[Key] = Body

    def get_object(
        self,
        Bucket,
        Key,
    ):
        if Key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
                "GetObject",
            )
        return {"Body": SharedFakeS3Body(self.objects[Key])}

    def list_objects_v2(
        self,
        Bucket,
        Prefix,
    ):
        contents = [{"Key": key} for key in self.objects if key.startswith(Prefix)]
        if not contents:
            return {}
        return {"Contents": contents}


class LatestReferenceFailingS3(SharedFakeS3):
    def put_object(
        self,
        Bucket,
        Key,
        Body,
    ):
        if Key.endswith("/latest"):
            raise ClientError(
                {
                    "Error": {
                        "Code": "AccessDenied",
                        "Message": "latest reference unavailable",
                    }
                },
                "PutObject",
            )
        super().put_object(Bucket=Bucket, Key=Key, Body=Body)


class SharedFakeS3Body:
    def __init__(self, data):
        self.data = data

    def read(self):
        return self.data


class FailingSnapshotHistoryStorage:
    def load_history(self):
        raise SnapshotStorageError("snapshot history is unavailable")


class FailingLatestSnapshotStorage:
    def load_latest(self):
        raise SnapshotStorageError("latest snapshot is unavailable")


class FakeInventoryService:
    def collect_snapshot(self):
        return Snapshot(
            discovery_scope=DEFAULT_LOCAL_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(
                Resource(
                    id=Identifier.new(),
                    external_id="resource-001",
                ),
            ),
        )


def _resource(resource_external_id: str) -> Resource:
    return Resource(id=Identifier.new(), external_id=resource_external_id)


def _churn_history(resource_count: int) -> tuple[Snapshot, ...]:
    resources = tuple(
        _resource(f"resource-{index:03d}") for index in range(1, resource_count + 1)
    )
    return (
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        ),
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=resources,
        ),
        Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
            resources=(),
        ),
    )


def _history_for_scope(discovery_scope: DiscoveryScope) -> tuple[Snapshot, ...]:
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    return (
        Snapshot(
            discovery_scope=discovery_scope,
            id=Identifier.new(),
            resources=(),
        ),
        Snapshot(
            discovery_scope=discovery_scope,
            id=Identifier.new(),
            resources=(resource,),
        ),
    )


def _s3_storage_for_scope(
    client: SharedFakeS3,
    namespace: str,
    discovery_scope: DiscoveryScope,
) -> S3SnapshotStorage:
    return S3SnapshotStorage(
        client=client,
        bucket="history-bucket",
        key=namespace,
        serializer=SnapshotSerializer(),
        discovery_scope=discovery_scope,
    )


def _s3_record_keys(
    client: SharedFakeS3,
    namespace: str,
) -> list[str]:
    return sorted(
        key
        for key in client.objects
        if key.startswith(f"{namespace}/") and key.endswith(".json")
    )


def _s3_direct_record_keys(
    client: SharedFakeS3,
    namespace: str,
) -> list[str]:
    return sorted(
        key
        for key in client.objects
        if key.startswith(f"{namespace}/") and key.endswith(".json")
    )


def test_explain_command_is_registered():
    args = build_parser().parse_args(["explain"])

    assert args.command == "explain"
    assert "explain" in COMMANDS


def test_global_discovery_scope_option_is_accepted():
    args = build_parser().parse_args(["--discovery-scope", "scope-a", "run"])

    assert args.command == "run"
    assert args.discovery_scope == "scope-a"


def test_global_discovery_scope_option_is_optional():
    args = build_parser().parse_args(["run"])

    assert args.discovery_scope is None


def test_help_includes_global_discovery_scope_option():
    help_text = build_parser().format_help()

    assert "--discovery-scope" in help_text


@patch("opscript.command_registry.version_command")
def test_version_remains_configuration_independent(version_command, capsys):
    version_command.return_value = (
        Failure(error="unused"),
        "opscript vtest",
    )

    exit_code = main(["--discovery-scope", "scope-a", "version"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "opscript vtest" in captured.out
    version_command.assert_called_once()


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_discovery_scope_override_applies_to_run_workflow(
    default_provider,
    capsys,
):
    selected_scopes = []

    def build_provider(config):
        selected_scopes.append(config.discovery_scope)
        return ScopedDiscoveryProvider(config.discovery_scope)

    default_provider.side_effect = build_provider

    exit_code = main(["--discovery-scope", "scope-a", "run"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Infrastructure Change Summary" in captured.out
    assert selected_scopes == [DiscoveryScope("scope-a")]


@pytest.mark.parametrize(
    "argv",
    (
        ("--discovery-scope", "scope-a", "churn"),
        ("--discovery-scope", "scope-a", "metadata-grouping", "--metadata", "tags.Env"),
        ("--discovery-scope", "scope-a", "observation-history"),
    ),
)
@patch("opscript.commands.build_snapshot_storage")
def test_discovery_scope_override_reaches_historical_command_storage(
    build_snapshot_storage,
    argv,
    capsys,
):
    selected_scopes = []

    def build_storage(config=None):
        selected_scopes.append(config.discovery_scope)
        return FakeSnapshotHistoryStorage(_history_for_scope(config.discovery_scope))

    build_snapshot_storage.side_effect = build_storage

    exit_code = main(list(argv))

    capsys.readouterr()

    assert exit_code == 0
    assert selected_scopes == [DiscoveryScope("scope-a")]


@patch("opscript.bootstrap.Boto3AWSClientFactory")
@patch("opscript.bootstrap.build_default_discovery_provider")
def test_repeated_cli_scope_switching_keeps_histories_independent(
    build_default_discovery_provider,
    factory_class,
    monkeypatch,
    capsys,
):
    client = SharedFakeS3()
    factory_class.return_value.client.return_value = client
    discovered_scopes = []

    def build_provider(config):
        discovered_scopes.append(config.discovery_scope)
        return ScopedDiscoveryProvider(config.discovery_scope)

    build_default_discovery_provider.side_effect = build_provider
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("OPSCRIPT_S3_BUCKET", "history-bucket")
    monkeypatch.setenv("OPSCRIPT_S3_KEY", "runtime-root")
    monkeypatch.delenv("OPSCRIPT_DISCOVERY_SCOPE", raising=False)

    scope_a_run = main(["--discovery-scope", "scope-a", "run"])
    capsys.readouterr()
    scope_b_run = main(["--discovery-scope", "scope-b", "run"])
    capsys.readouterr()
    scope_a_history = main(["--discovery-scope", "scope-a", "inventory-history"])
    history_output = capsys.readouterr()

    namespace_a = "runtime-root/discovery-scopes/scope-a"
    namespace_b = "runtime-root/discovery-scopes/scope-b"
    storage_a = _s3_storage_for_scope(client, namespace_a, DiscoveryScope("scope-a"))
    storage_b = _s3_storage_for_scope(client, namespace_b, DiscoveryScope("scope-b"))
    history_a = storage_a.load_history()
    history_b = storage_b.load_history()

    assert (scope_a_run, scope_b_run, scope_a_history) == (0, 0, 0)
    assert discovered_scopes == [
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-b"),
    ]
    assert tuple(snapshot.discovery_scope for snapshot in history_a) == (
        DiscoveryScope("scope-a"),
    )
    assert tuple(snapshot.discovery_scope for snapshot in history_b) == (
        DiscoveryScope("scope-b"),
    )
    assert storage_a.load_latest().discovery_scope == DiscoveryScope("scope-a")
    assert storage_b.load_latest().discovery_scope == DiscoveryScope("scope-b")
    assert "Historical Inventory Timeline" in history_output.out
    assert "Recorded resources: 1" in history_output.out


@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_shared_s3_root_partitions_scope_namespaces(
    factory_class,
    monkeypatch,
):
    from opscript.bootstrap import build_snapshot_storage

    client = SharedFakeS3()
    factory_class.return_value.client.return_value = client
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("OPSCRIPT_S3_BUCKET", "history-bucket")
    monkeypatch.setenv("OPSCRIPT_S3_KEY", "runtime-root")

    storage_a = build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            s3_bucket="history-bucket",
            s3_key="runtime-root",
            discovery_scope=DiscoveryScope("scope-a"),
        )
    )
    storage_b = build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            s3_bucket="history-bucket",
            s3_key="runtime-root",
            discovery_scope=DiscoveryScope("scope-b"),
        )
    )
    first_a = Snapshot(discovery_scope=DiscoveryScope("scope-a"), id=Identifier.new())
    second_a = Snapshot(discovery_scope=DiscoveryScope("scope-a"), id=Identifier.new())
    only_b = Snapshot(discovery_scope=DiscoveryScope("scope-b"), id=Identifier.new())

    storage_a.save(first_a)
    storage_b.save(only_b)
    storage_a.save(second_a)

    namespace_a = "runtime-root/discovery-scopes/scope-a"
    namespace_b = "runtime-root/discovery-scopes/scope-b"
    records_a = _s3_record_keys(client, namespace_a)
    records_b = _s3_record_keys(client, namespace_b)

    assert storage_a.key == namespace_a
    assert storage_b.key == namespace_b
    assert tuple(snapshot.id for snapshot in storage_a.load_history()) == (
        first_a.id,
        second_a.id,
    )
    assert tuple(snapshot.id for snapshot in storage_b.load_history()) == (only_b.id,)
    assert storage_a.load_latest().id == second_a.id
    assert storage_b.load_latest().id == only_b.id
    assert len(records_a) == 2
    assert len(records_b) == 1
    assert client.objects[f"{namespace_a}/latest"] in records_a
    assert client.objects[f"{namespace_b}/latest"] in records_b
    assert client.objects[f"{namespace_a}/latest"] not in records_b
    assert client.objects[f"{namespace_b}/latest"] not in records_a


@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_health_evaluates_discovery_scope_override(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    capsys,
):
    selected_scopes = []

    def record_scope(config):
        selected_scopes.append(config.discovery_scope)
        return object()

    build_snapshot_storage.side_effect = record_scope
    build_default_discovery_provider.side_effect = record_scope
    build_analysis_service.side_effect = record_scope
    build_reporting_service.side_effect = record_scope

    exit_code = main(["--discovery-scope", "scope-a", "health"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Health: healthy" in captured.out
    assert selected_scopes == [
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-a"),
    ]


@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_repeated_health_scope_selection_has_no_configuration_leakage(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    monkeypatch,
    capsys,
):
    selected_scopes = []

    def record_scope(config):
        selected_scopes.append(config.discovery_scope)
        return object()

    build_snapshot_storage.side_effect = record_scope
    build_default_discovery_provider.side_effect = record_scope
    build_analysis_service.side_effect = record_scope
    build_reporting_service.side_effect = record_scope
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "environment-scope")

    first_exit = main(["--discovery-scope", "scope-a", "health"])
    capsys.readouterr()
    second_exit = main(["--discovery-scope", "scope-b", "health"])
    capsys.readouterr()

    assert (first_exit, second_exit) == (0, 0)
    assert selected_scopes == [
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-a"),
        DiscoveryScope("scope-b"),
        DiscoveryScope("scope-b"),
        DiscoveryScope("scope-b"),
        DiscoveryScope("scope-b"),
    ]
    assert os.environ["OPSCRIPT_DISCOVERY_SCOPE"] == "environment-scope"


def test_invalid_discovery_scope_override_fails_without_environment_fallback(
    monkeypatch,
    capsys,
):
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "environment-scope")

    exit_code = main(["--discovery-scope", "", "run"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Configuration error: Opscript discovery scope must not be empty." in (
        captured.out
    )


def test_invalid_discovery_scope_override_preserves_json_error_contract(
    monkeypatch,
    capsys,
):
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "environment-scope")

    exit_code = main(["--json", "--discovery-scope", "", "run"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Configuration error: Opscript discovery scope must not be empty.",
    }


def test_health_with_invalid_discovery_scope_override_reports_unhealthy(
    monkeypatch,
    capsys,
):
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "environment-scope")

    exit_code = main(["--discovery-scope", "", "health"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Health: unhealthy" in captured.out
    assert "configuration: unhealthy" in captured.out
    assert "Opscript discovery scope must not be empty." in captured.out


def test_instability_command_is_registered():
    args = build_parser().parse_args(["instability"])

    assert args.command == "instability"
    assert "instability" in COMMANDS


def test_stability_command_is_registered():
    args = build_parser().parse_args(["stability"])

    assert args.command == "stability"
    assert "stability" in COMMANDS


def test_activity_command_is_registered():
    args = build_parser().parse_args(["activity"])

    assert args.command == "activity"
    assert "activity" in COMMANDS


def test_change_frequency_command_is_registered():
    args = build_parser().parse_args(["change-frequency"])

    assert args.command == "change-frequency"
    assert "change-frequency" in COMMANDS


def test_churn_command_is_registered():
    args = build_parser().parse_args(["churn"])

    assert args.command == "churn"
    assert args.all is False
    assert "churn" in COMMANDS


def test_churn_command_accepts_all():
    args = build_parser().parse_args(["churn", "--all"])

    assert args.command == "churn"
    assert args.all is True


def test_metadata_grouping_command_is_registered():
    args = build_parser().parse_args(
        ["metadata-grouping", "--metadata", "tags.Environment"]
    )

    assert args.command == "metadata-grouping"
    assert args.metadata == "tags.Environment"
    assert "metadata-grouping" in COMMANDS


def test_observation_history_command_is_registered():
    args = build_parser().parse_args(["observation-history", "resource-001"])

    assert args.command == "observation-history"
    assert args.resource_external_id == "resource-001"
    assert "observation-history" in COMMANDS


def test_inventory_history_command_is_registered():
    args = build_parser().parse_args(["inventory-history"])

    assert args.command == "inventory-history"
    assert "inventory-history" in COMMANDS


def test_knowledge_review_json_stdout_is_single_document(capsys, caplog):
    result = Success(value=ServiceResult(message="unused"))
    output = json.dumps(
        {
            "status": "success",
            "engineering_knowledge": {
                "supported_engineering_conditions": [],
            },
        }
    )

    with patch(
        "opscript.command_registry.knowledge_review_command",
        return_value=(result, output),
    ) as knowledge_review_command:
        with caplog.at_level(logging.INFO, logger="opscript"):
            exit_code = main(["knowledge-review", "--json"])

    captured = capsys.readouterr()
    data = _json_from_entire_stdout(captured)
    startup_messages = [
        record.message
        for record in caplog.records
        if record.message == "Opscript run started"
    ]

    assert exit_code == 0
    assert data == {
        "status": "success",
        "engineering_knowledge": {
            "supported_engineering_conditions": [],
        },
    }
    assert startup_messages == ["Opscript run started"]
    knowledge_review_command.assert_called_once()


def test_knowledge_review_evolution_json_stdout_is_single_document(capsys):
    result = Success(value=ServiceResult(message="unused"))
    output = json.dumps(
        {
            "status": "success",
            "engineering_knowledge": {
                "supported_engineering_conditions": [],
                "engineering_knowledge_evolution": {
                    "introduced_supported_engineering_conditions": [],
                    "removed_supported_engineering_conditions": [],
                    "unchanged_supported_engineering_conditions": [],
                },
            },
        }
    )

    with patch(
        "opscript.command_registry.knowledge_review_command",
        return_value=(result, output),
    ) as knowledge_review_command:
        exit_code = main(["knowledge-review", "--evolution", "--json"])

    captured = capsys.readouterr()
    data = _json_from_entire_stdout(captured)
    args = knowledge_review_command.call_args.args[0]

    assert exit_code == 0
    assert data["status"] == "success"
    assert "engineering_knowledge_evolution" in data["engineering_knowledge"]
    assert args.evolution is True


def test_knowledge_review_controlled_json_failure_stdout_is_single_document(capsys):
    exit_code = main(["knowledge-review", "--fail", "--json"])

    captured = capsys.readouterr()
    data = _json_from_entire_stdout(captured)

    assert exit_code == 1
    assert data == {
        "status": "error",
        "error": "Opscript knowledge-review failed",
    }
    assert "Traceback" not in captured.out


def test_knowledge_review_sequence_phase_completion_rendered_stderr_contains_required_fields():
    script = textwrap.dedent(
        """
        import sys

        from platformiq.core import Identifier
        from platformiq.model import DiscoveryScope, Resource, Snapshot
        from platformiq.model.value_objects import ResourceState

        import opscript.application.knowledge_review_workflow as workflow
        from opscript.cli import main

        class FakeSnapshotHistoryStorage:
            def load_history(self):
                return tuple(
                    Snapshot(
                        discovery_scope=DiscoveryScope("scope-001"),
                        id=Identifier.new(),
                        resources=(
                            Resource(
                                id=Identifier.new(),
                                external_id="resource-001",
                                state=ResourceState(properties={"version": version}),
                            ),
                        ),
                    )
                    for version in (1, 2, 3, 3, 4, 5)
                )

        workflow.build_snapshot_storage = lambda config=None: FakeSnapshotHistoryStorage()
        raise SystemExit(main(["knowledge-review", "--sequence"]))
        """
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        cwd=os.getcwd(),
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        text=True,
    )
    sequence_completion = [
        line
        for line in completed.stderr.splitlines()
        if "event=workflow_phase_completed" in line
        and "phase=engineering_knowledge_sequence_analysis" in line
    ]

    assert completed.returncode == 0
    assert len(sequence_completion) == 1
    assert "workflow=knowledge_review" in sequence_completion[0]
    assert "duration_ms=" in sequence_completion[0]


def test_explain_command_accepts_subject():
    args = build_parser().parse_args(["explain", "--subject", "resource-001"])

    assert args.command == "explain"
    assert args.subject == "resource-001"


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_success(default_provider, capsys, caplog):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main([])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Infrastructure Change Summary" in captured.out
    assert "Resource created: resource-001" in captured.out
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    configuration_validated = [
        message
        for message in messages
        if message.startswith("event=configuration_validated ")
    ]
    assert len(configuration_validated) == 1
    assert _field(configuration_validated[0], "command") == "run"
    assert _field(configuration_validated[0], "execution_id") == _field(
        execution_started[0], "execution_id"
    )
    assert "execution_id" not in captured.out


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_explain_command_success(default_provider, capsys, caplog):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["explain"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Infrastructure Change Summary" in captured.out
    assert "Resource created: resource-001" in captured.out
    assert "Finding Explanations:" in captured.out
    assert "   Previous:" in captured.out
    assert "   Current:" in captured.out
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    explain_started = [
        message for message in messages if message.startswith("event=explain_started ")
    ]
    rendered = [
        message
        for message in messages
        if message.startswith("event=explain_explanations_rendered ")
    ]
    assert len(explain_started) == 1
    assert _field(explain_started[0], "execution_id") == _field(
        execution_started[0], "execution_id"
    )
    assert _field(explain_started[0], "workflow") == "explain"
    assert len(rendered) == 1
    assert _field(rendered[0], "explanation_count") == "1"
    assert _field(rendered[0], "phase") == "explanation_rendering"
    assert _field(rendered[0], "workflow") == "explain"
    assert _field(rendered[0], "execution_id") is None
    assert "execution_id" not in captured.out
    assert get_active_execution() is None


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_explain_command_json_success(default_provider, capsys):
    default_provider.return_value = FakeDiscoveryProvider()

    exit_code = main(["explain", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Infrastructure Change Summary" in output["message"]
    assert "Finding Explanations:" in output["message"]
    assert "   Previous:" in output["message"]
    assert "   Current:" in output["message"]


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_explain_command_subject_success(default_provider, capsys):
    default_provider.return_value = FakeDiscoveryProvider()

    exit_code = main(["explain", "--subject", "resource-001"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Infrastructure Change Summary" in captured.out
    assert "Finding Explanations:" in captured.out
    assert "   Subject: resource-001" in captured.out
    assert "No findings found for subject" not in captured.out


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_explain_command_subject_handles_no_matching_findings(
    default_provider,
    capsys,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["explain", "--subject", "missing-resource"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    rendered = [
        message
        for message in messages
        if message.startswith("event=explain_explanations_rendered ")
    ]

    assert exit_code == 0
    assert "Infrastructure Change Summary" in captured.out
    assert "Finding Explanations:" in captured.out
    assert "No findings found for subject 'missing-resource'." in captured.out
    assert "   Previous:" not in captured.out
    assert "   Current:" not in captured.out
    assert len(rendered) == 1
    assert _field(rendered[0], "explanation_count") == "0"
    assert _field(rendered[0], "execution_id") is None
    assert not any(message.startswith("event=explain_failed ") for message in messages)


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_explain_command_subject_json_success(default_provider, capsys):
    default_provider.return_value = FakeDiscoveryProvider()

    exit_code = main(["explain", "--subject", "resource-001", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Finding Explanations:" in output["message"]
    assert "   Subject: resource-001" in output["message"]
    assert "   Previous:" in output["message"]
    assert "   Current:" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_instability_command_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["instability"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Operational Instability Concentration" in captured.out
    assert "Resource: resource-001" in captured.out
    assert "Recorded activity: 3" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_instability_command_json_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["instability", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Operational Instability Concentration" in output["message"]
    assert "Resource: resource-001" in output["message"]
    assert "Recorded activity: 3" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_instability_command_empty_history_report(build_snapshot_storage, capsys):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    exit_code = main(["instability"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Operational Instability Concentration" in captured.out
    assert "No recorded infrastructure activity found." in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_stability_command_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["stability"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Environment Stability Trend" in captured.out
    assert "Trend direction: decreasing" in captured.out
    assert "Activity delta: -3" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_stability_command_json_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["stability", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Environment Stability Trend" in output["message"]
    assert "Trend direction: decreasing" in output["message"]
    assert "Activity delta: -3" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_stability_command_insufficient_history_report(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    exit_code = main(["stability"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Environment Stability Trend" in captured.out
    assert "Insufficient history to determine activity direction." in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_activity_command_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["activity"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Operational Activity Dominance" in captured.out
    assert "Activity Summary" in captured.out
    assert "Layer:" in captured.out
    assert "Type:" in captured.out
    assert "Count:" in captured.out
    assert "Comparisons:" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_activity_command_json_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["activity", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Operational Activity Dominance" in output["message"]
    assert "Activity Summary" in output["message"]
    assert "Layer:" in output["message"]
    assert "Type:" in output["message"]
    assert "Count:" in output["message"]
    assert "Comparisons:" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_activity_command_empty_history_report(build_snapshot_storage, capsys):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    exit_code = main(["activity"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Operational Activity Dominance" in captured.out
    assert "No recorded operational activity found." in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_change_frequency_command_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["change-frequency"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Resource Change Frequency" in captured.out
    assert "Resource: resource-001" in captured.out
    assert "Observed snapshots: 2" in captured.out
    assert "Recorded changes: 0" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_change_frequency_command_json_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["change-frequency", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource Change Frequency" in output["message"]
    assert "Resource: resource-001" in output["message"]
    assert "Observed snapshots: 2" in output["message"]
    assert "Recorded changes: 0" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_change_frequency_command_empty_history_report(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(())

    exit_code = main(["change-frequency"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource Change Frequency" in captured.out
    assert "No observed resources found." in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    exit_code = main(["churn"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Resource Churn Trend" in captured.out
    assert "Resource: resource-001" in captured.out
    assert "Trend direction:" in captured.out
    assert "Activity delta:" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_json_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    exit_code = main(["churn", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource Churn Trend" in output["message"]
    assert "Resource: resource-001" in output["message"]
    assert "Trend direction:" in output["message"]
    assert "Activity delta:" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_default_truncates_to_twenty_entries(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(_churn_history(21))

    exit_code = main(["churn"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource: resource-001" in captured.out
    assert "Resource: resource-020" in captured.out
    assert "Resource: resource-021" not in captured.out
    assert (
        "Showing 20 of 21 resource trends. "
        "1 omitted. Use --all to show the complete report."
    ) in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_default_preserves_order(build_snapshot_storage, capsys):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(_churn_history(21))

    exit_code = main(["churn"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.index("Resource: resource-001") < captured.out.index(
        "Resource: resource-002"
    )
    assert captured.out.index("Resource: resource-019") < captured.out.index(
        "Resource: resource-020"
    )


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_default_does_not_truncate_twenty_or_fewer_entries(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(_churn_history(20))

    exit_code = main(["churn"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource: resource-020" in captured.out
    assert "omitted. Use --all to show the complete report." not in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_all_renders_complete_report(build_snapshot_storage, capsys):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(_churn_history(21))

    exit_code = main(["churn", "--all"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource: resource-001" in captured.out
    assert "Resource: resource-021" in captured.out
    assert "omitted. Use --all to show the complete report." not in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_json_default_is_concise(build_snapshot_storage, capsys):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(_churn_history(21))

    exit_code = main(["churn", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource: resource-020" in output["message"]
    assert "Resource: resource-021" not in output["message"]
    assert (
        "Showing 20 of 21 resource trends. "
        "1 omitted. Use --all to show the complete report."
    ) in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_json_all_is_complete(build_snapshot_storage, capsys):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(_churn_history(21))

    exit_code = main(["churn", "--all", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource: resource-001" in output["message"]
    assert "Resource: resource-021" in output["message"]
    assert "omitted. Use --all to show the complete report." not in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_churn_command_empty_history_report(build_snapshot_storage, capsys):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    exit_code = main(["churn"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource Churn Trend" in captured.out
    assert "No recorded resource activity found." in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_metadata_grouping_command_success(build_snapshot_storage, capsys):
    prod = _resource_with_properties(
        "i-prod",
        {"tags": {"Environment": "prod"}},
    )
    dev = _resource_with_properties(
        "i-dev",
        {"tags": {"Environment": "dev"}},
    )
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(prod, dev),
            ),
        )
    )

    exit_code = main(["metadata-grouping", "--metadata", "tags.Environment"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Resource Metadata Grouping" in captured.out
    assert "Metadata: tags.Environment" in captured.out
    assert "Value: dev" in captured.out
    assert "Value: prod" in captured.out
    assert "- i-dev" in captured.out
    assert "- i-prod" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_metadata_grouping_command_json_success(build_snapshot_storage, capsys):
    resource = _resource_with_properties(
        "i-prod",
        {"tags": {"Environment": "prod"}},
    )
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["metadata-grouping", "--metadata", "tags.Environment", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource Metadata Grouping" in output["message"]
    assert "Metadata: tags.Environment" in output["message"]
    assert "Value: prod" in output["message"]
    assert "- i-prod" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_metadata_grouping_command_empty_grouping_report(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    exit_code = main(["metadata-grouping", "--metadata", "tags.Environment"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource Metadata Grouping" in captured.out
    assert "No recorded metadata groups found." in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_metadata_grouping_command_storage_failure_returns_json_failure(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FailingSnapshotHistoryStorage()

    exit_code = main(["metadata-grouping", "--metadata", "tags.Environment", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Resource metadata grouping failed: snapshot history is unavailable",
    }


@patch("opscript.commands.build_snapshot_storage")
def test_main_observation_history_command_success(build_snapshot_storage, capsys):
    first_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=first_snapshot_id,
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=latest_snapshot_id,
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["observation-history"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Resource Observation History" in captured.out
    assert "Resource: resource-001" in captured.out
    assert f"First observed snapshot: {first_snapshot_id}" in captured.out
    assert f"Latest observed snapshot: {latest_snapshot_id}" in captured.out
    assert "Observed snapshots: 2" in captured.out
    assert "Observation gaps: 1" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_observation_history_command_json_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["observation-history", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource Observation History" in output["message"]
    assert "Resource: resource-001" in output["message"]
    assert "Observed snapshots: 1" in output["message"]
    assert "Observation gaps: 0" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_observation_history_command_global_json_success(
    build_snapshot_storage,
    capsys,
):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["--json", "observation-history"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource Observation History" in output["message"]
    assert "Resource: resource-001" in output["message"]
    assert "Observation gaps: 0" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_observation_history_command_filters_resource(
    build_snapshot_storage,
    capsys,
):
    resource_001 = Resource(id=Identifier.new(), external_id="resource-001")
    resource_002 = Resource(id=Identifier.new(), external_id="resource-002")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_001, resource_002),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_001,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_001, resource_002),
            ),
        )
    )

    exit_code = main(["observation-history", "resource-002"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource Observation History" in captured.out
    assert "Resource: resource-002" in captured.out
    assert "Observation gaps: 1" in captured.out
    assert "Resource: resource-001" not in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_observation_history_command_empty_history_report(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(())

    exit_code = main(["observation-history"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource Observation History" in captured.out
    assert "No resource observation history found." in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_observation_history_command_history_validation_failure(
    build_snapshot_storage,
    capsys,
):
    snapshot_id = Identifier.new()
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(),
            ),
        )
    )

    exit_code = main(["observation-history"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Resource observation history failed: Duplicate snapshot ID detected"
        in captured.out
    )


@patch("opscript.commands.build_snapshot_storage")
def test_main_observation_history_command_storage_failure_returns_json_failure(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FailingSnapshotHistoryStorage()

    exit_code = main(["observation-history", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Resource observation history failed: snapshot history is unavailable",
    }


def test_main_observation_history_command_fail_flag(capsys):
    exit_code = main(["observation-history", "--fail"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Opscript observation-history failed" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_inventory_history_command_success(build_snapshot_storage, capsys):
    first_snapshot_id = Identifier.new()
    second_snapshot_id = Identifier.new()
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=first_snapshot_id,
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=second_snapshot_id,
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["inventory-history"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Historical Inventory Timeline" in captured.out
    assert f"Snapshot: {first_snapshot_id}" in captured.out
    assert "Recorded resources: 0" in captured.out
    assert f"Snapshot: {second_snapshot_id}" in captured.out
    assert "Recorded resources: 1" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_inventory_history_command_json_success(build_snapshot_storage, capsys):
    snapshot_id = Identifier.new()
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["inventory-history", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Historical Inventory Timeline" in output["message"]
    assert f"Snapshot: {snapshot_id}" in output["message"]
    assert "Recorded resources: 1" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_inventory_history_command_global_json_success(
    build_snapshot_storage,
    capsys,
):
    snapshot_id = Identifier.new()
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(),
            ),
        )
    )

    exit_code = main(["--json", "inventory-history"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Historical Inventory Timeline" in output["message"]
    assert f"Snapshot: {snapshot_id}" in output["message"]
    assert "Recorded resources: 0" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_inventory_history_command_empty_history_report(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(())

    exit_code = main(["inventory-history"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Historical Inventory Timeline" in captured.out
    assert "No historical inventory observations found." in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_inventory_history_command_history_validation_failure(
    build_snapshot_storage,
    capsys,
):
    snapshot_id = Identifier.new()
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(),
            ),
        )
    )

    exit_code = main(["inventory-history"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Historical inventory timeline failed: Duplicate snapshot ID detected"
        in captured.out
    )


@patch("opscript.commands.build_snapshot_storage")
def test_main_inventory_history_command_storage_failure_returns_json_failure(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FailingSnapshotHistoryStorage()

    exit_code = main(["inventory-history", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Historical inventory timeline failed: snapshot history is unavailable",
    }


def test_main_inventory_history_command_fail_flag(capsys):
    exit_code = main(["inventory-history", "--fail"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Opscript inventory-history failed" in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_resource_evolution_command_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["resource-evolution", "resource-001"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource Evolution: resource-001" in captured.out
    assert "Resource Change History: resource-001" in captured.out
    assert '"status": "success"' not in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_resource_evolution_command_json_success(
    build_snapshot_storage,
    capsys,
):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["resource-evolution", "resource-001", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource Evolution: resource-001" in output["message"]
    assert "Resource Change History: resource-001" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_resource_evolution_command_global_json_success(
    build_snapshot_storage,
    capsys,
):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["--json", "resource-evolution", "resource-001"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Resource Evolution: resource-001" in output["message"]
    assert "Resource Change History: resource-001" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_environment_evolution_command_success(build_snapshot_storage, capsys):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["environment-evolution"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Environment Evolution" in captured.out
    assert "Summary:" in captured.out
    assert '"status": "success"' not in captured.out


@patch("opscript.commands.build_snapshot_storage")
def test_main_environment_evolution_command_json_success(
    build_snapshot_storage,
    capsys,
):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["environment-evolution", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Environment Evolution" in output["message"]
    assert "Summary:" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_environment_evolution_command_global_json_success(
    build_snapshot_storage,
    capsys,
):
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    exit_code = main(["--json", "environment-evolution"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Environment Evolution" in output["message"]
    assert "Summary:" in output["message"]


@pytest.mark.parametrize(
    ("argv", "expected_error"),
    (
        (
            ["resource-evolution", "resource-001"],
            "Resource evolution failed: snapshot history is unavailable",
        ),
        (
            ["environment-evolution"],
            "Environment evolution failed: snapshot history is unavailable",
        ),
        (
            ["instability"],
            "Instability concentration failed: snapshot history is unavailable",
        ),
        (
            ["stability"],
            "Environment stability trend failed: snapshot history is unavailable",
        ),
        (
            ["activity"],
            "Operational activity dominance failed: snapshot history is unavailable",
        ),
        (
            ["change-frequency"],
            "Resource change frequency failed: snapshot history is unavailable",
        ),
        (
            ["churn"],
            "Resource churn trend failed: snapshot history is unavailable",
        ),
    ),
)
@patch("opscript.commands.build_snapshot_storage")
def test_main_historical_behavior_commands_return_failure_for_storage_failure(
    build_snapshot_storage,
    argv,
    expected_error,
    capsys,
):
    build_snapshot_storage.return_value = FailingSnapshotHistoryStorage()

    exit_code = main(argv)

    captured = capsys.readouterr()

    assert exit_code == 1
    assert expected_error in captured.out


@pytest.mark.parametrize(
    ("argv", "expected_error"),
    (
        (
            ["resource-evolution", "resource-001", "--json"],
            "Resource evolution failed: snapshot history is unavailable",
        ),
        (
            ["environment-evolution", "--json"],
            "Environment evolution failed: snapshot history is unavailable",
        ),
        (
            ["instability", "--json"],
            "Instability concentration failed: snapshot history is unavailable",
        ),
        (
            ["stability", "--json"],
            "Environment stability trend failed: snapshot history is unavailable",
        ),
        (
            ["activity", "--json"],
            "Operational activity dominance failed: snapshot history is unavailable",
        ),
        (
            ["change-frequency", "--json"],
            "Resource change frequency failed: snapshot history is unavailable",
        ),
        (
            ["churn", "--json"],
            "Resource churn trend failed: snapshot history is unavailable",
        ),
    ),
)
@patch("opscript.commands.build_snapshot_storage")
def test_main_historical_behavior_commands_return_json_failure_for_storage_failure(
    build_snapshot_storage,
    argv,
    expected_error,
    capsys,
):
    build_snapshot_storage.return_value = FailingSnapshotHistoryStorage()

    exit_code = main(argv)

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": expected_error,
    }


@patch("opscript.commands.build_snapshot_storage")
def test_main_resource_evolution_command_returns_failure_for_history_validation(
    build_snapshot_storage,
    capsys,
):
    snapshot_id = Identifier.new()
    build_snapshot_storage.return_value = FakeSnapshotHistoryStorage(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(),
            ),
        )
    )

    exit_code = main(["resource-evolution", "resource-001"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Resource evolution failed: Duplicate snapshot ID detected" in captured.out


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_run_command_success(default_provider, capsys):
    default_provider.return_value = FakeDiscoveryProvider()

    exit_code = main(["run"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Infrastructure Change Summary" in captured.out
    assert "Resource created: resource-001" in captured.out
    assert "Finding Explanations:" not in captured.out
    assert '"status": "success"' not in captured.out


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_run_command_json_success(default_provider, capsys):
    default_provider.return_value = FakeDiscoveryProvider()

    exit_code = main(["run", "--json"])

    captured = capsys.readouterr()
    output = _json_from_entire_stdout(captured)

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Infrastructure Change Summary" in output["message"]
    assert "Resource created: resource-001" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_run_command_storage_failure_returns_failure(
    build_snapshot_storage,
    capsys,
    caplog,
):
    build_snapshot_storage.return_value = FailingLatestSnapshotStorage()

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message for message in messages if "event=execution_started" in message
    ]
    workflow_started = [
        message
        for message in messages
        if "event=workflow_started" in message and "workflow=observation" in message
    ]
    phase_started = [
        message
        for message in messages
        if "event=workflow_phase_started" in message
        and "workflow=observation" in message
    ]
    phase_failed = [
        message
        for message in messages
        if "event=workflow_phase_failed" in message
        and "workflow=observation" in message
    ]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message and "workflow=observation" in message
    ]
    execution_failed = [
        message for message in messages if "event=execution_failed" in message
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 1
    assert "Infrastructure observation failed: latest snapshot is unavailable" in (
        captured.out
    )
    assert len(execution_started) == 1
    assert len(workflow_started) == 1
    assert len(phase_started) == 1
    assert len(phase_failed) == 1
    assert len(workflow_failed) == 1
    assert len(execution_failed) == 1
    assert _field(workflow_started[0], "execution_id") == execution_id
    assert _field(phase_started[0], "execution_id") == execution_id
    assert _field(phase_failed[0], "execution_id") == execution_id
    assert _field(workflow_failed[0], "execution_id") == execution_id
    assert _field(execution_failed[0], "execution_id") == execution_id


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_sequential_workflow_phase_events_inherit_only_their_own_execution(
    default_provider,
    capsys,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        assert main(["run"]) == 0
        assert main(["run"]) == 0

    capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_ids = [
        _field(message, "execution_id")
        for message in messages
        if "event=execution_started" in message
    ]
    phase_ids = [
        _field(message, "execution_id")
        for message in messages
        if "event=workflow_phase_" in message and "workflow=observation" in message
    ]
    configuration_ids = [
        _field(message, "execution_id")
        for message in messages
        if message.startswith("event=configuration_validated ")
    ]

    assert len(execution_ids) == 2
    assert execution_ids[0] != execution_ids[1]
    assert configuration_ids == execution_ids
    assert phase_ids[:8] == [execution_ids[0]] * 8
    assert phase_ids[8:] == [execution_ids[1]] * 8
    assert get_active_execution() is None


@patch("opscript.commands.build_snapshot_storage")
@patch("opscript.bootstrap.build_default_discovery_provider")
def test_storage_lifecycle_uses_cli_execution_identity(
    default_provider,
    build_snapshot_storage,
    tmp_path,
    capsys,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()

    def build_storage(config=None):
        return FileSnapshotStorage(
            path=str(tmp_path / "snapshots"),
            serializer=SnapshotSerializer(),
            discovery_scope=config.discovery_scope,
        )

    build_snapshot_storage.side_effect = build_storage

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    storage_events = [
        message for message in messages if message.startswith("event=snapshot_storage_")
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 0
    assert "Infrastructure Change Summary" in captured.out
    assert "execution_id" not in captured.out
    assert storage_events
    assert all(
        _field(message, "execution_id") == execution_id for message in storage_events
    )
    assert get_active_execution() is None


@patch("opscript.commands.build_snapshot_storage")
@patch("opscript.bootstrap.build_default_discovery_provider")
def test_snapshot_persistence_degradation_uses_cli_execution_identity(
    default_provider,
    build_snapshot_storage,
    capsys,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()
    client = LatestReferenceFailingS3()

    def build_storage(config=None):
        return S3SnapshotStorage(
            client=client,
            bucket="history-bucket",
            key="runtime-root",
            serializer=SnapshotSerializer(),
            discovery_scope=config.discovery_scope,
        )

    build_snapshot_storage.side_effect = build_storage

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    degraded_events = [
        message
        for message in messages
        if message.startswith("event=snapshot_persistence_degraded ")
    ]
    latest_maintenance_failures = [
        message
        for message in messages
        if message.startswith(
            "event=snapshot_storage_latest_reference_maintenance_failed "
        )
    ]
    execution_completed = [
        message
        for message in messages
        if message.startswith("event=execution_completed ")
    ]
    execution_id = _field(execution_started[0], "execution_id")
    record_keys = _s3_direct_record_keys(client, "runtime-root")

    assert exit_code == 0
    assert "Infrastructure Change Summary" in captured.out
    assert "execution_id" not in captured.out
    assert len(execution_started) == 1
    assert len(degraded_events) == 1
    assert len(latest_maintenance_failures) == 1
    assert len(execution_completed) == 1
    assert _field(degraded_events[0], "execution_id") == execution_id
    assert _field(latest_maintenance_failures[0], "execution_id") == execution_id
    assert _field(execution_completed[0], "execution_id") == execution_id
    assert "latest_reference_maintenance=failed" in degraded_events[0]
    assert "operation=snapshot_persistence" in degraded_events[0]
    assert "phase=latest_reference_update" in degraded_events[0]
    assert "snapshot_committed=True" in degraded_events[0]
    assert "latest reference unavailable" not in degraded_events[0]
    assert len(record_keys) == 1
    assert "runtime-root/latest" not in client.objects
    assert all("execution_id" not in key for key in client.objects)
    assert all("execution_id" not in str(body) for body in client.objects.values())
    assert get_active_execution() is None


@patch("opscript.commands.build_snapshot_storage")
@patch("opscript.bootstrap.build_default_discovery_provider")
def test_snapshot_persistence_degradation_execution_identity_isolated_between_runs(
    default_provider,
    build_snapshot_storage,
    capsys,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()
    clients = []

    def build_storage(config=None):
        client = LatestReferenceFailingS3()
        clients.append(client)
        return S3SnapshotStorage(
            client=client,
            bucket="history-bucket",
            key="runtime-root",
            serializer=SnapshotSerializer(),
            discovery_scope=config.discovery_scope,
        )

    build_snapshot_storage.side_effect = build_storage

    with caplog.at_level(logging.INFO, logger="opscript"):
        assert main(["run"]) == 0
        assert main(["run"]) == 0

    capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_ids = [
        _field(message, "execution_id")
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    degraded_ids = [
        _field(message, "execution_id")
        for message in messages
        if message.startswith("event=snapshot_persistence_degraded ")
    ]

    assert len(clients) == 2
    assert len(execution_ids) == 2
    assert execution_ids[0] != execution_ids[1]
    assert degraded_ids == execution_ids
    assert all(
        len(_s3_direct_record_keys(client, "runtime-root")) == 1 for client in clients
    )
    assert get_active_execution() is None


@patch("opscript.commands.build_snapshot_storage")
def test_main_run_command_storage_failure_returns_json_failure(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FailingLatestSnapshotStorage()

    exit_code = main(["run", "--json"])

    captured = capsys.readouterr()
    output = _json_from_entire_stdout(captured)

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Infrastructure observation failed: latest snapshot is unavailable",
    }


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_change_review_alias_success(default_provider, capsys):
    default_provider.return_value = FakeDiscoveryProvider()

    exit_code = main(["change-review"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Infrastructure Change Summary" in captured.out
    assert "Resource created: resource-001" in captured.out


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_change_review_alias_json_success(default_provider, capsys):
    default_provider.return_value = FakeDiscoveryProvider()

    exit_code = main(["change-review", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Infrastructure Change Summary" in output["message"]
    assert "Resource created: resource-001" in output["message"]


@patch("opscript.commands.build_snapshot_storage")
def test_main_change_review_alias_storage_failure_returns_failure(
    build_snapshot_storage,
    capsys,
):
    build_snapshot_storage.return_value = FailingLatestSnapshotStorage()

    exit_code = main(["change-review"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Infrastructure observation failed: latest snapshot is unavailable" in (
        captured.out
    )


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_explain_command_handles_no_findings(default_provider, capsys, caplog):
    default_provider.return_value = EmptyDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["explain"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    rendered = [
        message
        for message in messages
        if message.startswith("event=explain_explanations_rendered ")
    ]

    assert exit_code == 0
    assert "No observations." in captured.out
    assert "Finding Explanations:" in captured.out
    assert "No finding explanations available." in captured.out
    assert len(rendered) == 1
    assert _field(rendered[0], "explanation_count") == "0"
    assert _field(rendered[0], "execution_id") is None
    assert not any(message.startswith("event=explain_failed ") for message in messages)


@patch("opscript.command_registry.explain_command")
def test_main_explain_command_handles_explanation_failure(explain_command, capsys):
    explain_command.return_value = (
        Failure(error="Finding explanation failed: unavailable"),
        "Finding explanation failed: unavailable",
    )

    exit_code = main(["explain"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Finding explanation failed: unavailable" in captured.out


@patch(
    "opscript.commands.render_workflow_outcome_explanations",
    side_effect=FindingExplanationError("unavailable"),
)
@patch("opscript.bootstrap.build_default_discovery_provider")
def test_main_explain_command_json_handles_explanation_failure(
    default_provider,
    render_workflow_outcome_explanations,
    capsys,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["explain", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])
    messages = [record.message for record in caplog.records]
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    explain_started = [
        message for message in messages if message.startswith("event=explain_started ")
    ]
    explain_failed = [
        message for message in messages if message.startswith("event=explain_failed ")
    ]

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Finding explanation failed: unavailable",
    }
    render_workflow_outcome_explanations.assert_called_once()
    assert len(explain_started) == 1
    assert len(explain_failed) == 1
    assert _field(explain_started[0], "execution_id") == _field(
        execution_started[0], "execution_id"
    )
    assert _field(explain_failed[0], "execution_id") == _field(
        execution_started[0], "execution_id"
    )
    assert _field(explain_failed[0], "phase") == "explanation_rendering"
    assert _field(explain_failed[0], "reason") == "finding_explanation_error"
    assert _field(explain_failed[0], "workflow") == "explain"
    assert not any(
        message.startswith("event=explain_explanations_rendered ")
        for message in messages
    )
    assert "execution_id" not in captured.out
    assert get_active_execution() is None


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_direct_explain_command_success_omits_execution_identity(
    default_provider,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        result, output = explain_command(
            types.SimpleNamespace(fail=False, json=False, subject=None)
        )

    messages = [record.message for record in caplog.records]
    explain_started = [
        message for message in messages if message.startswith("event=explain_started ")
    ]
    rendered = [
        message
        for message in messages
        if message.startswith("event=explain_explanations_rendered ")
    ]

    assert isinstance(result, Success)
    assert "Finding Explanations:" in output
    assert len(explain_started) == 1
    assert _field(explain_started[0], "execution_id") is None
    assert len(rendered) == 1
    assert _field(rendered[0], "execution_id") is None
    assert not any(message.startswith("event=execution_") for message in messages)
    assert get_active_execution() is None


@patch(
    "opscript.commands.render_workflow_outcome_explanations",
    side_effect=FindingExplanationError("unavailable"),
)
@patch("opscript.bootstrap.build_default_discovery_provider")
def test_direct_explain_command_failure_omits_execution_identity(
    default_provider,
    render_workflow_outcome_explanations,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        result, output = explain_command(
            types.SimpleNamespace(fail=False, json=False, subject=None)
        )

    messages = [record.message for record in caplog.records]
    explain_started = [
        message for message in messages if message.startswith("event=explain_started ")
    ]
    explain_failed = [
        message for message in messages if message.startswith("event=explain_failed ")
    ]

    assert isinstance(result, Failure)
    assert output == "Finding explanation failed: unavailable"
    render_workflow_outcome_explanations.assert_called_once()
    assert len(explain_started) == 1
    assert _field(explain_started[0], "execution_id") is None
    assert len(explain_failed) == 1
    assert _field(explain_failed[0], "execution_id") is None
    assert not any(message.startswith("event=execution_") for message in messages)
    assert get_active_execution() is None


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_sequential_explain_invocations_use_distinct_execution_identities(
    default_provider,
    capsys,
    caplog,
):
    default_provider.return_value = FakeDiscoveryProvider()

    with caplog.at_level(logging.INFO, logger="opscript"):
        first_exit = main(["explain"])
        second_exit = main(["explain"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    explain_started = [
        message for message in messages if message.startswith("event=explain_started ")
    ]
    rendered = [
        message
        for message in messages
        if message.startswith("event=explain_explanations_rendered ")
    ]
    execution_ids = [_field(message, "execution_id") for message in execution_started]

    assert first_exit == 0
    assert second_exit == 0
    assert len(execution_ids) == 2
    assert execution_ids[0] != execution_ids[1]
    assert [_field(message, "execution_id") for message in explain_started] == (
        execution_ids
    )
    assert len(rendered) == 2
    assert all(_field(message, "execution_id") is None for message in rendered)
    assert "execution_id" not in captured.out
    assert get_active_execution() is None


def test_main_failure(capsys):
    exit_code = main(["--fail"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Opscript run failed" in captured.out


@patch("opscript.commands.build_inventory_service")
def test_main_inventory_command_success(build_inventory_service, capsys):
    build_inventory_service.return_value = FakeInventoryService()

    exit_code = main(["inventory"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Inventory collected: 1 resources" in captured.out
    assert '"status": "success"' not in captured.out


@patch("opscript.commands.build_inventory_service")
def test_main_inventory_command_json_success(build_inventory_service, capsys):
    build_inventory_service.return_value = FakeInventoryService()

    exit_code = main(["inventory", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert output["message"] == "Inventory collected: 1 resources"


@patch("opscript.commands.build_inventory_service")
def test_main_inventory_command_authorization_failure_text(
    build_inventory_service,
    capsys,
):
    from opscript.errors import OpscriptProviderError, FailureCategory

    class FailingInventoryService:
        def collect_snapshot(self):
            raise OpscriptProviderError(
                "AccessDenied: User is not authorized",
                FailureCategory.AUTHORIZATION,
            )

    build_inventory_service.return_value = FailingInventoryService()

    exit_code = main(["inventory"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert (
        "Inventory collection failed: AccessDenied: User is not authorized"
        in captured.out
    )
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert "Inventory collected" not in captured.out


@patch("opscript.commands.build_inventory_service")
def test_main_inventory_command_authorization_failure_json_local(
    build_inventory_service,
    capsys,
):
    from opscript.errors import OpscriptProviderError, FailureCategory

    class FailingInventoryService:
        def collect_snapshot(self):
            raise OpscriptProviderError(
                "AccessDenied: User is not authorized",
                FailureCategory.AUTHORIZATION,
            )

    build_inventory_service.return_value = FailingInventoryService()

    exit_code = main(["inventory", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Inventory collection failed: AccessDenied: User is not authorized",
    }
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


@patch("opscript.commands.build_inventory_service")
def test_main_inventory_command_authorization_failure_json_global(
    build_inventory_service,
    capsys,
):
    from opscript.errors import OpscriptProviderError, FailureCategory

    class FailingInventoryService:
        def collect_snapshot(self):
            raise OpscriptProviderError(
                "AccessDenied: User is not authorized",
                FailureCategory.AUTHORIZATION,
            )

    build_inventory_service.return_value = FailingInventoryService()

    exit_code = main(["--json", "inventory"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output == {
        "status": "error",
        "error": "Inventory collection failed: AccessDenied: User is not authorized",
    }
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


def test_inventory_command_parser_json_placements():
    args_global = build_parser().parse_args(["--json", "inventory"])
    assert getattr(args_global, "json", False) is True

    args_local = build_parser().parse_args(["inventory", "--json"])
    assert getattr(args_local, "json", False) is True

    args_none = build_parser().parse_args(["inventory"])
    assert getattr(args_none, "json", False) is False


@patch("opscript.cli.build_config")
@patch("opscript.cli_operations.build_config")
@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_main_health(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    health_build_config,
    cli_build_config,
    capsys,
):
    config = OpscriptConfig()
    cli_build_config.return_value = config
    health_build_config.return_value = config
    build_snapshot_storage.return_value = object()
    build_default_discovery_provider.return_value = object()
    build_analysis_service.return_value = object()
    build_reporting_service.return_value = object()

    exit_code = main(["health"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Opscript run started" in captured.out
    assert "Health: healthy" in captured.out
    assert "configuration: healthy" in captured.out
    assert "storage: healthy" in captured.out
    assert "discovery: healthy" in captured.out
    assert "workflow: healthy" in captured.out
    build_snapshot_storage.assert_called_once_with(config)
    build_default_discovery_provider.assert_called_once_with(config)
    build_analysis_service.assert_called_once_with(config)
    build_reporting_service.assert_called_once_with(config)


@patch("opscript.cli.build_config")
@patch("opscript.cli_operations.build_config")
@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_main_health_command_json_success(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    health_build_config,
    cli_build_config,
    capsys,
):
    config = OpscriptConfig()
    cli_build_config.return_value = config
    health_build_config.return_value = config
    build_snapshot_storage.return_value = object()
    build_default_discovery_provider.return_value = object()
    build_analysis_service.return_value = object()
    build_reporting_service.return_value = object()

    exit_code = main(["health", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert "Health: healthy" in output["message"]
    assert "configuration: healthy" in output["message"]
    assert "storage: healthy" in output["message"]
    assert "discovery: healthy" in output["message"]
    assert "workflow: healthy" in output["message"]


@patch("opscript.cli.build_config")
@patch("opscript.cli_operations.build_config")
@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_main_health_unhealthy_configuration_exits_one(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    health_build_config,
    cli_build_config,
    capsys,
):
    cli_build_config.side_effect = ConfigurationError(
        "Opscript production environment must not use memory storage."
    )

    exit_code = main(["health"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Health: unhealthy" in captured.out
    assert "configuration: unhealthy" in captured.out
    assert "must not use memory storage" in captured.out
    assert "storage: unhealthy" in captured.out
    assert "discovery: unhealthy" in captured.out
    assert "workflow: unhealthy" in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
    health_build_config.assert_not_called()
    build_snapshot_storage.assert_not_called()
    build_default_discovery_provider.assert_not_called()
    build_analysis_service.assert_not_called()
    build_reporting_service.assert_not_called()


@patch("opscript.cli.build_config")
@patch("opscript.cli_operations.build_config")
@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_main_health_unhealthy_storage_exits_one(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    health_build_config,
    cli_build_config,
    capsys,
):
    config = OpscriptConfig()
    cli_build_config.return_value = config
    health_build_config.return_value = config
    build_snapshot_storage.side_effect = SnapshotStorageError(
        "snapshot storage unavailable"
    )
    build_default_discovery_provider.return_value = object()
    build_analysis_service.return_value = object()
    build_reporting_service.return_value = object()

    exit_code = main(["health"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Health: unhealthy" in captured.out
    assert "storage: unhealthy - snapshot storage unavailable" in captured.out
    assert "configuration: healthy" in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


@patch("opscript.cli.build_config")
@patch("opscript.cli_operations.build_config")
@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_main_health_unhealthy_discovery_exits_one(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    health_build_config,
    cli_build_config,
    capsys,
):
    config = OpscriptConfig()
    cli_build_config.return_value = config
    health_build_config.return_value = config
    build_snapshot_storage.return_value = object()
    build_default_discovery_provider.side_effect = ProviderError(
        "discovery composition unavailable"
    )
    build_analysis_service.return_value = object()
    build_reporting_service.return_value = object()

    exit_code = main(["health"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Health: unhealthy" in captured.out
    assert "discovery: unhealthy - discovery composition unavailable" in captured.out


@patch("opscript.cli.build_config")
@patch("opscript.cli_operations.build_config")
@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_main_health_unhealthy_workflow_exits_one(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    health_build_config,
    cli_build_config,
    capsys,
):
    config = OpscriptConfig()
    cli_build_config.return_value = config
    health_build_config.return_value = config
    build_snapshot_storage.return_value = object()
    build_default_discovery_provider.return_value = object()
    build_analysis_service.side_effect = SnapshotStorageError(
        "workflow composition unavailable"
    )
    build_reporting_service.return_value = object()

    exit_code = main(["health"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Health: unhealthy" in captured.out
    assert "workflow: unhealthy - workflow composition unavailable" in captured.out


@patch("opscript.cli.build_config")
@patch("opscript.cli_operations.build_config")
@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_main_health_unhealthy_command_local_json_returns_error(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    health_build_config,
    cli_build_config,
    capsys,
):
    config = OpscriptConfig()
    cli_build_config.return_value = config
    health_build_config.return_value = config
    build_snapshot_storage.side_effect = SnapshotStorageError(
        "snapshot storage unavailable"
    )
    build_default_discovery_provider.return_value = object()
    build_analysis_service.return_value = object()
    build_reporting_service.return_value = object()

    exit_code = main(["health", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output["status"] == "error"
    assert "Health: unhealthy" in output["error"]
    assert "storage: unhealthy - snapshot storage unavailable" in output["error"]


@patch("opscript.cli.build_config")
@patch("opscript.cli_operations.build_config")
@patch("opscript.cli_operations.build_snapshot_storage")
@patch("opscript.cli_operations.build_default_discovery_provider")
@patch("opscript.cli_operations.build_analysis_service")
@patch("opscript.cli_operations.build_reporting_service")
def test_main_health_unhealthy_global_json_returns_error(
    build_reporting_service,
    build_analysis_service,
    build_default_discovery_provider,
    build_snapshot_storage,
    health_build_config,
    cli_build_config,
    capsys,
):
    config = OpscriptConfig()
    cli_build_config.return_value = config
    health_build_config.return_value = config
    build_snapshot_storage.side_effect = SnapshotStorageError(
        "snapshot storage unavailable"
    )
    build_default_discovery_provider.return_value = object()
    build_analysis_service.return_value = object()
    build_reporting_service.return_value = object()

    exit_code = main(["--json", "health"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 1
    assert output["status"] == "error"
    assert "Health: unhealthy" in output["error"]
    assert "storage: unhealthy - snapshot storage unavailable" in output["error"]


@patch("opscript.command_registry.run_command")
def test_main_invalid_production_config_fails_before_workflow(
    run_command,
    monkeypatch,
    capsys,
    caplog,
):
    monkeypatch.setenv("OPSCRIPT_ENVIRONMENT", "prod")
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "memory")

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["run"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]

    assert exit_code == 1
    assert "Configuration error:" in captured.out
    assert "must not use memory storage" in captured.out
    assert "Opscript run started" not in captured.out
    run_command.assert_not_called()
    execution_started = [
        message
        for message in messages
        if message.startswith("event=execution_started ")
    ]
    configuration_failed = [
        message
        for message in messages
        if message.startswith("event=configuration_validation_failed ")
    ]
    workflow_events = [
        message for message in messages if message.startswith("event=workflow_")
    ]
    assert len(configuration_failed) == 1
    assert _field(configuration_failed[0], "command") == "run"
    assert _field(configuration_failed[0], "reason") == "configuration_error"
    assert _field(configuration_failed[0], "execution_id") == _field(
        execution_started[0], "execution_id"
    )
    assert workflow_events == []
    assert "execution_id" not in captured.out


@patch("opscript.command_registry.run_command")
def test_main_invalid_production_config_json_fails_before_workflow(
    run_command,
    monkeypatch,
    capsys,
):
    monkeypatch.setenv("OPSCRIPT_ENVIRONMENT", "prod")
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "memory")

    exit_code = main(["run", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert exit_code == 1
    assert output["status"] == "error"
    assert output["error"].startswith("Configuration error: ")
    assert "must not use memory storage" in output["error"]
    assert "Opscript run started" not in captured.out
    run_command.assert_not_called()


@patch("opscript.command_registry.run_command")
def test_main_invalid_production_config_global_json_fails_before_workflow(
    run_command,
    monkeypatch,
    capsys,
):
    monkeypatch.setenv("OPSCRIPT_ENVIRONMENT", "prod")
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "memory")

    exit_code = main(["--json", "run"])

    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert exit_code == 1
    assert output["status"] == "error"
    assert output["error"].startswith("Configuration error: ")
    assert "must not use memory storage" in output["error"]
    assert "Opscript run started" not in captured.out
    run_command.assert_not_called()


def test_main_version_command_success(capsys, monkeypatch):
    version_module = types.ModuleType("opscript._version")
    version_module.__version__ = "test"
    monkeypatch.setitem(sys.modules, "opscript._version", version_module)

    exit_code = main(["version"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "opscript vtest" in captured.out
    assert '"status": "success"' not in captured.out


def test_main_version_command_uses_package_metadata_without_generated_version(
    capsys,
    monkeypatch,
):
    from importlib.metadata import version

    monkeypatch.delitem(sys.modules, "opscript._version", raising=False)

    exit_code = main(["version"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert f"opscript v{version('opscript')}" in captured.out
    assert "Traceback" not in captured.err
    assert '"status": "success"' not in captured.out


def test_main_version_command_json_success(capsys, monkeypatch):
    version_module = types.ModuleType("opscript._version")
    version_module.__version__ = "test"
    monkeypatch.setitem(sys.modules, "opscript._version", version_module)

    exit_code = main(["version", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert output["message"] == "opscript vtest"


def test_main_version_command_json_uses_package_metadata_without_generated_version(
    capsys,
    monkeypatch,
):
    from importlib.metadata import version

    monkeypatch.delitem(sys.modules, "opscript._version", raising=False)

    exit_code = main(["version", "--json"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert output["message"] == f"opscript v{version('opscript')}"
    assert "Traceback" not in captured.err


def test_main_version_command_global_json_success(capsys, monkeypatch):
    version_module = types.ModuleType("opscript._version")
    version_module.__version__ = "test"
    monkeypatch.setitem(sys.modules, "opscript._version", version_module)

    exit_code = main(["--json", "version"])

    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])

    assert exit_code == 0
    assert output["status"] == "success"
    assert output["message"] == "opscript vtest"


def test_version_command_parser_json_placements():
    args_global = build_parser().parse_args(["--json", "version"])
    assert getattr(args_global, "json", False) is True

    args_local = build_parser().parse_args(["version", "--json"])
    assert getattr(args_local, "json", False) is True

    args_none = build_parser().parse_args(["version"])
    assert getattr(args_none, "json", False) is False


@patch("opscript.command_registry.version_command")
def test_main_version_does_not_log_configuration_validation(
    version_command,
    capsys,
    caplog,
):
    version_command.return_value = (
        Failure(error="unused"),
        "opscript vtest",
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(["version"])

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]

    assert exit_code == 0
    assert "opscript v" in captured.out
    assert not any("configuration_validated" in message for message in messages)
    assert not any("configuration_validation_failed" in message for message in messages)


def _resource_with_properties(
    external_id: str,
    properties: dict,
) -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
        state=ResourceState(properties=properties),
    )


class FakeCrossScopeStorage:
    def __init__(self, snapshots):
        self.snapshots = snapshots

    def load_history(self):
        return self.snapshots

    def load_latest(self):
        return self.snapshots[-1] if self.snapshots else None


def test_cross_scope_activity_command_appears_in_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "cross-scope-activity" in captured.out


def test_cross_scope_activity_subcommand_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["cross-scope-activity", "--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--discovery-scope" in captured.out


def test_cross_scope_activity_repeated_scopes_parse(capsys):
    with patch("opscript.bootstrap.build_snapshot_storage") as mock_storage:
        mock_storage.return_value = FakeCrossScopeStorage(())
        exit_code = main(
            [
                "cross-scope-activity",
                "--discovery-scope",
                "scope-a",
                "--discovery-scope",
                "scope-b",
            ]
        )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Comparison Status: Insufficient Evidence" in captured.out
    assert "Requested Scopes: scope-a, scope-b" in captured.out


def test_cross_scope_activity_fewer_than_two_scopes_fails(capsys):
    exit_code = main(["cross-scope-activity", "--discovery-scope", "scope-a"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "At least two Discovery Scopes are required." in captured.out


def test_cross_scope_activity_duplicate_scopes_fails(capsys):
    exit_code = main(
        [
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-a",
        ]
    )
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Duplicate Discovery Scopes are not allowed." in captured.out


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_workflow_composition(build_snapshot_storage, capsys):
    storages = {
        "scope-a": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-a"))),
        "scope-b": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-b"))),
    }

    def side_effect(config=None):
        return storages[config.discovery_scope.value]

    build_snapshot_storage.side_effect = side_effect

    exit_code = main(
        [
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Cross-Scope Activity Comparison" in captured.out
    assert "Requested Scopes: scope-a, scope-b" in captured.out
    assert "Eligible Scopes: scope-a, scope-b" in captured.out
    assert "Compared Scopes: 2" in captured.out
    assert "Scope: scope-a" in captured.out
    assert "Scope: scope-b" in captured.out
    assert "Aggregate Totals:" in captured.out


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_workflow_json_success(build_snapshot_storage, capsys):
    storages = {
        "scope-a": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-a"))),
        "scope-b": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-b"))),
    }

    def side_effect(config=None):
        return storages[config.discovery_scope.value]

    build_snapshot_storage.side_effect = side_effect

    exit_code = main(
        [
            "--json",
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])
    assert output["status"] == "success"
    assert output["workflow_status"] == "comparison_produced"
    assert output["requested_scopes"] == ["scope-a", "scope-b"]
    assert output["eligible_scopes"] == ["scope-a", "scope-b"]
    assert "activity_report" in output
    assert output["activity_report"]["compared_scope_count"] == 2
    assert len(output["activity_report"]["scope_reports"]) == 2
    assert output["activity_report"]["scope_reports"][0]["discovery_scope"] == "scope-a"


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_lifecycle_logs_success(
    build_snapshot_storage,
    capsys,
    caplog,
):
    storages = {
        "scope-a": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-a"))),
        "scope-b": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-b"))),
    }

    def side_effect(config=None):
        return storages[config.discovery_scope.value]

    build_snapshot_storage.side_effect = side_effect

    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(
            [
                "cross-scope-activity",
                "--discovery-scope",
                "scope-a",
                "--discovery-scope",
                "scope-b",
            ]
        )

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message for message in messages if "event=execution_started" in message
    ]
    started = [
        message
        for message in messages
        if "event=workflow_started" in message
        and "workflow=cross_scope_activity" in message
    ]
    completed = [
        message
        for message in messages
        if "event=workflow_completed" in message
        and "workflow=cross_scope_activity" in message
    ]
    failed = [
        message
        for message in messages
        if "event=workflow_failed" in message
        and "workflow=cross_scope_activity" in message
    ]
    phase_events = [
        message
        for message in messages
        if "event=workflow_phase_" in message
        and "workflow=cross_scope_activity" in message
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 0
    assert "Cross-Scope Activity Comparison" in captured.out
    assert len(execution_started) == 1
    assert len(started) == 1
    assert len(completed) == 1
    assert failed == []
    assert _field(started[0], "execution_id") == execution_id
    assert _field(completed[0], "execution_id") == execution_id
    assert "duration_ms=" in completed[0]
    assert "status=comparison_produced" in completed[0]
    assert phase_events
    assert all(
        _field(message, "execution_id") == execution_id for message in phase_events
    )


def test_cross_scope_activity_lifecycle_logs_failure(capsys, caplog):
    with caplog.at_level(logging.INFO, logger="opscript"):
        exit_code = main(
            [
                "cross-scope-activity",
                "--discovery-scope",
                "scope-a",
                "--discovery-scope",
                "scope-a",
            ]
        )

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message for message in messages if "event=execution_started" in message
    ]
    started = [
        message
        for message in messages
        if "event=workflow_started" in message
        and "workflow=cross_scope_activity" in message
    ]
    completed = [
        message
        for message in messages
        if "event=workflow_completed" in message
        and "workflow=cross_scope_activity" in message
    ]
    failed = [
        message
        for message in messages
        if "event=workflow_failed" in message
        and "workflow=cross_scope_activity" in message
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 1
    assert "Duplicate Discovery Scopes are not allowed." in captured.out
    assert len(execution_started) == 1
    assert len(started) == 1
    assert completed == []
    assert len(failed) == 1
    assert _field(started[0], "execution_id") == execution_id
    assert _field(failed[0], "execution_id") == execution_id
    assert "duration_ms=" in failed[0]
    assert "reason=duplicate_discovery_scopes" in failed[0]


def test_cross_scope_activity_phase_failure_logs_workflow_failure(capsys, caplog):
    from opscript.application import (
        DiscoveryScopeActivityComparisonService,
        DiscoveryScopeActivityReportService,
        DiscoveryScopeActivityWorkflow,
        DiscoveryScopeActivityWorkflowError,
        DiscoveryScopeEligibilityService,
        DiscoveryScopeEligibilityWorkflow,
    )

    class FailingFactsService:
        def derive(self, eligibility, history):
            raise DiscoveryScopeActivityWorkflowError("synthetic fact failure")

    storages = {
        "scope-a": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-a"))),
        "scope-b": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-b"))),
    }

    def storage_factory(discovery_scope):
        return storages[discovery_scope.value]

    workflow = DiscoveryScopeActivityWorkflow(
        eligibility_workflow=DiscoveryScopeEligibilityWorkflow(
            eligibility_service=DiscoveryScopeEligibilityService()
        ),
        activity_facts_service=FailingFactsService(),
        comparison_service=DiscoveryScopeActivityComparisonService(),
        report_service=DiscoveryScopeActivityReportService(),
        storage_factory=storage_factory,
    )

    with (
        patch(
            "opscript.bootstrap.build_discovery_scope_activity_workflow",
            return_value=workflow,
        ),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        exit_code = main(
            [
                "cross-scope-activity",
                "--discovery-scope",
                "scope-a",
                "--discovery-scope",
                "scope-b",
            ]
        )

    captured = capsys.readouterr()
    messages = [record.message for record in caplog.records]
    execution_started = [
        message for message in messages if "event=execution_started" in message
    ]
    phase_events = [
        message
        for message in messages
        if "event=workflow_phase_" in message
        and "workflow=cross_scope_activity" in message
    ]
    workflow_failed = [
        message
        for message in messages
        if "event=workflow_failed" in message
        and "workflow=cross_scope_activity" in message
    ]
    execution_failed = [
        message for message in messages if "event=execution_failed" in message
    ]
    execution_id = _field(execution_started[0], "execution_id")

    assert exit_code == 1
    assert "synthetic fact failure" in captured.out
    assert len(execution_started) == 1
    assert workflow_failed
    assert execution_failed
    assert _cross_scope_phase_order(phase_events) == (
        ("workflow_phase_started", "scope_qualification"),
        ("workflow_phase_completed", "scope_qualification"),
        ("workflow_phase_started", "activity_fact_derivation"),
        ("workflow_phase_failed", "activity_fact_derivation"),
    )
    assert all(
        _field(message, "execution_id") == execution_id for message in phase_events
    )
    assert _field(workflow_failed[-1], "execution_id") == execution_id
    assert _field(execution_failed[-1], "execution_id") == execution_id
    assert "reason=activity_fact_derivation_failed" in phase_events[-1]
    assert "synthetic fact failure" not in phase_events[-1]
    assert "reason=workflow_error" in workflow_failed[-1]


@patch("opscript.bootstrap.build_snapshot_storage")
def test_cross_scope_activity_workflow_json_insufficiency(
    build_snapshot_storage, capsys
):
    storages = {
        "scope-a": FakeCrossScopeStorage(_history_for_scope(DiscoveryScope("scope-a"))),
        "scope-b": FakeCrossScopeStorage(()),
    }

    def side_effect(config=None):
        return storages[config.discovery_scope.value]

    build_snapshot_storage.side_effect = side_effect

    exit_code = main(
        [
            "--json",
            "cross-scope-activity",
            "--discovery-scope",
            "scope-a",
            "--discovery-scope",
            "scope-b",
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out.splitlines()[-1])
    assert output["status"] == "success"
    assert output["workflow_status"] == "insufficient_eligible_scopes"
    assert output["requested_scopes"] == ["scope-a", "scope-b"]
    assert output["eligible_scopes"] == ["scope-a"]
    assert len(output["excluded_scopes"]) == 1
    assert output["excluded_scopes"][0]["discovery_scope"] == "scope-b"
    assert output["activity_report"] is None


def _cross_scope_phase_order(messages):
    return tuple(
        (_log_field(message, "event"), _log_field(message, "phase"))
        for message in messages
    )


def _log_field(message, field_name):
    prefix = f"{field_name}="
    for part in message.split():
        if part.startswith(prefix):
            return part.removeprefix(prefix)
    return ""

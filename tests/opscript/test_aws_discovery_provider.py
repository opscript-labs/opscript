from opscript.config import DEFAULT_DISCOVERY_SCOPE
import logging

import pytest

from opscript.logger import format_log_event
from opscript.execution import (
    activate_execution,
    active_execution_log_fields,
    create_execution,
    get_active_execution,
)
from opscript.provider.aws import AWSDiscoveryProvider
from platformiq.core import Identifier
from platformiq.errors.provider import ProviderError
from platformiq.model import Resource, Snapshot
from platformiq.serialization import SnapshotSerializer

TEST_SCOPE = DEFAULT_DISCOVERY_SCOPE


class FakeEC2Discovery:
    def discover(self):
        return ()


class SuccessfulEC2Discovery:
    def discover(self):
        return (
            Resource(
                id=Identifier.new(),
                external_id="ec2-resource",
            ),
        )


class FakeLambdaDiscovery:
    def discover(self):
        return ()


class FailingLambdaDiscovery:
    def discover(self):
        raise ProviderError("lambda discovery failed")


class FailingDiscovery:
    def __init__(self, error):
        self.error = error

    def discover(self):
        raise self.error


class ServiceLoggingDiscovery:
    def discover(self):
        logging.getLogger("opscript").info(
            format_log_event(
                "aws_discovery_service_started",
                provider="aws",
                service="fake",
                **active_execution_log_fields(),
            )
        )
        logging.getLogger("opscript").info(
            format_log_event(
                "aws_discovery_service_completed",
                provider="aws",
                service="fake",
                resource_count=0,
                page_count=1,
                duration_ms=0,
                **active_execution_log_fields(),
            )
        )
        return ()


class FakeS3Discovery:
    def __init__(self):
        self.called = False

    def discover(self):
        self.called = True
        return ()


class FakeRDSDiscovery:
    def __init__(self):
        self.called = False

    def discover(self):
        self.called = True
        return ()


class FakeECRDiscovery:
    def __init__(self):
        self.called = False

    def discover(self):
        self.called = True
        return ()


class FakeEventBridgeDiscovery:
    def __init__(self):
        self.called = False

    def discover(self):
        self.called = True
        return ()


class FakeAPIGatewayDiscovery:
    def __init__(self):
        self.called = False

    def discover(self):
        self.called = True
        return (
            Resource(
                id=Identifier.new(),
                external_id="api-gateway-resource",
            ),
        )


class FakeSQSDiscovery:
    def __init__(self):
        self.called = False

    def discover(self):
        self.called = True
        return (
            Resource(
                id=Identifier.new(),
                external_id="sqs-resource",
            ),
        )


class FakeSNSDiscovery:
    def __init__(self):
        self.called = False

    def discover(self):
        self.called = True
        return (
            Resource(
                id=Identifier.new(),
                external_id="sns-resource",
            ),
        )


def _field(message: str, name: str) -> str | None:
    prefix = f"{name}="
    for part in message.split():
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


def test_aws_discovery_provider_returns_snapshot():
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        FakeEC2Discovery(),
        FakeLambdaDiscovery(),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )

    snapshot = provider.discover()

    assert isinstance(snapshot, Snapshot)
    assert [resource.external_id for resource in snapshot.resources] == [
        "api-gateway-resource",
        "sqs-resource",
        "sns-resource",
    ]


def test_aws_discovery_provider_logs_aggregate_start_and_completion(caplog):
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        FakeEC2Discovery(),
        FakeLambdaDiscovery(),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        provider.discover()

    messages = [record.message for record in caplog.records]
    started = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_started ")
    ]
    completed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_completed ")
    ]

    assert len(started) == 1
    assert "provider=aws" in started[0]
    assert len(completed) == 1
    assert "provider=aws" in completed[0]
    assert "resource_count=3" in completed[0]
    assert "service_count=9" in completed[0]
    assert "duration_ms=" in completed[0]
    assert "execution_id=" not in started[0]
    assert "execution_id=" not in completed[0]
    assert get_active_execution() is None


def test_aggregate_discovery_lifecycle_uses_active_execution_identity(caplog):
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        FakeEC2Discovery(),
        FakeLambdaDiscovery(),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        provider.discover()

    messages = [record.message for record in caplog.records]
    started = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_started ")
    ]
    completed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_completed ")
    ]
    failed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_failed ")
    ]

    assert len(started) == 1
    assert len(completed) == 1
    assert failed == []
    assert _field(started[0], "execution_id") == execution.identity
    assert _field(completed[0], "execution_id") == execution.identity
    assert "provider=aws" in started[0]
    assert "provider=aws" in completed[0]
    assert "resource_count=3" in completed[0]
    assert "service_count=9" in completed[0]
    assert get_active_execution() is None


def test_aggregate_discovery_execution_identity_stays_out_of_snapshot_serialization():
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        FakeEC2Discovery(),
        FakeLambdaDiscovery(),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )
    execution = create_execution()

    with activate_execution(execution):
        snapshot = provider.discover()
        data = SnapshotSerializer().serialize(snapshot)

    assert execution.identity not in str(data)
    assert "execution" not in data
    assert snapshot.discovery_scope == TEST_SCOPE
    assert get_active_execution() is None


def test_aws_discovery_provider_logs_failure_once_and_reraises_original_exception(
    caplog,
):
    error = ProviderError("aggregate discovery failed")
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        FakeEC2Discovery(),
        FailingDiscovery(error),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(ProviderError) as captured:
            provider.discover()

    messages = [record.message for record in caplog.records]
    started = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_started ")
    ]
    failed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_failed ")
    ]
    completed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_completed ")
    ]

    assert captured.value is error
    assert len(started) == 1
    assert len(failed) == 1
    assert "provider=aws" in failed[0]
    assert "duration_ms=" in failed[0]
    assert "aggregate discovery failed" not in failed[0]
    assert "execution_id=" not in started[0]
    assert "execution_id=" not in failed[0]
    assert completed == []
    assert get_active_execution() is None


def test_aggregate_discovery_failure_uses_active_execution_identity(caplog):
    error = ProviderError("aggregate discovery failed")
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        FakeEC2Discovery(),
        FailingDiscovery(error),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        with pytest.raises(ProviderError) as captured:
            provider.discover()

    messages = [record.message for record in caplog.records]
    started = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_started ")
    ]
    failed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_failed ")
    ]
    completed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_completed ")
    ]

    assert captured.value is error
    assert len(started) == 1
    assert len(failed) == 1
    assert completed == []
    assert _field(started[0], "execution_id") == execution.identity
    assert _field(failed[0], "execution_id") == execution.identity
    assert "aggregate discovery failed" not in failed[0]
    assert get_active_execution() is None


def test_aws_discovery_provider_does_not_suppress_service_logs(caplog):
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        ServiceLoggingDiscovery(),
        FakeLambdaDiscovery(),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        provider.discover()

    messages = [record.message for record in caplog.records]
    service_started = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_service_started ")
    ]
    service_completed = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_service_completed ")
    ]

    assert len(service_started) == 1
    assert "service=fake" in service_started[0]
    assert len(service_completed) == 1
    assert "service=fake" in service_completed[0]


def test_service_specific_discovery_events_use_active_execution_identity(caplog):
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        ServiceLoggingDiscovery(),
        FakeLambdaDiscovery(),
        FakeS3Discovery(),
        FakeRDSDiscovery(),
        FakeECRDiscovery(),
        FakeEventBridgeDiscovery(),
        FakeAPIGatewayDiscovery(),
        FakeSQSDiscovery(),
        FakeSNSDiscovery(),
    )
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        provider.discover()

    messages = [record.message for record in caplog.records]
    service_messages = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_service_")
    ]
    aggregate_messages = [
        message
        for message in messages
        if message.startswith("event=aws_discovery_started ")
        or message.startswith("event=aws_discovery_completed ")
    ]

    assert service_messages
    assert aggregate_messages
    assert all(
        _field(message, "execution_id") == execution.identity
        for message in service_messages
    )
    assert all(
        _field(message, "execution_id") == execution.identity
        for message in aggregate_messages
    )
    assert get_active_execution() is None


def test_aws_discovery_provider_fails_without_returning_partial_snapshot():
    s3_discovery = FakeS3Discovery()
    rds_discovery = FakeRDSDiscovery()
    ecr_discovery = FakeECRDiscovery()
    eventbridge_discovery = FakeEventBridgeDiscovery()
    api_gateway_discovery = FakeAPIGatewayDiscovery()
    sqs_discovery = FakeSQSDiscovery()
    sns_discovery = FakeSNSDiscovery()
    provider = AWSDiscoveryProvider(
        TEST_SCOPE,
        SuccessfulEC2Discovery(),
        FailingLambdaDiscovery(),
        s3_discovery,
        rds_discovery,
        ecr_discovery,
        eventbridge_discovery,
        api_gateway_discovery,
        sqs_discovery,
        sns_discovery,
    )

    with pytest.raises(ProviderError, match="lambda discovery failed"):
        provider.discover()

    assert s3_discovery.called is False
    assert rds_discovery.called is False
    assert ecr_discovery.called is False
    assert eventbridge_discovery.called is False
    assert api_gateway_discovery.called is False
    assert sqs_discovery.called is False
    assert sns_discovery.called is False

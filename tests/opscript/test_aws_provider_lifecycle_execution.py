import logging

import pytest

from opscript.execution import (
    activate_execution,
    create_execution,
    get_active_execution,
)
from opscript.provider.aws.api_gateway.discovery import APIGatewayDiscovery
from opscript.provider.aws.api_gateway.mapper import APIGatewayResourceMapper
from opscript.provider.aws.ec2.discovery import EC2Discovery
from opscript.provider.aws.ec2.mapper import EC2ResourceMapper
from opscript.provider.aws.ecr.discovery import ECRDiscovery
from opscript.provider.aws.ecr.mapper import ECRResourceMapper
from opscript.provider.aws.eventbridge.discovery import EventBridgeDiscovery
from opscript.provider.aws.eventbridge.mapper import EventBridgeResourceMapper
from opscript.provider.aws.lambda_function.discovery import LambdaDiscovery
from opscript.provider.aws.lambda_function.mapper import LambdaResourceMapper
from opscript.provider.aws.rds.discovery import RDSDiscovery
from opscript.provider.aws.rds.mapper import RDSResourceMapper
from opscript.provider.aws.s3.discovery import S3Discovery
from opscript.provider.aws.s3.mapper import S3ResourceMapper
from opscript.provider.aws.sns.discovery import SNSDiscovery
from opscript.provider.aws.sns.mapper import SNSResourceMapper
from opscript.provider.aws.sqs.discovery import SQSDiscovery
from opscript.provider.aws.sqs.mapper import SQSResourceMapper


class EmptyResponseClient:
    def __init__(self, operation_name: str, response: dict):
        self.operation_name = operation_name
        self.response = response
        self.calls = 0

    def __getattr__(self, name: str):
        if name != self.operation_name:
            raise AttributeError(name)

        def operation():
            self.calls += 1
            return self.response

        return operation


class FailingClient:
    def __init__(self, operation_name: str):
        self.operation_name = operation_name

    def __getattr__(self, name: str):
        if name != self.operation_name:
            raise AttributeError(name)

        def operation():
            raise RuntimeError("provider payload should stay out of lifecycle logs")

        return operation


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class PaginatedEC2Client:
    def __init__(self):
        self.paginator_requests = 0

    def get_paginator(self, operation_name):
        assert operation_name == "describe_instances"
        self.paginator_requests += 1
        return FakePaginator(
            (
                {"Reservations": []},
                {"Reservations": []},
            )
        )


PROVIDER_CASES = (
    pytest.param(
        EC2Discovery,
        EC2ResourceMapper,
        "ec2",
        "describe_instances",
        {"Reservations": []},
        id="ec2",
    ),
    pytest.param(
        LambdaDiscovery,
        LambdaResourceMapper,
        "lambda",
        "list_functions",
        {"Functions": []},
        id="lambda",
    ),
    pytest.param(
        S3Discovery,
        S3ResourceMapper,
        "s3",
        "list_buckets",
        {"Buckets": []},
        id="s3",
    ),
    pytest.param(
        RDSDiscovery,
        RDSResourceMapper,
        "rds",
        "describe_db_instances",
        {"DBInstances": []},
        id="rds",
    ),
    pytest.param(
        ECRDiscovery,
        ECRResourceMapper,
        "ecr",
        "describe_repositories",
        {"repositories": []},
        id="ecr",
    ),
    pytest.param(
        EventBridgeDiscovery,
        EventBridgeResourceMapper,
        "eventbridge",
        "list_rules",
        {"Rules": []},
        id="eventbridge",
    ),
    pytest.param(
        APIGatewayDiscovery,
        APIGatewayResourceMapper,
        "api_gateway",
        "get_rest_apis",
        {"items": []},
        id="api_gateway",
    ),
    pytest.param(
        SQSDiscovery,
        SQSResourceMapper,
        "sqs",
        "list_queues",
        {},
        id="sqs",
    ),
    pytest.param(
        SNSDiscovery,
        SNSResourceMapper,
        "sns",
        "list_topics",
        {"Topics": []},
        id="sns",
    ),
)


def _field(message: str, name: str) -> str | None:
    prefix = f"{name}="
    for part in message.split():
        if part.startswith(prefix):
            return part[len(prefix) :]
    return None


def _messages(caplog, prefix: str) -> list[str]:
    return [
        record.message for record in caplog.records if record.message.startswith(prefix)
    ]


@pytest.mark.parametrize(
    ("discovery_class", "mapper_class", "service", "operation_name", "response"),
    PROVIDER_CASES,
)
def test_provider_lifecycle_omits_execution_identity_without_active_execution(
    discovery_class,
    mapper_class,
    service,
    operation_name,
    response,
    caplog,
):
    discovery = discovery_class(
        EmptyResponseClient(operation_name, response),
        mapper_class(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        resources = discovery.discover()

    started = _messages(caplog, "event=aws_discovery_service_started ")
    completed = _messages(caplog, "event=aws_discovery_service_completed ")
    failed = _messages(caplog, "event=aws_discovery_service_failed ")

    assert resources == ()
    assert len(started) == 1
    assert len(completed) == 1
    assert failed == []
    assert f"service={service}" in started[0]
    assert f"service={service}" in completed[0]
    assert "execution_id=" not in started[0]
    assert "execution_id=" not in completed[0]
    assert get_active_execution() is None


@pytest.mark.parametrize(
    ("discovery_class", "mapper_class", "service", "operation_name", "response"),
    PROVIDER_CASES,
)
def test_provider_lifecycle_uses_active_execution_identity(
    discovery_class,
    mapper_class,
    service,
    operation_name,
    response,
    caplog,
):
    discovery = discovery_class(
        EmptyResponseClient(operation_name, response),
        mapper_class(),
    )
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        resources = discovery.discover()

    started = _messages(caplog, "event=aws_discovery_service_started ")
    completed = _messages(caplog, "event=aws_discovery_service_completed ")
    failed = _messages(caplog, "event=aws_discovery_service_failed ")

    assert resources == ()
    assert len(started) == 1
    assert len(completed) == 1
    assert failed == []
    assert f"service={service}" in started[0]
    assert f"service={service}" in completed[0]
    assert _field(started[0], "execution_id") == execution.identity
    assert _field(completed[0], "execution_id") == execution.identity
    assert get_active_execution() is None


@pytest.mark.parametrize(
    ("discovery_class", "mapper_class", "service", "operation_name", "response"),
    PROVIDER_CASES,
)
def test_provider_failure_lifecycle_omits_execution_identity_without_active_execution(
    discovery_class,
    mapper_class,
    service,
    operation_name,
    response,
    caplog,
):
    discovery = discovery_class(
        FailingClient(operation_name),
        mapper_class(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        with pytest.raises(RuntimeError, match="provider payload"):
            discovery.discover()

    started = _messages(caplog, "event=aws_discovery_service_started ")
    completed = _messages(caplog, "event=aws_discovery_service_completed ")
    failed = _messages(caplog, "event=aws_discovery_service_failed ")

    assert len(started) == 1
    assert completed == []
    assert len(failed) == 1
    assert f"service={service}" in started[0]
    assert f"service={service}" in failed[0]
    assert "execution_id=" not in started[0]
    assert "execution_id=" not in failed[0]
    assert "provider payload should stay out of lifecycle logs" not in failed[0]
    assert response is not None
    assert get_active_execution() is None


@pytest.mark.parametrize(
    ("discovery_class", "mapper_class", "service", "operation_name", "response"),
    PROVIDER_CASES,
)
def test_provider_failure_lifecycle_uses_active_execution_identity(
    discovery_class,
    mapper_class,
    service,
    operation_name,
    response,
    caplog,
):
    discovery = discovery_class(
        FailingClient(operation_name),
        mapper_class(),
    )
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        with pytest.raises(RuntimeError, match="provider payload"):
            discovery.discover()

    started = _messages(caplog, "event=aws_discovery_service_started ")
    completed = _messages(caplog, "event=aws_discovery_service_completed ")
    failed = _messages(caplog, "event=aws_discovery_service_failed ")

    assert len(started) == 1
    assert completed == []
    assert len(failed) == 1
    assert f"service={service}" in started[0]
    assert f"service={service}" in failed[0]
    assert _field(started[0], "execution_id") == execution.identity
    assert _field(failed[0], "execution_id") == execution.identity
    assert "provider payload should stay out of lifecycle logs" not in failed[0]
    assert response is not None
    assert get_active_execution() is None


def test_provider_pagination_uses_one_execution_identity_for_service_lifecycle(
    caplog,
):
    client = PaginatedEC2Client()
    discovery = EC2Discovery(client, EC2ResourceMapper())
    execution = create_execution()

    with (
        activate_execution(execution),
        caplog.at_level(logging.INFO, logger="opscript"),
    ):
        resources = discovery.discover()

    started = _messages(caplog, "event=aws_discovery_service_started ")
    completed = _messages(caplog, "event=aws_discovery_service_completed ")
    failed = _messages(caplog, "event=aws_discovery_service_failed ")

    assert resources == ()
    assert client.paginator_requests == 1
    assert len(started) == 1
    assert len(completed) == 1
    assert failed == []
    assert _field(started[0], "execution_id") == execution.identity
    assert _field(completed[0], "execution_id") == execution.identity
    assert "page_count=2" in completed[0]
    assert get_active_execution() is None

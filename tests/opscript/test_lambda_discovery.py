import logging

import pytest

from opscript.provider.aws.lambda_function.discovery import LambdaDiscovery
from opscript.provider.aws.lambda_function.mapper import LambdaResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


class FakeLambdaClient:
    def list_functions(self):
        return {"Functions": [{"FunctionName": "opscript-processor"}]}


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class FakePaginatedLambdaClient:
    def get_paginator(self, operation_name):
        assert operation_name == "list_functions"
        return FakePaginator(
            (
                {"Functions": [{"FunctionName": "first-function"}]},
                {"Functions": [{"FunctionName": "second-function"}]},
            )
        )


class FailingLambdaClient:
    def list_functions(self):
        raise RuntimeError("lambda unavailable")


def test_lambda_discovery_returns_resources():

    discovery = LambdaDiscovery(
        FakeLambdaClient(),
        LambdaResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == "opscript-processor"


def test_lambda_discovery_logs_start_and_completion(caplog):
    discovery = LambdaDiscovery(
        FakeLambdaClient(),
        LambdaResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=lambda",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=lambda",
    )


def test_lambda_discovery_handles_multiple_pages():
    discovery = LambdaDiscovery(
        FakePaginatedLambdaClient(),
        LambdaResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [
        "first-function",
        "second-function",
    ]


def test_lambda_discovery_logs_paginated_page_count(caplog):
    discovery = LambdaDiscovery(
        FakePaginatedLambdaClient(),
        LambdaResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "page_count=2",
        "resource_count=2",
        "service=lambda",
    )


def test_lambda_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = LambdaDiscovery(
        FailingLambdaClient(),
        LambdaResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="lambda unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=lambda",
    )

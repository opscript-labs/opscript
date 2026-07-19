import logging

import pytest

from opscript.provider.aws.sqs.discovery import SQSDiscovery
from opscript.provider.aws.sqs.mapper import SQSResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/123456789012/opscript-queue"


class FakeSQSClient:
    def list_queues(self):
        return {"QueueUrls": [QUEUE_URL]}


class EmptySQSClient:
    def list_queues(self):
        return {}


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class FakePaginatedSQSClient:
    def get_paginator(self, operation_name):
        assert operation_name == "list_queues"
        return FakePaginator(
            (
                {"QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123/first"]},
                {"QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123/second"]},
            )
        )


class FailingSQSClient:
    def list_queues(self):
        raise RuntimeError("sqs unavailable")


def test_sqs_discovery_returns_resources():
    discovery = SQSDiscovery(
        FakeSQSClient(),
        SQSResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == QUEUE_URL
    assert resources[0].state.properties == {}


def test_sqs_discovery_handles_empty_responses():
    discovery = SQSDiscovery(
        EmptySQSClient(),
        SQSResourceMapper(),
    )

    assert discovery.discover() == ()


def test_sqs_discovery_uses_direct_call_fallback():
    discovery = SQSDiscovery(
        FakeSQSClient(),
        SQSResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [QUEUE_URL]


def test_sqs_discovery_logs_start_and_completion(caplog):
    discovery = SQSDiscovery(
        FakeSQSClient(),
        SQSResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=sqs",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=sqs",
    )


def test_sqs_discovery_handles_multiple_pages():
    discovery = SQSDiscovery(
        FakePaginatedSQSClient(),
        SQSResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [
        "https://sqs.us-east-1.amazonaws.com/123/first",
        "https://sqs.us-east-1.amazonaws.com/123/second",
    ]


def test_sqs_discovery_logs_paginated_page_count(caplog):
    discovery = SQSDiscovery(
        FakePaginatedSQSClient(),
        SQSResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "page_count=2",
        "resource_count=2",
        "service=sqs",
    )


def test_sqs_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = SQSDiscovery(
        FailingSQSClient(),
        SQSResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="sqs unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=sqs",
    )

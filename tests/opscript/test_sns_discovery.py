import logging

import pytest

from opscript.provider.aws.sns.discovery import SNSDiscovery
from opscript.provider.aws.sns.mapper import SNSResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:opscript-topic"


class FakeSNSClient:
    def list_topics(self):
        return {"Topics": [{"TopicArn": TOPIC_ARN}]}


class EmptySNSClient:
    def list_topics(self):
        return {}


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class FakePaginatedSNSClient:
    def get_paginator(self, operation_name):
        assert operation_name == "list_topics"
        return FakePaginator(
            (
                {"Topics": [{"TopicArn": "arn:aws:sns:us-east-1:123:first"}]},
                {"Topics": [{"TopicArn": "arn:aws:sns:us-east-1:123:second"}]},
            )
        )


class FailingSNSClient:
    def list_topics(self):
        raise RuntimeError("sns unavailable")


def test_sns_discovery_returns_resources():
    discovery = SNSDiscovery(
        FakeSNSClient(),
        SNSResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == TOPIC_ARN
    assert resources[0].state.properties == {}


def test_sns_discovery_handles_empty_responses():
    discovery = SNSDiscovery(
        EmptySNSClient(),
        SNSResourceMapper(),
    )

    assert discovery.discover() == ()


def test_sns_discovery_uses_direct_call_fallback():
    discovery = SNSDiscovery(
        FakeSNSClient(),
        SNSResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [TOPIC_ARN]


def test_sns_discovery_logs_start_and_completion(caplog):
    discovery = SNSDiscovery(
        FakeSNSClient(),
        SNSResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=sns",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=sns",
    )


def test_sns_discovery_handles_multiple_pages():
    discovery = SNSDiscovery(
        FakePaginatedSNSClient(),
        SNSResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [
        "arn:aws:sns:us-east-1:123:first",
        "arn:aws:sns:us-east-1:123:second",
    ]


def test_sns_discovery_logs_paginated_page_count(caplog):
    discovery = SNSDiscovery(
        FakePaginatedSNSClient(),
        SNSResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "page_count=2",
        "resource_count=2",
        "service=sns",
    )


def test_sns_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = SNSDiscovery(
        FailingSNSClient(),
        SNSResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="sns unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=sns",
    )

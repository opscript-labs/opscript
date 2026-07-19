import logging

import pytest

from opscript.provider.aws.eventbridge.discovery import EventBridgeDiscovery
from opscript.provider.aws.eventbridge.mapper import EventBridgeResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


class FakeEventBridgeClient:
    def list_rules(self):
        return {
            "Rules": [
                {
                    "Name": "opscript-schedule",
                    "Arn": (
                        "arn:aws:events:us-east-1:123456789012:rule/opscript-schedule"
                    ),
                    "EventBusName": "default",
                    "State": "ENABLED",
                    "ScheduleExpression": "rate(1 hour)",
                    "EventPattern": '{"source":["aws.ec2"]}',
                    "Description": "Opscript scheduled run",
                }
            ]
        }


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class FakePaginatedEventBridgeClient:
    def get_paginator(self, operation_name):
        assert operation_name == "list_rules"
        return FakePaginator(
            (
                {"Rules": [{"Name": "first-rule"}]},
                {"Rules": [{"Name": "second-rule"}]},
            )
        )


class FailingEventBridgeClient:
    def list_rules(self):
        raise RuntimeError("eventbridge unavailable")


def test_eventbridge_discovery_returns_resources():
    discovery = EventBridgeDiscovery(
        FakeEventBridgeClient(),
        EventBridgeResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == "opscript-schedule"
    assert resources[0].state.properties == {
        "arn": "arn:aws:events:us-east-1:123456789012:rule/opscript-schedule",
        "event_bus_name": "default",
        "state": "ENABLED",
        "schedule_expression": "rate(1 hour)",
        "event_pattern": '{"source":["aws.ec2"]}',
        "description": "Opscript scheduled run",
    }


def test_eventbridge_discovery_logs_start_and_completion(caplog):
    discovery = EventBridgeDiscovery(
        FakeEventBridgeClient(),
        EventBridgeResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=eventbridge",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=eventbridge",
    )


def test_eventbridge_discovery_handles_multiple_pages():
    discovery = EventBridgeDiscovery(
        FakePaginatedEventBridgeClient(),
        EventBridgeResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [
        "first-rule",
        "second-rule",
    ]


def test_eventbridge_discovery_logs_paginated_page_count(caplog):
    discovery = EventBridgeDiscovery(
        FakePaginatedEventBridgeClient(),
        EventBridgeResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "page_count=2",
        "resource_count=2",
        "service=eventbridge",
    )


def test_eventbridge_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = EventBridgeDiscovery(
        FailingEventBridgeClient(),
        EventBridgeResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="eventbridge unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=eventbridge",
    )

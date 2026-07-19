import logging

import pytest

from opscript.provider.aws.ec2.discovery import EC2Discovery
from opscript.provider.aws.ec2.mapper import EC2ResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


class FakeEC2Client:
    def describe_instances(self):
        return {"Reservations": [{"Instances": [{"InstanceId": "i-12345"}]}]}


class FakeTaggedEC2Client:
    def describe_instances(self):
        return {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-tagged",
                            "Tags": [
                                {
                                    "Key": "Environment",
                                    "Value": "prod",
                                },
                                {
                                    "Key": "Owner",
                                    "Value": "platform",
                                },
                            ],
                        }
                    ]
                }
            ]
        }


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class FakePaginatedEC2Client:
    def get_paginator(self, operation_name):
        assert operation_name == "describe_instances"
        return FakePaginator(
            (
                {"Reservations": [{"Instances": [{"InstanceId": "i-first"}]}]},
                {"Reservations": [{"Instances": [{"InstanceId": "i-second"}]}]},
            )
        )


class FailingEC2Client:
    def describe_instances(self):
        raise RuntimeError("ec2 unavailable")


def test_ec2_discovery_returns_resources():

    discovery = EC2Discovery(
        FakeEC2Client(),
        EC2ResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == "i-12345"


def test_ec2_discovery_passes_instance_tags_to_mapper():
    discovery = EC2Discovery(
        FakeTaggedEC2Client(),
        EC2ResourceMapper(),
    )

    resources = discovery.discover()

    assert resources[0].external_id == "i-tagged"
    assert resources[0].state.properties["tags"] == {
        "Environment": "prod",
        "Owner": "platform",
    }


def test_ec2_discovery_accepts_missing_tags():
    discovery = EC2Discovery(
        FakeEC2Client(),
        EC2ResourceMapper(),
    )

    resources = discovery.discover()

    assert resources[0].state.properties["tags"] == {}


def test_ec2_discovery_logs_start_and_completion(caplog):
    discovery = EC2Discovery(
        FakeEC2Client(),
        EC2ResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=ec2",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=ec2",
    )


def test_ec2_discovery_handles_multiple_pages():
    discovery = EC2Discovery(
        FakePaginatedEC2Client(),
        EC2ResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [
        "i-first",
        "i-second",
    ]


def test_ec2_discovery_logs_paginated_page_count(caplog):
    discovery = EC2Discovery(
        FakePaginatedEC2Client(),
        EC2ResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "page_count=2",
        "resource_count=2",
        "service=ec2",
    )


def test_ec2_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = EC2Discovery(
        FailingEC2Client(),
        EC2ResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="ec2 unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=ec2",
    )

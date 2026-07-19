import logging

import pytest

from opscript.provider.aws.rds.discovery import RDSDiscovery
from opscript.provider.aws.rds.mapper import RDSResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


class FakeRDSClient:
    def describe_db_instances(self):
        return {
            "DBInstances": [
                {
                    "DBInstanceIdentifier": "opscript-db",
                    "Engine": "postgres",
                    "EngineVersion": "16.3",
                    "DBInstanceClass": "db.t4g.micro",
                    "MultiAZ": True,
                    "PubliclyAccessible": False,
                    "AllocatedStorage": 20,
                    "StorageType": "gp3",
                }
            ]
        }


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class FakePaginatedRDSClient:
    def get_paginator(self, operation_name):
        assert operation_name == "describe_db_instances"
        return FakePaginator(
            (
                {"DBInstances": [{"DBInstanceIdentifier": "first-db"}]},
                {"DBInstances": [{"DBInstanceIdentifier": "second-db"}]},
            )
        )


class FailingRDSClient:
    def describe_db_instances(self):
        raise RuntimeError("rds unavailable")


def test_rds_discovery_returns_resources():

    discovery = RDSDiscovery(
        FakeRDSClient(),
        RDSResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == "opscript-db"
    assert resources[0].state.properties == {
        "engine": "postgres",
        "engine_version": "16.3",
        "instance_class": "db.t4g.micro",
        "multi_az": True,
        "publicly_accessible": False,
        "allocated_storage": 20,
        "storage_type": "gp3",
    }


def test_rds_discovery_logs_start_and_completion(caplog):
    discovery = RDSDiscovery(
        FakeRDSClient(),
        RDSResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=rds",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=rds",
    )


def test_rds_discovery_handles_multiple_pages():
    discovery = RDSDiscovery(
        FakePaginatedRDSClient(),
        RDSResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [
        "first-db",
        "second-db",
    ]


def test_rds_discovery_logs_paginated_page_count(caplog):
    discovery = RDSDiscovery(
        FakePaginatedRDSClient(),
        RDSResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "page_count=2",
        "resource_count=2",
        "service=rds",
    )


def test_rds_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = RDSDiscovery(
        FailingRDSClient(),
        RDSResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="rds unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=rds",
    )

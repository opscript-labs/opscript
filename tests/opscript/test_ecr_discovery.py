import logging

import pytest

from opscript.provider.aws.ecr.discovery import ECRDiscovery
from opscript.provider.aws.ecr.mapper import ECRResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


class FakeECRClient:
    def describe_repositories(self):
        return {
            "repositories": [
                {
                    "repositoryName": "opscript/app",
                    "repositoryUri": (
                        "123456789012.dkr.ecr.us-east-1.amazonaws.com/opscript/app"
                    ),
                    "registryId": "123456789012",
                    "imageTagMutability": "MUTABLE",
                    "imageScanningConfiguration": {"scanOnPush": True},
                    "encryptionConfiguration": {"encryptionType": "AES256"},
                    "repositoryArn": (
                        "arn:aws:ecr:us-east-1:123456789012:repository/opscript/app"
                    ),
                    "createdAt": "2026-07-10T00:00:00Z",
                }
            ]
        }


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class FakePaginatedECRClient:
    def get_paginator(self, operation_name):
        assert operation_name == "describe_repositories"
        return FakePaginator(
            (
                {"repositories": [{"repositoryName": "first-repository"}]},
                {"repositories": [{"repositoryName": "second-repository"}]},
            )
        )


class FailingECRClient:
    def describe_repositories(self):
        raise RuntimeError("ecr unavailable")


def test_ecr_discovery_returns_resources():

    discovery = ECRDiscovery(
        FakeECRClient(),
        ECRResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == "opscript/app"
    assert resources[0].state.properties == {
        "repository_uri": ("123456789012.dkr.ecr.us-east-1.amazonaws.com/opscript/app"),
        "registry_id": "123456789012",
        "image_tag_mutability": "MUTABLE",
        "image_scanning_configuration": {"scanOnPush": True},
        "encryption_configuration": {"encryptionType": "AES256"},
        "repository_arn": (
            "arn:aws:ecr:us-east-1:123456789012:repository/opscript/app"
        ),
        "created_at": "2026-07-10T00:00:00Z",
    }


def test_ecr_discovery_logs_start_and_completion(caplog):
    discovery = ECRDiscovery(
        FakeECRClient(),
        ECRResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=ecr",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=ecr",
    )


def test_ecr_discovery_handles_multiple_pages():
    discovery = ECRDiscovery(
        FakePaginatedECRClient(),
        ECRResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [
        "first-repository",
        "second-repository",
    ]


def test_ecr_discovery_logs_paginated_page_count(caplog):
    discovery = ECRDiscovery(
        FakePaginatedECRClient(),
        ECRResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "page_count=2",
        "resource_count=2",
        "service=ecr",
    )


def test_ecr_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = ECRDiscovery(
        FailingECRClient(),
        ECRResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="ecr unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=ecr",
    )

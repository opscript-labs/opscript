import logging

import pytest

from opscript.provider.aws.s3.discovery import S3Discovery
from opscript.provider.aws.s3.mapper import S3ResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


class FakeS3Client:
    def list_buckets(self):
        return {"Buckets": [{"Name": "opscript-state"}]}


class FailingS3Client:
    def list_buckets(self):
        raise RuntimeError("s3 unavailable")


def test_s3_discovery_returns_resources():

    discovery = S3Discovery(
        FakeS3Client(),
        S3ResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == "opscript-state"


def test_s3_discovery_logs_start_and_completion(caplog):
    discovery = S3Discovery(
        FakeS3Client(),
        S3ResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=s3",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=s3",
    )


def test_s3_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = S3Discovery(
        FailingS3Client(),
        S3ResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="s3 unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=s3",
    )

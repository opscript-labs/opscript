import logging

import pytest

from opscript.provider.aws.api_gateway.discovery import APIGatewayDiscovery
from opscript.provider.aws.api_gateway.mapper import APIGatewayResourceMapper
from platformiq.model import Resource


def assert_log_contains_all(
    messages: list[str],
    *parts: str,
) -> None:
    assert any(all(part in message for part in parts) for message in messages)


class FakeAPIGatewayClient:
    def get_rest_apis(self):
        return {
            "items": [
                {
                    "id": "abc123",
                    "name": "opscript-api",
                    "description": "Opscript REST API",
                    "createdDate": "2026-07-10T00:00:00Z",
                    "version": "v1",
                    "apiKeySource": "HEADER",
                    "endpointConfiguration": {"types": ["REGIONAL"]},
                    "binaryMediaTypes": ["application/octet-stream"],
                    "minimumCompressionSize": 1024,
                    "disableExecuteApiEndpoint": False,
                    "policy": '{"Version":"2012-10-17"}',
                    "warnings": ["warning"],
                    "tags": {"Environment": "prod"},
                }
            ]
        }


class EmptyAPIGatewayClient:
    def get_rest_apis(self):
        return {"items": []}


class FakePaginator:
    def __init__(self, pages):
        self.pages = pages

    def paginate(self):
        return self.pages


class FakePaginatedAPIGatewayClient:
    def get_paginator(self, operation_name):
        assert operation_name == "get_rest_apis"
        return FakePaginator(
            (
                {"items": [{"id": "first-api"}]},
                {"items": [{"id": "second-api"}]},
            )
        )


class FailingAPIGatewayClient:
    def get_rest_apis(self):
        raise RuntimeError("api gateway unavailable")


def test_api_gateway_discovery_returns_resources():
    discovery = APIGatewayDiscovery(
        FakeAPIGatewayClient(),
        APIGatewayResourceMapper(),
    )

    resources = discovery.discover()

    assert len(resources) == 1
    assert isinstance(resources[0], Resource)
    assert resources[0].external_id == "abc123"
    assert resources[0].state.properties == {
        "name": "opscript-api",
        "description": "Opscript REST API",
        "created_date": "2026-07-10T00:00:00Z",
        "version": "v1",
        "api_key_source": "HEADER",
        "endpoint_configuration": {"types": ["REGIONAL"]},
        "binary_media_types": ["application/octet-stream"],
        "minimum_compression_size": 1024,
        "disable_execute_api_endpoint": False,
        "policy": '{"Version":"2012-10-17"}',
        "warnings": ["warning"],
        "tags": {"Environment": "prod"},
    }


def test_api_gateway_discovery_handles_empty_responses():
    discovery = APIGatewayDiscovery(
        EmptyAPIGatewayClient(),
        APIGatewayResourceMapper(),
    )

    assert discovery.discover() == ()


def test_api_gateway_discovery_uses_direct_call_fallback():
    discovery = APIGatewayDiscovery(
        FakeAPIGatewayClient(),
        APIGatewayResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == ["abc123"]


def test_api_gateway_discovery_logs_start_and_completion(caplog):
    discovery = APIGatewayDiscovery(
        FakeAPIGatewayClient(),
        APIGatewayResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_started",
        "provider=aws",
        "service=api_gateway",
    )
    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "duration_ms=",
        "page_count=1",
        "provider=aws",
        "resource_count=1",
        "service=api_gateway",
    )


def test_api_gateway_discovery_handles_multiple_pages():
    discovery = APIGatewayDiscovery(
        FakePaginatedAPIGatewayClient(),
        APIGatewayResourceMapper(),
    )

    resources = discovery.discover()

    assert [resource.external_id for resource in resources] == [
        "first-api",
        "second-api",
    ]


def test_api_gateway_discovery_logs_paginated_page_count(caplog):
    discovery = APIGatewayDiscovery(
        FakePaginatedAPIGatewayClient(),
        APIGatewayResourceMapper(),
    )

    with caplog.at_level(logging.INFO, logger="opscript"):
        discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_completed",
        "page_count=2",
        "resource_count=2",
        "service=api_gateway",
    )


def test_api_gateway_discovery_logs_failure_without_swallowing_exception(caplog):
    discovery = APIGatewayDiscovery(
        FailingAPIGatewayClient(),
        APIGatewayResourceMapper(),
    )

    with caplog.at_level(logging.ERROR, logger="opscript"):
        with pytest.raises(RuntimeError, match="api gateway unavailable"):
            discovery.discover()

    messages = [record.message for record in caplog.records]

    assert_log_contains_all(
        messages,
        "event=aws_discovery_service_failed",
        "duration_ms=",
        "page_count=0",
        "provider=aws",
        "service=api_gateway",
    )

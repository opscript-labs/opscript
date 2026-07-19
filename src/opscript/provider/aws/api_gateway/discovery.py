from __future__ import annotations

from time import perf_counter

from platformiq.model import Resource

from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger

from .mapper import APIGatewayResourceMapper

logger = get_logger()


class APIGatewayDiscovery:
    """
    Discovers AWS API Gateway REST APIs.
    """

    def __init__(
        self,
        client,
        mapper: APIGatewayResourceMapper,
    ):
        self.client = client
        self.mapper = mapper

    def discover(self) -> tuple[Resource, ...]:
        """
        Discover API Gateway REST APIs.
        """

        started_at = perf_counter()
        logger.info(
            format_log_event(
                "aws_discovery_service_started",
                provider="aws",
                service="api_gateway",
                **active_execution_log_fields(),
            )
        )
        resources = []
        page_count = 0

        try:
            for response in self._pages():
                page_count += 1
                for rest_api in response.get("items", []):
                    resources.append(
                        self.mapper.map(
                            rest_api=rest_api,
                        )
                    )
        except Exception:
            logger.error(
                format_log_event(
                    "aws_discovery_service_failed",
                    provider="aws",
                    service="api_gateway",
                    page_count=page_count,
                    duration_ms=self._duration_ms(started_at),
                    **active_execution_log_fields(),
                )
            )
            raise

        logger.info(
            format_log_event(
                "aws_discovery_service_completed",
                provider="aws",
                service="api_gateway",
                resource_count=len(resources),
                page_count=page_count,
                duration_ms=self._duration_ms(started_at),
                **active_execution_log_fields(),
            )
        )

        return tuple(resources)

    def _duration_ms(
        self,
        started_at: float,
    ) -> int:
        return int((perf_counter() - started_at) * 1000)

    def _pages(self):
        if hasattr(self.client, "get_paginator"):
            paginator = self.client.get_paginator("get_rest_apis")
            return paginator.paginate()

        return (self.client.get_rest_apis(),)

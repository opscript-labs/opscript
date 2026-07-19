from __future__ import annotations

from time import perf_counter

from platformiq.model import Resource

from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger

from .mapper import LambdaResourceMapper

logger = get_logger()


class LambdaDiscovery:
    """
    Discovers AWS Lambda functions.
    """

    def __init__(
        self,
        client,
        mapper: LambdaResourceMapper,
    ):
        self.client = client
        self.mapper = mapper

    def discover(self) -> tuple[Resource, ...]:
        """
        Discover Lambda functions.
        """

        started_at = perf_counter()
        logger.info(
            format_log_event(
                "aws_discovery_service_started",
                provider="aws",
                service="lambda",
                **active_execution_log_fields(),
            )
        )
        resources = []
        page_count = 0

        try:
            for response in self._pages():
                page_count += 1
                for function in response.get("Functions", []):
                    resources.append(
                        self.mapper.map(
                            function_name=function["FunctionName"],
                        )
                    )
        except Exception:
            logger.error(
                format_log_event(
                    "aws_discovery_service_failed",
                    provider="aws",
                    service="lambda",
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
                service="lambda",
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
            paginator = self.client.get_paginator("list_functions")
            return paginator.paginate()

        return (self.client.list_functions(),)

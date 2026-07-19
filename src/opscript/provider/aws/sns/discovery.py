from __future__ import annotations

from time import perf_counter

from platformiq.model import Resource

from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger

from .mapper import SNSResourceMapper

logger = get_logger()


class SNSDiscovery:
    """
    Discovers AWS SNS topics.
    """

    def __init__(
        self,
        client,
        mapper: SNSResourceMapper,
    ):
        self.client = client
        self.mapper = mapper

    def discover(self) -> tuple[Resource, ...]:
        """
        Discover SNS topics.
        """

        started_at = perf_counter()
        logger.info(
            format_log_event(
                "aws_discovery_service_started",
                provider="aws",
                service="sns",
                **active_execution_log_fields(),
            )
        )
        resources = []
        page_count = 0

        try:
            for response in self._pages():
                page_count += 1
                for topic in response.get("Topics", []):
                    resources.append(
                        self.mapper.map(
                            topic_arn=topic["TopicArn"],
                        )
                    )
        except Exception:
            logger.error(
                format_log_event(
                    "aws_discovery_service_failed",
                    provider="aws",
                    service="sns",
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
                service="sns",
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
            paginator = self.client.get_paginator("list_topics")
            return paginator.paginate()

        return (self.client.list_topics(),)

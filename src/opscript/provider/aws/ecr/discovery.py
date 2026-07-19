from __future__ import annotations

from time import perf_counter

from platformiq.model import Resource

from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger

from .mapper import ECRResourceMapper

logger = get_logger()


class ECRDiscovery:
    """
    Discovers AWS ECR repositories.
    """

    def __init__(
        self,
        client,
        mapper: ECRResourceMapper,
    ):
        self.client = client
        self.mapper = mapper

    def discover(self) -> tuple[Resource, ...]:
        """
        Discover ECR repositories.
        """

        started_at = perf_counter()
        logger.info(
            format_log_event(
                "aws_discovery_service_started",
                provider="aws",
                service="ecr",
                **active_execution_log_fields(),
            )
        )
        resources = []
        page_count = 0

        try:
            for response in self._pages():
                page_count += 1
                for repository in response.get("repositories", []):
                    resources.append(
                        self.mapper.map(
                            repository=repository,
                        )
                    )
        except Exception:
            logger.error(
                format_log_event(
                    "aws_discovery_service_failed",
                    provider="aws",
                    service="ecr",
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
                service="ecr",
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
            paginator = self.client.get_paginator("describe_repositories")
            return paginator.paginate()

        return (self.client.describe_repositories(),)

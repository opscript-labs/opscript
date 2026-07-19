from __future__ import annotations

from time import perf_counter

from platformiq.model import Resource

from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger

from .mapper import S3ResourceMapper

logger = get_logger()


class S3Discovery:
    """
    Discovers AWS S3 buckets.
    """

    def __init__(
        self,
        client,
        mapper: S3ResourceMapper,
    ):
        self.client = client
        self.mapper = mapper

    def discover(self) -> tuple[Resource, ...]:
        """
        Discover S3 buckets.
        """

        started_at = perf_counter()
        logger.info(
            format_log_event(
                "aws_discovery_service_started",
                provider="aws",
                service="s3",
                **active_execution_log_fields(),
            )
        )

        resources = []
        page_count = 0

        try:
            response = self.client.list_buckets()
            page_count = 1

            for bucket in response.get("Buckets", []):
                resources.append(
                    self.mapper.map(
                        bucket_name=bucket["Name"],
                    )
                )
        except Exception:
            logger.error(
                format_log_event(
                    "aws_discovery_service_failed",
                    provider="aws",
                    service="s3",
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
                service="s3",
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

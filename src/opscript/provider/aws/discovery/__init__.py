from __future__ import annotations

from time import perf_counter

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Snapshot

from opscript.execution import active_execution_log_fields
from opscript.logger import format_log_event, get_logger

from ..api_gateway.discovery import APIGatewayDiscovery
from ..ecr.discovery import ECRDiscovery
from ..ec2.discovery import EC2Discovery
from ..eventbridge.discovery import EventBridgeDiscovery
from ..lambda_function.discovery import LambdaDiscovery
from ..rds.discovery import RDSDiscovery
from ..s3.discovery import S3Discovery
from ..sns.discovery import SNSDiscovery
from ..sqs.discovery import SQSDiscovery


logger = get_logger()


def _aggregate_discovery_lifecycle_fields(**fields: object) -> dict[str, object]:
    return {
        **active_execution_log_fields(),
        **fields,
    }


class AWSDiscoveryProvider:
    """
    Coordinates AWS resource discovery across
    supported AWS services.
    """

    def __init__(
        self,
        discovery_scope: DiscoveryScope,
        ec2_discovery: EC2Discovery,
        lambda_discovery: LambdaDiscovery,
        s3_discovery: S3Discovery,
        rds_discovery: RDSDiscovery,
        ecr_discovery: ECRDiscovery,
        eventbridge_discovery: EventBridgeDiscovery,
        api_gateway_discovery: APIGatewayDiscovery,
        sqs_discovery: SQSDiscovery,
        sns_discovery: SNSDiscovery,
    ):
        self.discovery_scope = discovery_scope
        self.ec2_discovery = ec2_discovery
        self.lambda_discovery = lambda_discovery
        self.s3_discovery = s3_discovery
        self.rds_discovery = rds_discovery
        self.ecr_discovery = ecr_discovery
        self.eventbridge_discovery = eventbridge_discovery
        self.api_gateway_discovery = api_gateway_discovery
        self.sqs_discovery = sqs_discovery
        self.sns_discovery = sns_discovery

    def discover(self) -> Snapshot:
        """
        Discover all supported AWS resources and
        assemble a single snapshot.
        """

        started_at = perf_counter()
        discoveries = (
            self.ec2_discovery,
            self.lambda_discovery,
            self.s3_discovery,
            self.rds_discovery,
            self.ecr_discovery,
            self.eventbridge_discovery,
            self.api_gateway_discovery,
            self.sqs_discovery,
            self.sns_discovery,
        )

        logger.info(
            format_log_event(
                "aws_discovery_started",
                **_aggregate_discovery_lifecycle_fields(provider="aws"),
            )
        )

        try:
            resources = tuple(
                resource
                for discovery in discoveries
                for resource in discovery.discover()
            )
        except Exception:
            logger.error(
                format_log_event(
                    "aws_discovery_failed",
                    **_aggregate_discovery_lifecycle_fields(
                        provider="aws",
                        duration_ms=int((perf_counter() - started_at) * 1000),
                    ),
                )
            )
            raise

        logger.info(
            format_log_event(
                "aws_discovery_completed",
                **_aggregate_discovery_lifecycle_fields(
                    provider="aws",
                    duration_ms=int((perf_counter() - started_at) * 1000),
                    resource_count=len(resources),
                    service_count=len(discoveries),
                ),
            )
        )

        return Snapshot(
            id=Identifier.new(),
            discovery_scope=self.discovery_scope,
            resources=resources,
        )

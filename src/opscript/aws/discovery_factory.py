from __future__ import annotations

from opscript.aws import AWSClientFactory
from opscript.provider.aws import AWSDiscoveryProvider
from opscript.provider.aws.api_gateway.discovery import APIGatewayDiscovery
from opscript.provider.aws.api_gateway.mapper import APIGatewayResourceMapper
from opscript.provider.aws.ecr.discovery import ECRDiscovery
from opscript.provider.aws.ecr.mapper import ECRResourceMapper
from opscript.provider.aws.ec2.discovery import EC2Discovery
from opscript.provider.aws.ec2.mapper import EC2ResourceMapper
from opscript.provider.aws.eventbridge.discovery import EventBridgeDiscovery
from opscript.provider.aws.eventbridge.mapper import EventBridgeResourceMapper
from opscript.provider.aws.lambda_function.discovery import LambdaDiscovery
from opscript.provider.aws.lambda_function.mapper import LambdaResourceMapper
from opscript.provider.aws.rds.discovery import RDSDiscovery
from opscript.provider.aws.rds.mapper import RDSResourceMapper
from opscript.provider.aws.s3.discovery import S3Discovery
from opscript.provider.aws.s3.mapper import S3ResourceMapper
from opscript.provider.aws.sns.discovery import SNSDiscovery
from opscript.provider.aws.sns.mapper import SNSResourceMapper
from opscript.provider.aws.sqs.discovery import SQSDiscovery
from opscript.provider.aws.sqs.mapper import SQSResourceMapper
from platformiq.model import DiscoveryScope


def build_ec2_discovery(
    client_factory: AWSClientFactory,
) -> EC2Discovery:
    return EC2Discovery(
        client=client_factory.client("ec2"),
        mapper=EC2ResourceMapper(),
    )


def build_lambda_discovery(
    client_factory: AWSClientFactory,
) -> LambdaDiscovery:
    return LambdaDiscovery(
        client=client_factory.client("lambda"),
        mapper=LambdaResourceMapper(),
    )


def build_s3_discovery(
    client_factory: AWSClientFactory,
) -> S3Discovery:
    return S3Discovery(
        client=client_factory.client("s3"),
        mapper=S3ResourceMapper(),
    )


def build_rds_discovery(
    client_factory: AWSClientFactory,
) -> RDSDiscovery:
    return RDSDiscovery(
        client=client_factory.client("rds"),
        mapper=RDSResourceMapper(),
    )


def build_ecr_discovery(
    client_factory: AWSClientFactory,
) -> ECRDiscovery:
    return ECRDiscovery(
        client=client_factory.client("ecr"),
        mapper=ECRResourceMapper(),
    )


def build_eventbridge_discovery(
    client_factory: AWSClientFactory,
) -> EventBridgeDiscovery:
    return EventBridgeDiscovery(
        client=client_factory.client("events"),
        mapper=EventBridgeResourceMapper(),
    )


def build_api_gateway_discovery(
    client_factory: AWSClientFactory,
) -> APIGatewayDiscovery:
    return APIGatewayDiscovery(
        client=client_factory.client("apigateway"),
        mapper=APIGatewayResourceMapper(),
    )


def build_sqs_discovery(
    client_factory: AWSClientFactory,
) -> SQSDiscovery:
    return SQSDiscovery(
        client=client_factory.client("sqs"),
        mapper=SQSResourceMapper(),
    )


def build_sns_discovery(
    client_factory: AWSClientFactory,
) -> SNSDiscovery:
    return SNSDiscovery(
        client=client_factory.client("sns"),
        mapper=SNSResourceMapper(),
    )


def build_aws_discovery_provider(
    client_factory: AWSClientFactory,
    discovery_scope: DiscoveryScope,
) -> AWSDiscoveryProvider:
    return AWSDiscoveryProvider(
        discovery_scope=discovery_scope,
        ec2_discovery=build_ec2_discovery(client_factory),
        lambda_discovery=build_lambda_discovery(client_factory),
        s3_discovery=build_s3_discovery(client_factory),
        rds_discovery=build_rds_discovery(client_factory),
        ecr_discovery=build_ecr_discovery(client_factory),
        eventbridge_discovery=build_eventbridge_discovery(client_factory),
        api_gateway_discovery=build_api_gateway_discovery(client_factory),
        sqs_discovery=build_sqs_discovery(client_factory),
        sns_discovery=build_sns_discovery(client_factory),
    )


def build_default_discovery_provider() -> AWSDiscoveryProvider:
    """
    Build the default discovery provider using the production
    boto3-backed AWS client factory.
    """

    from opscript.aws import Boto3AWSClientFactory

    from opscript.config import DEFAULT_DISCOVERY_SCOPE

    return build_aws_discovery_provider(
        Boto3AWSClientFactory(),
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
    )

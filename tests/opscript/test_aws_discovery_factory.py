from opscript.config import DEFAULT_DISCOVERY_SCOPE
from unittest.mock import patch

from opscript.aws.discovery_factory import (
    build_api_gateway_discovery,
    build_aws_discovery_provider,
    build_default_discovery_provider,
    build_ecr_discovery,
    build_ec2_discovery,
    build_eventbridge_discovery,
    build_lambda_discovery,
    build_rds_discovery,
    build_s3_discovery,
    build_sns_discovery,
    build_sqs_discovery,
)
from opscript.provider.aws import AWSDiscoveryProvider
from opscript.provider.aws.api_gateway.discovery import APIGatewayDiscovery
from opscript.provider.aws.ecr.discovery import ECRDiscovery
from opscript.provider.aws.ec2.discovery import EC2Discovery
from opscript.provider.aws.eventbridge.discovery import EventBridgeDiscovery
from opscript.provider.aws.lambda_function.discovery import LambdaDiscovery
from opscript.provider.aws.rds.discovery import RDSDiscovery
from opscript.provider.aws.s3.discovery import S3Discovery
from opscript.provider.aws.sns.discovery import SNSDiscovery
from opscript.provider.aws.sqs.discovery import SQSDiscovery

TEST_SCOPE = DEFAULT_DISCOVERY_SCOPE


class FakeAWSClientFactory:
    def __init__(self):
        self.requested_services = []

    def client(self, service_name: str):
        self.requested_services.append(service_name)
        return object()


def test_build_ec2_discovery_uses_ec2_client():
    factory = FakeAWSClientFactory()

    discovery = build_ec2_discovery(factory)

    assert isinstance(discovery, EC2Discovery)
    assert factory.requested_services == ["ec2"]


def test_build_api_gateway_discovery_uses_apigateway_client():
    factory = FakeAWSClientFactory()

    discovery = build_api_gateway_discovery(factory)

    assert isinstance(discovery, APIGatewayDiscovery)
    assert factory.requested_services == ["apigateway"]


def test_build_ecr_discovery_uses_ecr_client():
    factory = FakeAWSClientFactory()

    discovery = build_ecr_discovery(factory)

    assert isinstance(discovery, ECRDiscovery)
    assert factory.requested_services == ["ecr"]


def test_build_eventbridge_discovery_uses_events_client():
    factory = FakeAWSClientFactory()

    discovery = build_eventbridge_discovery(factory)

    assert isinstance(discovery, EventBridgeDiscovery)
    assert factory.requested_services == ["events"]


def test_build_lambda_discovery_uses_lambda_client():
    factory = FakeAWSClientFactory()

    discovery = build_lambda_discovery(factory)

    assert isinstance(discovery, LambdaDiscovery)
    assert factory.requested_services == ["lambda"]


def test_build_s3_discovery_uses_s3_client():
    factory = FakeAWSClientFactory()

    discovery = build_s3_discovery(factory)

    assert isinstance(discovery, S3Discovery)
    assert factory.requested_services == ["s3"]


def test_build_sqs_discovery_uses_sqs_client():
    factory = FakeAWSClientFactory()

    discovery = build_sqs_discovery(factory)

    assert isinstance(discovery, SQSDiscovery)
    assert factory.requested_services == ["sqs"]


def test_build_sns_discovery_uses_sns_client():
    factory = FakeAWSClientFactory()

    discovery = build_sns_discovery(factory)

    assert isinstance(discovery, SNSDiscovery)
    assert factory.requested_services == ["sns"]


def test_build_rds_discovery_uses_rds_client():
    factory = FakeAWSClientFactory()

    discovery = build_rds_discovery(factory)

    assert isinstance(discovery, RDSDiscovery)
    assert factory.requested_services == ["rds"]


def test_build_aws_discovery_provider_uses_supported_aws_services():
    factory = FakeAWSClientFactory()

    provider = build_aws_discovery_provider(factory, discovery_scope=TEST_SCOPE)

    assert isinstance(provider, AWSDiscoveryProvider)
    assert provider.discovery_scope == TEST_SCOPE
    assert factory.requested_services == [
        "ec2",
        "lambda",
        "s3",
        "rds",
        "ecr",
        "events",
        "apigateway",
        "sqs",
        "sns",
    ]


@patch("opscript.aws.Boto3AWSClientFactory")
def test_build_default_discovery_provider_uses_boto3_factory(factory_class):
    factory = FakeAWSClientFactory()
    factory_class.return_value = factory

    provider = build_default_discovery_provider()

    assert isinstance(provider, AWSDiscoveryProvider)
    factory_class.assert_called_once_with()
    assert factory.requested_services == [
        "ec2",
        "lambda",
        "s3",
        "rds",
        "ecr",
        "events",
        "apigateway",
        "sqs",
        "sns",
    ]

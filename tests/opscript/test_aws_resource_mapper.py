from opscript.config import DEFAULT_DISCOVERY_SCOPE
import json
from datetime import UTC, datetime

from opscript.provider.aws.api_gateway.mapper import APIGatewayResourceMapper
from opscript.provider.aws.ec2.mapper import EC2ResourceMapper
from opscript.provider.aws.ecr.mapper import ECRResourceMapper
from opscript.provider.aws.eventbridge.mapper import EventBridgeResourceMapper
from opscript.provider.aws.lambda_function.mapper import LambdaResourceMapper
from opscript.provider.aws.rds.mapper import RDSResourceMapper
from opscript.provider.aws.s3.mapper import S3ResourceMapper
from opscript.provider.aws.sns.mapper import SNSResourceMapper
from opscript.provider.aws.sqs.mapper import SQSResourceMapper
from platformiq.core import Identifier
from platformiq.model import Resource
from platformiq.model.snapshot import Snapshot
from platformiq.serialization import SnapshotSerializer


def test_ec2_resource_mapper_creates_resource():
    mapper = EC2ResourceMapper()

    resource = mapper.map(
        instance_id="i-123456",
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == "i-123456"


def test_api_gateway_resource_mapper_creates_resource_with_properties():
    mapper = APIGatewayResourceMapper()

    resource = mapper.map(
        rest_api={
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
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == "abc123"
    assert resource.state.properties == {
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


def test_api_gateway_resource_mapper_normalizes_created_date_datetime():
    mapper = APIGatewayResourceMapper()
    created_date = datetime(2026, 7, 10, 12, 30, 45, tzinfo=UTC)

    resource = mapper.map(
        rest_api={
            "id": "abc123",
            "createdDate": created_date,
        }
    )

    assert resource.state.properties["created_date"] == "2026-07-10T12:30:45+00:00"


def test_api_gateway_resource_mapper_preserves_absent_created_date_as_none():
    mapper = APIGatewayResourceMapper()

    resource = mapper.map(
        rest_api={
            "id": "abc123",
        }
    )

    assert resource.state.properties["created_date"] is None


def test_api_gateway_resource_serializes_to_json_and_deserializes_with_properties():
    mapper = APIGatewayResourceMapper()
    created_date = datetime(2026, 7, 10, 12, 30, 45, tzinfo=UTC)
    resource = mapper.map(
        rest_api={
            "id": "abc123",
            "name": "opscript-api",
            "description": "Opscript REST API",
            "createdDate": created_date,
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
    )
    serializer = SnapshotSerializer()
    snapshot = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(resource,),
    )

    data = serializer.serialize(snapshot)
    json.dumps(data)
    deserialized = serializer.deserialize(data)

    assert deserialized.resources[0].state.properties == {
        "name": "opscript-api",
        "description": "Opscript REST API",
        "created_date": "2026-07-10T12:30:45+00:00",
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


def test_ecr_resource_mapper_creates_resource_with_properties():
    mapper = ECRResourceMapper()

    resource = mapper.map(
        repository={
            "repositoryName": "opscript/app",
            "repositoryUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/opscript/app",
            "registryId": "123456789012",
            "imageTagMutability": "MUTABLE",
            "imageScanningConfiguration": {"scanOnPush": True},
            "encryptionConfiguration": {"encryptionType": "AES256"},
            "repositoryArn": (
                "arn:aws:ecr:us-east-1:123456789012:repository/opscript/app"
            ),
            "createdAt": "2026-07-10T00:00:00Z",
        }
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == "opscript/app"
    assert resource.state.properties == {
        "repository_uri": ("123456789012.dkr.ecr.us-east-1.amazonaws.com/opscript/app"),
        "registry_id": "123456789012",
        "image_tag_mutability": "MUTABLE",
        "image_scanning_configuration": {"scanOnPush": True},
        "encryption_configuration": {"encryptionType": "AES256"},
        "repository_arn": (
            "arn:aws:ecr:us-east-1:123456789012:repository/opscript/app"
        ),
        "created_at": "2026-07-10T00:00:00Z",
    }


def test_ecr_resource_mapper_normalizes_created_at_datetime():
    mapper = ECRResourceMapper()
    created_at = datetime(2026, 7, 10, 12, 30, 45, tzinfo=UTC)

    resource = mapper.map(
        repository={
            "repositoryName": "opscript/app",
            "createdAt": created_at,
        }
    )

    assert resource.state.properties["created_at"] == "2026-07-10T12:30:45+00:00"


def test_ecr_resource_mapper_preserves_absent_created_at_as_none():
    mapper = ECRResourceMapper()

    resource = mapper.map(
        repository={
            "repositoryName": "opscript/app",
        }
    )

    assert resource.state.properties["created_at"] is None


def test_ecr_resource_serializes_to_json_and_deserializes_with_properties():
    mapper = ECRResourceMapper()
    created_at = datetime(2026, 7, 10, 12, 30, 45, tzinfo=UTC)
    resource = mapper.map(
        repository={
            "repositoryName": "opscript/app",
            "repositoryUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/opscript/app",
            "registryId": "123456789012",
            "imageTagMutability": "IMMUTABLE",
            "imageScanningConfiguration": {"scanOnPush": True},
            "encryptionConfiguration": {"encryptionType": "AES256"},
            "repositoryArn": (
                "arn:aws:ecr:us-east-1:123456789012:repository/opscript/app"
            ),
            "createdAt": created_at,
        }
    )
    serializer = SnapshotSerializer()
    snapshot = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(resource,),
    )

    data = serializer.serialize(snapshot)
    json.dumps(data)
    deserialized = serializer.deserialize(data)

    assert deserialized.resources[0].state.properties == {
        "repository_uri": ("123456789012.dkr.ecr.us-east-1.amazonaws.com/opscript/app"),
        "registry_id": "123456789012",
        "image_tag_mutability": "IMMUTABLE",
        "image_scanning_configuration": {"scanOnPush": True},
        "encryption_configuration": {"encryptionType": "AES256"},
        "repository_arn": (
            "arn:aws:ecr:us-east-1:123456789012:repository/opscript/app"
        ),
        "created_at": "2026-07-10T12:30:45+00:00",
    }


def test_eventbridge_resource_mapper_creates_resource_with_properties():
    mapper = EventBridgeResourceMapper()

    resource = mapper.map(
        rule={
            "Name": "opscript-schedule",
            "Arn": "arn:aws:events:us-east-1:123456789012:rule/opscript-schedule",
            "EventBusName": "default",
            "State": "ENABLED",
            "ScheduleExpression": "rate(1 hour)",
            "EventPattern": '{"source":["aws.ec2"]}',
            "Description": "Opscript scheduled run",
        }
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == "opscript-schedule"
    assert resource.state.properties == {
        "arn": "arn:aws:events:us-east-1:123456789012:rule/opscript-schedule",
        "event_bus_name": "default",
        "state": "ENABLED",
        "schedule_expression": "rate(1 hour)",
        "event_pattern": '{"source":["aws.ec2"]}',
        "description": "Opscript scheduled run",
    }


def test_ec2_resource_mapper_preserves_tags_in_resource_state():
    mapper = EC2ResourceMapper()

    resource = mapper.map(
        instance_id="i-123456",
        tags=[
            {
                "Key": "Environment",
                "Value": "prod",
            },
            {
                "Key": "Owner",
                "Value": "platform",
            },
        ],
    )

    assert resource.state.properties["tags"] == {
        "Environment": "prod",
        "Owner": "platform",
    }


def test_ec2_resource_mapper_uses_empty_tags_when_missing():
    mapper = EC2ResourceMapper()

    resource = mapper.map(
        instance_id="i-123456",
    )

    assert resource.state.properties["tags"] == {}


def test_lambda_resource_mapper_creates_resource():
    mapper = LambdaResourceMapper()

    resource = mapper.map(
        function_name="opscript-processor",
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == "opscript-processor"


def test_s3_resource_mapper_creates_resource():
    mapper = S3ResourceMapper()

    resource = mapper.map(
        bucket_name="opscript-state",
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == "opscript-state"


def test_sqs_resource_mapper_creates_resource_with_minimal_state():
    mapper = SQSResourceMapper()
    queue_url = "https://sqs.us-east-1.amazonaws.com/123456789012/opscript-queue"

    resource = mapper.map(
        queue_url=queue_url,
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == queue_url
    assert resource.state.properties == {}


def test_sns_resource_mapper_creates_resource_with_minimal_state():
    mapper = SNSResourceMapper()
    topic_arn = "arn:aws:sns:us-east-1:123456789012:opscript-topic"

    resource = mapper.map(
        topic_arn=topic_arn,
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == topic_arn
    assert resource.state.properties == {}


def test_rds_resource_mapper_creates_resource_with_properties():
    mapper = RDSResourceMapper()

    resource = mapper.map(
        db_instance={
            "DBInstanceIdentifier": "opscript-db",
            "Engine": "postgres",
            "EngineVersion": "16.3",
            "DBInstanceClass": "db.t4g.micro",
            "MultiAZ": True,
            "PubliclyAccessible": False,
            "AllocatedStorage": 20,
            "StorageType": "gp3",
        }
    )

    assert isinstance(resource, Resource)
    assert resource.external_id == "opscript-db"
    assert resource.state.properties == {
        "engine": "postgres",
        "engine_version": "16.3",
        "instance_class": "db.t4g.micro",
        "multi_az": True,
        "publicly_accessible": False,
        "allocated_storage": 20,
        "storage_type": "gp3",
    }

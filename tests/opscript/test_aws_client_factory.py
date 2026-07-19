from unittest.mock import Mock, patch

from opscript.aws import Boto3AWSClientFactory


@patch("opscript.aws.client_factory.boto3.client")
def test_boto3_client_factory_creates_client(mock_client):
    expected = Mock()
    mock_client.return_value = expected

    factory = Boto3AWSClientFactory()

    client = factory.client("ec2")

    mock_client.assert_called_once_with("ec2")
    assert client is expected


@patch("opscript.aws.client_factory.boto3.client")
def test_boto3_client_factory_passes_timeout_config_when_provided(mock_client):
    expected = Mock()
    mock_client.return_value = expected

    factory = Boto3AWSClientFactory(
        connect_timeout=2,
        read_timeout=5,
    )

    client = factory.client("ec2")

    mock_client.assert_called_once()
    service_name = mock_client.call_args.args[0]
    config = mock_client.call_args.kwargs["config"]

    assert service_name == "ec2"
    assert config.connect_timeout == 2
    assert config.read_timeout == 5
    assert client is expected


@patch("opscript.aws.client_factory.boto3.client")
def test_boto3_client_factory_passes_retry_config_when_provided(mock_client):
    expected = Mock()
    mock_client.return_value = expected

    factory = Boto3AWSClientFactory(
        retry_mode="standard",
        retry_total_max_attempts=4,
    )

    client = factory.client("ec2")

    mock_client.assert_called_once()
    service_name = mock_client.call_args.args[0]
    config = mock_client.call_args.kwargs["config"]

    assert service_name == "ec2"
    assert config.retries == {
        "mode": "standard",
        "total_max_attempts": 4,
    }
    assert client is expected


@patch("opscript.aws.client_factory.boto3.client")
def test_boto3_client_factory_combines_timeout_and_retry_config(mock_client):
    expected = Mock()
    mock_client.return_value = expected

    factory = Boto3AWSClientFactory(
        connect_timeout=2,
        read_timeout=5,
        retry_mode="adaptive",
        retry_total_max_attempts=6,
    )

    client = factory.client("ec2")

    mock_client.assert_called_once()
    service_name = mock_client.call_args.args[0]
    config = mock_client.call_args.kwargs["config"]

    assert service_name == "ec2"
    assert config.connect_timeout == 2
    assert config.read_timeout == 5
    assert config.retries == {
        "mode": "adaptive",
        "total_max_attempts": 6,
    }
    assert client is expected

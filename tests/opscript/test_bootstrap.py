import os
from unittest.mock import patch

import pytest
from platformiq.core import Identifier
from platformiq.model import DiscoveryScope, Snapshot

from opscript.application import InventoryService
from opscript.bootstrap import (
    PRODUCTION_SNAPSHOT_NAMESPACE,
    build_analysis_service,
    build_aws_client_factory,
    build_config,
    build_default_discovery_provider,
    build_inventory_service,
    build_reporting_service,
    build_snapshot_storage,
)
from opscript.config import (
    OpscriptConfig,
    ConfigurationError,
    DEFAULT_DISCOVERY_SCOPE,
    DEFAULT_LOCAL_DISCOVERY_SCOPE,
)
from opscript.storage import S3SnapshotStorage
from opscript.storage.memory import InMemorySnapshotStorage


class FakeDiscoveryProvider:
    def discover(self):
        return Snapshot(
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            id=Identifier.new(),
        )


def test_build_config_uses_default_values(monkeypatch):
    monkeypatch.delenv("OPSCRIPT_ENVIRONMENT", raising=False)
    monkeypatch.delenv("OPSCRIPT_LOG_LEVEL", raising=False)
    monkeypatch.delenv("OPSCRIPT_STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("OPSCRIPT_DISCOVERY_SCOPE", raising=False)
    monkeypatch.delenv("OPSCRIPT_S3_BUCKET", raising=False)
    monkeypatch.delenv("OPSCRIPT_S3_KEY", raising=False)
    monkeypatch.delenv("OPSCRIPT_AWS_CONNECT_TIMEOUT", raising=False)
    monkeypatch.delenv("OPSCRIPT_AWS_READ_TIMEOUT", raising=False)

    config = build_config()

    assert config.environment == "dev"
    assert config.log_level == "INFO"
    assert config.storage_backend == "memory"
    assert config.discovery_scope == DEFAULT_LOCAL_DISCOVERY_SCOPE
    assert config.discovery_scope != DEFAULT_DISCOVERY_SCOPE
    assert config.s3_bucket is None
    assert config.s3_key is None
    assert config.connect_timeout is None
    assert config.read_timeout is None


def test_build_config_reads_environment_variables(monkeypatch):
    monkeypatch.setenv("OPSCRIPT_ENVIRONMENT", "test")
    monkeypatch.setenv("OPSCRIPT_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "configured-scope")
    monkeypatch.setenv("OPSCRIPT_S3_BUCKET", "history-bucket")
    monkeypatch.setenv("OPSCRIPT_S3_KEY", "snapshots/history.json")
    monkeypatch.setenv("OPSCRIPT_AWS_CONNECT_TIMEOUT", "2.5")
    monkeypatch.setenv("OPSCRIPT_AWS_READ_TIMEOUT", "10")

    config = build_config()

    assert config.environment == "test"
    assert config.log_level == "DEBUG"
    assert config.storage_backend == "s3"
    assert str(config.discovery_scope) == "configured-scope"
    assert config.s3_bucket == "history-bucket"
    assert config.s3_key == "snapshots/history.json"
    assert config.connect_timeout == 2.5
    assert config.read_timeout == 10


def test_build_config_discovery_scope_override_beats_environment(monkeypatch):
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "environment-scope")

    config = build_config(discovery_scope_override="cli-scope")

    assert config.discovery_scope == DiscoveryScope("cli-scope")


def test_build_config_accepts_discovery_scope_override_value_object(monkeypatch):
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "environment-scope")

    config = build_config(discovery_scope_override=DiscoveryScope("cli-scope"))

    assert config.discovery_scope == DiscoveryScope("cli-scope")


def test_build_config_discovery_scope_environment_beats_default(monkeypatch):
    monkeypatch.setenv("OPSCRIPT_ENVIRONMENT", "prod")
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "environment-scope")
    monkeypatch.setenv("OPSCRIPT_S3_BUCKET", "history-bucket")
    monkeypatch.setenv("OPSCRIPT_S3_KEY", "environments/prod/snapshots")

    config = build_config()

    assert config.discovery_scope == DiscoveryScope("environment-scope")


def test_build_config_discovery_scope_override_does_not_mutate_environment(
    monkeypatch,
):
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "environment-scope")

    config = build_config(discovery_scope_override="cli-scope")

    assert config.discovery_scope == DiscoveryScope("cli-scope")
    assert os.getenv("OPSCRIPT_DISCOVERY_SCOPE") == "environment-scope"


@pytest.mark.parametrize("value", ("", "   "))
def test_build_config_fails_for_empty_discovery_scope_override(value):
    with pytest.raises(ConfigurationError, match="discovery scope must not be empty"):
        build_config(discovery_scope_override=value)


def test_build_config_resolves_prod_to_runtime_v1_production_scope(monkeypatch):
    monkeypatch.setenv("OPSCRIPT_ENVIRONMENT", "prod")
    monkeypatch.setenv("OPSCRIPT_STORAGE_BACKEND", "s3")
    monkeypatch.setenv("OPSCRIPT_S3_BUCKET", "history-bucket")
    monkeypatch.setenv("OPSCRIPT_S3_KEY", "environments/prod/snapshots")
    monkeypatch.delenv("OPSCRIPT_DISCOVERY_SCOPE", raising=False)

    config = build_config()

    assert config.discovery_scope == DEFAULT_DISCOVERY_SCOPE


def test_build_config_resolves_non_production_to_local_scope(monkeypatch):
    monkeypatch.setenv("OPSCRIPT_ENVIRONMENT", "dev")
    monkeypatch.delenv("OPSCRIPT_DISCOVERY_SCOPE", raising=False)

    config = build_config()

    assert config.discovery_scope == DEFAULT_LOCAL_DISCOVERY_SCOPE
    assert config.discovery_scope != DEFAULT_DISCOVERY_SCOPE


def test_build_config_fails_for_invalid_log_level(monkeypatch):
    monkeypatch.setenv("OPSCRIPT_LOG_LEVEL", "INVALID")

    with pytest.raises(ConfigurationError, match="log level"):
        build_config()


@pytest.mark.parametrize(
    ("env_var", "value"),
    (
        ("OPSCRIPT_AWS_CONNECT_TIMEOUT", "not-a-number"),
        ("OPSCRIPT_AWS_READ_TIMEOUT", "not-a-number"),
        ("OPSCRIPT_AWS_CONNECT_TIMEOUT", "0"),
        ("OPSCRIPT_AWS_READ_TIMEOUT", "-1"),
    ),
)
def test_build_config_fails_for_invalid_timeout_values(
    monkeypatch,
    env_var,
    value,
):
    monkeypatch.setenv(env_var, value)

    with pytest.raises(ConfigurationError, match="timeout|must be a number"):
        build_config()


def test_build_config_fails_for_prod_memory_storage():
    config = OpscriptConfig(
        environment="prod",
        storage_backend="memory",
    )

    with pytest.raises(ConfigurationError, match="must not use memory storage"):
        config.validate()


def test_build_config_accepts_prod_s3_storage():
    config = OpscriptConfig(
        environment="prod",
        storage_backend="s3",
        s3_bucket="history-bucket",
        s3_key="snapshots",
    )

    config.validate()


def test_build_aws_client_factory_uses_configured_timeout_values():
    factory = build_aws_client_factory(
        OpscriptConfig(
            connect_timeout=2,
            read_timeout=10,
        )
    )

    assert factory.connect_timeout == 2
    assert factory.read_timeout == 10


def test_build_config_fails_for_prod_s3_storage_without_bucket():
    config = OpscriptConfig(
        environment="prod",
        storage_backend="s3",
        s3_key="snapshots",
    )

    with pytest.raises(ConfigurationError, match="requires both bucket and key"):
        config.validate()


def test_build_config_fails_for_prod_s3_storage_without_key():
    config = OpscriptConfig(
        environment="prod",
        storage_backend="s3",
        s3_bucket="history-bucket",
    )

    with pytest.raises(ConfigurationError, match="requires both bucket and key"):
        config.validate()


def test_build_config_fails_when_s3_bucket_is_missing():
    config = OpscriptConfig(
        storage_backend="s3",
        s3_key="snapshots/history.json",
    )

    with pytest.raises(ConfigurationError, match="requires both bucket and key"):
        config.validate()


def test_build_config_fails_when_s3_key_is_missing():
    config = OpscriptConfig(
        storage_backend="s3",
        s3_bucket="history-bucket",
    )

    with pytest.raises(ConfigurationError, match="requires both bucket and key"):
        config.validate()


def test_build_snapshot_storage_returns_in_memory_storage():
    storage = build_snapshot_storage(
        config=OpscriptConfig(),
    )

    assert isinstance(storage, InMemorySnapshotStorage)


@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_snapshot_storage_returns_s3_storage(factory_class):
    client = object()
    factory_class.return_value.client.return_value = client

    storage = build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            s3_bucket="history-bucket",
            s3_key="snapshots/history.json",
        ),
    )

    assert isinstance(storage, S3SnapshotStorage)
    assert storage.client is client
    assert storage.bucket == "history-bucket"
    assert storage.key == "snapshots/history.json"
    factory_class.return_value.client.assert_called_once_with("s3")
    factory_class.assert_called_once_with(
        connect_timeout=None,
        read_timeout=None,
        retry_mode="standard",
        retry_total_max_attempts=1,
    )


@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_snapshot_storage_preserves_production_namespace_for_default_scope(
    factory_class,
):
    client = object()
    factory_class.return_value.client.return_value = client

    storage = build_snapshot_storage(
        config=OpscriptConfig(
            environment="prod",
            storage_backend="s3",
            discovery_scope=DEFAULT_DISCOVERY_SCOPE,
            s3_bucket="history-bucket",
            s3_key=PRODUCTION_SNAPSHOT_NAMESPACE,
        ),
    )

    assert isinstance(storage, S3SnapshotStorage)
    assert storage.key == PRODUCTION_SNAPSHOT_NAMESPACE


@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_snapshot_storage_preserves_default_local_namespace(factory_class):
    client = object()
    factory_class.return_value.client.return_value = client

    storage = build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            discovery_scope=DEFAULT_LOCAL_DISCOVERY_SCOPE,
            s3_bucket="history-bucket",
            s3_key="snapshots/history.json",
        ),
    )

    assert isinstance(storage, S3SnapshotStorage)
    assert storage.key == "snapshots/history.json"


@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_snapshot_storage_derives_namespace_from_discovery_scope(
    factory_class,
):
    client = object()
    factory_class.return_value.client.return_value = client

    storage = build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            discovery_scope=DiscoveryScope("scope alpha/one"),
            s3_bucket="history-bucket",
            s3_key="environments/dev/snapshots",
        ),
    )

    assert isinstance(storage, S3SnapshotStorage)
    assert (
        storage.key == "environments/dev/snapshots/discovery-scopes/scope%20alpha%2Fone"
    )


@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_snapshot_storage_derives_distinct_namespaces_for_distinct_scopes(
    factory_class,
):
    client = object()
    factory_class.return_value.client.return_value = client

    first = build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            discovery_scope=DiscoveryScope("scope-001"),
            s3_bucket="history-bucket",
            s3_key="environments/dev/snapshots",
        ),
    )
    second = build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            discovery_scope=DiscoveryScope("scope-002"),
            s3_bucket="history-bucket",
            s3_key="environments/dev/snapshots",
        ),
    )

    assert isinstance(first, S3SnapshotStorage)
    assert isinstance(second, S3SnapshotStorage)
    assert first.key == "environments/dev/snapshots/discovery-scopes/scope-001"
    assert second.key == "environments/dev/snapshots/discovery-scopes/scope-002"
    assert first.key != second.key


@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_snapshot_storage_repeated_scope_construction_is_deterministic(
    factory_class,
):
    client = object()
    factory_class.return_value.client.return_value = client
    config = OpscriptConfig(
        storage_backend="s3",
        discovery_scope=DiscoveryScope("scope-001"),
        s3_bucket="history-bucket",
        s3_key="environments/dev/snapshots",
    )

    first = build_snapshot_storage(config=config)
    second = build_snapshot_storage(config=config)

    assert isinstance(first, S3SnapshotStorage)
    assert isinstance(second, S3SnapshotStorage)
    assert first.key == second.key
    assert first.key == "environments/dev/snapshots/discovery-scopes/scope-001"


@pytest.mark.parametrize(
    ("scope_value", "encoded_segment"),
    (
        ("scope/one", "scope%2Fone"),
        ("scope\\one", "scope%5Cone"),
        ("scope%one", "scope%25one"),
        ("scope one", "scope%20one"),
        ("scope-\u6771\u4eac", "scope-%E6%9D%B1%E4%BA%AC"),
        ("..", "%2E%2E"),
        ("../scope", "%2E%2E%2Fscope"),
    ),
)
@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_snapshot_storage_encodes_scope_as_one_opaque_namespace_segment(
    factory_class,
    scope_value,
    encoded_segment,
):
    client = object()
    factory_class.return_value.client.return_value = client

    storage = build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            discovery_scope=DiscoveryScope(scope_value),
            s3_bucket="history-bucket",
            s3_key="environments/dev/snapshots",
        ),
    )

    assert isinstance(storage, S3SnapshotStorage)
    assert (
        storage.key == f"environments/dev/snapshots/discovery-scopes/{encoded_segment}"
    )

    suffix = storage.key.removeprefix("environments/dev/snapshots/discovery-scopes/")
    assert "/" not in suffix
    assert "\\" not in suffix
    assert suffix not in {".", ".."}


@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_snapshot_storage_passes_timeout_values_to_s3_client_factory(
    factory_class,
):
    client = object()
    factory_class.return_value.client.return_value = client

    build_snapshot_storage(
        config=OpscriptConfig(
            storage_backend="s3",
            s3_bucket="history-bucket",
            s3_key="snapshots/history.json",
            connect_timeout=2,
            read_timeout=10,
        ),
    )

    factory_class.assert_called_once_with(
        connect_timeout=2,
        read_timeout=10,
        retry_mode="standard",
        retry_total_max_attempts=1,
    )


@patch("opscript.bootstrap.build_aws_discovery_provider")
@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_build_default_discovery_provider_uses_configured_client_factory(
    factory_class,
    discovery_provider_factory,
):
    provider = FakeDiscoveryProvider()
    discovery_provider_factory.return_value = provider

    result = build_default_discovery_provider(
        OpscriptConfig(
            connect_timeout=2,
            read_timeout=10,
        )
    )

    assert result is provider
    factory_class.assert_called_once_with(
        connect_timeout=2,
        read_timeout=10,
        retry_mode="standard",
        retry_total_max_attempts=1,
    )
    discovery_provider_factory.assert_called_once_with(
        factory_class.return_value,
        discovery_scope=DEFAULT_LOCAL_DISCOVERY_SCOPE,
    )


@patch("opscript.bootstrap.build_default_discovery_provider")
def test_build_inventory_service_uses_default_discovery_provider(default_provider):
    provider = FakeDiscoveryProvider()
    default_provider.return_value = provider

    service = build_inventory_service(
        config=OpscriptConfig(),
    )

    assert isinstance(service, InventoryService)
    assert service.discovery_provider is provider
    default_provider.assert_called_once_with(
        OpscriptConfig(),
    )


def test_build_inventory_service_accepts_explicit_discovery_provider():
    provider = FakeDiscoveryProvider()

    service = build_inventory_service(
        discovery_provider=provider,
        config=OpscriptConfig(),
    )

    assert service.discovery_provider is provider


def test_build_analysis_service_returns_analysis_service():
    service = build_analysis_service(
        config=OpscriptConfig(),
    )

    assert service is not None


def test_build_reporting_service_returns_reporting_service():
    service = build_reporting_service(
        config=OpscriptConfig(),
    )

    assert service is not None


def test_build_config_uses_default_sdk_total_max_attempts(monkeypatch):
    monkeypatch.delenv("OPSCRIPT_AWS_SDK_TOTAL_MAX_ATTEMPTS", raising=False)
    config = build_config()
    assert config.sdk_total_max_attempts == 1


def test_build_config_reads_sdk_total_max_attempts(monkeypatch):
    monkeypatch.setenv("OPSCRIPT_AWS_SDK_TOTAL_MAX_ATTEMPTS", "3")
    config = build_config()
    assert config.sdk_total_max_attempts == 3


@pytest.mark.parametrize(
    "value",
    ("0", "-1", "not-an-int"),
)
def test_build_config_fails_for_invalid_sdk_total_max_attempts(monkeypatch, value):
    monkeypatch.setenv("OPSCRIPT_AWS_SDK_TOTAL_MAX_ATTEMPTS", value)
    with pytest.raises(ConfigurationError):
        build_config()


def test_build_aws_client_factory_uses_configured_retry_values():
    factory = build_aws_client_factory(
        OpscriptConfig(
            sdk_total_max_attempts=3,
        )
    )

    assert factory.retry_mode == "standard"
    assert factory.retry_total_max_attempts == 3


@patch("opscript.bootstrap.build_aws_discovery_provider")
@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_composition_uses_identical_config_object(
    factory_class,
    discovery_provider_factory,
):
    config = OpscriptConfig(
        discovery_scope=DiscoveryScope("scope-identity-check"),
        storage_backend="memory",
    )

    storage = build_snapshot_storage(config=config)
    provider = build_default_discovery_provider(config=config)

    assert storage.discovery_scope == config.discovery_scope
    assert provider is discovery_provider_factory.return_value
    discovery_provider_factory.assert_called_once_with(
        factory_class.return_value,
        discovery_scope=config.discovery_scope,
    )


@patch("opscript.bootstrap.build_aws_discovery_provider")
@patch("opscript.bootstrap.Boto3AWSClientFactory")
def test_environment_mutation_does_not_affect_composition(
    factory_class,
    discovery_provider_factory,
    monkeypatch,
):
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "initial-scope")
    config = build_config()

    # Change environment variable after resolution
    monkeypatch.setenv("OPSCRIPT_DISCOVERY_SCOPE", "mutated-scope")

    storage = build_snapshot_storage(config=config)
    provider = build_default_discovery_provider(config=config)

    # They should retain initial-scope
    assert storage.discovery_scope == DiscoveryScope("initial-scope")
    assert provider is discovery_provider_factory.return_value
    discovery_provider_factory.assert_called_once_with(
        factory_class.return_value,
        discovery_scope=DiscoveryScope("initial-scope"),
    )

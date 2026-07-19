import logging

from opscript.config import DEFAULT_DISCOVERY_SCOPE
import pytest
from botocore.exceptions import ClientError, ProxyConnectionError
from platformiq.core import Identifier
from platformiq.model import Resource, Snapshot
from platformiq.errors.provider import ProviderError

from opscript.application import InventoryService, RetryPolicy
from opscript.errors import OpscriptProviderError, FailureCategory
from opscript.execution import (
    activate_execution,
    create_execution,
    get_active_execution,
)
from opscript.provider.aws import AWSDiscoveryProvider
from opscript.storage import SnapshotCommittedWithDegradedLatestError


class FakeDiscoveryProvider:
    def discover(self):
        return Snapshot(discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new())


class FakeSnapshotStorage:
    def __init__(self):
        self.saved_snapshot = None

    def save(self, snapshot):
        self.saved_snapshot = snapshot

    def load_latest(self):
        return self.saved_snapshot


class DegradedLatestSnapshotStorage:
    def __init__(self):
        self.saved_snapshot = None
        self.save_calls = 0

    def save(self, snapshot):
        self.saved_snapshot = snapshot
        self.save_calls += 1
        raise SnapshotCommittedWithDegradedLatestError(
            "Snapshot record committed, but latest reference maintenance failed",
            record_key="snapshot.json/records/0001.json",
            original_exception=RuntimeError("latest reference unavailable"),
        )

    def load_latest(self):
        return self.saved_snapshot


class SuccessfulServiceDiscovery:
    def discover(self):
        return (
            Resource(
                id=Identifier.new(),
                external_id="partial-resource",
            ),
        )


class FailingServiceDiscovery:
    def discover(self):
        raise ProviderError("service discovery failed")


class UnreachedServiceDiscovery:
    def __init__(self):
        self.called = False

    def discover(self):
        self.called = True
        return ()


def test_inventory_service_collects_and_stores_snapshot():
    discovery = FakeDiscoveryProvider()
    storage = FakeSnapshotStorage()

    service = InventoryService(
        discovery,
        storage,
    )

    snapshot = service.collect_snapshot()

    assert storage.saved_snapshot == snapshot


def test_inventory_service_treats_latest_reference_failure_as_degraded_commit(caplog):
    discovery = FakeDiscoveryProvider()
    storage = DegradedLatestSnapshotStorage()

    service = InventoryService(
        discovery,
        storage,
    )

    snapshot = service.collect_snapshot()

    messages = [record.message for record in caplog.records]
    degraded_messages = [
        message
        for message in messages
        if "event=snapshot_persistence_degraded" in message
    ]
    assert snapshot == storage.saved_snapshot
    assert storage.save_calls == 1
    assert len(degraded_messages) == 1
    assert "snapshot_committed=True" in degraded_messages[0]
    assert "latest_reference_maintenance=failed" in degraded_messages[0]
    assert "phase=latest_reference_update" in degraded_messages[0]
    assert "execution_id=" not in degraded_messages[0]
    assert "event=execution_" not in degraded_messages[0]
    assert get_active_execution() is None


def test_inventory_service_degraded_snapshot_persistence_inherits_active_execution(
    caplog,
):
    discovery = FakeDiscoveryProvider()
    storage = DegradedLatestSnapshotStorage()
    service = InventoryService(
        discovery,
        storage,
    )
    execution = create_execution()

    with caplog.at_level(logging.WARNING, logger="opscript"):
        with activate_execution(execution):
            snapshot = service.collect_snapshot()

    messages = [record.message for record in caplog.records]
    degraded_messages = [
        message
        for message in messages
        if "event=snapshot_persistence_degraded" in message
    ]

    assert snapshot == storage.saved_snapshot
    assert storage.save_calls == 1
    assert len(degraded_messages) == 1
    assert f"execution_id={execution.identity}" in degraded_messages[0]
    assert "snapshot_committed=True" in degraded_messages[0]
    assert "latest_reference_maintenance=failed" in degraded_messages[0]
    assert get_active_execution() is None


def test_inventory_service_does_not_save_partial_snapshot_when_service_discovery_fails():
    storage = FakeSnapshotStorage()
    unreached_discovery = UnreachedServiceDiscovery()
    discovery = AWSDiscoveryProvider(
        DEFAULT_DISCOVERY_SCOPE,
        SuccessfulServiceDiscovery(),
        FailingServiceDiscovery(),
        unreached_discovery,
        UnreachedServiceDiscovery(),
        UnreachedServiceDiscovery(),
        UnreachedServiceDiscovery(),
        UnreachedServiceDiscovery(),
        UnreachedServiceDiscovery(),
        UnreachedServiceDiscovery(),
    )

    service = InventoryService(
        discovery,
        storage,
        retry_policy=RetryPolicy(max_attempts=1),
    )

    with pytest.raises(OpscriptProviderError) as exc_info:
        service.collect_snapshot()

    assert exc_info.value.category == FailureCategory.INTERNAL_DEFECT
    assert storage.saved_snapshot is None
    assert unreached_discovery.called is False


def test_inventory_service_does_not_retry_on_plain_provider_error():
    attempts = 0
    storage = FakeSnapshotStorage()

    class PlainErrorProvider:
        def discover(self):
            nonlocal attempts
            attempts += 1
            raise ProviderError("some generic provider failure")

    service = InventoryService(
        PlainErrorProvider(),
        storage,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    # plain ProviderError maps to FailureCategory.INTERNAL_DEFECT, which is not retryable
    with pytest.raises(OpscriptProviderError) as exc_info:
        service.collect_snapshot()

    assert attempts == 1
    assert exc_info.value.category == FailureCategory.INTERNAL_DEFECT
    assert storage.saved_snapshot is None


def test_inventory_service_retries_and_recovers_on_throttling_client_error():
    attempts = 0
    storage = FakeSnapshotStorage()
    expected_snapshot = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()
    )

    error_response = {"Error": {"Code": "Throttling", "Message": "Rate limit exceeded"}}
    client_error = ClientError(error_response, "DescribeInstances")

    class ThrottlingProvider:
        def discover(self):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise client_error
            return expected_snapshot

    service = InventoryService(
        ThrottlingProvider(),
        storage,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    snapshot = service.collect_snapshot()

    assert snapshot == expected_snapshot
    assert attempts == 2
    assert storage.saved_snapshot == expected_snapshot


def test_inventory_service_fails_immediately_on_non_retryable_provider_errors():
    attempts = 0
    storage = FakeSnapshotStorage()

    error_response = {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}
    client_error = ClientError(error_response, "DescribeInstances")

    class AuthFailingProvider:
        def discover(self):
            nonlocal attempts
            attempts += 1
            raise client_error

    service = InventoryService(
        AuthFailingProvider(),
        storage,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    with pytest.raises(OpscriptProviderError) as exc_info:
        service.collect_snapshot()

    assert attempts == 1
    assert exc_info.value.category == FailureCategory.AUTHORIZATION
    assert exc_info.value.__cause__ == client_error
    assert storage.saved_snapshot is None


def test_inventory_service_retries_and_exhausts_on_proxy_connection_error():
    attempts = 0
    storage = FakeSnapshotStorage()
    error = ProxyConnectionError(proxy_url="http://127.0.0.1:9")

    class ProxyFailingProvider:
        def discover(self):
            nonlocal attempts
            attempts += 1
            raise error

    service = InventoryService(
        ProxyFailingProvider(),
        storage,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    with pytest.raises(OpscriptProviderError) as exc_info:
        service.collect_snapshot()

    assert attempts == 3
    assert exc_info.value.category == FailureCategory.NETWORK
    assert exc_info.value.__cause__ == error
    assert storage.saved_snapshot is None


def test_inventory_service_retries_and_succeeds_on_proxy_connection_error():
    attempts = 0
    storage = FakeSnapshotStorage()
    error = ProxyConnectionError(proxy_url="http://127.0.0.1:9")
    expected_snapshot = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE, id=Identifier.new()
    )

    class ProxyTransientProvider:
        def discover(self):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise error
            return expected_snapshot

    service = InventoryService(
        ProxyTransientProvider(),
        storage,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    snapshot = service.collect_snapshot()

    assert snapshot == expected_snapshot
    assert attempts == 2
    assert storage.saved_snapshot == expected_snapshot

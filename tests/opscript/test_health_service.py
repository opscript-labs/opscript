from opscript.application import HealthService
from opscript.cli_operations import format_health_report
from opscript.config import OpscriptConfig, ConfigurationError
from opscript.execution import get_active_execution
from opscript.storage import SnapshotStorageError
from platformiq.errors import ProviderError


def test_health_service_reports_configuration_health():
    service = HealthService()

    report = service.check()

    assert report.overall_status == "healthy"
    assert len(report.checks) == 1
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "healthy"
    assert report.checks[0].message == "Configuration is valid."


def test_health_service_direct_invocation_does_not_create_execution(caplog):
    service = HealthService()

    report = service.check()

    messages = [record.message for record in caplog.records]
    assert report.overall_status == "healthy"
    assert not any("event=execution_" in message for message in messages)
    assert not any("event=configuration_" in message for message in messages)
    assert get_active_execution() is None


def test_format_health_report():
    service = HealthService()

    output = format_health_report(service.check())

    assert output == (
        "Health: healthy\n\nChecks:\n- configuration: healthy - Configuration is valid."
    )


def test_health_service_uses_config_loader():
    service = HealthService(
        config_loader=lambda: OpscriptConfig(
            environment="prod",
            storage_backend="s3",
            s3_bucket="history-bucket",
            s3_key="snapshots",
        )
    )

    report = service.check()

    assert report.overall_status == "healthy"
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "healthy"
    assert report.checks[0].message == "Configuration is valid."


def test_health_service_reports_invalid_configuration():
    def load_invalid_config():
        raise ConfigurationError("Opscript test configuration failed.")

    service = HealthService(config_loader=load_invalid_config)

    report = service.check()

    assert report.overall_status == "unhealthy"
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "unhealthy"
    assert report.checks[0].message == "Opscript test configuration failed."


def test_health_service_reports_configuration_validation_failure():
    service = HealthService(
        config_loader=lambda: OpscriptConfig(
            environment="prod",
            storage_backend="memory",
        )
    )

    report = service.check()

    assert report.overall_status == "unhealthy"
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "unhealthy"
    assert (
        report.checks[0].message
        == "Opscript production environment must not use memory storage."
    )


def test_health_service_reports_configuration_and_storage_health():
    storage_configs = []

    def build_storage(config):
        storage_configs.append(config)
        return object()

    config = OpscriptConfig(
        environment="prod",
        storage_backend="s3",
        s3_bucket="history-bucket",
        s3_key="snapshots",
    )
    service = HealthService(
        config_loader=lambda: config,
        storage_builder=build_storage,
    )

    report = service.check()

    assert report.overall_status == "healthy"
    assert len(report.checks) == 2
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "healthy"
    assert report.checks[1].name == "storage"
    assert report.checks[1].status == "healthy"
    assert report.checks[1].message == "Storage is ready."
    assert storage_configs == [config]


def test_health_service_reports_storage_readiness_failure():
    def build_storage(config):
        raise SnapshotStorageError("storage is unavailable")

    service = HealthService(
        config_loader=lambda: OpscriptConfig(),
        storage_builder=build_storage,
    )

    report = service.check()

    assert report.overall_status == "unhealthy"
    assert len(report.checks) == 2
    assert report.checks[0].status == "healthy"
    assert report.checks[1].name == "storage"
    assert report.checks[1].status == "unhealthy"
    assert report.checks[1].message == "storage is unavailable"


def test_health_service_does_not_check_storage_when_configuration_is_invalid():
    storage_called = False

    def build_storage(config):
        nonlocal storage_called
        storage_called = True
        return object()

    service = HealthService(
        config_loader=lambda: OpscriptConfig(
            environment="prod",
            storage_backend="memory",
        ),
        storage_builder=build_storage,
    )

    report = service.check()

    assert report.overall_status == "unhealthy"
    assert len(report.checks) == 2
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "unhealthy"
    assert report.checks[1].name == "storage"
    assert report.checks[1].status == "unhealthy"
    assert (
        report.checks[1].message
        == "Storage readiness was not checked because configuration is invalid."
    )
    assert storage_called is False


def test_health_service_reports_configuration_and_discovery_health():
    discovery_configs = []

    def build_discovery_provider(config):
        discovery_configs.append(config)
        return object()

    config = OpscriptConfig(
        environment="prod",
        storage_backend="s3",
        s3_bucket="history-bucket",
        s3_key="snapshots",
    )
    service = HealthService(
        config_loader=lambda: config,
        discovery_provider_builder=build_discovery_provider,
    )

    report = service.check()

    assert report.overall_status == "healthy"
    assert len(report.checks) == 2
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "healthy"
    assert report.checks[1].name == "discovery"
    assert report.checks[1].status == "healthy"
    assert report.checks[1].message == "Discovery provider is ready."
    assert discovery_configs == [config]


def test_health_service_does_not_check_discovery_when_configuration_is_invalid():
    discovery_called = False

    def build_discovery_provider(config):
        nonlocal discovery_called
        discovery_called = True
        return object()

    service = HealthService(
        config_loader=lambda: OpscriptConfig(
            environment="prod",
            storage_backend="memory",
        ),
        discovery_provider_builder=build_discovery_provider,
    )

    report = service.check()

    assert report.overall_status == "unhealthy"
    assert len(report.checks) == 2
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "unhealthy"
    assert report.checks[1].name == "discovery"
    assert report.checks[1].status == "unhealthy"
    assert (
        report.checks[1].message
        == "Discovery readiness was not checked because configuration is invalid."
    )
    assert discovery_called is False


def test_health_service_reports_discovery_readiness_failure():
    def build_discovery_provider(config):
        raise ProviderError("discovery construction failed")

    service = HealthService(
        config_loader=lambda: OpscriptConfig(),
        discovery_provider_builder=build_discovery_provider,
    )

    report = service.check()

    assert report.overall_status == "unhealthy"
    assert len(report.checks) == 2
    assert report.checks[0].status == "healthy"
    assert report.checks[1].name == "discovery"
    assert report.checks[1].status == "unhealthy"
    assert report.checks[1].message == "discovery construction failed"


def test_health_service_discovery_readiness_does_not_call_discover():
    class DiscoveryProvider:
        def discover(self):
            raise AssertionError("discover must not be called")

    service = HealthService(
        config_loader=lambda: OpscriptConfig(),
        discovery_provider_builder=lambda config: DiscoveryProvider(),
    )

    report = service.check()

    assert report.overall_status == "healthy"
    assert len(report.checks) == 2
    assert report.checks[1].name == "discovery"
    assert report.checks[1].status == "healthy"


def test_health_service_reports_configuration_and_workflow_health():
    workflow_configs = []

    def build_workflow(config):
        workflow_configs.append(config)
        return object()

    config = OpscriptConfig(
        environment="prod",
        storage_backend="s3",
        s3_bucket="history-bucket",
        s3_key="snapshots",
    )
    service = HealthService(
        config_loader=lambda: config,
        workflow_builder=build_workflow,
    )

    report = service.check()

    assert report.overall_status == "healthy"
    assert len(report.checks) == 2
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "healthy"
    assert report.checks[1].name == "workflow"
    assert report.checks[1].status == "healthy"
    assert report.checks[1].message == "Workflow composition is ready."
    assert workflow_configs == [config]


def test_health_service_does_not_check_workflow_when_configuration_is_invalid():
    workflow_called = False

    def build_workflow(config):
        nonlocal workflow_called
        workflow_called = True
        return object()

    service = HealthService(
        config_loader=lambda: OpscriptConfig(
            environment="prod",
            storage_backend="memory",
        ),
        workflow_builder=build_workflow,
    )

    report = service.check()

    assert report.overall_status == "unhealthy"
    assert len(report.checks) == 2
    assert report.checks[0].name == "configuration"
    assert report.checks[0].status == "unhealthy"
    assert report.checks[1].name == "workflow"
    assert report.checks[1].status == "unhealthy"
    assert (
        report.checks[1].message
        == "Workflow readiness was not checked because configuration is invalid."
    )
    assert workflow_called is False


def test_health_service_reports_workflow_readiness_failure():
    def build_workflow(config):
        raise SnapshotStorageError("workflow storage dependency unavailable")

    service = HealthService(
        config_loader=lambda: OpscriptConfig(),
        workflow_builder=build_workflow,
    )

    report = service.check()

    assert report.overall_status == "unhealthy"
    assert len(report.checks) == 2
    assert report.checks[0].status == "healthy"
    assert report.checks[1].name == "workflow"
    assert report.checks[1].status == "unhealthy"
    assert report.checks[1].message == "workflow storage dependency unavailable"


def test_health_service_workflow_readiness_does_not_execute_workflow_method():
    class Workflow:
        def run(self):
            raise AssertionError("workflow must not be executed")

    service = HealthService(
        config_loader=lambda: OpscriptConfig(),
        workflow_builder=lambda config: Workflow(),
    )

    report = service.check()

    assert report.overall_status == "healthy"
    assert len(report.checks) == 2
    assert report.checks[1].name == "workflow"
    assert report.checks[1].status == "healthy"

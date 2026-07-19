from dataclasses import dataclass
from typing import Callable

from platformiq.errors import ProviderError

from opscript.config import OpscriptConfig, ConfigurationError
from opscript.storage import SnapshotStorageError


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    status: str
    message: str


@dataclass(frozen=True)
class HealthReport:
    overall_status: str
    checks: tuple[HealthCheckResult, ...]


class HealthService:
    def __init__(
        self,
        config_loader: Callable[[], OpscriptConfig] | None = None,
        storage_builder: Callable[[OpscriptConfig], object] | None = None,
        discovery_provider_builder: Callable[[OpscriptConfig], object] | None = None,
        workflow_builder: Callable[[OpscriptConfig], object] | None = None,
    ):
        self.config_loader = config_loader
        self.storage_builder = storage_builder
        self.discovery_provider_builder = discovery_provider_builder
        self.workflow_builder = workflow_builder

    def check(self) -> HealthReport:
        config, configuration_check = self._check_configuration()
        checks = (configuration_check,)

        if self.storage_builder is not None:
            checks = (
                *checks,
                self._check_storage(
                    config,
                    configuration_check,
                ),
            )

        if self.discovery_provider_builder is not None:
            checks = (
                *checks,
                self._check_discovery(
                    config,
                    configuration_check,
                ),
            )

        if self.workflow_builder is not None:
            checks = (
                *checks,
                self._check_workflow(
                    config,
                    configuration_check,
                ),
            )

        overall_status = (
            "healthy"
            if all(check.status == "healthy" for check in checks)
            else "unhealthy"
        )

        return HealthReport(
            overall_status=overall_status,
            checks=checks,
        )

    def _check_configuration(
        self,
    ) -> tuple[OpscriptConfig | None, HealthCheckResult]:
        if self.config_loader is None:
            return (
                OpscriptConfig(),
                HealthCheckResult(
                    name="configuration",
                    status="healthy",
                    message="Configuration is valid.",
                ),
            )

        try:
            config = self.config_loader()
            config.validate()
        except ConfigurationError as error:
            return (
                None,
                HealthCheckResult(
                    name="configuration",
                    status="unhealthy",
                    message=str(error),
                ),
            )

        return (
            config,
            HealthCheckResult(
                name="configuration",
                status="healthy",
                message="Configuration is valid.",
            ),
        )

    def _check_storage(
        self,
        config: OpscriptConfig | None,
        configuration_check: HealthCheckResult,
    ) -> HealthCheckResult:
        if configuration_check.status != "healthy" or config is None:
            return HealthCheckResult(
                name="storage",
                status="unhealthy",
                message="Storage readiness was not checked because configuration is invalid.",
            )

        try:
            self.storage_builder(config)
        except (ConfigurationError, SnapshotStorageError) as error:
            return HealthCheckResult(
                name="storage",
                status="unhealthy",
                message=str(error),
            )

        return HealthCheckResult(
            name="storage",
            status="healthy",
            message="Storage is ready.",
        )

    def _check_discovery(
        self,
        config: OpscriptConfig | None,
        configuration_check: HealthCheckResult,
    ) -> HealthCheckResult:
        if configuration_check.status != "healthy" or config is None:
            return HealthCheckResult(
                name="discovery",
                status="unhealthy",
                message="Discovery readiness was not checked because configuration is invalid.",
            )

        try:
            self.discovery_provider_builder(config)
        except (ConfigurationError, ProviderError) as error:
            return HealthCheckResult(
                name="discovery",
                status="unhealthy",
                message=str(error),
            )

        return HealthCheckResult(
            name="discovery",
            status="healthy",
            message="Discovery provider is ready.",
        )

    def _check_workflow(
        self,
        config: OpscriptConfig | None,
        configuration_check: HealthCheckResult,
    ) -> HealthCheckResult:
        if configuration_check.status != "healthy" or config is None:
            return HealthCheckResult(
                name="workflow",
                status="unhealthy",
                message="Workflow readiness was not checked because configuration is invalid.",
            )

        try:
            self.workflow_builder(config)
        except (ConfigurationError, ProviderError, SnapshotStorageError) as error:
            return HealthCheckResult(
                name="workflow",
                status="unhealthy",
                message=str(error),
            )

        return HealthCheckResult(
            name="workflow",
            status="healthy",
            message="Workflow composition is ready.",
        )

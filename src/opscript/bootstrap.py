from __future__ import annotations

from dataclasses import replace
from urllib.parse import quote

from platformiq.analysis import SnapshotDiffer
from platformiq.contracts import DiscoveryProvider, SnapshotStorage
from platformiq.model import DiscoveryScope
from platformiq.serialization import SnapshotSerializer

from opscript.application import (
    AnalysisService,
    DiscoveryScopeActivityComparisonService,
    DiscoveryScopeActivityFactsService,
    DiscoveryScopeActivityReportService,
    DiscoveryScopeActivityWorkflow,
    DiscoveryScopeEligibilityService,
    DiscoveryScopeEligibilityWorkflow,
    InventoryService,
    ReportingService,
)
from opscript.aws import Boto3AWSClientFactory, build_aws_discovery_provider
from opscript.config import (
    DEFAULT_DISCOVERY_SCOPE,
    DEFAULT_LOCAL_DISCOVERY_SCOPE,
    OpscriptConfig,
    load_config_from_environment,
)
from opscript.storage import S3SnapshotStorage
from opscript.storage.memory import InMemorySnapshotStorage


PRODUCTION_SNAPSHOT_NAMESPACE = "environments/prod/snapshots"


class NoOpReporter:
    """
    Placeholder reporter for legacy DiffResult reporting.

    Observation reporting is handled directly by ReportingService.
    """

    def report(self, result):
        return "drift report"


def build_config(
    discovery_scope_override: str | DiscoveryScope | None = None,
) -> OpscriptConfig:
    return load_config_from_environment(
        discovery_scope_override=discovery_scope_override,
    )


def build_aws_client_factory(
    config: OpscriptConfig,
) -> Boto3AWSClientFactory:
    return Boto3AWSClientFactory(
        connect_timeout=config.connect_timeout,
        read_timeout=config.read_timeout,
        retry_mode="standard",
        retry_total_max_attempts=config.sdk_total_max_attempts,
    )


def build_default_discovery_provider(
    config: OpscriptConfig | None = None,
):
    active_config = config or build_config()
    active_config.validate()

    return build_aws_discovery_provider(
        build_aws_client_factory(active_config),
        discovery_scope=active_config.discovery_scope,
    )


def build_snapshot_storage(
    config: OpscriptConfig | None = None,
) -> SnapshotStorage:
    active_config = config or build_config()
    active_config.validate()

    if active_config.storage_backend == "s3":
        return S3SnapshotStorage(
            client=build_aws_client_factory(active_config).client("s3"),
            bucket=active_config.s3_bucket,
            key=_snapshot_storage_namespace(active_config),
            serializer=SnapshotSerializer(),
            discovery_scope=active_config.discovery_scope,
        )

    return InMemorySnapshotStorage(discovery_scope=active_config.discovery_scope)


def build_snapshot_storage_for_discovery_scope(
    config: OpscriptConfig,
    discovery_scope: DiscoveryScope,
) -> SnapshotStorage:
    return build_snapshot_storage(
        config=replace(
            config,
            discovery_scope=discovery_scope,
        )
    )


def build_discovery_scope_activity_workflow(
    config: OpscriptConfig | None = None,
) -> DiscoveryScopeActivityWorkflow:
    active_config = config or build_config()
    active_config.validate()

    return DiscoveryScopeActivityWorkflow(
        eligibility_workflow=DiscoveryScopeEligibilityWorkflow(
            eligibility_service=DiscoveryScopeEligibilityService()
        ),
        activity_facts_service=DiscoveryScopeActivityFactsService(
            analysis_service=build_analysis_service(active_config)
        ),
        comparison_service=DiscoveryScopeActivityComparisonService(),
        report_service=DiscoveryScopeActivityReportService(),
        storage_factory=lambda discovery_scope: (
            build_snapshot_storage_for_discovery_scope(
                active_config,
                discovery_scope,
            )
        ),
    )


def _snapshot_storage_namespace(
    config: OpscriptConfig,
) -> str:
    configured_namespace = config.s3_key.rstrip("/")

    if config.discovery_scope in {
        DEFAULT_DISCOVERY_SCOPE,
        DEFAULT_LOCAL_DISCOVERY_SCOPE,
    }:
        return configured_namespace

    scope_namespace = _encode_scope_namespace_segment(config.discovery_scope)
    return f"{configured_namespace}/discovery-scopes/{scope_namespace}"


def _encode_scope_namespace_segment(
    discovery_scope: DiscoveryScope,
) -> str:
    return quote(str(discovery_scope), safe="").replace(".", "%2E")


def build_inventory_service(
    discovery_provider: DiscoveryProvider | None = None,
    snapshot_storage: SnapshotStorage | None = None,
    config: OpscriptConfig | None = None,
) -> InventoryService:
    active_config = config or build_config()
    active_config.validate()

    return InventoryService(
        discovery_provider=discovery_provider
        or build_default_discovery_provider(active_config),
        snapshot_storage=snapshot_storage or build_snapshot_storage(active_config),
    )


def build_analysis_service(
    config: OpscriptConfig | None = None,
) -> AnalysisService:
    active_config = config or build_config()
    active_config.validate()

    return AnalysisService(
        SnapshotDiffer(),
    )


def build_reporting_service(
    config: OpscriptConfig | None = None,
) -> ReportingService:
    active_config = config or build_config()
    active_config.validate()

    return ReportingService(
        reporter=NoOpReporter(),
    )

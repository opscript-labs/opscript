from opscript.application import (
    HealthReport,
    HealthService,
    InfrastructureChangeSummaryService,
    WorkflowExecution,
    WorkflowMetricsFactory,
)
from opscript.bootstrap import (
    build_analysis_service,
    build_config,
    build_default_discovery_provider,
    build_reporting_service,
    build_snapshot_storage,
)
from opscript.config import OpscriptConfig, ConfigurationError
from opscript.formatter import format_output
from opscript.models import Failure, ServiceResult, Success


def format_health_report(report: HealthReport) -> str:
    lines = [
        f"Health: {report.overall_status}",
        "",
        "Checks:",
    ]

    for check in report.checks:
        lines.append(f"- {check.name}: {check.status} - {check.message}")

    return "\n".join(lines)


def _build_observation_workflow_composition(config: OpscriptConfig):
    analysis = build_analysis_service(config)
    summary = InfrastructureChangeSummaryService()
    reporting = build_reporting_service(config)
    execution = WorkflowExecution()
    metrics = WorkflowMetricsFactory()

    return (
        analysis,
        summary,
        reporting,
        execution,
        metrics,
    )


def health_command(args, config=None, config_error: ConfigurationError | None = None):
    if config_error is not None:
        config_loader = _raise_configuration_error(config_error)
        active_config = None
    else:
        active_config = config or build_config()

        def config_loader():
            return active_config

    service = HealthService(
        config_loader=config_loader,
        storage_builder=lambda c=None: build_snapshot_storage(c or active_config),
        discovery_provider_builder=lambda c=None: build_default_discovery_provider(
            c or active_config
        ),
        workflow_builder=lambda c=None: _build_observation_workflow_composition(
            c or active_config
        ),
    )
    report = service.check()

    output = format_health_report(report)

    if report.overall_status == "healthy":
        result = Success(
            value=ServiceResult(
                message=output,
            )
        )
    else:
        result = Failure(error=output)

    output = format_output(result, json_mode=args.json)

    return result, output


def _raise_configuration_error(error: ConfigurationError):
    def config_loader():
        raise error

    return config_loader

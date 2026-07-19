import argparse
import sys

from opscript.bootstrap import build_config
from opscript.command_registry import COMMANDS
from opscript.config import ConfigurationError
from opscript.execution import active_execution_log_fields
from opscript.formatter import format_output
from opscript.logger import format_log_event, get_logger
from opscript.runtime import run_accepted_runtime_operation
from opscript.service import Failure, Success

logger = get_logger()


def add_workflow_parser(subparsers, name: str):
    parser = subparsers.add_parser(name)
    parser.add_argument("--fail", action="store_true")
    parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    return parser


def build_parser():
    parser = argparse.ArgumentParser(
        prog="opscript",
        description="Opscript - Infrastructure knowledge CLI",
    )

    parser.add_argument("--fail", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--discovery-scope")
    parser.add_argument("--version", action="store_true")

    subparsers = parser.add_subparsers(dest="command")

    add_workflow_parser(subparsers, "run")
    add_workflow_parser(subparsers, "change-review")
    explain_parser = add_workflow_parser(subparsers, "explain")
    explain_parser.add_argument("--subject")
    add_workflow_parser(subparsers, "instability")
    add_workflow_parser(subparsers, "stability")
    add_workflow_parser(subparsers, "activity")
    add_workflow_parser(subparsers, "change-frequency")
    knowledge_review_parser = subparsers.add_parser("knowledge-review")
    knowledge_review_parser.add_argument("--fail", action="store_true")
    knowledge_review_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
    )
    knowledge_review_parser.add_argument("--evolution", action="store_true")
    knowledge_review_parser.add_argument("--sequence", action="store_true")
    churn_parser = add_workflow_parser(subparsers, "churn")
    churn_parser.add_argument("--all", action="store_true")
    metadata_grouping_parser = add_workflow_parser(subparsers, "metadata-grouping")
    metadata_grouping_parser.add_argument("--metadata", required=True)
    observation_history_parser = add_workflow_parser(subparsers, "observation-history")
    observation_history_parser.add_argument("resource_external_id", nargs="?")
    add_workflow_parser(subparsers, "inventory-history")
    cross_scope_activity_parser = add_workflow_parser(
        subparsers,
        "cross-scope-activity",
    )
    cross_scope_activity_parser.add_argument(
        "--discovery-scope",
        action="append",
        dest="comparison_discovery_scopes",
        required=True,
    )

    version_parser = subparsers.add_parser("version")
    version_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
    )

    inventory_parser = subparsers.add_parser("inventory")
    inventory_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
    )

    environment_evolution_parser = subparsers.add_parser("environment-evolution")
    environment_evolution_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
    )

    health_parser = subparsers.add_parser("health")
    health_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
    )

    resource_evolution_parser = subparsers.add_parser("resource-evolution")
    resource_evolution_parser.add_argument("resource_external_id")
    resource_evolution_parser.add_argument(
        "--json",
        action="store_true",
        default=argparse.SUPPRESS,
    )

    return parser


def emit(message: str) -> None:
    print(message)


def emit_startup(json_mode: bool) -> None:
    if json_mode:
        logger.info("Opscript run started")
        return

    emit("Opscript run started")


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    parser = build_parser()
    args, _ = parser.parse_known_args(argv)

    if args.version:
        command = "version"
    else:
        command = args.command or "run"

    handler = COMMANDS.get(command)

    if handler is None:
        emit("Unknown command")
        return 2

    return run_accepted_runtime_operation(
        lambda: _run_accepted_cli_operation(args, command, handler),
        terminal_status=lambda exit_code: "completed" if exit_code == 0 else "failed",
    )


def _run_accepted_cli_operation(args, command: str, handler) -> int:
    if command == "version":
        result, output = handler(args)
        emit(output)
        logger.info(output)
        return 0

    config = None
    config_error = None
    try:
        config = build_config(
            discovery_scope_override=args.discovery_scope,
        )
    except ConfigurationError as error:
        config_error = error
        if command != "health":
            message = f"Configuration error: {error}"
            logger.error(
                format_log_event(
                    "configuration_validation_failed",
                    command=command,
                    reason="configuration_error",
                    **active_execution_log_fields(),
                )
            )
            result = Failure(error=message)
            output = format_output(result, json_mode=args.json)
            emit(output)
            return 1

    logger.info(
        format_log_event(
            "configuration_validated",
            command=command,
            **active_execution_log_fields(),
        )
    )

    emit_startup(args.json)

    if command == "health":
        result, output = handler(args, config=config, config_error=config_error)
    else:
        result, output = handler(args, config=config)

    emit(output)

    if isinstance(result, Failure):
        return 1

    if isinstance(result, Success):
        return 0

    emit("Unknown result")
    return 2


if __name__ == "__main__":
    sys.exit(main())

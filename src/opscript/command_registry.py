from opscript.cli_operations import health_command
from opscript.commands import (
    activity_command,
    change_frequency_command,
    churn_command,
    cross_scope_activity_command,
    environment_evolution_command,
    explain_command,
    instability_command,
    inventory_command,
    inventory_history_command,
    knowledge_review_command,
    metadata_grouping_command,
    observation_history_command,
    resource_evolution_command,
    run_command,
    stability_command,
    version_command,
)


def handle_run(args, config=None):
    return run_command(args, config=config)


def handle_change_review(args, config=None):
    return run_command(args, config=config)


def handle_explain(args, config=None):
    return explain_command(args, config=config)


def handle_version(args, config=None):
    return version_command(args)


def handle_inventory(args, config=None):
    return inventory_command(args, config=config)


def handle_inventory_history(args, config=None):
    return inventory_history_command(args, config=config)


def handle_resource_evolution(args, config=None):
    return resource_evolution_command(args, config=config)


def handle_environment_evolution(args, config=None):
    return environment_evolution_command(args, config=config)


def handle_instability(args, config=None):
    return instability_command(args, config=config)


def handle_stability(args, config=None):
    return stability_command(args, config=config)


def handle_activity(args, config=None):
    return activity_command(args, config=config)


def handle_change_frequency(args, config=None):
    return change_frequency_command(args, config=config)


def handle_churn(args, config=None):
    return churn_command(args, config=config)


def handle_knowledge_review(args, config=None):
    return knowledge_review_command(args, config=config)


def handle_metadata_grouping(args, config=None):
    return metadata_grouping_command(args, config=config)


def handle_observation_history(args, config=None):
    return observation_history_command(args, config=config)


def handle_cross_scope_activity(args, config=None):
    return cross_scope_activity_command(args, config=config)


def handle_health(args, config=None, config_error=None):
    return health_command(args, config=config, config_error=config_error)


COMMANDS = {
    "run": handle_run,
    "change-review": handle_change_review,
    "explain": handle_explain,
    "version": handle_version,
    "inventory": handle_inventory,
    "inventory-history": handle_inventory_history,
    "resource-evolution": handle_resource_evolution,
    "environment-evolution": handle_environment_evolution,
    "instability": handle_instability,
    "stability": handle_stability,
    "activity": handle_activity,
    "change-frequency": handle_change_frequency,
    "knowledge-review": handle_knowledge_review,
    "churn": handle_churn,
    "metadata-grouping": handle_metadata_grouping,
    "observation-history": handle_observation_history,
    "cross-scope-activity": handle_cross_scope_activity,
    "health": handle_health,
}

import json

from opscript.models import Failure, Success


def format_output(result, json_mode: bool = False):
    """
    Formats CLI output for both text and JSON modes.
    """

    if isinstance(result, Failure):
        if json_mode:
            return json.dumps(
                {
                    "status": "error",
                    "error": result.error,
                }
            )
        return result.error

    if isinstance(result, Success):
        from opscript.application.engineering_knowledge_report_projection import (
            EngineeringKnowledgeServiceResult,
        )
        from opscript.models import DiscoveryScopeActivityServiceResult

        if isinstance(result.value, EngineeringKnowledgeServiceResult):
            if json_mode:
                engineering_knowledge = {
                    "supported_engineering_conditions": [
                        _engineering_knowledge_condition(entry)
                        for entry in result.value.supported_engineering_conditions
                    ]
                }
                if result.value.engineering_knowledge_evolution is not None:
                    engineering_knowledge["engineering_knowledge_evolution"] = (
                        _engineering_knowledge_evolution(
                            result.value.engineering_knowledge_evolution,
                            earlier_qualified_evaluation=(
                                result.value.earlier_qualified_evaluation
                            ),
                            later_qualified_evaluation=(
                                result.value.later_qualified_evaluation
                            ),
                        )
                    )
                elif (
                    result.value.engineering_knowledge_evolution_unavailable_message
                    is not None
                ):
                    engineering_knowledge["engineering_knowledge_evolution"] = {
                        "availability": "unavailable",
                        "message": (
                            result.value.engineering_knowledge_evolution_unavailable_message
                        ),
                    }
                if result.value.engineering_knowledge_sequence_analysis is not None:
                    engineering_knowledge["engineering_knowledge_sequence_analysis"] = (
                        _engineering_knowledge_sequence_analysis(
                            result.value.engineering_knowledge_sequence_analysis
                        )
                    )
                return json.dumps(
                    {
                        "status": "success",
                        "engineering_knowledge": engineering_knowledge,
                    }
                )
            return result.value.message

        if isinstance(result.value, DiscoveryScopeActivityServiceResult):
            res = result.value.workflow_result
            if json_mode:
                data = {
                    "status": "success",
                    "workflow_status": res.comparison_status,
                    "reason": res.reason,
                    "requested_scopes": [s.value for s in res.requested_scopes],
                    "eligible_scopes": [s.value for s in res.eligible_scopes],
                    "excluded_scopes": [
                        {
                            "discovery_scope": e.discovery_scope.value,
                            "eligibility_status": e.eligibility_status,
                            "reason": e.reason,
                        }
                        for e in res.excluded_scopes
                    ],
                }
                if res.activity_report:
                    rep = res.activity_report
                    data["activity_report"] = {
                        "compared_scope_count": rep.compared_scope_count,
                        "total_endpoint_resources": rep.total_endpoint_resources,
                        "total_introduced": rep.total_introduced,
                        "total_modified": rep.total_modified,
                        "total_removed": rep.total_removed,
                        "total_represented_changes": rep.total_represented_changes,
                        "scope_reports": [
                            {
                                "discovery_scope": r.discovery_scope.value,
                                "snapshot_count": r.snapshot_count,
                                "valid_interval_count": r.valid_interval_count,
                                "endpoint_resource_count": r.endpoint_resource_count,
                                "introduced_count": r.introduced_count,
                                "modified_count": r.modified_count,
                                "removed_count": r.removed_count,
                                "total_represented_change_count": r.total_represented_change_count,
                                "effective_evidence_window": r.effective_evidence_window,
                            }
                            for r in rep.scope_reports
                        ],
                    }
                else:
                    data["activity_report"] = None
                return json.dumps(data)
            else:
                return result.value.message

        message = result.value.message

        if json_mode:
            return json.dumps(
                {
                    "status": "success",
                    "message": message,
                }
            )

        return message

    if json_mode:
        return json.dumps(
            {
                "status": "error",
                "error": "Unknown result type",
            }
        )

    return "Unknown result type"


def _engineering_knowledge_condition(entry):
    condition = {
        "engineering_condition": entry.engineering_condition,
        "recognition_basis": entry.recognition_basis,
        "discovery_scope": entry.discovery_scope.value,
        "qualified_observation_window": {
            "previous_snapshot": str(entry.observation_window_previous_snapshot_id),
            "current_snapshot": str(entry.observation_window_current_snapshot_id),
        },
    }

    if entry.canonical_subject is not None:
        condition["subject"] = entry.canonical_subject

    return condition


def _engineering_knowledge_evolution(
    comparison,
    *,
    earlier_qualified_evaluation=None,
    later_qualified_evaluation=None,
):
    evolution = {
        "introduced_supported_engineering_conditions": [
            _engineering_knowledge_evolution_condition(entry)
            for entry in comparison.introduced
        ],
        "removed_supported_engineering_conditions": [
            _engineering_knowledge_evolution_condition(entry)
            for entry in comparison.removed
        ],
        "unchanged_supported_engineering_conditions": [
            _engineering_knowledge_evolution_condition(unchanged.evaluation_b)
            for unchanged in comparison.unchanged
        ],
    }

    if (
        earlier_qualified_evaluation is not None
        and later_qualified_evaluation is not None
    ):
        return {
            "earlier_qualified_evaluation": _engineering_knowledge_evaluation_context(
                earlier_qualified_evaluation
            ),
            "later_qualified_evaluation": _engineering_knowledge_evaluation_context(
                later_qualified_evaluation
            ),
            **evolution,
        }

    return evolution


def _engineering_knowledge_evaluation_context(context):
    return {
        "discovery_scope": context.discovery_scope.value,
        "qualified_observation_window": {
            "previous_snapshot": str(context.observation_window_previous_snapshot_id),
            "current_snapshot": str(context.observation_window_current_snapshot_id),
        },
    }


def _engineering_knowledge_evolution_condition(entry):
    condition = {
        "engineering_condition": entry.engineering_condition,
        "discovery_scope": entry.discovery_scope.value,
    }

    if entry.canonical_subject is not None:
        condition["subject"] = entry.canonical_subject

    return condition


def _engineering_knowledge_sequence_analysis(result):
    if result.availability == "unavailable":
        return {
            "availability": "unavailable",
            "message": result.message,
        }

    analysis = result.analysis
    supported_engineering_condition = {
        "engineering_condition": analysis.engineering_condition,
        "discovery_scope": analysis.discovery_scope.value,
    }

    if analysis.canonical_subject is not None:
        supported_engineering_condition["subject"] = analysis.canonical_subject

    return {
        "availability": "available",
        "supported_engineering_condition": supported_engineering_condition,
        "qualified_evaluation_sequence": {
            "start_evaluation": _sequence_evaluation_context(
                analysis.sequence_start_evaluation
            ),
            "end_evaluation": _sequence_evaluation_context(
                analysis.sequence_end_evaluation
            ),
            "qualified_evaluation_count": analysis.qualified_evaluation_count,
        },
        "support_state_at_sequence_start": _support_state(
            analysis.supported_at_sequence_start
        ),
        "support_state_at_sequence_end": _support_state(
            analysis.supported_at_sequence_end
        ),
        "continuous_support": _analytical_state(analysis.continuously_supported),
        "new_support_within_sequence": _analytical_state(analysis.newly_supported),
        "support_end_within_sequence": _analytical_state(analysis.no_longer_supported),
        "reappearance_within_sequence": _analytical_state(analysis.reappeared),
    }


def _sequence_evaluation_context(context):
    return {
        "qualified_observation_window": {
            "previous_snapshot": str(context.observation_window_previous_snapshot_id),
            "current_snapshot": str(context.observation_window_current_snapshot_id),
        }
    }


def _support_state(supported: bool) -> str:
    if supported:
        return "supported"

    return "unsupported"


def _analytical_state(established: bool) -> str:
    if established:
        return "established"

    return "not_established"

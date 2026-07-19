from opscript.application.engineering_condition_support_comparison_projection import (
    EngineeringConditionSupportComparisonProjection,
)


_CLASSIFICATION_TEXT = {
    "SUPPORTED_IN_ALL_SCOPES": "Supported in all compared Discovery Scopes",
    "SUPPORTED_IN_SOME_SCOPES": "Supported in some compared Discovery Scopes",
    "SUPPORTED_IN_NO_SCOPES": "Supported in no compared Discovery Scopes",
}


def format_engineering_condition_support_comparison(
    projection: EngineeringConditionSupportComparisonProjection,
) -> str:
    if not isinstance(projection, EngineeringConditionSupportComparisonProjection):
        raise TypeError(
            "projection must be EngineeringConditionSupportComparisonProjection."
        )

    lines = [
        "Engineering Condition",
        "",
        projection.engineering_condition,
        "",
        "Support Distribution",
        "",
        _CLASSIFICATION_TEXT[projection.classification],
        "",
        "Compared Discovery Scopes",
        *_scope_lines(projection.compared_discovery_scopes),
        "",
        "Supported",
        *_scope_lines(projection.supported_discovery_scopes),
        "",
        "Not Supported",
        *_scope_lines(projection.not_supported_discovery_scopes),
        "",
        "Excluded",
        *_excluded_scope_lines(projection.excluded_discovery_scopes),
    ]
    return "\n".join(lines)


def _scope_lines(discovery_scopes) -> list[str]:
    if not discovery_scopes:
        return ["None"]

    return [f"- {discovery_scope}" for discovery_scope in discovery_scopes]


def _excluded_scope_lines(excluded_discovery_scopes) -> list[str]:
    if not excluded_discovery_scopes:
        return ["None"]

    lines = []
    for excluded_scope in excluded_discovery_scopes:
        lines.extend(
            [
                f"- {excluded_scope.discovery_scope}",
                "  Reason:",
                f"  {excluded_scope.reason}",
            ]
        )
    return lines

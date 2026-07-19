from datetime import UTC, datetime

from opscript.application.engineering_condition_evaluation import (
    EngineeringConditionComparisonEligibility,
    ExcludedEngineeringConditionEvaluation,
    compare_engineering_condition_support_distribution,
)
from opscript.application.engineering_condition_support_comparison_formatter import (
    format_engineering_condition_support_comparison,
)
from opscript.application.engineering_condition_support_comparison_projection import (
    project_engineering_condition_support_comparison,
)
from opscript.execution import get_active_execution
from opscript.models import (
    QualifiedHistoricalEvidence,
    RecognitionResult,
    ScopeLocalEngineeringConditionEvaluation,
)
from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation


ENGINEERING_CONDITION = (
    RecognitionResult.recurring_infrastructure_removal_activity_condition
)


def test_all_supported_output_is_deterministic():
    output = _format(
        _projection(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert output == "\n".join(
        [
            "Engineering Condition",
            "",
            ENGINEERING_CONDITION,
            "",
            "Support Distribution",
            "",
            "Supported in all compared Discovery Scopes",
            "",
            "Compared Discovery Scopes",
            "- scope-a",
            "- scope-b",
            "",
            "Supported",
            "- scope-a",
            "- scope-b",
            "",
            "Not Supported",
            "None",
            "",
            "Excluded",
            "None",
        ]
    )


def test_some_supported_output_is_deterministic():
    output = _format(
        _projection(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
        )
    )

    assert "Supported in some compared Discovery Scopes" in output
    assert "- scope-a" in output
    assert "- scope-b" in output


def test_none_supported_output_is_deterministic():
    output = _format(
        _projection(
            _evaluation("scope-a", "not_supported"),
            _evaluation("scope-b", "not_supported"),
        )
    )

    assert "Supported in no compared Discovery Scopes" in output
    assert _section(output, "Supported") == ["None"]
    assert _section(output, "Not Supported") == ["- scope-a", "- scope-b"]


def test_exclusions_are_rendered_with_exact_reason():
    output = _format(
        _projection(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
            excluded=(
                _excluded(
                    "scope-c",
                    reason="engineering_condition_mismatch",
                ),
            ),
        )
    )

    assert _section(output, "Excluded") == [
        "- scope-c",
        "  Reason:",
        "  engineering_condition_mismatch",
    ]


def test_ordering_is_preserved_for_all_populations():
    output = _format(
        _projection(
            _evaluation("scope-b", "not_supported"),
            _evaluation("scope-a", "supported"),
            _evaluation("scope-d", "not_supported"),
            _evaluation("scope-c", "supported"),
            excluded=(
                _excluded("scope-f"),
                _excluded("scope-e"),
            ),
        )
    )

    assert _section(output, "Compared Discovery Scopes") == [
        "- scope-b",
        "- scope-a",
        "- scope-d",
        "- scope-c",
    ]
    assert _section(output, "Supported") == ["- scope-a", "- scope-c"]
    assert _section(output, "Not Supported") == ["- scope-b", "- scope-d"]
    assert _section(output, "Excluded") == [
        "- scope-f",
        "  Reason:",
        "  engineering_condition_mismatch",
        "- scope-e",
        "  Reason:",
        "  engineering_condition_mismatch",
    ]


def test_empty_excluded_population_renders_none():
    output = _format(
        _projection(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert _section(output, "Excluded") == ["None"]


def test_repeated_formatting_returns_identical_output():
    projection = _projection(
        _evaluation("scope-a", "supported"),
        _evaluation("scope-b", "not_supported"),
    )

    assert _format(projection) == _format(projection)


def test_formatter_does_not_mutate_projection_or_scopes():
    projection = _projection(
        _evaluation("scope-a", "supported"),
        _evaluation("scope-b", "not_supported"),
    )
    before = (
        projection.compared_discovery_scopes,
        projection.supported_discovery_scopes,
        projection.not_supported_discovery_scopes,
        projection.excluded_discovery_scopes,
    )

    _format(projection)

    assert (
        projection.compared_discovery_scopes,
        projection.supported_discovery_scopes,
        projection.not_supported_discovery_scopes,
        projection.excluded_discovery_scopes,
    ) == before
    assert projection.compared_discovery_scopes[0] is before[0][0]


def test_formatter_does_not_execute_comparison_or_compatibility():
    names = format_engineering_condition_support_comparison.__code__.co_names

    assert "compare_engineering_condition_support_distribution" not in names
    assert "assess_engineering_condition_comparison_eligibility" not in names
    assert "Recognition" not in names
    assert "Finding" not in names


def test_formatter_has_no_runtime_or_telemetry_side_effects():
    projection = _projection(
        _evaluation("scope-a", "supported"),
        _evaluation("scope-b", "not_supported"),
    )
    before_execution = get_active_execution()

    _format(projection)

    assert before_execution is None
    assert get_active_execution() is None
    names = format_engineering_condition_support_comparison.__code__.co_names
    assert "format_log_event" not in names
    assert "Workflow" not in names
    assert "boto3" not in names
    assert "load_history" not in names
    assert "save" not in names


def test_formatter_does_not_generate_json():
    output = _format(
        _projection(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "supported"),
        )
    )

    assert not output.startswith("{")
    assert '"status"' not in output
    assert (
        "json" not in format_engineering_condition_support_comparison.__code__.co_names
    )


def test_formatter_uses_no_prohibited_product_words():
    output = _format(
        _projection(
            _evaluation("scope-a", "supported"),
            _evaluation("scope-b", "not_supported"),
        )
    ).lower()

    for word in (
        "healthy",
        "risk",
        "confidence",
        "compliance",
        "recommendation",
        "severity",
        "best",
        "worst",
        "preferred",
    ):
        assert word not in output


def _format(projection) -> str:
    return format_engineering_condition_support_comparison(projection)


def _projection(
    *eligible_evaluations: ScopeLocalEngineeringConditionEvaluation,
    excluded: tuple[ExcludedEngineeringConditionEvaluation, ...] = (),
):
    comparison = compare_engineering_condition_support_distribution(
        EngineeringConditionComparisonEligibility(
            requested_evaluations=tuple(eligible_evaluations)
            + tuple(exclusion.evaluation for exclusion in excluded),
            eligible_evaluations=eligible_evaluations,
            excluded_evaluations=excluded,
        )
    )
    return project_engineering_condition_support_comparison(comparison)


def _excluded(
    scope_value: str,
    *,
    reason: str = "engineering_condition_mismatch",
) -> ExcludedEngineeringConditionEvaluation:
    return ExcludedEngineeringConditionEvaluation(
        evaluation=_other_condition_evaluation(scope_value),
        reason=reason,
    )


def _evaluation(
    scope_value: str,
    outcome: str,
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome=outcome,
        qualified_historical_evidence=_qualified_evidence(
            DiscoveryScope(scope_value),
            "resource_removed" if outcome == "supported" else "resource_created",
        ),
        engineering_condition=ENGINEERING_CONDITION,
    )


def _other_condition_evaluation(
    scope_value: str,
) -> ScopeLocalEngineeringConditionEvaluation:
    return ScopeLocalEngineeringConditionEvaluation(
        outcome="supported",
        qualified_historical_evidence=_qualified_evidence(
            DiscoveryScope(scope_value),
            "resource_created",
        ),
        engineering_condition=(
            RecognitionResult.recurring_infrastructure_introduction_activity_condition
        ),
    )


def _qualified_evidence(
    scope: DiscoveryScope,
    observation_type: str,
) -> QualifiedHistoricalEvidence:
    snapshot_ids = tuple(Identifier.new() for _ in range(5))
    intervals = tuple(
        CompletedComparisonInterval(
            discovery_scope=scope,
            previous_snapshot_id=snapshot_ids[index],
            current_snapshot_id=snapshot_ids[index + 1],
            observations=(
                Observation(
                    subject=f"{scope.value}-{index}",
                    type=observation_type,
                    message=f"{observation_type}: {scope.value}",
                    timestamp=datetime.now(UTC),
                    previous_snapshot_id=snapshot_ids[index],
                    current_snapshot_id=snapshot_ids[index + 1],
                ),
            ),
        )
        for index in range(4)
    )
    return QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=snapshot_ids[0],
        observation_window_current_snapshot_id=snapshot_ids[-1],
        completed_intervals=intervals,
        canonical_subject=None,
    )


def _section(output: str, heading: str) -> list[str]:
    lines = output.splitlines()
    start = lines.index(heading) + 1
    while start < len(lines) and lines[start] == "":
        start += 1

    collected = []
    for line in lines[start:]:
        if line == "":
            break
        collected.append(line)
    return collected

from datetime import UTC, datetime

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation

from opscript.application.knowledge_evaluation_workflow import (
    evaluate_engineering_knowledge,
)
from opscript.models import QualifiedHistoricalEvidence


def test_ec001_only_returns_one_finding():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_modified",),
                ("resource_modified",),
                ("resource_created",),
                ("resource_modified",),
            ),
            canonical_subject="resource-001",
        )
    )

    assert len(findings) == 1
    assert (
        findings[0].recognition_result.engineering_condition
        == "frequent_infrastructure_modification"
    )


def test_ec002_only_returns_one_finding():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_removed",),
                ("other_resource_removed",),
                ("resource_created",),
                ("third_resource_removed",),
            ),
            canonical_subject=None,
        )
    )

    assert len(findings) == 1
    assert (
        findings[0].recognition_result.engineering_condition
        == "recurring_infrastructure_removal_activity"
    )


def test_ec003_only_returns_one_finding():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_created",),
                ("other_resource_created",),
                ("resource_modified",),
                ("third_resource_created",),
            ),
            canonical_subject=None,
        )
    )

    assert len(findings) == 1
    assert (
        findings[0].recognition_result.engineering_condition
        == "recurring_infrastructure_introduction_activity"
    )


def test_ec003_not_supported_is_omitted():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_created",),
                ("resource_modified",),
                ("resource_removed",),
                ("resource_modified",),
            ),
            canonical_subject=None,
        )
    )

    assert findings == ()


def test_both_supported_return_two_findings_in_rule_order():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_modified", "resource_removed"),
                ("resource_modified", "other_resource_removed"),
                ("resource_created",),
                ("resource_modified", "third_resource_removed"),
            ),
            canonical_subject="resource-001",
        )
    )

    assert tuple(
        finding.recognition_result.engineering_condition for finding in findings
    ) == (
        "frequent_infrastructure_modification",
        "recurring_infrastructure_removal_activity",
    )


def test_ec002_and_ec003_supported_return_two_findings_in_rule_order():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_removed", "resource_created"),
                ("other_resource_removed", "other_resource_created"),
                ("resource_modified",),
                ("third_resource_removed", "third_resource_created"),
            ),
            canonical_subject=None,
        )
    )

    assert tuple(
        finding.recognition_result.engineering_condition for finding in findings
    ) == (
        "recurring_infrastructure_removal_activity",
        "recurring_infrastructure_introduction_activity",
    )
    assert (
        findings[0].recognition_result.qualified_historical_evidence.canonical_subject
        is None
    )
    assert (
        findings[1].recognition_result.qualified_historical_evidence.canonical_subject
        is None
    )


def test_ec001_and_ec003_supported_return_two_findings_in_rule_order():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_modified", "resource_created"),
                ("resource_modified", "other_resource_created"),
                ("resource_removed",),
                ("resource_modified", "third_resource_created"),
            ),
            canonical_subject="resource-001",
        )
    )

    assert tuple(
        finding.recognition_result.engineering_condition for finding in findings
    ) == (
        "frequent_infrastructure_modification",
        "recurring_infrastructure_introduction_activity",
    )


def test_all_three_supported_return_three_findings_in_rule_order():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_modified", "resource_removed", "resource_created"),
                (
                    "resource_modified",
                    "other_resource_removed",
                    "other_resource_created",
                ),
                ("resource_removed", "resource_created"),
                ("resource_modified",),
                ("third_resource_removed", "third_resource_created"),
            ),
            canonical_subject="resource-001",
        )
    )

    assert tuple(
        finding.recognition_result.engineering_condition for finding in findings
    ) == (
        "frequent_infrastructure_modification",
        "recurring_infrastructure_removal_activity",
        "recurring_infrastructure_introduction_activity",
    )
    assert (
        findings[0].recognition_result.qualified_historical_evidence.canonical_subject
        == "resource-001"
    )
    assert (
        findings[1].recognition_result.qualified_historical_evidence.canonical_subject
        is None
    )
    assert (
        findings[2].recognition_result.qualified_historical_evidence.canonical_subject
        is None
    )


def test_neither_supported_returns_empty_tuple():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_modified",),
                ("resource_created",),
                ("resource_removed",),
                ("resource_created",),
            ),
            canonical_subject="resource-001",
        )
    )

    assert findings == ()


def test_ec001_is_skipped_without_canonical_subject_and_scope_level_rules_still_run():
    findings = evaluate_engineering_knowledge(
        _evidence(
            (
                ("resource_modified", "resource_removed", "resource_created"),
                (
                    "resource_modified",
                    "other_resource_removed",
                    "other_resource_created",
                ),
                ("resource_modified",),
                (
                    "resource_modified",
                    "third_resource_removed",
                    "third_resource_created",
                ),
            ),
            canonical_subject=None,
        )
    )

    assert tuple(
        finding.recognition_result.engineering_condition for finding in findings
    ) == (
        "recurring_infrastructure_removal_activity",
        "recurring_infrastructure_introduction_activity",
    )


def test_repeated_workflow_execution_is_deterministic():
    evidence = _evidence(
        (
            ("resource_modified", "resource_removed"),
            ("resource_modified", "other_resource_removed"),
            ("resource_created",),
            ("resource_modified", "third_resource_removed"),
        ),
        canonical_subject="resource-001",
    )

    assert evaluate_engineering_knowledge(evidence) == evaluate_engineering_knowledge(
        evidence
    )


def test_workflow_does_not_mutate_qualified_historical_evidence():
    evidence = _evidence(
        (
            ("resource_modified", "resource_removed"),
            ("resource_modified", "other_resource_removed"),
            ("resource_created",),
            ("resource_modified", "third_resource_removed"),
        ),
        canonical_subject="resource-001",
    )
    intervals = evidence.completed_intervals

    evaluate_engineering_knowledge(evidence)

    assert evidence.completed_intervals is intervals


def test_workflow_does_not_mutate_completed_intervals_or_observations():
    evidence = _evidence(
        (
            ("resource_modified", "resource_removed"),
            ("resource_modified", "other_resource_removed"),
            ("resource_created",),
            ("resource_modified", "third_resource_removed"),
        ),
        canonical_subject="resource-001",
    )
    interval = evidence.completed_intervals[0]
    observations = interval.observations
    observation = observations[0]

    evaluate_engineering_knowledge(evidence)

    assert evidence.completed_intervals[0] is interval
    assert evidence.completed_intervals[0].observations is observations
    assert evidence.completed_intervals[0].observations[0] is observation


def _evidence(
    observation_groups: tuple[tuple[str, ...], ...],
    *,
    canonical_subject: str | None,
) -> QualifiedHistoricalEvidence:
    scope = DiscoveryScope("scope-001")
    snapshot_ids = tuple(Identifier.new() for _ in range(len(observation_groups) + 1))
    intervals = tuple(
        _interval(
            discovery_scope=scope,
            previous_snapshot_id=snapshot_ids[index],
            current_snapshot_id=snapshot_ids[index + 1],
            observation_types=observation_types,
        )
        for index, observation_types in enumerate(observation_groups)
    )
    return QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=snapshot_ids[0],
        observation_window_current_snapshot_id=snapshot_ids[-1],
        completed_intervals=intervals,
        canonical_subject=canonical_subject,
    )


def _interval(
    *,
    discovery_scope: DiscoveryScope,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    observation_types: tuple[str, ...],
) -> CompletedComparisonInterval:
    return CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=tuple(
            _observation(
                observation_type=observation_type,
                previous_snapshot_id=previous_snapshot_id,
                current_snapshot_id=current_snapshot_id,
            )
            for observation_type in observation_types
        ),
    )


def _observation(
    *,
    observation_type: str,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
) -> Observation:
    subject = "resource-001"
    normalized_type = observation_type
    if observation_type == "other_resource_removed":
        subject = "resource-002"
        normalized_type = "resource_removed"
    elif observation_type == "third_resource_removed":
        subject = "resource-003"
        normalized_type = "resource_removed"
    elif observation_type == "other_resource_created":
        subject = "resource-002"
        normalized_type = "resource_created"
    elif observation_type == "third_resource_created":
        subject = "resource-003"
        normalized_type = "resource_created"

    return Observation(
        subject=subject,
        type=normalized_type,
        message=f"{normalized_type}: {subject}",
        timestamp=datetime.now(UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

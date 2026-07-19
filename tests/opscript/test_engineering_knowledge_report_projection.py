from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import (
    CompletedComparisonInterval,
    DiscoveryScope,
    Finding,
    Observation,
)

from opscript.application.engineering_knowledge_report_projection import (
    EngineeringKnowledgeReportEntry,
    _RECOGNITION_BASIS_BY_ENGINEERING_CONDITION,
    project_engineering_knowledge_report,
)
from opscript.models import QualifiedHistoricalEvidence, RecognizedFinding

EC001_RECOGNITION_BASIS = (
    "Qualified historical evidence demonstrated repeated modification of the "
    "reported subject across the qualified observation window."
)
EC002_RECOGNITION_BASIS = (
    "Qualified historical evidence demonstrated recurring infrastructure removal "
    "activity across the qualified observation window for the Discovery Scope."
)
EC003_RECOGNITION_BASIS = (
    "Qualified historical evidence demonstrated recurring infrastructure "
    "introduction activity across the qualified observation window for the "
    "Discovery Scope."
)


def test_empty_recognized_findings_project_to_empty_immutable_tuple():
    report = project_engineering_knowledge_report(())

    assert report == ()
    assert isinstance(report, tuple)


def test_one_ec001_recognized_finding_projects_correctly():
    finding = _recognized_finding(
        engineering_condition="frequent_infrastructure_modification",
        observation_groups=(
            ("resource_modified",),
            ("resource_modified",),
            ("resource_created",),
            ("resource_modified",),
        ),
        canonical_subject="resource-001",
    )

    entry = project_engineering_knowledge_report((finding,))[0]

    assert entry.engineering_condition == "frequent_infrastructure_modification"
    assert entry.recognition_outcome == "supported"
    assert (
        entry.discovery_scope
        == finding.recognition_result.qualified_historical_evidence.discovery_scope
    )
    assert entry.canonical_subject == "resource-001"
    assert entry.recognition_basis == EC001_RECOGNITION_BASIS


def test_one_ec002_recognized_finding_projects_correctly():
    finding = _recognized_finding(
        engineering_condition="recurring_infrastructure_removal_activity",
        observation_groups=(
            ("resource_removed",),
            ("other_resource_removed",),
            ("resource_created",),
            ("third_resource_removed",),
        ),
        canonical_subject=None,
    )

    entry = project_engineering_knowledge_report((finding,))[0]

    assert entry.engineering_condition == "recurring_infrastructure_removal_activity"
    assert entry.recognition_outcome == "supported"
    assert entry.canonical_subject is None
    assert entry.recognition_basis == EC002_RECOGNITION_BASIS


def test_one_ec003_recognized_finding_projects_recognition_basis():
    finding = _recognized_finding(
        engineering_condition="recurring_infrastructure_introduction_activity",
        observation_groups=(
            ("resource_created",),
            ("other_resource_created",),
            ("resource_modified",),
            ("third_resource_created",),
        ),
        canonical_subject=None,
    )

    entry = project_engineering_knowledge_report((finding,))[0]

    assert (
        entry.engineering_condition == "recurring_infrastructure_introduction_activity"
    )
    assert entry.recognition_basis == EC003_RECOGNITION_BASIS


def test_ec001_and_ec002_use_same_report_entry_shape():
    ec001 = project_engineering_knowledge_report(
        (
            _recognized_finding(
                engineering_condition="frequent_infrastructure_modification",
                observation_groups=(("resource_modified",),) * 4,
                canonical_subject="resource-001",
            ),
        )
    )[0]
    ec002 = project_engineering_knowledge_report(
        (
            _recognized_finding(
                engineering_condition="recurring_infrastructure_removal_activity",
                observation_groups=(("resource_removed",),) * 4,
                canonical_subject=None,
            ),
        )
    )[0]

    assert type(ec001) is type(ec002) is EngineeringKnowledgeReportEntry
    assert tuple(ec001.__dict__.keys()) == tuple(ec002.__dict__.keys())


def test_engineering_condition_identity_is_preserved():
    finding = _recognized_finding(
        engineering_condition="recurring_infrastructure_removal_activity",
        observation_groups=(("resource_removed",),) * 4,
        canonical_subject=None,
    )

    entry = project_engineering_knowledge_report((finding,))[0]

    assert (
        entry.engineering_condition == finding.recognition_result.engineering_condition
    )


def test_discovery_scope_is_preserved():
    finding = _recognized_finding(
        engineering_condition="frequent_infrastructure_modification",
        observation_groups=(("resource_modified",),) * 4,
        canonical_subject="resource-001",
    )

    entry = project_engineering_knowledge_report((finding,))[0]

    assert (
        entry.discovery_scope
        is finding.recognition_result.qualified_historical_evidence.discovery_scope
    )


def test_canonical_subject_presence_and_absence_are_preserved():
    ec001 = _recognized_finding(
        engineering_condition="frequent_infrastructure_modification",
        observation_groups=(("resource_modified",),) * 4,
        canonical_subject="resource-001",
    )
    ec002 = _recognized_finding(
        engineering_condition="recurring_infrastructure_removal_activity",
        observation_groups=(("resource_removed",),) * 4,
        canonical_subject=None,
    )

    report = project_engineering_knowledge_report((ec001, ec002))

    assert report[0].canonical_subject == "resource-001"
    assert report[1].canonical_subject is None


def test_observation_window_boundaries_are_preserved_in_roles():
    finding = _recognized_finding(
        engineering_condition="frequent_infrastructure_modification",
        observation_groups=(("resource_modified",),) * 4,
        canonical_subject="resource-001",
    )
    evidence = finding.recognition_result.qualified_historical_evidence

    entry = project_engineering_knowledge_report((finding,))[0]

    assert (
        entry.observation_window_previous_snapshot_id
        is evidence.observation_window_previous_snapshot_id
    )
    assert (
        entry.observation_window_current_snapshot_id
        is evidence.observation_window_current_snapshot_id
    )


def test_recognition_calibration_values_are_preserved():
    finding = _recognized_finding(
        engineering_condition="recurring_infrastructure_removal_activity",
        observation_groups=(("resource_removed",),) * 4,
        canonical_subject=None,
    )
    recognition_result = finding.recognition_result

    entry = project_engineering_knowledge_report((finding,))[0]

    assert entry.recognition_threshold == recognition_result.recognition_threshold
    assert (
        entry.minimum_completed_interval_count
        == recognition_result.minimum_completed_interval_count
    )


def test_input_order_is_preserved():
    ec002 = _recognized_finding(
        engineering_condition="recurring_infrastructure_removal_activity",
        observation_groups=(("resource_removed",),) * 4,
        canonical_subject=None,
    )
    ec001 = _recognized_finding(
        engineering_condition="frequent_infrastructure_modification",
        observation_groups=(("resource_modified",),) * 4,
        canonical_subject="resource-001",
    )

    report = project_engineering_knowledge_report((ec002, ec001))

    assert tuple(entry.engineering_condition for entry in report) == (
        "recurring_infrastructure_removal_activity",
        "frequent_infrastructure_modification",
    )


def test_repeated_projection_is_deterministic():
    findings = (
        _recognized_finding(
            engineering_condition="frequent_infrastructure_modification",
            observation_groups=(("resource_modified",),) * 4,
            canonical_subject="resource-001",
        ),
    )

    assert project_engineering_knowledge_report(findings) == (
        project_engineering_knowledge_report(findings)
    )


def test_returned_projection_is_immutable():
    entry = project_engineering_knowledge_report(
        (
            _recognized_finding(
                engineering_condition="frequent_infrastructure_modification",
                observation_groups=(("resource_modified",),) * 4,
                canonical_subject="resource-001",
            ),
        )
    )[0]

    with pytest.raises(FrozenInstanceError):
        entry.recognition_outcome = "not_supported"


def test_source_artifacts_remain_unchanged():
    finding = _recognized_finding(
        engineering_condition="frequent_infrastructure_modification",
        observation_groups=(("resource_modified",),) * 4,
        canonical_subject="resource-001",
    )
    recognition_result = finding.recognition_result
    evidence = recognition_result.qualified_historical_evidence
    intervals = evidence.completed_intervals
    observation = intervals[0].observations[0]

    project_engineering_knowledge_report((finding,))

    assert finding.recognition_result is recognition_result
    assert recognition_result.qualified_historical_evidence is evidence
    assert evidence.completed_intervals is intervals
    assert intervals[0].observations[0] is observation


def test_missing_approved_basis_is_rejected_without_generic_wording(monkeypatch):
    finding = _recognized_finding(
        engineering_condition="frequent_infrastructure_modification",
        observation_groups=(("resource_modified",),) * 4,
        canonical_subject="resource-001",
    )
    approved_basis = dict(_RECOGNITION_BASIS_BY_ENGINEERING_CONDITION)
    approved_basis.pop("frequent_infrastructure_modification")
    monkeypatch.setattr(
        "opscript.application.engineering_knowledge_report_projection."
        "_RECOGNITION_BASIS_BY_ENGINEERING_CONDITION",
        approved_basis,
    )

    with pytest.raises(ValueError, match="no approved recognition basis"):
        project_engineering_knowledge_report((finding,))


def test_platformiq_finding_is_rejected():
    finding = Finding(
        subject="resource-001",
        type="infrastructure_changed",
        message="Infrastructure changed: resource-001",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_modified",
    )

    with pytest.raises(TypeError, match="RecognizedFinding"):
        project_engineering_knowledge_report((finding,))  # type: ignore[arg-type]


def test_report_entry_has_no_judgment_or_workflow_fields():
    entry = project_engineering_knowledge_report(
        (
            _recognized_finding(
                engineering_condition="frequent_infrastructure_modification",
                observation_groups=(("resource_modified",),) * 4,
                canonical_subject="resource-001",
            ),
        )
    )[0]

    for field_name in (
        "severity",
        "confidence",
        "risk",
        "recommendation",
        "ownership",
        "workflow_state",
        "urgency",
        "remediation",
        "business_impact",
        "root_cause",
    ):
        assert not hasattr(entry, field_name)


def _recognized_finding(
    *,
    engineering_condition: str,
    observation_groups: tuple[tuple[str, ...], ...],
    canonical_subject: str | None,
) -> RecognizedFinding:
    return RecognizedFinding(
        recognition_result=__import__(
            "opscript.models",
            fromlist=("RecognitionResult",),
        ).RecognitionResult(
            outcome="supported",
            qualified_historical_evidence=_evidence(
                observation_groups,
                canonical_subject=canonical_subject,
            ),
            engineering_condition=engineering_condition,  # type: ignore[arg-type]
        )
    )


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

import inspect
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.analysis.findings import findings_from_observations
from platformiq.core import Identifier
from platformiq.model import (
    CompletedComparisonInterval,
    DiscoveryScope,
    Finding,
    Observation,
)

from opscript.application.recurring_infrastructure_removal_activity_rule import (
    RecurringInfrastructureRemovalActivityRule,
)
from opscript.application.recognized_finding_projection import (
    recognized_finding_from_recognition,
)
from opscript.models import (
    QualifiedHistoricalEvidence,
    RecognizedFinding,
    RecognitionResult,
)


def test_recognized_finding_is_immutable():
    finding = RecognizedFinding(recognition_result=_recognition_result("supported"))

    with pytest.raises(FrozenInstanceError):
        finding.recognition_result = _recognition_result("supported")


def test_recognized_finding_stores_exactly_one_recognition_result():
    recognition_result = _recognition_result("supported")

    finding = RecognizedFinding(recognition_result=recognition_result)

    assert finding.recognition_result is recognition_result
    assert tuple(finding.__dict__.keys()) == ("recognition_result",)


def test_recognized_finding_accepts_supported_recognition_result():
    recognition_result = _recognition_result("supported")

    finding = RecognizedFinding(recognition_result=recognition_result)

    assert finding.recognition_result == recognition_result


def test_recognized_finding_rejects_not_supported_recognition_result():
    with pytest.raises(ValueError, match="supported recognition"):
        RecognizedFinding(recognition_result=_recognition_result("not_supported"))


def test_recognized_finding_exposes_no_duplicated_context_fields():
    finding = RecognizedFinding(recognition_result=_recognition_result("supported"))

    assert not hasattr(finding, "engineering_condition")
    assert not hasattr(finding, "subject")
    assert not hasattr(finding, "discovery_scope")
    assert not hasattr(finding, "threshold")
    assert not hasattr(finding, "qualified_historical_evidence")


def test_recognized_finding_contains_no_lifecycle_fields():
    finding = RecognizedFinding(recognition_result=_recognition_result("supported"))

    assert not hasattr(finding, "category")
    assert not hasattr(finding, "type")
    assert not hasattr(finding, "source_observation_type")


def test_recognized_finding_contains_no_operational_state_fields():
    finding = RecognizedFinding(recognition_result=_recognition_result("supported"))

    assert not hasattr(finding, "severity")
    assert not hasattr(finding, "confidence")
    assert not hasattr(finding, "recommendation")
    assert not hasattr(finding, "ownership")
    assert not hasattr(finding, "acknowledgment")
    assert not hasattr(finding, "workflow_state")


def test_recognized_finding_is_not_platformiq_finding():
    finding = RecognizedFinding(recognition_result=_recognition_result("supported"))

    assert not isinstance(finding, Finding)
    assert type(finding) is not Finding


def test_recognized_finding_preserves_exact_recognition_result_instance():
    recognition_result = _recognition_result("supported")

    finding = RecognizedFinding(recognition_result=recognition_result)

    assert finding.recognition_result is recognition_result


def test_supported_recognition_projects_to_one_recognized_finding():
    recognition_result = _recognition_result("supported")

    finding = recognized_finding_from_recognition(recognition_result)

    assert isinstance(finding, RecognizedFinding)
    assert finding.recognition_result is recognition_result


def test_not_supported_recognition_projection_is_rejected():
    with pytest.raises(ValueError, match="supported recognition"):
        recognized_finding_from_recognition(_recognition_result("not_supported"))


def test_supported_recurring_removal_recognition_projects_to_one_recognized_finding():
    recognition_result = _recurring_removal_recognition_result(
        (
            "resource_removed",
            "resource_removed",
            "resource_created",
            "resource_removed",
        )
    )

    finding = recognized_finding_from_recognition(recognition_result)

    assert recognition_result.outcome == "supported"
    assert (
        recognition_result.engineering_condition
        == "recurring_infrastructure_removal_activity"
    )
    assert isinstance(finding, RecognizedFinding)
    assert finding.recognition_result is recognition_result
    assert (
        finding.recognition_result.engineering_condition
        == "recurring_infrastructure_removal_activity"
    )


def test_recurring_removal_projection_does_not_duplicate_evidence_fields():
    recognition_result = _recurring_removal_recognition_result(
        (
            "resource_removed",
            "resource_removed",
            "resource_created",
            "resource_removed",
        )
    )

    finding = recognized_finding_from_recognition(recognition_result)

    assert tuple(finding.__dict__.keys()) == ("recognition_result",)
    assert not hasattr(finding, "engineering_condition")
    assert not hasattr(finding, "discovery_scope")
    assert not hasattr(finding, "canonical_subject")
    assert not hasattr(finding, "observation_window_previous_snapshot_id")
    assert not hasattr(finding, "observation_window_current_snapshot_id")
    assert not hasattr(finding, "completed_intervals")


def test_not_supported_recurring_removal_recognition_projection_is_rejected():
    recognition_result = _recurring_removal_recognition_result(
        (
            "resource_removed",
            "resource_created",
            "resource_modified",
            "resource_removed",
        )
    )

    assert recognition_result.outcome == "not_supported"

    with pytest.raises(ValueError, match="supported recognition"):
        recognized_finding_from_recognition(recognition_result)


def test_equal_supported_recognitions_produce_equal_recognized_findings():
    recognition_result = _recognition_result("supported")
    first = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=recognition_result.qualified_historical_evidence,
    )
    second = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=recognition_result.qualified_historical_evidence,
    )

    assert recognized_finding_from_recognition(first) == (
        recognized_finding_from_recognition(second)
    )


def test_equal_supported_recurring_removal_recognitions_produce_equal_findings():
    evidence = _qualified_evidence(
        (
            "resource_removed",
            "resource_removed",
            "resource_created",
            "resource_removed",
        )
    )
    first = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=evidence,
        engineering_condition="recurring_infrastructure_removal_activity",
    )
    second = RecognitionResult(
        outcome="supported",
        qualified_historical_evidence=evidence,
        engineering_condition="recurring_infrastructure_removal_activity",
    )

    assert recognized_finding_from_recognition(first) == (
        recognized_finding_from_recognition(second)
    )


def test_repeated_projection_is_deterministic():
    recognition_result = _recognition_result("supported")

    assert recognized_finding_from_recognition(recognition_result) == (
        recognized_finding_from_recognition(recognition_result)
    )


def test_repeated_recurring_removal_projection_is_deterministic():
    recognition_result = _recurring_removal_recognition_result(
        (
            "resource_removed",
            "resource_removed",
            "resource_created",
            "resource_removed",
        )
    )

    assert recognized_finding_from_recognition(recognition_result) == (
        recognized_finding_from_recognition(recognition_result)
    )


def test_projection_contains_no_condition_specific_branching():
    source = inspect.getsource(recognized_finding_from_recognition)

    assert "engineering_condition" not in source
    assert "recurring_infrastructure_removal_activity" not in source
    assert "frequent_infrastructure_modification" not in source


def test_projection_does_not_mutate_recognition_result():
    recognition_result = _recognition_result("supported")
    original_outcome = recognition_result.outcome

    recognized_finding_from_recognition(recognition_result)

    assert recognition_result.outcome == original_outcome


def test_projection_does_not_mutate_qualified_historical_evidence():
    recognition_result = _recognition_result("supported")
    evidence = recognition_result.qualified_historical_evidence
    original_intervals = evidence.completed_intervals

    recognized_finding_from_recognition(recognition_result)

    assert evidence.completed_intervals == original_intervals


def test_projection_does_not_mutate_intervals_or_observations():
    recognition_result = _recognition_result("supported")
    interval = recognition_result.qualified_historical_evidence.completed_intervals[0]
    observation = interval.observations[0]
    original_observation = observation

    recognized_finding_from_recognition(recognition_result)

    assert interval.observations[0] is original_observation
    assert observation.type == "resource_modified"


def test_projection_performs_no_recognition_re_evaluation():
    recognition_result = _recognition_result(
        "supported",
        observation_types=("resource_created",) * 4,
    )

    finding = recognized_finding_from_recognition(recognition_result)

    assert finding.recognition_result is recognition_result
    assert finding.recognition_result.outcome == "supported"


def test_recognized_finding_has_no_generated_identifier_or_timestamp():
    finding = recognized_finding_from_recognition(_recognition_result("supported"))

    assert not hasattr(finding, "id")
    assert not hasattr(finding, "timestamp")


def test_existing_platformiq_finding_remains_constructible():
    finding = Finding(
        subject="resource-001",
        type="infrastructure_changed",
        message="Infrastructure changed: resource-001",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_modified",
    )

    assert finding.type == "infrastructure_changed"


def test_existing_findings_from_observations_behavior_remains_unchanged():
    observation = Observation(
        subject="resource-001",
        type="resource_modified",
        message="Resource modified: resource-001",
        timestamp=datetime.now(UTC),
    )

    findings = findings_from_observations((observation,))

    assert findings == (
        Finding(
            subject="resource-001",
            type="infrastructure_changed",
            message="Infrastructure changed: resource-001",
            timestamp=observation.timestamp,
            source_observation_type="resource_modified",
        ),
    )


def test_recognized_finding_is_not_accepted_as_platformiq_finding_type():
    recognized_finding = recognized_finding_from_recognition(
        _recognition_result("supported")
    )

    assert not isinstance(recognized_finding, Finding)


def test_no_existing_analysis_result_or_workflow_references_recognized_finding():
    from platformiq.model.analysis_result import AnalysisResult

    assert "RecognizedFinding" not in AnalysisResult.__annotations__.values()


def _recognition_result(
    outcome: str,
    *,
    observation_types: tuple[str, ...] = ("resource_modified",) * 4,
) -> RecognitionResult:
    return RecognitionResult(
        outcome=outcome,  # type: ignore[arg-type]
        qualified_historical_evidence=_qualified_evidence(observation_types),
    )


def _recurring_removal_recognition_result(
    observation_types: tuple[str, ...],
) -> RecognitionResult:
    return RecurringInfrastructureRemovalActivityRule().evaluate(
        _qualified_evidence(observation_types)
    )


def _qualified_evidence(
    observation_types: tuple[str, ...],
) -> QualifiedHistoricalEvidence:
    scope = DiscoveryScope("scope-001")
    snapshot_ids = tuple(Identifier.new() for _ in range(len(observation_types) + 1))
    intervals = tuple(
        _interval(
            discovery_scope=scope,
            previous_snapshot_id=snapshot_ids[index],
            current_snapshot_id=snapshot_ids[index + 1],
            observation_type=observation_type,
        )
        for index, observation_type in enumerate(observation_types)
    )
    return QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=snapshot_ids[0],
        observation_window_current_snapshot_id=snapshot_ids[-1],
        completed_intervals=intervals,
        canonical_subject="resource-001",
    )


def _interval(
    *,
    discovery_scope: DiscoveryScope,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    observation_type: str,
) -> CompletedComparisonInterval:
    return CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=(
            Observation(
                subject="resource-001",
                type=observation_type,
                message=f"{observation_type}: resource-001",
                timestamp=datetime.now(UTC),
                previous_snapshot_id=previous_snapshot_id,
                current_snapshot_id=current_snapshot_id,
            ),
        ),
    )

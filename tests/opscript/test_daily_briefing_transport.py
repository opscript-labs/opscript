from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
import json

import pytest

from opscript.application.daily_briefing_projection import (
    DailyBriefingProjection,
)
from opscript.application.daily_briefing_transport import (
    DAILY_BRIEFING_TRANSPORT_VERSION,
    DailyBriefingTransportRepresentation,
    daily_briefing_transport_from_projection,
    daily_briefing_transport_to_dict,
)
from platformiq.core import Identifier
from platformiq.model import AnalysisResult, DiffResult, Finding, Observation


TIMESTAMP = datetime(2026, 1, 1, 9, 18, tzinfo=UTC)


def test_transport_representation_is_versioned() -> None:
    projection = DailyBriefingProjection().project(_analysis_result())

    representation = daily_briefing_transport_from_projection(projection)

    assert representation.version == DAILY_BRIEFING_TRANSPORT_VERSION
    assert representation.version == "daily_briefing.v1"


def test_transport_preserves_projection_scope_and_summary() -> None:
    previous_snapshot_id = Identifier.from_string(
        "00000000-0000-0000-0000-000000000001"
    )
    current_snapshot_id = Identifier.from_string("00000000-0000-0000-0000-000000000002")
    observation = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    finding = _finding(
        "new_infrastructure_introduced",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    projection = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
            findings=(finding,),
        )
    )

    representation = daily_briefing_transport_from_projection(projection)

    assert representation.scope.previous_snapshot_id == str(previous_snapshot_id)
    assert representation.scope.current_snapshot_id == str(current_snapshot_id)
    assert representation.structural_summary.observation_count == 1
    assert representation.structural_summary.finding_count == 1
    assert representation.structural_summary.introduced_count == 1
    assert representation.structural_summary.modified_count == 0
    assert representation.structural_summary.removed_count == 0
    assert representation.structural_summary.distinct_affected_subject_count == 1
    assert representation.structural_summary.is_empty is False


def test_transport_preserves_selected_observation_fields() -> None:
    previous_snapshot_id = Identifier.from_string(
        "00000000-0000-0000-0000-000000000001"
    )
    current_snapshot_id = Identifier.from_string("00000000-0000-0000-0000-000000000002")
    observation = _observation(
        "resource_modified",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        message="Resource changed",
        metadata={"region": "us-east-1", "count": 2},
    )
    projection = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
        )
    )

    representation = daily_briefing_transport_from_projection(projection)

    transport_observation = representation.observations[0]
    assert transport_observation.subject == "resource-b"
    assert transport_observation.type == "resource_modified"
    assert transport_observation.message == "Resource changed"
    assert transport_observation.timestamp == TIMESTAMP.isoformat()
    assert transport_observation.previous_snapshot_id == str(previous_snapshot_id)
    assert transport_observation.current_snapshot_id == str(current_snapshot_id)
    assert tuple(entry.key for entry in transport_observation.metadata) == (
        "count",
        "region",
    )


def test_transport_preserves_selected_finding_fields() -> None:
    previous_snapshot_id = Identifier.from_string(
        "00000000-0000-0000-0000-000000000001"
    )
    current_snapshot_id = Identifier.from_string("00000000-0000-0000-0000-000000000002")
    finding = _finding(
        "infrastructure_changed",
        "resource-b",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        message="Finding text",
        metadata={"owner": "platform"},
        source_observation_type="resource_modified",
    )
    projection = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            findings=(finding,),
        )
    )

    representation = daily_briefing_transport_from_projection(projection)

    transport_finding = representation.findings[0]
    assert transport_finding.subject == "resource-b"
    assert transport_finding.type == "infrastructure_changed"
    assert transport_finding.message == "Finding text"
    assert transport_finding.timestamp == TIMESTAMP.isoformat()
    assert transport_finding.source_observation_type == "resource_modified"
    assert transport_finding.previous_snapshot_id == str(previous_snapshot_id)
    assert transport_finding.current_snapshot_id == str(current_snapshot_id)
    assert tuple(entry.key for entry in transport_finding.metadata) == ("owner",)


def test_empty_projection_maps_to_empty_transport_collections() -> None:
    projection = DailyBriefingProjection().project(_analysis_result())

    representation = daily_briefing_transport_from_projection(projection)

    assert representation.observations == ()
    assert representation.findings == ()
    assert representation.structural_summary.is_empty is True


def test_transport_representation_is_immutable() -> None:
    projection = DailyBriefingProjection().project(_analysis_result())
    representation = daily_briefing_transport_from_projection(projection)

    with pytest.raises(FrozenInstanceError):
        representation.version = "daily_briefing.v2"

    with pytest.raises(AttributeError):
        representation.observations.append(object())


def test_transport_dict_is_json_ready_and_preserves_shape() -> None:
    previous_snapshot_id = Identifier.from_string(
        "00000000-0000-0000-0000-000000000001"
    )
    current_snapshot_id = Identifier.from_string("00000000-0000-0000-0000-000000000002")
    observation = _observation(
        "resource_created",
        "resource-a",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        metadata={"nested": {"key": "value"}, "tags": ("a", "b")},
    )
    projection = DailyBriefingProjection().project(
        _analysis_result(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
        )
    )
    representation = daily_briefing_transport_from_projection(projection)

    payload = daily_briefing_transport_to_dict(representation)

    json.dumps(payload)
    assert payload == {
        "version": "daily_briefing.v1",
        "daily_briefing": {
            "scope": {
                "previous_snapshot_id": str(previous_snapshot_id),
                "current_snapshot_id": str(current_snapshot_id),
            },
            "structural_summary": {
                "observation_count": 1,
                "finding_count": 0,
                "introduced_count": 1,
                "modified_count": 0,
                "removed_count": 0,
                "distinct_affected_subject_count": 1,
                "is_empty": False,
            },
            "observations": [
                {
                    "subject": "resource-a",
                    "type": "resource_created",
                    "message": "Observation for resource-a",
                    "timestamp": TIMESTAMP.isoformat(),
                    "previous_snapshot_id": str(previous_snapshot_id),
                    "current_snapshot_id": str(current_snapshot_id),
                    "metadata": {
                        "nested": {"key": "value"},
                        "tags": ["a", "b"],
                    },
                }
            ],
            "findings": [],
        },
    }


def test_transport_rejects_non_projection_input() -> None:
    with pytest.raises(TypeError, match="DailyBriefingProjectionResult"):
        daily_briefing_transport_from_projection(object())


def test_dict_conversion_rejects_non_transport_input() -> None:
    with pytest.raises(TypeError, match="DailyBriefingTransportRepresentation"):
        daily_briefing_transport_to_dict(object())


def test_transport_mapping_does_not_mutate_projection() -> None:
    projection = DailyBriefingProjection().project(_analysis_result())
    before = projection

    daily_briefing_transport_from_projection(projection)

    assert projection == before


def test_transport_mapping_uses_existing_projection_result_only() -> None:
    projection = DailyBriefingProjection().project(_analysis_result())

    representation = daily_briefing_transport_from_projection(projection)

    assert isinstance(representation, DailyBriefingTransportRepresentation)
    assert not hasattr(representation, "analysis_result")
    assert not hasattr(representation, "projection_service")
    assert not hasattr(representation, "lambda_event")
    assert not hasattr(representation, "http_status")


def _analysis_result(
    *,
    previous_snapshot_id: Identifier | None = None,
    current_snapshot_id: Identifier | None = None,
    observations: tuple[Observation, ...] = (),
    findings: tuple[Finding, ...] = (),
) -> AnalysisResult:
    return AnalysisResult(
        diff=DiffResult(
            previous_snapshot_id=previous_snapshot_id or Identifier.new(),
            current_snapshot_id=current_snapshot_id or Identifier.new(),
        ),
        observations=observations,
        findings=findings,
    )


def _observation(
    observation_type: str,
    subject: str,
    *,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    message: str | None = None,
    metadata: dict[str, object] | None = None,
) -> Observation:
    return Observation(
        subject=subject,
        type=observation_type,
        message=message or f"Observation for {subject}",
        timestamp=TIMESTAMP,
        metadata=metadata,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )


def _finding(
    finding_type: str,
    subject: str,
    *,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    source_observation_type: str = "resource_created",
    message: str | None = None,
    metadata: dict[str, object] | None = None,
) -> Finding:
    return Finding(
        subject=subject,
        type=finding_type,
        message=message or f"Finding for {subject}",
        timestamp=TIMESTAMP,
        source_observation_type=source_observation_type,
        metadata=metadata,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

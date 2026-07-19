from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opscript.application.daily_briefing_projection import (
    DailyBriefingProjectionResult,
)
from platformiq.model import Finding, Observation


DAILY_BRIEFING_TRANSPORT_VERSION = "daily_briefing.v1"


@dataclass(frozen=True)
class DailyBriefingTransportMetadataEntry:
    key: str
    value: Any


@dataclass(frozen=True)
class DailyBriefingTransportScope:
    previous_snapshot_id: str
    current_snapshot_id: str


@dataclass(frozen=True)
class DailyBriefingTransportStructuralSummary:
    observation_count: int
    finding_count: int
    introduced_count: int
    modified_count: int
    removed_count: int
    distinct_affected_subject_count: int
    is_empty: bool


@dataclass(frozen=True)
class DailyBriefingTransportObservation:
    subject: str
    type: str
    message: str
    timestamp: str
    previous_snapshot_id: str
    current_snapshot_id: str
    metadata: tuple[DailyBriefingTransportMetadataEntry, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class DailyBriefingTransportFinding:
    subject: str
    type: str
    message: str
    timestamp: str
    source_observation_type: str
    previous_snapshot_id: str
    current_snapshot_id: str
    metadata: tuple[DailyBriefingTransportMetadataEntry, ...] = field(
        default_factory=tuple
    )


@dataclass(frozen=True)
class DailyBriefingTransportRepresentation:
    version: str
    scope: DailyBriefingTransportScope
    structural_summary: DailyBriefingTransportStructuralSummary
    observations: tuple[DailyBriefingTransportObservation, ...] = field(
        default_factory=tuple
    )
    findings: tuple[DailyBriefingTransportFinding, ...] = field(default_factory=tuple)


def daily_briefing_transport_from_projection(
    projection: DailyBriefingProjectionResult,
) -> DailyBriefingTransportRepresentation:
    if not isinstance(projection, DailyBriefingProjectionResult):
        raise TypeError("projection must be a DailyBriefingProjectionResult.")

    return DailyBriefingTransportRepresentation(
        version=DAILY_BRIEFING_TRANSPORT_VERSION,
        scope=DailyBriefingTransportScope(
            previous_snapshot_id=str(projection.scope.previous_snapshot_id),
            current_snapshot_id=str(projection.scope.current_snapshot_id),
        ),
        structural_summary=DailyBriefingTransportStructuralSummary(
            observation_count=projection.structural_summary.observation_count,
            finding_count=projection.structural_summary.finding_count,
            introduced_count=projection.structural_summary.introduced_count,
            modified_count=projection.structural_summary.modified_count,
            removed_count=projection.structural_summary.removed_count,
            distinct_affected_subject_count=(
                projection.structural_summary.distinct_affected_subject_count
            ),
            is_empty=projection.structural_summary.is_empty,
        ),
        observations=tuple(
            _transport_observation(observation)
            for observation in projection.observations
        ),
        findings=tuple(_transport_finding(finding) for finding in projection.findings),
    )


def daily_briefing_transport_to_dict(
    representation: DailyBriefingTransportRepresentation,
) -> dict[str, Any]:
    if not isinstance(representation, DailyBriefingTransportRepresentation):
        raise TypeError(
            "representation must be a DailyBriefingTransportRepresentation."
        )

    return {
        "version": representation.version,
        "daily_briefing": {
            "scope": {
                "previous_snapshot_id": representation.scope.previous_snapshot_id,
                "current_snapshot_id": representation.scope.current_snapshot_id,
            },
            "structural_summary": {
                "observation_count": (
                    representation.structural_summary.observation_count
                ),
                "finding_count": representation.structural_summary.finding_count,
                "introduced_count": (
                    representation.structural_summary.introduced_count
                ),
                "modified_count": representation.structural_summary.modified_count,
                "removed_count": representation.structural_summary.removed_count,
                "distinct_affected_subject_count": (
                    representation.structural_summary.distinct_affected_subject_count
                ),
                "is_empty": representation.structural_summary.is_empty,
            },
            "observations": [
                _transport_observation_to_dict(observation)
                for observation in representation.observations
            ],
            "findings": [
                _transport_finding_to_dict(finding)
                for finding in representation.findings
            ],
        },
    }


def _transport_observation(
    observation: Observation,
) -> DailyBriefingTransportObservation:
    return DailyBriefingTransportObservation(
        subject=observation.subject,
        type=observation.type,
        message=observation.message,
        timestamp=observation.timestamp.isoformat(),
        previous_snapshot_id=str(observation.previous_snapshot_id),
        current_snapshot_id=str(observation.current_snapshot_id),
        metadata=_transport_metadata(observation.metadata),
    )


def _transport_finding(finding: Finding) -> DailyBriefingTransportFinding:
    return DailyBriefingTransportFinding(
        subject=finding.subject,
        type=finding.type,
        message=finding.message,
        timestamp=finding.timestamp.isoformat(),
        source_observation_type=finding.source_observation_type,
        previous_snapshot_id=str(finding.previous_snapshot_id),
        current_snapshot_id=str(finding.current_snapshot_id),
        metadata=_transport_metadata(finding.metadata),
    )


def _transport_metadata(
    metadata: dict[str, Any] | None,
) -> tuple[DailyBriefingTransportMetadataEntry, ...]:
    if metadata is None:
        return ()

    return tuple(
        DailyBriefingTransportMetadataEntry(key=key, value=_transport_value(value))
        for key, value in sorted(metadata.items())
    )


def _transport_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, tuple | list):
        return tuple(_transport_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(
            DailyBriefingTransportMetadataEntry(
                key=str(key),
                value=_transport_value(item_value),
            )
            for key, item_value in sorted(value.items())
        )
    return str(value)


def _metadata_entries_to_dict(
    metadata: tuple[DailyBriefingTransportMetadataEntry, ...],
) -> dict[str, Any]:
    return {entry.key: _transport_dict_value(entry.value) for entry in metadata}


def _transport_dict_value(value: Any) -> Any:
    if isinstance(value, tuple):
        if all(isinstance(item, DailyBriefingTransportMetadataEntry) for item in value):
            return _metadata_entries_to_dict(value)
        return [_transport_dict_value(item) for item in value]
    return value


def _transport_observation_to_dict(
    observation: DailyBriefingTransportObservation,
) -> dict[str, Any]:
    return {
        "subject": observation.subject,
        "type": observation.type,
        "message": observation.message,
        "timestamp": observation.timestamp,
        "previous_snapshot_id": observation.previous_snapshot_id,
        "current_snapshot_id": observation.current_snapshot_id,
        "metadata": _metadata_entries_to_dict(observation.metadata),
    }


def _transport_finding_to_dict(
    finding: DailyBriefingTransportFinding,
) -> dict[str, Any]:
    return {
        "subject": finding.subject,
        "type": finding.type,
        "message": finding.message,
        "timestamp": finding.timestamp,
        "source_observation_type": finding.source_observation_type,
        "previous_snapshot_id": finding.previous_snapshot_id,
        "current_snapshot_id": finding.current_snapshot_id,
        "metadata": _metadata_entries_to_dict(finding.metadata),
    }

from datetime import UTC, datetime

from platformiq.model import (
    AnalysisResult,
    CompletedComparisonInterval,
    DiscoveryScope,
    Observation,
)

from opscript.models import QualifiedHistoricalEvidence


def build_qualified_historical_evidence(
    analysis_history: tuple[AnalysisResult, ...],
    *,
    discovery_scope: DiscoveryScope,
    canonical_subject: str | None,
) -> QualifiedHistoricalEvidence:
    intervals = tuple(
        _completed_interval(result, discovery_scope=discovery_scope)
        for result in analysis_history
    )

    return QualifiedHistoricalEvidence(
        discovery_scope=discovery_scope,
        observation_window_previous_snapshot_id=intervals[0].previous_snapshot_id,
        observation_window_current_snapshot_id=intervals[-1].current_snapshot_id,
        completed_intervals=intervals,
        canonical_subject=canonical_subject,
    )


def canonical_subject_from_history(
    analysis_history: tuple[AnalysisResult, ...],
) -> str | None:
    modified_subjects = {
        observation.subject
        for result in analysis_history
        for observation in result.observations
        if observation.type == "resource_modified"
    }

    if not modified_subjects:
        return None

    return sorted(modified_subjects)[0]


def scope_level_qualified_historical_evidence(
    evidence: QualifiedHistoricalEvidence,
) -> QualifiedHistoricalEvidence:
    if evidence.canonical_subject is None:
        return evidence

    return QualifiedHistoricalEvidence(
        discovery_scope=evidence.discovery_scope,
        observation_window_previous_snapshot_id=(
            evidence.observation_window_previous_snapshot_id
        ),
        observation_window_current_snapshot_id=(
            evidence.observation_window_current_snapshot_id
        ),
        completed_intervals=evidence.completed_intervals,
        canonical_subject=None,
    )


def _completed_interval(
    result: AnalysisResult,
    *,
    discovery_scope: DiscoveryScope,
) -> CompletedComparisonInterval:
    return CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=result.diff.previous_snapshot_id,
        current_snapshot_id=result.diff.current_snapshot_id,
        observations=tuple(
            _recognition_observation(observation) for observation in result.observations
        ),
    )


def _recognition_observation(observation: Observation) -> Observation:
    if observation.type != "resource_deleted":
        return observation

    return Observation(
        subject=observation.subject,
        type="resource_removed",
        message=f"Resource removed: {observation.subject}",
        timestamp=observation.timestamp or datetime.now(UTC),
        previous_snapshot_id=observation.previous_snapshot_id,
        current_snapshot_id=observation.current_snapshot_id,
        metadata=observation.metadata,
    )

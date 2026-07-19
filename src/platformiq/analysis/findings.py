from __future__ import annotations

from platformiq.model.finding import Finding
from platformiq.model.observation import Observation


def findings_from_observations(
    observations: tuple[Observation, ...],
) -> tuple[Finding, ...]:
    findings: list[Finding] = []

    for observation in observations:
        if observation.type == "resource_created":
            findings.append(
                Finding(
                    subject=observation.subject,
                    type="new_infrastructure_introduced",
                    message=f"New infrastructure introduced: {observation.subject}",
                    timestamp=observation.timestamp,
                    source_observation_type=observation.type,
                    metadata=observation.metadata,
                    previous_snapshot_id=observation.previous_snapshot_id,
                    current_snapshot_id=observation.current_snapshot_id,
                )
            )

        if observation.type == "resource_deleted":
            findings.append(
                Finding(
                    subject=observation.subject,
                    type="infrastructure_removed",
                    message=f"Infrastructure removed: {observation.subject}",
                    timestamp=observation.timestamp,
                    source_observation_type=observation.type,
                    metadata=observation.metadata,
                    previous_snapshot_id=observation.previous_snapshot_id,
                    current_snapshot_id=observation.current_snapshot_id,
                )
            )

        if observation.type == "resource_modified":
            findings.append(
                Finding(
                    subject=observation.subject,
                    type="infrastructure_changed",
                    message=f"Infrastructure changed: {observation.subject}",
                    timestamp=observation.timestamp,
                    source_observation_type=observation.type,
                    metadata=observation.metadata,
                    previous_snapshot_id=observation.previous_snapshot_id,
                    current_snapshot_id=observation.current_snapshot_id,
                )
            )

    return tuple(findings)

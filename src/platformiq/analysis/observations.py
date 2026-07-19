from __future__ import annotations

from datetime import UTC, datetime

from platformiq.model.diff_result import DiffResult
from platformiq.model.observation import Observation


def observations_from_diff(diff_result: DiffResult) -> tuple[Observation, ...]:
    observations: list[Observation] = []

    for resource in diff_result.created:
        observations.append(
            Observation(
                subject=resource.external_id,
                type="resource_created",
                message=f"Resource created: {resource.external_id}",
                timestamp=datetime.now(UTC),
                previous_snapshot_id=diff_result.previous_snapshot_id,
                current_snapshot_id=diff_result.current_snapshot_id,
            )
        )

    for resource in diff_result.deleted:
        observations.append(
            Observation(
                subject=resource.external_id,
                type="resource_deleted",
                message=f"Resource deleted: {resource.external_id}",
                timestamp=datetime.now(UTC),
                previous_snapshot_id=diff_result.previous_snapshot_id,
                current_snapshot_id=diff_result.current_snapshot_id,
            )
        )

    for resource in diff_result.modified:
        observations.append(
            Observation(
                subject=resource.external_id,
                type="resource_modified",
                message=f"Resource modified: {resource.external_id}",
                timestamp=datetime.now(UTC),
                previous_snapshot_id=diff_result.previous_snapshot_id,
                current_snapshot_id=diff_result.current_snapshot_id,
            )
        )

    return tuple(observations)

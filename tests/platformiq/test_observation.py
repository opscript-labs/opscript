from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model.observation import Observation


def test_observation_is_immutable():
    observation = Observation(
        subject="resource-1",
        type="resource_created",
        message="Resource was created.",
        timestamp=datetime.now(UTC),
    )

    with pytest.raises(FrozenInstanceError):
        observation.subject = "resource-2"


def test_observation_accepts_complete_comparison_provenance():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    observation = Observation(
        subject="resource-1",
        type="resource_modified",
        message="Resource was modified.",
        timestamp=datetime.now(UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    assert observation.previous_snapshot_id == previous_snapshot_id
    assert observation.current_snapshot_id == current_snapshot_id


def test_observation_accepts_absent_comparison_provenance():
    observation = Observation(
        subject="resource-1",
        type="resource_observed",
        message="Resource was observed.",
        timestamp=datetime.now(UTC),
    )

    assert observation.previous_snapshot_id is None
    assert observation.current_snapshot_id is None


@pytest.mark.parametrize(
    ("previous_snapshot_id", "current_snapshot_id"),
    [
        (Identifier.new(), None),
        (None, Identifier.new()),
    ],
)
def test_observation_rejects_partial_comparison_provenance(
    previous_snapshot_id: Identifier | None,
    current_snapshot_id: Identifier | None,
):
    with pytest.raises(
        ValueError,
        match=(
            "Observation comparison provenance must include both "
            "previous_snapshot_id and current_snapshot_id"
        ),
    ):
        Observation(
            subject="resource-1",
            type="resource_modified",
            message="Resource was modified.",
            timestamp=datetime.now(UTC),
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        )

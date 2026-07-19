from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model.finding import Finding


def test_finding_construction_allows_absent_comparison_provenance():
    finding = Finding(
        subject="resource-1",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced.",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
    )

    assert finding.previous_snapshot_id is None
    assert finding.current_snapshot_id is None


def test_finding_construction_allows_complete_comparison_provenance():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    finding = Finding(
        subject="resource-1",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced.",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    assert finding.previous_snapshot_id == previous_snapshot_id
    assert finding.current_snapshot_id == current_snapshot_id


def test_finding_rejects_previous_snapshot_without_current_snapshot():
    with pytest.raises(
        ValueError, match="previous_snapshot_id and current_snapshot_id"
    ):
        Finding(
            subject="resource-1",
            type="new_infrastructure_introduced",
            message="New infrastructure introduced.",
            timestamp=datetime.now(UTC),
            source_observation_type="resource_created",
            previous_snapshot_id=Identifier.new(),
        )


def test_finding_rejects_current_snapshot_without_previous_snapshot():
    with pytest.raises(
        ValueError, match="previous_snapshot_id and current_snapshot_id"
    ):
        Finding(
            subject="resource-1",
            type="new_infrastructure_introduced",
            message="New infrastructure introduced.",
            timestamp=datetime.now(UTC),
            source_observation_type="resource_created",
            current_snapshot_id=Identifier.new(),
        )


def test_finding_is_immutable():
    finding = Finding(
        subject="resource-1",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced.",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
    )

    with pytest.raises(FrozenInstanceError):
        finding.subject = "resource-2"

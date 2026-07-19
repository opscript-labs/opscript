from datetime import UTC, datetime

from platformiq.analysis.findings import findings_from_observations
from platformiq.core import Identifier
from platformiq.model.observation import Observation


def test_resource_created_observation_becomes_new_infrastructure_finding():
    observation = Observation(
        subject="resource-001",
        type="resource_created",
        message="Resource created: resource-001",
        timestamp=datetime.now(UTC),
    )

    findings = findings_from_observations((observation,))

    assert len(findings) == 1
    assert findings[0].subject == "resource-001"
    assert findings[0].type == "new_infrastructure_introduced"
    assert findings[0].source_observation_type == "resource_created"
    assert findings[0].previous_snapshot_id is None
    assert findings[0].current_snapshot_id is None


def test_resource_deleted_observation_becomes_infrastructure_removed_finding():
    observation = Observation(
        subject="resource-001",
        type="resource_deleted",
        message="Resource deleted: resource-001",
        timestamp=datetime.now(UTC),
    )

    findings = findings_from_observations((observation,))

    assert len(findings) == 1
    assert findings[0].subject == "resource-001"
    assert findings[0].type == "infrastructure_removed"
    assert findings[0].source_observation_type == "resource_deleted"


def test_resource_modified_observation_becomes_infrastructure_changed_finding():
    observation = Observation(
        subject="resource-001",
        type="resource_modified",
        message="Resource modified: resource-001",
        timestamp=datetime.now(UTC),
    )

    findings = findings_from_observations((observation,))

    assert len(findings) == 1
    assert findings[0].subject == "resource-001"
    assert findings[0].type == "infrastructure_changed"
    assert findings[0].source_observation_type == "resource_modified"


def test_unsupported_observation_does_not_create_finding():
    observation = Observation(
        subject="resource-001",
        type="unsupported_observation",
        message="Unsupported observation: resource-001",
        timestamp=datetime.now(UTC),
    )

    findings = findings_from_observations((observation,))

    assert findings == ()


def test_scoped_observation_derives_scoped_finding():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = Observation(
        subject="resource-001",
        type="resource_created",
        message="Resource created: resource-001",
        timestamp=datetime.now(UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    findings = findings_from_observations((observation,))

    assert len(findings) == 1
    assert findings[0].previous_snapshot_id == previous_snapshot_id
    assert findings[0].current_snapshot_id == current_snapshot_id


def test_scoped_observation_derivation_preserves_existing_finding_semantics():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    timestamp = datetime.now(UTC)
    metadata = {"provider": "test"}
    observation = Observation(
        subject="resource-001",
        type="resource_modified",
        message="Resource modified: resource-001",
        timestamp=timestamp,
        metadata=metadata,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    findings = findings_from_observations((observation,))

    assert len(findings) == 1
    assert findings[0].subject == "resource-001"
    assert findings[0].type == "infrastructure_changed"
    assert findings[0].message == "Infrastructure changed: resource-001"
    assert findings[0].timestamp == timestamp
    assert findings[0].source_observation_type == "resource_modified"
    assert findings[0].metadata == metadata
    assert findings[0].previous_snapshot_id == previous_snapshot_id
    assert findings[0].current_snapshot_id == current_snapshot_id

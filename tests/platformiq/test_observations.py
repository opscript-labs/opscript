from platformiq.analysis.observations import observations_from_diff
from platformiq.core import Identifier
from platformiq.model.diff_result import DiffResult
from platformiq.model.resource import Resource
from platformiq.model.value_objects import ResourceState


def test_created_resource_produces_observation_with_interval_provenance():
    resource = Resource(
        id="resource-1",
        external_id="arn:aws:s3:::example-bucket",
        state=ResourceState(),
    )
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    diff = DiffResult(
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        created=(resource,),
    )

    observations = observations_from_diff(diff)

    assert len(observations) == 1

    observation = observations[0]

    assert observation.subject == resource.external_id
    assert observation.type == "resource_created"
    assert observation.previous_snapshot_id == previous_snapshot_id
    assert observation.current_snapshot_id == current_snapshot_id


def test_deleted_resource_produces_observation_with_interval_provenance():
    resource = Resource(
        id="resource-1",
        external_id="arn:aws:s3:::deleted-bucket",
        state=ResourceState(),
    )
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    diff = DiffResult(
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        deleted=(resource,),
    )

    observations = observations_from_diff(diff)

    assert len(observations) == 1

    observation = observations[0]

    assert observation.subject == resource.external_id
    assert observation.type == "resource_deleted"
    assert observation.previous_snapshot_id == previous_snapshot_id
    assert observation.current_snapshot_id == current_snapshot_id


def test_modified_resource_produces_observation_with_interval_provenance():
    resource = Resource(
        id="resource-1",
        external_id="arn:aws:s3:::modified-bucket",
        state=ResourceState(),
    )
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    diff = DiffResult(
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        modified=(resource,),
    )

    observations = observations_from_diff(diff)

    assert len(observations) == 1

    observation = observations[0]

    assert observation.subject == resource.external_id
    assert observation.type == "resource_modified"
    assert observation.previous_snapshot_id == previous_snapshot_id
    assert observation.current_snapshot_id == current_snapshot_id

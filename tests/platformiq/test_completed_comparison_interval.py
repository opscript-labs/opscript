from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import (
    CompletedComparisonInterval,
    DiscoveryScope,
    Finding,
    Observation,
)


def test_interval_accepts_scope_ordered_boundaries_and_zero_observations():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    interval = CompletedComparisonInterval(
        discovery_scope=DiscoveryScope("scope-001"),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    assert interval.discovery_scope == DiscoveryScope("scope-001")
    assert interval.previous_snapshot_id == previous_snapshot_id
    assert interval.current_snapshot_id == current_snapshot_id
    assert interval.observations == ()


def test_interval_accepts_one_matching_observation():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = _observation(
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    interval = CompletedComparisonInterval(
        discovery_scope=DiscoveryScope("scope-001"),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=(observation,),
    )

    assert interval.observations == (observation,)


def test_interval_accepts_multiple_matching_observations():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observations = (
        _observation(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observation_type="resource_created",
        ),
        _observation(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observation_type="resource_modified",
        ),
    )

    interval = CompletedComparisonInterval(
        discovery_scope=DiscoveryScope("scope-001"),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=observations,
    )

    assert interval.observations == observations


def test_interval_is_immutable():
    interval = CompletedComparisonInterval(
        discovery_scope=DiscoveryScope("scope-001"),
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
    )

    with pytest.raises(FrozenInstanceError):
        interval.current_snapshot_id = Identifier.new()


def test_interval_equality_is_deterministic():
    discovery_scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = _observation(
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    first = CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=(observation,),
    )
    second = CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=(observation,),
    )

    assert first == second


def test_reversed_boundaries_produce_distinct_interval():
    discovery_scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()

    interval = CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    reversed_interval = CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=current_snapshot_id,
        current_snapshot_id=previous_snapshot_id,
    )

    assert interval != reversed_interval


def test_observation_missing_comparison_provenance_is_rejected():
    with pytest.raises(
        ValueError,
        match="complete comparison provenance",
    ):
        CompletedComparisonInterval(
            discovery_scope=DiscoveryScope("scope-001"),
            previous_snapshot_id=Identifier.new(),
            current_snapshot_id=Identifier.new(),
            observations=(_observation_without_interval(),),
        )


def test_observation_with_different_previous_snapshot_id_is_rejected():
    interval_previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    observation = _observation(
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=current_snapshot_id,
    )

    with pytest.raises(
        ValueError,
        match="previous_snapshot_id must match",
    ):
        CompletedComparisonInterval(
            discovery_scope=DiscoveryScope("scope-001"),
            previous_snapshot_id=interval_previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
            observations=(observation,),
        )


def test_observation_with_different_current_snapshot_id_is_rejected():
    previous_snapshot_id = Identifier.new()
    interval_current_snapshot_id = Identifier.new()
    observation = _observation(
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=Identifier.new(),
    )

    with pytest.raises(
        ValueError,
        match="current_snapshot_id must match",
    ):
        CompletedComparisonInterval(
            discovery_scope=DiscoveryScope("scope-001"),
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=interval_current_snapshot_id,
            observations=(observation,),
        )


def test_zero_observations_remains_valid_evidence():
    interval = CompletedComparisonInterval(
        discovery_scope=DiscoveryScope("scope-001"),
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
        observations=(),
    )

    assert interval.observations == ()


def test_mutable_input_collection_cannot_mutate_stored_observations():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    first = _observation(
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    mutable_observations = [first]

    interval = CompletedComparisonInterval(
        discovery_scope=DiscoveryScope("scope-001"),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=mutable_observations,  # type: ignore[arg-type]
    )
    mutable_observations.append(
        _observation(
            previous_snapshot_id=previous_snapshot_id,
            current_snapshot_id=current_snapshot_id,
        )
    )

    assert interval.observations == (first,)


def test_interval_has_no_recognition_qualification_or_finding_semantics():
    interval = CompletedComparisonInterval(
        discovery_scope=DiscoveryScope("scope-001"),
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
    )

    assert not hasattr(interval, "recognition_result")
    assert not hasattr(interval, "qualification_status")
    assert not hasattr(interval, "finding")
    assert not isinstance(interval, Finding)


def _observation(
    *,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
    observation_type: str = "resource_modified",
) -> Observation:
    return Observation(
        subject="resource-001",
        type=observation_type,
        message=f"{observation_type}: resource-001",
        timestamp=datetime.now(UTC),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )


def _observation_without_interval() -> Observation:
    return Observation(
        subject="resource-001",
        type="resource_observed",
        message="Resource observed: resource-001",
        timestamp=datetime.now(UTC),
    )

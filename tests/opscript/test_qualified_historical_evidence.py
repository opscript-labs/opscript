from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from platformiq.core import Identifier
from platformiq.model import CompletedComparisonInterval, DiscoveryScope, Observation

from opscript.models import QualifiedHistoricalEvidence


def test_empty_completed_interval_population_is_rejected():
    with pytest.raises(ValueError, match="requires completed intervals"):
        QualifiedHistoricalEvidence(
            discovery_scope=DiscoveryScope("scope-001"),
            observation_window_previous_snapshot_id=Identifier.new(),
            observation_window_current_snapshot_id=Identifier.new(),
            completed_intervals=(),
        )


def test_default_empty_completed_interval_population_is_rejected():
    with pytest.raises(ValueError, match="requires completed intervals"):
        QualifiedHistoricalEvidence(
            discovery_scope=DiscoveryScope("scope-001"),
            observation_window_previous_snapshot_id=Identifier.new(),
            observation_window_current_snapshot_id=Identifier.new(),
        )


def test_one_interval():
    scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    evidence = QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=previous_snapshot_id,
        observation_window_current_snapshot_id=current_snapshot_id,
        completed_intervals=(interval,),
        canonical_subject="resource-001",
    )

    assert evidence.discovery_scope == scope
    assert evidence.completed_intervals == (interval,)
    assert evidence.canonical_subject == "resource-001"


def test_multiple_ordered_intervals():
    scope = DiscoveryScope("scope-001")
    first_snapshot_id = Identifier.new()
    middle_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()
    first_interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=first_snapshot_id,
        current_snapshot_id=middle_snapshot_id,
    )
    second_interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=middle_snapshot_id,
        current_snapshot_id=latest_snapshot_id,
    )

    evidence = QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=first_snapshot_id,
        observation_window_current_snapshot_id=latest_snapshot_id,
        completed_intervals=(first_interval, second_interval),
    )

    assert evidence.completed_intervals == (first_interval, second_interval)


def test_zero_observation_interval_is_retained():
    scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    interval = CompletedComparisonInterval(
        discovery_scope=scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    evidence = QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=previous_snapshot_id,
        observation_window_current_snapshot_id=current_snapshot_id,
        completed_intervals=(interval,),
    )

    assert evidence.completed_intervals[0].observations == ()


def test_completed_interval_collection_is_immutable():
    scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    mutable_intervals = [interval]

    evidence = QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=previous_snapshot_id,
        observation_window_current_snapshot_id=current_snapshot_id,
        completed_intervals=mutable_intervals,  # type: ignore[arg-type]
    )
    mutable_intervals.clear()

    assert evidence.completed_intervals == (interval,)

    with pytest.raises(FrozenInstanceError):
        evidence.completed_intervals = ()


def test_duplicate_interval_is_rejected():
    scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    with pytest.raises(ValueError, match="duplicates"):
        QualifiedHistoricalEvidence(
            discovery_scope=scope,
            observation_window_previous_snapshot_id=previous_snapshot_id,
            observation_window_current_snapshot_id=current_snapshot_id,
            completed_intervals=(interval, interval),
        )


def test_mixed_discovery_scope_is_rejected():
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    interval = _interval(
        discovery_scope=DiscoveryScope("scope-002"),
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    with pytest.raises(ValueError, match="discovery_scope must match"):
        QualifiedHistoricalEvidence(
            discovery_scope=DiscoveryScope("scope-001"),
            observation_window_previous_snapshot_id=previous_snapshot_id,
            observation_window_current_snapshot_id=current_snapshot_id,
            completed_intervals=(interval,),
        )


def test_interval_starting_outside_declared_window_is_rejected():
    scope = DiscoveryScope("scope-001")
    interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
    )

    with pytest.raises(ValueError, match="start at the observation window"):
        QualifiedHistoricalEvidence(
            discovery_scope=scope,
            observation_window_previous_snapshot_id=Identifier.new(),
            observation_window_current_snapshot_id=interval.current_snapshot_id,
            completed_intervals=(interval,),
        )


def test_interval_ending_outside_declared_window_is_rejected():
    scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=Identifier.new(),
    )

    with pytest.raises(ValueError, match="end at the observation window"):
        QualifiedHistoricalEvidence(
            discovery_scope=scope,
            observation_window_previous_snapshot_id=previous_snapshot_id,
            observation_window_current_snapshot_id=Identifier.new(),
            completed_intervals=(interval,),
        )


def test_non_contiguous_interval_order_is_rejected():
    scope = DiscoveryScope("scope-001")
    first_snapshot_id = Identifier.new()
    middle_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()
    first_interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=first_snapshot_id,
        current_snapshot_id=middle_snapshot_id,
    )
    second_interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=latest_snapshot_id,
    )

    with pytest.raises(ValueError, match="ordered contiguously"):
        QualifiedHistoricalEvidence(
            discovery_scope=scope,
            observation_window_previous_snapshot_id=first_snapshot_id,
            observation_window_current_snapshot_id=latest_snapshot_id,
            completed_intervals=(first_interval, second_interval),
        )


def test_equality_is_deterministic():
    scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )

    first = QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=previous_snapshot_id,
        observation_window_current_snapshot_id=current_snapshot_id,
        completed_intervals=(interval,),
        canonical_subject="resource-001",
    )
    second = QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=previous_snapshot_id,
        observation_window_current_snapshot_id=current_snapshot_id,
        completed_intervals=(interval,),
        canonical_subject="resource-001",
    )

    assert first == second


def test_no_recognition_semantics_are_present():
    scope = DiscoveryScope("scope-001")
    previous_snapshot_id = Identifier.new()
    current_snapshot_id = Identifier.new()
    interval = _interval(
        discovery_scope=scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
    )
    evidence = QualifiedHistoricalEvidence(
        discovery_scope=scope,
        observation_window_previous_snapshot_id=previous_snapshot_id,
        observation_window_current_snapshot_id=current_snapshot_id,
        completed_intervals=(interval,),
    )

    assert not hasattr(evidence, "recognition_result")
    assert not hasattr(evidence, "engineering_condition")
    assert not hasattr(evidence, "finding")
    assert not hasattr(evidence, "threshold")


def _interval(
    *,
    discovery_scope: DiscoveryScope,
    previous_snapshot_id: Identifier,
    current_snapshot_id: Identifier,
) -> CompletedComparisonInterval:
    return CompletedComparisonInterval(
        discovery_scope=discovery_scope,
        previous_snapshot_id=previous_snapshot_id,
        current_snapshot_id=current_snapshot_id,
        observations=(
            Observation(
                subject="resource-001",
                type="resource_modified",
                message="Resource modified: resource-001",
                timestamp=datetime.now(UTC),
                previous_snapshot_id=previous_snapshot_id,
                current_snapshot_id=current_snapshot_id,
            ),
        ),
    )

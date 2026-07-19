from dataclasses import FrozenInstanceError

import pytest

from platformiq.core import Identifier
from platformiq.model import DiscoveryScope

from opscript.models import (
    DiscoveryScopeActivityComparison,
    DiscoveryScopeActivityFacts,
    DiscoveryScopeActivityReport,
    DiscoveryScopeActivityWorkflowResult,
    DiscoveryScopeEligibility,
    ExcludedDiscoveryScopeActivity,
    HistoricalInventoryObservation,
    ResourceMetadataGroup,
    ResourceObservationSummary,
    ScopeActivityReport,
)


def test_resource_observation_summary_constructs():
    first_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()

    summary = ResourceObservationSummary(
        resource_external_id="resource-001",
        first_observed_snapshot_id=first_snapshot_id,
        latest_observed_snapshot_id=latest_snapshot_id,
        observed_snapshot_count=3,
        observation_gap_count=1,
    )

    assert summary.resource_external_id == "resource-001"
    assert summary.first_observed_snapshot_id == first_snapshot_id
    assert summary.latest_observed_snapshot_id == latest_snapshot_id
    assert summary.observed_snapshot_count == 3
    assert summary.observation_gap_count == 1


def test_resource_observation_summary_is_immutable():
    summary = ResourceObservationSummary(
        resource_external_id="resource-001",
        first_observed_snapshot_id=Identifier.new(),
        latest_observed_snapshot_id=Identifier.new(),
        observed_snapshot_count=3,
        observation_gap_count=0,
    )

    with pytest.raises(FrozenInstanceError):
        summary.observed_snapshot_count = 4


def test_resource_observation_summary_preserves_observed_snapshot_count():
    summary = ResourceObservationSummary(
        resource_external_id="resource-001",
        first_observed_snapshot_id=Identifier.new(),
        latest_observed_snapshot_id=Identifier.new(),
        observed_snapshot_count=7,
        observation_gap_count=2,
    )

    assert summary.observed_snapshot_count == 7


def test_resource_observation_summary_preserves_identifiers():
    first_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()

    summary = ResourceObservationSummary(
        resource_external_id="resource-001",
        first_observed_snapshot_id=first_snapshot_id,
        latest_observed_snapshot_id=latest_snapshot_id,
        observed_snapshot_count=2,
        observation_gap_count=0,
    )

    assert summary.first_observed_snapshot_id is first_snapshot_id
    assert summary.latest_observed_snapshot_id is latest_snapshot_id


def test_resource_observation_summary_preserves_zero_gaps():
    summary = ResourceObservationSummary(
        resource_external_id="resource-001",
        first_observed_snapshot_id=Identifier.new(),
        latest_observed_snapshot_id=Identifier.new(),
        observed_snapshot_count=4,
        observation_gap_count=0,
    )

    assert summary.observation_gap_count == 0


def test_resource_observation_summary_preserves_multiple_gaps():
    summary = ResourceObservationSummary(
        resource_external_id="resource-001",
        first_observed_snapshot_id=Identifier.new(),
        latest_observed_snapshot_id=Identifier.new(),
        observed_snapshot_count=4,
        observation_gap_count=2,
    )

    assert summary.observation_gap_count == 2


def test_historical_inventory_observation_constructs():
    snapshot_id = Identifier.new()

    observation = HistoricalInventoryObservation(
        snapshot_id=snapshot_id,
        recorded_resource_count=3,
    )

    assert observation.snapshot_id == snapshot_id
    assert observation.recorded_resource_count == 3


def test_historical_inventory_observation_is_immutable():
    observation = HistoricalInventoryObservation(
        snapshot_id=Identifier.new(),
        recorded_resource_count=3,
    )

    with pytest.raises(FrozenInstanceError):
        observation.recorded_resource_count = 4


def test_historical_inventory_observation_preserves_identifier():
    snapshot_id = Identifier.new()

    observation = HistoricalInventoryObservation(
        snapshot_id=snapshot_id,
        recorded_resource_count=3,
    )

    assert observation.snapshot_id is snapshot_id


def test_historical_inventory_observation_preserves_recorded_resource_count():
    observation = HistoricalInventoryObservation(
        snapshot_id=Identifier.new(),
        recorded_resource_count=7,
    )

    assert observation.recorded_resource_count == 7


def test_discovery_scope_eligibility_constructs():
    discovery_scope = DiscoveryScope("scope-a")

    eligibility = DiscoveryScopeEligibility(
        discovery_scope=discovery_scope,
        eligibility_status="eligible",
        reason="comparison_history_available",
        snapshot_count=2,
        valid_interval_count=1,
    )

    assert eligibility.discovery_scope == discovery_scope
    assert eligibility.eligibility_status == "eligible"
    assert eligibility.reason == "comparison_history_available"
    assert eligibility.snapshot_count == 2
    assert eligibility.valid_interval_count == 1


def test_discovery_scope_eligibility_is_immutable():
    eligibility = DiscoveryScopeEligibility(
        discovery_scope=DiscoveryScope("scope-a"),
        eligibility_status="partially_eligible",
        reason="insufficient_comparison_history",
        snapshot_count=1,
        valid_interval_count=0,
    )

    with pytest.raises(FrozenInstanceError):
        eligibility.eligibility_status = "eligible"


def test_discovery_scope_activity_facts_constructs():
    discovery_scope = DiscoveryScope("scope-a")

    facts = DiscoveryScopeActivityFacts(
        discovery_scope=discovery_scope,
        effective_evidence_window="Snapshot 1 -> Snapshot 2",
        snapshot_count=2,
        valid_interval_count=1,
        endpoint_resource_count=3,
        introduced_count=1,
        modified_count=1,
        removed_count=1,
        total_represented_change_count=3,
    )

    assert facts.discovery_scope == discovery_scope
    assert facts.effective_evidence_window == "Snapshot 1 -> Snapshot 2"
    assert facts.snapshot_count == 2
    assert facts.valid_interval_count == 1
    assert facts.endpoint_resource_count == 3
    assert facts.introduced_count == 1
    assert facts.modified_count == 1
    assert facts.removed_count == 1
    assert facts.total_represented_change_count == 3


def test_discovery_scope_activity_facts_is_immutable():
    facts = DiscoveryScopeActivityFacts(
        discovery_scope=DiscoveryScope("scope-a"),
        effective_evidence_window=None,
        snapshot_count=0,
        valid_interval_count=0,
        endpoint_resource_count=0,
        introduced_count=0,
        modified_count=0,
        removed_count=0,
        total_represented_change_count=0,
    )

    with pytest.raises(FrozenInstanceError):
        facts.snapshot_count = 1


def test_discovery_scope_activity_comparison_constructs():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    first = _activity_facts(scope_a)
    second = _activity_facts(scope_b)

    comparison = DiscoveryScopeActivityComparison(
        compared_scope_count=2,
        compared_scopes=(scope_a, scope_b),
        total_endpoint_resources=5,
        total_introduced=1,
        total_modified=2,
        total_removed=3,
        total_represented_changes=6,
        evidence_windows=("Snapshot 1 -> Snapshot 2", "Snapshot 1 -> Snapshot 3"),
        per_scope=(first, second),
    )

    assert comparison.compared_scope_count == 2
    assert comparison.compared_scopes == (scope_a, scope_b)
    assert comparison.total_endpoint_resources == 5
    assert comparison.total_introduced == 1
    assert comparison.total_modified == 2
    assert comparison.total_removed == 3
    assert comparison.total_represented_changes == 6
    assert comparison.evidence_windows == (
        "Snapshot 1 -> Snapshot 2",
        "Snapshot 1 -> Snapshot 3",
    )
    assert comparison.per_scope == (first, second)


def test_discovery_scope_activity_comparison_is_immutable():
    comparison = DiscoveryScopeActivityComparison(
        compared_scope_count=0,
    )

    with pytest.raises(FrozenInstanceError):
        comparison.compared_scope_count = 1


def test_scope_activity_report_constructs():
    discovery_scope = DiscoveryScope("scope-a")

    report = ScopeActivityReport(
        discovery_scope=discovery_scope,
        snapshot_count=2,
        valid_interval_count=1,
        endpoint_resource_count=2,
        introduced_count=1,
        modified_count=2,
        removed_count=3,
        total_represented_change_count=6,
        effective_evidence_window="Snapshot 1 -> Snapshot 2",
    )

    assert report.discovery_scope == discovery_scope
    assert report.snapshot_count == 2
    assert report.valid_interval_count == 1
    assert report.endpoint_resource_count == 2
    assert report.introduced_count == 1
    assert report.modified_count == 2
    assert report.removed_count == 3
    assert report.total_represented_change_count == 6
    assert report.effective_evidence_window == "Snapshot 1 -> Snapshot 2"


def test_scope_activity_report_is_immutable():
    report = ScopeActivityReport(
        discovery_scope=DiscoveryScope("scope-a"),
        snapshot_count=0,
        valid_interval_count=0,
        endpoint_resource_count=0,
        introduced_count=0,
        modified_count=0,
        removed_count=0,
        total_represented_change_count=0,
        effective_evidence_window=None,
    )

    with pytest.raises(FrozenInstanceError):
        report.endpoint_resource_count = 1


def test_discovery_scope_activity_report_constructs():
    scope_report = ScopeActivityReport(
        discovery_scope=DiscoveryScope("scope-a"),
        snapshot_count=2,
        valid_interval_count=1,
        endpoint_resource_count=2,
        introduced_count=1,
        modified_count=2,
        removed_count=3,
        total_represented_change_count=6,
        effective_evidence_window="Snapshot 1 -> Snapshot 2",
    )

    report = DiscoveryScopeActivityReport(
        compared_scope_count=1,
        scope_reports=(scope_report,),
        total_endpoint_resources=2,
        total_introduced=1,
        total_modified=2,
        total_removed=3,
        total_represented_changes=6,
    )

    assert report.compared_scope_count == 1
    assert report.scope_reports == (scope_report,)
    assert report.total_endpoint_resources == 2
    assert report.total_introduced == 1
    assert report.total_modified == 2
    assert report.total_removed == 3
    assert report.total_represented_changes == 6


def test_discovery_scope_activity_report_is_immutable():
    report = DiscoveryScopeActivityReport(compared_scope_count=0)

    with pytest.raises(FrozenInstanceError):
        report.compared_scope_count = 1


def test_excluded_discovery_scope_activity_constructs():
    discovery_scope = DiscoveryScope("scope-a")

    excluded = ExcludedDiscoveryScopeActivity(
        discovery_scope=discovery_scope,
        eligibility_status="ineligible",
        reason="no_snapshot_history",
    )

    assert excluded.discovery_scope == discovery_scope
    assert excluded.eligibility_status == "ineligible"
    assert excluded.reason == "no_snapshot_history"


def test_excluded_discovery_scope_activity_is_immutable():
    excluded = ExcludedDiscoveryScopeActivity(
        discovery_scope=DiscoveryScope("scope-a"),
        eligibility_status="ineligible",
        reason="no_snapshot_history",
    )

    with pytest.raises(FrozenInstanceError):
        excluded.reason = "changed"


def test_discovery_scope_activity_workflow_result_constructs():
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    excluded = ExcludedDiscoveryScopeActivity(
        discovery_scope=scope_b,
        eligibility_status="ineligible",
        reason="no_snapshot_history",
    )
    report = DiscoveryScopeActivityReport(compared_scope_count=1)

    result = DiscoveryScopeActivityWorkflowResult(
        comparison_status="comparison_produced",
        reason="comparison_available",
        requested_scopes=(scope_a, scope_b),
        eligible_scopes=(scope_a,),
        excluded_scopes=(excluded,),
        activity_report=report,
    )

    assert result.comparison_status == "comparison_produced"
    assert result.reason == "comparison_available"
    assert result.requested_scopes == (scope_a, scope_b)
    assert result.eligible_scopes == (scope_a,)
    assert result.excluded_scopes == (excluded,)
    assert result.activity_report == report


def test_discovery_scope_activity_workflow_result_is_immutable():
    result = DiscoveryScopeActivityWorkflowResult(
        comparison_status="no_eligible_scopes",
        reason="No requested Discovery Scopes are eligible for comparison.",
    )

    with pytest.raises(FrozenInstanceError):
        result.eligible_scopes = (DiscoveryScope("scope-a"),)


def test_resource_metadata_group_constructs():
    group = ResourceMetadataGroup(
        metadata_key="tags.Environment",
        metadata_value="prod",
        resource_count=1,
        resource_external_ids=("i-123456",),
    )

    assert group.metadata_key == "tags.Environment"
    assert group.metadata_value == "prod"
    assert group.resource_count == 1
    assert group.resource_external_ids == ("i-123456",)


def test_resource_metadata_group_allows_empty_resource_list():
    group = ResourceMetadataGroup(
        metadata_key="tags.Environment",
        metadata_value="prod",
        resource_count=0,
    )

    assert group.resource_external_ids == ()


def test_resource_metadata_group_stores_multiple_resources_deterministically():
    group = ResourceMetadataGroup(
        metadata_key="tags.Environment",
        metadata_value="prod",
        resource_count=3,
        resource_external_ids=(
            "i-300000",
            "i-100000",
            "i-200000",
        ),
    )

    assert group.resource_external_ids == (
        "i-100000",
        "i-200000",
        "i-300000",
    )


def test_resource_metadata_group_resource_external_ids_are_immutable():
    group = ResourceMetadataGroup(
        metadata_key="tags.Environment",
        metadata_value="prod",
        resource_count=1,
        resource_external_ids=("i-123456",),
    )

    with pytest.raises(FrozenInstanceError):
        group.resource_external_ids = ("i-654321",)


def _activity_facts(
    discovery_scope: DiscoveryScope,
) -> DiscoveryScopeActivityFacts:
    return DiscoveryScopeActivityFacts(
        discovery_scope=discovery_scope,
        effective_evidence_window="Snapshot 1 -> Snapshot 2",
        snapshot_count=2,
        valid_interval_count=1,
        endpoint_resource_count=1,
        introduced_count=1,
        modified_count=0,
        removed_count=0,
        total_represented_change_count=1,
    )

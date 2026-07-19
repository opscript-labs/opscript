from opscript.config import DEFAULT_DISCOVERY_SCOPE
from datetime import UTC, datetime

from platformiq.analysis import SnapshotDiffer
from platformiq.core import Identifier
from platformiq.model import (
    AnalysisResult,
    DiffResult,
    DiscoveryScope,
    Finding,
    Observation,
    Resource,
    Snapshot,
)
from platformiq.model.value_objects import ResourceState

from opscript.application import AnalysisService


def diff_result(**kwargs):
    return DiffResult(
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
        **kwargs,
    )


def test_analysis_service_returns_diff_result():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    previous = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(),
    )

    current = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(resource,),
    )

    result = service.analyze(
        previous,
        current,
    )

    assert result.created == (resource,)


def test_analysis_service_returns_observations():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    previous = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(),
    )

    current = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(resource,),
    )

    observations = service.observe(
        previous,
        current,
    )

    assert len(observations) == 1
    assert observations[0].subject == "resource-001"
    assert observations[0].type == "resource_created"


def test_analysis_service_returns_findings():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    previous = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(),
    )

    current = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(resource,),
    )

    findings = service.find(
        previous,
        current,
    )

    assert len(findings) == 1
    assert findings[0].subject == "resource-001"
    assert findings[0].type == "new_infrastructure_introduced"
    assert findings[0].source_observation_type == "resource_created"


def test_analysis_service_returns_full_analysis_result():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    previous = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(),
    )

    current = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(resource,),
    )

    result = service.analyze_full(
        previous,
        current,
    )

    assert result.diff.created == (resource,)
    assert len(result.observations) == 1
    assert result.observations[0].type == "resource_created"
    assert len(result.findings) == 1
    assert result.findings[0].type == "new_infrastructure_introduced"


def test_analysis_service_analyzes_snapshot_history_in_adjacent_pairs():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    first = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(),
    )

    second = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(resource,),
    )

    third = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
        resources=(),
    )

    results = service.analyze_history(
        (
            first,
            second,
            third,
        )
    )

    assert len(results) == 2
    assert results[0].diff.created == (resource,)
    assert results[1].diff.deleted == (resource,)


def test_analysis_service_returns_empty_history_analysis_for_fewer_than_two_snapshots():
    service = AnalysisService(SnapshotDiffer())

    snapshot = Snapshot(
        discovery_scope=DEFAULT_DISCOVERY_SCOPE,
        id=Identifier.new(),
    )

    assert service.analyze_history(()) == ()
    assert service.analyze_history((snapshot,)) == ()


def test_analysis_service_analyzes_independent_scope_histories_without_cross_contamination():
    service = AnalysisService(SnapshotDiffer())
    scope_a = DiscoveryScope("scope-a")
    scope_b = DiscoveryScope("scope-b")
    resource_a = Resource(id=Identifier.new(), external_id="resource-a")
    resource_b = Resource(id=Identifier.new(), external_id="resource-b")
    history_a = (
        Snapshot(discovery_scope=scope_a, id=Identifier.new(), resources=()),
        Snapshot(discovery_scope=scope_a, id=Identifier.new(), resources=(resource_a,)),
    )
    history_b = (
        Snapshot(discovery_scope=scope_b, id=Identifier.new(), resources=()),
        Snapshot(discovery_scope=scope_b, id=Identifier.new(), resources=(resource_b,)),
    )

    analysis_a = service.analyze_history(history_a)
    analysis_b = service.analyze_history(history_b)

    assert tuple(resource.external_id for resource in analysis_a[0].diff.created) == (
        "resource-a",
    )
    assert tuple(resource.external_id for resource in analysis_b[0].diff.created) == (
        "resource-b",
    )
    assert "resource-b" not in {
        resource.external_id for resource in analysis_a[0].diff.created
    }
    assert "resource-a" not in {
        resource.external_id for resource in analysis_b[0].diff.created
    }


def test_analysis_service_filters_history_for_created_resource():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    history = service.analyze_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    filtered = service.filter_history_for_resource(
        history,
        "resource-001",
    )

    assert len(filtered) == 1


def test_analysis_service_filters_history_for_deleted_resource():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    history = service.analyze_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    filtered = service.filter_history_for_resource(
        history,
        "resource-001",
    )

    assert len(filtered) == 1


def test_analysis_service_returns_empty_history_when_resource_not_present():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    history = service.analyze_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    filtered = service.filter_history_for_resource(
        history,
        "resource-999",
    )

    assert filtered == ()


def test_analysis_service_filtering_is_deterministic():
    service = AnalysisService(SnapshotDiffer())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    history = service.analyze_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    first = service.filter_history_for_resource(
        history,
        "resource-001",
    )

    second = service.filter_history_for_resource(
        history,
        "resource-001",
    )

    assert first == second


def test_analyze_resource_change_history_counts_changes_and_identifies_indices():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    history = (
        AnalysisResult(diff=diff_result(created=(resource,))),
        AnalysisResult(diff=diff_result()),
        AnalysisResult(diff=diff_result(modified=(resource,))),
        AnalysisResult(diff=diff_result()),
        AnalysisResult(diff=diff_result(deleted=(resource,))),
    )

    change_history = service.analyze_resource_change_history(history, "resource-001")

    assert change_history.resource_external_id == "resource-001"
    assert change_history.first_recorded_change == 1
    assert change_history.most_recent_recorded_change == 5
    assert change_history.recorded_change_count == 3
    assert change_history.recorded_change_span == "Comparison 1 -> Comparison 5"
    assert change_history.comparison_indices == (1, 3, 5)


def test_analyze_resource_change_history_deduplicates_same_resource_in_multiple_groups_same_comparison():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    history = (
        AnalysisResult(
            diff=diff_result(
                created=(resource,),
                modified=(resource,),
                deleted=(resource,),
            )
        ),
    )

    change_history = service.analyze_resource_change_history(history, "resource-001")

    assert change_history.recorded_change_count == 1
    assert change_history.comparison_indices == (1,)


def test_analyze_resource_change_history_returns_no_history_when_no_changes():
    service = AnalysisService(SnapshotDiffer())

    history = (
        AnalysisResult(diff=diff_result()),
        AnalysisResult(diff=diff_result()),
    )

    change_history = service.analyze_resource_change_history(history, "resource-001")

    assert change_history.resource_external_id == "resource-001"
    assert change_history.first_recorded_change is None
    assert change_history.most_recent_recorded_change is None
    assert change_history.recorded_change_count == 0
    assert change_history.recorded_change_span is None
    assert change_history.comparison_indices == ()


def test_analyze_latest_environment_change_identifies_latest_index():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    # Empty history
    assert service.analyze_latest_environment_change(()) is None

    # History with no changes
    history_no_changes = (
        AnalysisResult(diff=diff_result()),
        AnalysisResult(diff=diff_result()),
    )
    assert service.analyze_latest_environment_change(history_no_changes) is None

    # History with changes at various indices
    history_with_changes = (
        AnalysisResult(diff=diff_result(created=(resource,))),
        AnalysisResult(diff=diff_result()),
        AnalysisResult(diff=diff_result(modified=(resource,))),
        AnalysisResult(diff=diff_result()),
    )
    assert service.analyze_latest_environment_change(history_with_changes) == 3

    # History where latest comparison itself contains changes
    history_latest_change = (
        AnalysisResult(diff=diff_result(created=(resource,))),
        AnalysisResult(diff=diff_result(deleted=(resource,))),
    )
    assert service.analyze_latest_environment_change(history_latest_change) == 2


def test_analyze_instability_concentration_empty_history_returns_empty_summary():
    service = AnalysisService(SnapshotDiffer())

    summary = service.analyze_instability_concentration(())

    assert summary.resource_summaries == ()


def test_analyze_instability_concentration_summarizes_single_changed_resource():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (AnalysisResult(diff=diff_result(created=(resource,))),)

    summary = service.analyze_instability_concentration(history)

    assert len(summary.resource_summaries) == 1
    resource_summary = summary.resource_summaries[0]
    assert resource_summary.resource_external_id == "resource-001"
    assert resource_summary.comparison_count == 1
    assert resource_summary.change_count == 1
    assert resource_summary.observation_count == 0
    assert resource_summary.finding_count == 0
    assert resource_summary.first_observed_comparison == 1
    assert resource_summary.most_recent_observed_comparison == 1
    assert resource_summary.recorded_activity_count == 1


def test_analyze_instability_concentration_counts_created_modified_deleted_changes():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(diff=diff_result(created=(resource,))),
        AnalysisResult(diff=diff_result(modified=(resource,))),
        AnalysisResult(diff=diff_result(deleted=(resource,))),
    )

    summary = service.analyze_instability_concentration(history)

    assert summary.resource_summaries[0].comparison_count == 3
    assert summary.resource_summaries[0].change_count == 3
    assert summary.resource_summaries[0].recorded_activity_count == 3


def test_analyze_instability_concentration_counts_observations_and_findings():
    service = AnalysisService(SnapshotDiffer())
    history = (
        AnalysisResult(
            diff=diff_result(),
            observations=(
                _observation("resource-001"),
                _observation("resource-001"),
            ),
            findings=(_finding("resource-001"),),
        ),
    )

    summary = service.analyze_instability_concentration(history)

    assert summary.resource_summaries[0].resource_external_id == "resource-001"
    assert summary.resource_summaries[0].change_count == 0
    assert summary.resource_summaries[0].observation_count == 2
    assert summary.resource_summaries[0].finding_count == 1
    assert summary.resource_summaries[0].recorded_activity_count == 3


def test_analyze_instability_concentration_deduplicates_comparison_count():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(
            diff=diff_result(
                created=(resource,),
                modified=(resource,),
                deleted=(resource,),
            ),
            observations=(_observation("resource-001"),),
            findings=(_finding("resource-001"),),
        ),
    )

    summary = service.analyze_instability_concentration(history)

    assert summary.resource_summaries[0].comparison_count == 1
    assert summary.resource_summaries[0].change_count == 3
    assert summary.resource_summaries[0].observation_count == 1
    assert summary.resource_summaries[0].finding_count == 1
    assert summary.resource_summaries[0].recorded_activity_count == 5


def test_analyze_instability_concentration_tracks_first_and_most_recent_indices():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(diff=diff_result()),
        AnalysisResult(diff=diff_result(created=(resource,))),
        AnalysisResult(diff=diff_result()),
        AnalysisResult(diff=diff_result(modified=(resource,))),
    )

    summary = service.analyze_instability_concentration(history)

    assert summary.resource_summaries[0].first_observed_comparison == 2
    assert summary.resource_summaries[0].most_recent_observed_comparison == 4


def test_analyze_instability_concentration_sorts_by_recorded_activity_descending():
    service = AnalysisService(SnapshotDiffer())
    quiet = Resource(id=Identifier.new(), external_id="resource-quiet")
    active = Resource(id=Identifier.new(), external_id="resource-active")
    history = (
        AnalysisResult(
            diff=diff_result(
                created=(quiet, active),
                modified=(active,),
            ),
            observations=(_observation("resource-active"),),
        ),
    )

    summary = service.analyze_instability_concentration(history)

    assert tuple(
        resource_summary.resource_external_id
        for resource_summary in summary.resource_summaries
    ) == ("resource-active", "resource-quiet")


def test_analyze_instability_concentration_tie_breaks_by_resource_external_id():
    service = AnalysisService(SnapshotDiffer())
    b_resource = Resource(id=Identifier.new(), external_id="resource-b")
    a_resource = Resource(id=Identifier.new(), external_id="resource-a")
    history = (
        AnalysisResult(
            diff=diff_result(
                created=(b_resource, a_resource),
            ),
        ),
    )

    summary = service.analyze_instability_concentration(history)

    assert tuple(
        resource_summary.resource_external_id
        for resource_summary in summary.resource_summaries
    ) == ("resource-a", "resource-b")


def test_analyze_instability_concentration_includes_observation_only_resource():
    service = AnalysisService(SnapshotDiffer())
    history = (
        AnalysisResult(
            diff=diff_result(),
            observations=(_observation("resource-001"),),
            findings=(_finding("resource-001"),),
        ),
    )

    summary = service.analyze_instability_concentration(history)

    assert len(summary.resource_summaries) == 1
    assert summary.resource_summaries[0].resource_external_id == "resource-001"
    assert summary.resource_summaries[0].comparison_count == 1
    assert summary.resource_summaries[0].change_count == 0
    assert summary.resource_summaries[0].observation_count == 1
    assert summary.resource_summaries[0].finding_count == 1


def test_analyze_environment_stability_trend_empty_history_returns_insufficient_history():
    service = AnalysisService(SnapshotDiffer())

    trend = service.analyze_environment_stability_trend(())

    assert trend.comparison_activity == ()
    assert trend.first_activity_count is None
    assert trend.most_recent_activity_count is None
    assert trend.activity_delta is None
    assert trend.trend_direction == "insufficient_history"


def test_analyze_environment_stability_trend_single_comparison_returns_insufficient_history():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (AnalysisResult(diff=diff_result(created=(resource,))),)

    trend = service.analyze_environment_stability_trend(history)

    assert trend.first_activity_count == 1
    assert trend.most_recent_activity_count == 1
    assert trend.activity_delta == 0
    assert trend.trend_direction == "insufficient_history"


def test_analyze_environment_stability_trend_detects_decreasing_activity():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(
            diff=diff_result(created=(resource,)),
            observations=(_observation("resource-001"),),
            findings=(_finding("resource-001"),),
        ),
        AnalysisResult(diff=diff_result()),
    )

    trend = service.analyze_environment_stability_trend(history)

    assert trend.first_activity_count == 3
    assert trend.most_recent_activity_count == 0
    assert trend.activity_delta == -3
    assert trend.trend_direction == "decreasing"


def test_analyze_environment_stability_trend_detects_increasing_activity():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(diff=diff_result()),
        AnalysisResult(
            diff=diff_result(created=(resource,)),
            observations=(_observation("resource-001"),),
            findings=(_finding("resource-001"),),
        ),
    )

    trend = service.analyze_environment_stability_trend(history)

    assert trend.first_activity_count == 0
    assert trend.most_recent_activity_count == 3
    assert trend.activity_delta == 3
    assert trend.trend_direction == "increasing"


def test_analyze_environment_stability_trend_detects_unchanged_activity():
    service = AnalysisService(SnapshotDiffer())
    first = Resource(id=Identifier.new(), external_id="resource-001")
    second = Resource(id=Identifier.new(), external_id="resource-002")
    history = (
        AnalysisResult(diff=diff_result(created=(first,))),
        AnalysisResult(diff=diff_result(deleted=(second,))),
    )

    trend = service.analyze_environment_stability_trend(history)

    assert trend.first_activity_count == 1
    assert trend.most_recent_activity_count == 1
    assert trend.activity_delta == 0
    assert trend.trend_direction == "unchanged"


def test_analyze_environment_stability_trend_counts_comparison_activity_components():
    service = AnalysisService(SnapshotDiffer())
    created = Resource(id=Identifier.new(), external_id="resource-created")
    modified = Resource(id=Identifier.new(), external_id="resource-modified")
    deleted = Resource(id=Identifier.new(), external_id="resource-deleted")
    history = (
        AnalysisResult(
            diff=diff_result(
                created=(created,),
                modified=(modified,),
                deleted=(deleted,),
            ),
            observations=(
                _observation("resource-created"),
                _observation("resource-modified"),
            ),
            findings=(_finding("resource-created"),),
        ),
    )

    trend = service.analyze_environment_stability_trend(history)
    activity = trend.comparison_activity[0]

    assert activity.change_count == 3
    assert activity.observation_count == 2
    assert activity.finding_count == 1
    assert activity.recorded_activity_count == 6


def test_analyze_environment_stability_trend_uses_ordered_one_based_indices():
    service = AnalysisService(SnapshotDiffer())
    first = Resource(id=Identifier.new(), external_id="resource-001")
    second = Resource(id=Identifier.new(), external_id="resource-002")
    history = (
        AnalysisResult(diff=diff_result(created=(first,))),
        AnalysisResult(diff=diff_result()),
        AnalysisResult(diff=diff_result(created=(second,))),
    )

    trend = service.analyze_environment_stability_trend(history)

    assert tuple(
        activity.comparison_index for activity in trend.comparison_activity
    ) == (1, 2, 3)


def test_analyze_operational_activity_dominance_empty_history_returns_empty_summary():
    service = AnalysisService(SnapshotDiffer())

    summary = service.analyze_operational_activity_dominance(())

    assert summary.activity_summaries == ()


def test_analyze_operational_activity_dominance_counts_change_activity_types():
    service = AnalysisService(SnapshotDiffer())
    created = Resource(id=Identifier.new(), external_id="resource-created")
    modified = Resource(id=Identifier.new(), external_id="resource-modified")
    deleted = Resource(id=Identifier.new(), external_id="resource-deleted")
    history = (
        AnalysisResult(
            diff=diff_result(
                created=(created, created),
                modified=(modified,),
                deleted=(deleted, deleted, deleted),
            ),
        ),
    )

    summary = service.analyze_operational_activity_dominance(history)

    assert _activity(summary, "change", "created").activity_count == 2
    assert _activity(summary, "change", "modified").activity_count == 1
    assert _activity(summary, "change", "deleted").activity_count == 3


def test_analyze_operational_activity_dominance_counts_observation_types():
    service = AnalysisService(SnapshotDiffer())
    history = (
        AnalysisResult(
            diff=diff_result(),
            observations=(
                _observation("resource-001", observation_type="resource_created"),
                _observation("resource-002", observation_type="resource_created"),
                _observation("resource-003", observation_type="resource_modified"),
            ),
        ),
    )

    summary = service.analyze_operational_activity_dominance(history)

    assert _activity(summary, "observation", "resource_created").activity_count == 2
    assert _activity(summary, "observation", "resource_modified").activity_count == 1


def test_analyze_operational_activity_dominance_counts_finding_types():
    service = AnalysisService(SnapshotDiffer())
    history = (
        AnalysisResult(
            diff=diff_result(),
            findings=(
                _finding("resource-001", finding_type="new_infrastructure_introduced"),
                _finding("resource-002", finding_type="new_infrastructure_introduced"),
                _finding("resource-003", finding_type="configuration_changed"),
            ),
        ),
    )

    summary = service.analyze_operational_activity_dominance(history)

    assert (
        _activity(summary, "finding", "new_infrastructure_introduced").activity_count
        == 2
    )
    assert _activity(summary, "finding", "configuration_changed").activity_count == 1


def test_analyze_operational_activity_dominance_deduplicates_comparison_count():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(
            diff=diff_result(created=(resource, resource)),
            observations=(
                _observation("resource-001", observation_type="resource_created"),
                _observation("resource-002", observation_type="resource_created"),
            ),
            findings=(
                _finding("resource-001", finding_type="new_infrastructure_introduced"),
                _finding("resource-002", finding_type="new_infrastructure_introduced"),
            ),
        ),
    )

    summary = service.analyze_operational_activity_dominance(history)

    assert _activity(summary, "change", "created").activity_count == 2
    assert _activity(summary, "change", "created").comparison_count == 1
    assert _activity(summary, "observation", "resource_created").activity_count == 2
    assert _activity(summary, "observation", "resource_created").comparison_count == 1
    assert (
        _activity(summary, "finding", "new_infrastructure_introduced").activity_count
        == 2
    )
    assert (
        _activity(summary, "finding", "new_infrastructure_introduced").comparison_count
        == 1
    )


def test_analyze_operational_activity_dominance_tracks_multiple_comparisons():
    service = AnalysisService(SnapshotDiffer())
    first = Resource(id=Identifier.new(), external_id="resource-001")
    second = Resource(id=Identifier.new(), external_id="resource-002")
    history = (
        AnalysisResult(diff=diff_result(created=(first,))),
        AnalysisResult(diff=diff_result(created=(second,))),
    )

    summary = service.analyze_operational_activity_dominance(history)

    assert _activity(summary, "change", "created").activity_count == 2
    assert _activity(summary, "change", "created").comparison_count == 2


def test_analyze_operational_activity_dominance_excludes_zero_count_types():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (AnalysisResult(diff=diff_result(created=(resource,))),)

    summary = service.analyze_operational_activity_dominance(history)

    assert _activity(summary, "change", "created").activity_count == 1
    assert not any(
        activity.activity_layer == "change" and activity.activity_type == "modified"
        for activity in summary.activity_summaries
    )
    assert not any(
        activity.activity_layer == "change" and activity.activity_type == "deleted"
        for activity in summary.activity_summaries
    )


def test_analyze_operational_activity_dominance_sorts_by_activity_count_descending():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(
            diff=diff_result(created=(resource,)),
            observations=(
                _observation("resource-001", observation_type="resource_created"),
                _observation("resource-002", observation_type="resource_created"),
            ),
        ),
    )

    summary = service.analyze_operational_activity_dominance(history)

    assert tuple(
        (activity.activity_layer, activity.activity_type)
        for activity in summary.activity_summaries
    ) == (
        ("observation", "resource_created"),
        ("change", "created"),
    )


def test_analyze_operational_activity_dominance_tie_breaks_by_layer_then_type():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(
            diff=diff_result(created=(resource,)),
            observations=(
                _observation("resource-001", observation_type="resource_created"),
            ),
            findings=(_finding("resource-001", finding_type="configuration_changed"),),
        ),
    )

    summary = service.analyze_operational_activity_dominance(history)

    assert tuple(
        (activity.activity_layer, activity.activity_type)
        for activity in summary.activity_summaries
    ) == (
        ("change", "created"),
        ("finding", "configuration_changed"),
        ("observation", "resource_created"),
    )


def test_analyze_resource_change_frequency_empty_snapshots_returns_empty_summary():
    service = AnalysisService(SnapshotDiffer())

    summary = service.analyze_resource_change_frequency(())

    assert summary.resource_summaries == ()


def test_analyze_resource_change_frequency_one_snapshot_includes_zero_change_resources():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    resource_summary = summary.resource_summaries[0]
    assert resource_summary.resource_external_id == "resource-001"
    assert resource_summary.observed_snapshot_count == 1
    assert resource_summary.observed_comparison_count == 0
    assert resource_summary.recorded_change_count == 0
    assert resource_summary.first_observed_snapshot_index == 1
    assert resource_summary.most_recent_observed_snapshot_index == 1
    assert resource_summary.first_changed_comparison is None
    assert resource_summary.most_recent_changed_comparison is None


def test_analyze_resource_change_frequency_counts_unchanged_resource_zero_changes():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    resource_summary = summary.resource_summaries[0]
    assert resource_summary.observed_snapshot_count == 3
    assert resource_summary.observed_comparison_count == 2
    assert resource_summary.recorded_change_count == 0


def test_analyze_resource_change_frequency_counts_created_resource_change():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    resource_summary = summary.resource_summaries[0]
    assert resource_summary.recorded_change_count == 1
    assert resource_summary.first_changed_comparison == 1
    assert resource_summary.most_recent_changed_comparison == 1


def test_analyze_resource_change_frequency_counts_modified_resource_change():
    service = AnalysisService(SnapshotDiffer())
    previous_resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(properties={"size": "small"}),
    )
    current_resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(properties={"size": "large"}),
    )

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(previous_resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(current_resource,),
            ),
        )
    )

    resource_summary = summary.resource_summaries[0]
    assert resource_summary.recorded_change_count == 1
    assert resource_summary.first_changed_comparison == 1
    assert resource_summary.most_recent_changed_comparison == 1


def test_analyze_resource_change_frequency_counts_deleted_resource_change():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    resource_summary = summary.resource_summaries[0]
    assert resource_summary.recorded_change_count == 1
    assert resource_summary.first_changed_comparison == 1
    assert resource_summary.most_recent_changed_comparison == 1


def test_analyze_resource_change_frequency_tracks_observed_snapshot_indices():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    resource_summary = summary.resource_summaries[0]
    assert resource_summary.observed_snapshot_count == 2
    assert resource_summary.first_observed_snapshot_index == 2
    assert resource_summary.most_recent_observed_snapshot_index == 3


def test_analyze_resource_change_frequency_tracks_changed_comparison_indices():
    service = AnalysisService(SnapshotDiffer())
    previous_resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(properties={"size": "small"}),
    )
    current_resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
        state=ResourceState(properties={"size": "large"}),
    )

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(previous_resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(current_resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
        )
    )

    resource_summary = summary.resource_summaries[0]
    assert resource_summary.recorded_change_count == 3
    assert resource_summary.first_changed_comparison == 1
    assert resource_summary.most_recent_changed_comparison == 3


def test_analyze_resource_change_frequency_counts_observed_comparisons():
    service = AnalysisService(SnapshotDiffer())
    always_present = Resource(id=Identifier.new(), external_id="resource-always")
    created = Resource(id=Identifier.new(), external_id="resource-created")
    deleted = Resource(id=Identifier.new(), external_id="resource-deleted")

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(always_present, deleted),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(always_present, created, deleted),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(always_present, created),
            ),
        )
    )

    assert _change_frequency(summary, "resource-always").observed_comparison_count == 2
    assert _change_frequency(summary, "resource-created").observed_comparison_count == 2
    assert _change_frequency(summary, "resource-deleted").observed_comparison_count == 2


def test_analyze_resource_change_frequency_sorts_by_change_count_observed_snapshots_and_id():
    service = AnalysisService(SnapshotDiffer())
    quiet = Resource(id=Identifier.new(), external_id="resource-quiet")
    changed_short = Resource(id=Identifier.new(), external_id="resource-a")
    changed_long = Resource(id=Identifier.new(), external_id="resource-b")

    summary = service.analyze_resource_change_frequency(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(quiet,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(quiet, changed_long),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(quiet, changed_long, changed_short),
            ),
        )
    )

    assert tuple(
        resource_summary.resource_external_id
        for resource_summary in summary.resource_summaries
    ) == (
        "resource-quiet",
        "resource-b",
        "resource-a",
    )


def test_analyze_resource_churn_trends_empty_history_returns_empty_summary():
    service = AnalysisService(SnapshotDiffer())

    summary = service.analyze_resource_churn_trends(())

    assert summary.resource_trends == ()


def test_analyze_resource_churn_trends_one_active_comparison_returns_insufficient_history():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (AnalysisResult(diff=diff_result(created=(resource,))),)

    summary = service.analyze_resource_churn_trends(history)

    trend = summary.resource_trends[0]
    assert trend.resource_external_id == "resource-001"
    assert trend.first_activity_count == 1
    assert trend.most_recent_activity_count == 1
    assert trend.activity_delta == 0
    assert trend.trend_direction == "insufficient_history"


def test_analyze_resource_churn_trends_detects_increasing_resource_churn():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(diff=diff_result(created=(resource,))),
        AnalysisResult(
            diff=diff_result(modified=(resource,)),
            observations=(_observation("resource-001"),),
            findings=(_finding("resource-001"),),
        ),
    )

    summary = service.analyze_resource_churn_trends(history)

    trend = summary.resource_trends[0]
    assert trend.first_activity_count == 1
    assert trend.most_recent_activity_count == 3
    assert trend.activity_delta == 2
    assert trend.trend_direction == "increasing"


def test_analyze_resource_churn_trends_detects_decreasing_resource_churn():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(
            diff=diff_result(created=(resource,)),
            observations=(_observation("resource-001"),),
            findings=(_finding("resource-001"),),
        ),
        AnalysisResult(diff=diff_result(modified=(resource,))),
    )

    summary = service.analyze_resource_churn_trends(history)

    trend = summary.resource_trends[0]
    assert trend.first_activity_count == 3
    assert trend.most_recent_activity_count == 1
    assert trend.activity_delta == -2
    assert trend.trend_direction == "decreasing"


def test_analyze_resource_churn_trends_detects_unchanged_resource_churn():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(
            diff=diff_result(created=(resource,)),
            observations=(_observation("resource-001"),),
        ),
        AnalysisResult(
            diff=diff_result(modified=(resource,)),
            findings=(_finding("resource-001"),),
        ),
    )

    summary = service.analyze_resource_churn_trends(history)

    trend = summary.resource_trends[0]
    assert trend.first_activity_count == 2
    assert trend.most_recent_activity_count == 2
    assert trend.activity_delta == 0
    assert trend.trend_direction == "unchanged"


def test_analyze_resource_churn_trends_counts_activity_components_per_resource():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    other = Resource(id=Identifier.new(), external_id="resource-002")
    history = (
        AnalysisResult(
            diff=diff_result(
                created=(resource, other),
                modified=(resource,),
                deleted=(resource,),
            ),
            observations=(
                _observation("resource-001"),
                _observation("resource-001"),
                _observation("resource-002"),
            ),
            findings=(_finding("resource-001"),),
        ),
    )

    summary = service.analyze_resource_churn_trends(history)

    activity = _churn_trend(summary, "resource-001").comparison_activity[0]
    assert activity.comparison_index == 1
    assert activity.change_count == 3
    assert activity.observation_count == 2
    assert activity.finding_count == 1
    assert activity.recorded_activity_count == 6


def test_analyze_resource_churn_trends_ignores_zero_activity_comparisons():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")
    history = (
        AnalysisResult(diff=diff_result(created=(resource,))),
        AnalysisResult(diff=diff_result()),
        AnalysisResult(
            diff=diff_result(modified=(resource,)),
            observations=(_observation("resource-001"),),
        ),
    )

    summary = service.analyze_resource_churn_trends(history)

    trend = summary.resource_trends[0]
    assert tuple(
        activity.comparison_index for activity in trend.comparison_activity
    ) == (1, 3)
    assert trend.first_activity_count == 1
    assert trend.most_recent_activity_count == 2
    assert trend.trend_direction == "increasing"


def test_analyze_resource_churn_trends_includes_observation_and_finding_only_resources():
    service = AnalysisService(SnapshotDiffer())
    history = (
        AnalysisResult(
            diff=diff_result(),
            observations=(_observation("resource-observed"),),
            findings=(_finding("resource-found"),),
        ),
    )

    summary = service.analyze_resource_churn_trends(history)

    assert (
        _churn_trend(summary, "resource-observed")
        .comparison_activity[0]
        .observation_count
        == 1
    )
    assert (
        _churn_trend(summary, "resource-found").comparison_activity[0].finding_count
        == 1
    )


def test_analyze_resource_churn_trends_sorts_by_direction_delta_and_resource_id():
    service = AnalysisService(SnapshotDiffer())
    inc_a = Resource(id=Identifier.new(), external_id="resource-a")
    inc_b = Resource(id=Identifier.new(), external_id="resource-b")
    inc_c = Resource(id=Identifier.new(), external_id="resource-c")
    dec = Resource(id=Identifier.new(), external_id="resource-decreasing")
    unchanged = Resource(id=Identifier.new(), external_id="resource-unchanged")
    insufficient = Resource(id=Identifier.new(), external_id="resource-insufficient")

    history = (
        AnalysisResult(
            diff=diff_result(
                created=(inc_a, inc_b, inc_c, dec, unchanged, insufficient),
            ),
            observations=(
                _observation("resource-decreasing"),
                _observation("resource-decreasing"),
                _observation("resource-unchanged"),
            ),
        ),
        AnalysisResult(
            diff=diff_result(
                modified=(inc_a, inc_b, inc_c, dec, unchanged),
            ),
            observations=(
                _observation("resource-a"),
                _observation("resource-b"),
                _observation("resource-c"),
                _observation("resource-c"),
                _observation("resource-unchanged"),
            ),
            findings=(
                _finding("resource-a"),
                _finding("resource-b"),
                _finding("resource-c"),
            ),
        ),
    )

    summary = service.analyze_resource_churn_trends(history)

    assert tuple(trend.resource_external_id for trend in summary.resource_trends) == (
        "resource-c",
        "resource-a",
        "resource-b",
        "resource-decreasing",
        "resource-unchanged",
        "resource-insufficient",
    )


def test_analyze_resource_metadata_groups_empty_snapshot_history_returns_empty_tuple():
    service = AnalysisService(SnapshotDiffer())

    groups = service.analyze_resource_metadata_groups((), "tags.Environment")

    assert groups == ()


def test_analyze_resource_metadata_groups_summarizes_single_metadata_group():
    service = AnalysisService(SnapshotDiffer())
    resource = _resource_with_properties(
        "resource-001",
        {"tags": {"Environment": "prod"}},
    )

    groups = service.analyze_resource_metadata_groups(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        ),
        "tags.Environment",
    )

    assert len(groups) == 1
    assert groups[0].metadata_key == "tags.Environment"
    assert groups[0].metadata_value == "prod"
    assert groups[0].resource_count == 1
    assert groups[0].resource_external_ids == ("resource-001",)


def test_analyze_resource_metadata_groups_summarizes_multiple_metadata_groups():
    service = AnalysisService(SnapshotDiffer())
    prod = _resource_with_properties(
        "resource-prod",
        {"tags": {"Environment": "prod"}},
    )
    dev = _resource_with_properties(
        "resource-dev",
        {"tags": {"Environment": "dev"}},
    )

    groups = service.analyze_resource_metadata_groups(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(prod, dev),
            ),
        ),
        "tags.Environment",
    )

    assert tuple(group.metadata_value for group in groups) == ("dev", "prod")
    assert groups[0].resource_external_ids == ("resource-dev",)
    assert groups[1].resource_external_ids == ("resource-prod",)


def test_analyze_resource_metadata_groups_combines_multiple_snapshots():
    service = AnalysisService(SnapshotDiffer())
    first = _resource_with_properties(
        "resource-001",
        {"tags": {"Environment": "prod"}},
    )
    second = _resource_with_properties(
        "resource-002",
        {"tags": {"Environment": "prod"}},
    )

    groups = service.analyze_resource_metadata_groups(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(first,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(second,),
            ),
        ),
        "tags.Environment",
    )

    assert groups[0].metadata_value == "prod"
    assert groups[0].resource_count == 2
    assert groups[0].resource_external_ids == ("resource-001", "resource-002")


def test_analyze_resource_metadata_groups_ignores_resources_missing_metadata_path():
    service = AnalysisService(SnapshotDiffer())
    grouped = _resource_with_properties(
        "resource-grouped",
        {"tags": {"Environment": "prod"}},
    )
    missing_tags = _resource_with_properties("resource-missing-tags", {})
    missing_value = _resource_with_properties(
        "resource-missing-value",
        {"tags": {"Owner": "platform"}},
    )

    groups = service.analyze_resource_metadata_groups(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(grouped, missing_tags, missing_value),
            ),
        ),
        "tags.Environment",
    )

    assert len(groups) == 1
    assert groups[0].resource_external_ids == ("resource-grouped",)


def test_analyze_resource_metadata_groups_deduplicates_resource_across_snapshots():
    service = AnalysisService(SnapshotDiffer())
    first = _resource_with_properties(
        "resource-001",
        {"tags": {"Environment": "prod"}},
    )
    second = _resource_with_properties(
        "resource-001",
        {"tags": {"Environment": "prod"}},
    )

    groups = service.analyze_resource_metadata_groups(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(first,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(second,),
            ),
        ),
        "tags.Environment",
    )

    assert groups[0].resource_count == 1
    assert groups[0].resource_external_ids == ("resource-001",)


def test_analyze_resource_metadata_groups_uses_latest_metadata_value_for_resource():
    service = AnalysisService(SnapshotDiffer())
    dev = _resource_with_properties(
        "resource-001",
        {"tags": {"Environment": "dev"}},
    )
    prod = _resource_with_properties(
        "resource-001",
        {"tags": {"Environment": "prod"}},
    )

    groups = service.analyze_resource_metadata_groups(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(dev,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(prod,),
            ),
        ),
        "tags.Environment",
    )

    assert len(groups) == 1
    assert groups[0].metadata_value == "prod"
    assert groups[0].resource_external_ids == ("resource-001",)


def test_analyze_resource_metadata_groups_retains_last_value_when_later_metadata_missing():
    service = AnalysisService(SnapshotDiffer())
    tagged = _resource_with_properties(
        "resource-001",
        {"tags": {"Environment": "prod"}},
    )
    untagged = _resource_with_properties(
        "resource-001",
        {},
    )

    groups = service.analyze_resource_metadata_groups(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(tagged,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(untagged,),
            ),
        ),
        "tags.Environment",
    )

    assert len(groups) == 1
    assert groups[0].metadata_value == "prod"
    assert groups[0].resource_external_ids == ("resource-001",)


def test_analyze_resource_metadata_groups_returns_deterministic_group_ordering():
    service = AnalysisService(SnapshotDiffer())
    prod = _resource_with_properties(
        "resource-prod",
        {"tags": {"Environment": "prod"}},
    )
    dev_b = _resource_with_properties(
        "resource-dev-b",
        {"tags": {"Environment": "dev"}},
    )
    dev_a = _resource_with_properties(
        "resource-dev-a",
        {"tags": {"Environment": "dev"}},
    )

    groups = service.analyze_resource_metadata_groups(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(prod, dev_b, dev_a),
            ),
        ),
        "tags.Environment",
    )

    assert tuple(group.metadata_value for group in groups) == ("dev", "prod")
    assert groups[0].resource_external_ids == (
        "resource-dev-a",
        "resource-dev-b",
    )


def test_analyze_resource_observation_history_empty_snapshots_returns_empty_tuple():
    service = AnalysisService(SnapshotDiffer())

    summaries = service.analyze_resource_observation_history(())

    assert summaries == ()


def test_analyze_resource_observation_history_summarizes_single_resource_in_one_snapshot():
    service = AnalysisService(SnapshotDiffer())
    snapshot_id = Identifier.new()
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summaries = service.analyze_resource_observation_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(resource,),
            ),
        )
    )

    assert len(summaries) == 1
    assert summaries[0].resource_external_id == "resource-001"
    assert summaries[0].first_observed_snapshot_id == snapshot_id
    assert summaries[0].latest_observed_snapshot_id == snapshot_id
    assert summaries[0].observed_snapshot_count == 1
    assert summaries[0].observation_gap_count == 0


def test_analyze_resource_observation_history_counts_same_resource_across_snapshots():
    service = AnalysisService(SnapshotDiffer())
    first_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summaries = service.analyze_resource_observation_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=first_snapshot_id,
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=latest_snapshot_id,
                resources=(resource,),
            ),
        )
    )

    assert summaries[0].first_observed_snapshot_id == first_snapshot_id
    assert summaries[0].latest_observed_snapshot_id == latest_snapshot_id
    assert summaries[0].observed_snapshot_count == 3
    assert summaries[0].observation_gap_count == 0


def test_analyze_resource_observation_history_summarizes_multiple_resources():
    service = AnalysisService(SnapshotDiffer())
    resource_a = Resource(id=Identifier.new(), external_id="resource-a")
    resource_b = Resource(id=Identifier.new(), external_id="resource-b")

    summaries = service.analyze_resource_observation_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_a,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_a, resource_b),
            ),
        )
    )

    assert tuple(summary.resource_external_id for summary in summaries) == (
        "resource-a",
        "resource-b",
    )
    assert _observation_summary(summaries, "resource-a").observed_snapshot_count == 2
    assert _observation_summary(summaries, "resource-b").observed_snapshot_count == 1
    assert _observation_summary(summaries, "resource-a").observation_gap_count == 0
    assert _observation_summary(summaries, "resource-b").observation_gap_count == 0


def test_analyze_resource_observation_history_handles_resource_absent_from_some_snapshots():
    service = AnalysisService(SnapshotDiffer())
    first_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summaries = service.analyze_resource_observation_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=first_snapshot_id,
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=latest_snapshot_id,
                resources=(resource,),
            ),
        )
    )

    summary = summaries[0]
    assert summary.first_observed_snapshot_id == first_snapshot_id
    assert summary.latest_observed_snapshot_id == latest_snapshot_id
    assert summary.observed_snapshot_count == 2
    assert summary.observation_gap_count == 1


def test_analyze_resource_observation_history_counts_multiple_observation_gaps():
    service = AnalysisService(SnapshotDiffer())
    resource = Resource(id=Identifier.new(), external_id="resource-001")

    summaries = service.analyze_resource_observation_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource,),
            ),
        )
    )

    assert summaries[0].observed_snapshot_count == 4
    assert summaries[0].observation_gap_count == 2


def test_analyze_resource_observation_history_counts_duplicate_external_id_once_per_snapshot():
    service = AnalysisService(SnapshotDiffer())
    snapshot_id = Identifier.new()
    first = Resource(id=Identifier.new(), external_id="resource-001")
    duplicate = Resource(id=Identifier.new(), external_id="resource-001")

    summaries = service.analyze_resource_observation_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(first, duplicate),
            ),
        )
    )

    assert summaries[0].observed_snapshot_count == 1
    assert summaries[0].observation_gap_count == 0


def test_analyze_resource_observation_history_summarizes_multiple_gap_counts():
    service = AnalysisService(SnapshotDiffer())
    resource_a = Resource(id=Identifier.new(), external_id="resource-a")
    resource_b = Resource(id=Identifier.new(), external_id="resource-b")

    summaries = service.analyze_resource_observation_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_a, resource_b),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_b,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_a, resource_b),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_b,),
            ),
        )
    )

    assert _observation_summary(summaries, "resource-a").observation_gap_count == 1
    assert _observation_summary(summaries, "resource-b").observation_gap_count == 0


def test_analyze_resource_observation_history_sorts_by_resource_external_id():
    service = AnalysisService(SnapshotDiffer())
    resource_b = Resource(id=Identifier.new(), external_id="resource-b")
    resource_a = Resource(id=Identifier.new(), external_id="resource-a")

    summaries = service.analyze_resource_observation_history(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_b, resource_a),
            ),
        )
    )

    assert tuple(summary.resource_external_id for summary in summaries) == (
        "resource-a",
        "resource-b",
    )


def test_analyze_historical_inventory_timeline_empty_snapshots_returns_empty_tuple():
    service = AnalysisService(SnapshotDiffer())

    observations = service.analyze_historical_inventory_timeline(())

    assert observations == ()


def test_analyze_historical_inventory_timeline_counts_zero_resources():
    service = AnalysisService(SnapshotDiffer())
    snapshot_id = Identifier.new()

    observations = service.analyze_historical_inventory_timeline(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=(),
            ),
        )
    )

    assert len(observations) == 1
    assert observations[0].snapshot_id == snapshot_id
    assert observations[0].recorded_resource_count == 0


def test_analyze_historical_inventory_timeline_counts_resources():
    service = AnalysisService(SnapshotDiffer())
    snapshot_id = Identifier.new()
    resources = (
        Resource(id=Identifier.new(), external_id="resource-001"),
        Resource(id=Identifier.new(), external_id="resource-002"),
    )

    observations = service.analyze_historical_inventory_timeline(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=snapshot_id,
                resources=resources,
            ),
        )
    )

    assert observations[0].snapshot_id == snapshot_id
    assert observations[0].recorded_resource_count == 2


def test_analyze_historical_inventory_timeline_preserves_snapshot_order():
    service = AnalysisService(SnapshotDiffer())
    first_snapshot_id = Identifier.new()
    second_snapshot_id = Identifier.new()
    third_snapshot_id = Identifier.new()

    observations = service.analyze_historical_inventory_timeline(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=first_snapshot_id,
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=second_snapshot_id,
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=third_snapshot_id,
                resources=(),
            ),
        )
    )

    assert tuple(observation.snapshot_id for observation in observations) == (
        first_snapshot_id,
        second_snapshot_id,
        third_snapshot_id,
    )


def test_analyze_historical_inventory_timeline_counts_resources_per_snapshot():
    service = AnalysisService(SnapshotDiffer())
    resource_a = Resource(id=Identifier.new(), external_id="resource-a")
    resource_b = Resource(id=Identifier.new(), external_id="resource-b")

    observations = service.analyze_historical_inventory_timeline(
        (
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_a,),
            ),
            Snapshot(
                discovery_scope=DEFAULT_DISCOVERY_SCOPE,
                id=Identifier.new(),
                resources=(resource_a, resource_b),
            ),
        )
    )

    assert tuple(
        observation.recorded_resource_count for observation in observations
    ) == (0, 1, 2)


def _activity(
    summary,
    activity_layer: str,
    activity_type: str,
):
    return next(
        activity
        for activity in summary.activity_summaries
        if activity.activity_layer == activity_layer
        and activity.activity_type == activity_type
    )


def _churn_trend(
    summary,
    resource_external_id: str,
):
    return next(
        trend
        for trend in summary.resource_trends
        if trend.resource_external_id == resource_external_id
    )


def _change_frequency(
    summary,
    resource_external_id: str,
):
    return next(
        resource_summary
        for resource_summary in summary.resource_summaries
        if resource_summary.resource_external_id == resource_external_id
    )


def _observation_summary(
    summaries,
    resource_external_id: str,
):
    return next(
        summary
        for summary in summaries
        if summary.resource_external_id == resource_external_id
    )


def _observation(
    subject: str,
    observation_type: str = "resource_created",
) -> Observation:
    return Observation(
        subject=subject,
        type=observation_type,
        message=f"Resource created: {subject}",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _finding(
    subject: str,
    finding_type: str = "new_infrastructure_introduced",
) -> Finding:
    return Finding(
        subject=subject,
        type=finding_type,
        message=f"New infrastructure introduced: {subject}",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        source_observation_type="resource_created",
    )


def _resource_with_properties(
    external_id: str,
    properties: dict,
) -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
        state=ResourceState(properties=properties),
    )

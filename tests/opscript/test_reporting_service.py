from datetime import UTC, datetime

from platformiq.core import Identifier
from platformiq.model import AnalysisResult, DiffResult, Finding, Observation, Resource

from opscript import ReportingService
from opscript.models import (
    ComparisonActivity,
    EnvironmentActivityDominanceSummary,
    EnvironmentChangeFrequencySummary,
    EnvironmentChurnTrendSummary,
    EnvironmentInstabilitySummary,
    EnvironmentStabilityTrend,
    HistoricalInventoryObservation,
    InfrastructureChangeSummary,
    OperationalActivitySummary,
    ResourceChurnTrend,
    ResourceChangeFrequencySummary,
    ResourceComparisonActivity,
    ResourceMetadataGroup,
    ResourceObservationSummary,
    ResourceSummary,
    ResourceChangeHistory,
    ResourceInstabilitySummary,
)


class FakeReporter:
    def report(self, result):
        return "drift report"


def diff_result(**kwargs) -> DiffResult:
    return DiffResult(
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
        **kwargs,
    )


def test_reporting_service_generates_report():
    service = ReportingService(FakeReporter())

    output = service.generate_report(diff_result())

    assert output == "drift report"


def test_reporting_service_generates_observation_report():
    service = ReportingService(FakeReporter())

    observation = Observation(
        subject="resource-001",
        type="resource_created",
        message="Resource created: resource-001",
        timestamp=datetime.now(UTC),
    )

    output = service.generate_observation_report((observation,))

    assert output == "Observations:\n- Resource created: resource-001"


def test_reporting_service_generates_empty_observation_report():
    service = ReportingService(FakeReporter())

    output = service.generate_observation_report(())

    assert output == "No observations."


def test_reporting_service_generates_finding_report():
    service = ReportingService(FakeReporter())

    finding = Finding(
        subject="resource-001",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced: resource-001",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
    )

    output = service.generate_finding_report((finding,))

    assert output == "Findings:\n- New infrastructure introduced: resource-001"


def test_reporting_service_generates_empty_finding_report():
    service = ReportingService(FakeReporter())

    output = service.generate_finding_report(())

    assert output == "No findings."


def test_reporting_service_generates_analysis_report():
    service = ReportingService(FakeReporter())

    observation = Observation(
        subject="resource-001",
        type="resource_created",
        message="Resource created: resource-001",
        timestamp=datetime.now(UTC),
    )

    finding = Finding(
        subject="resource-001",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced: resource-001",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
    )

    result = AnalysisResult(
        diff=diff_result(),
        observations=(observation,),
        findings=(finding,),
    )

    output = service.generate_analysis_report(result)

    assert output == (
        "Observations:\n"
        "- Resource created: resource-001\n"
        "\n"
        "Findings:\n"
        "- New infrastructure introduced: resource-001"
    )


def test_reporting_service_generates_analysis_report_without_observations():
    service = ReportingService(FakeReporter())

    result = AnalysisResult(
        diff=diff_result(),
    )

    output = service.generate_analysis_report(result)

    assert output == "No observations."


def test_reporting_service_generates_infrastructure_change_summary_report():
    service = ReportingService(FakeReporter())

    resource = Resource(
        id=Identifier.new(),
        external_id="resource-001",
    )

    observation = Observation(
        subject="resource-001",
        type="resource_created",
        message="Resource created: resource-001",
        timestamp=datetime.now(UTC),
    )

    finding = Finding(
        subject="resource-001",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced: resource-001",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
    )

    resource_summary = ResourceSummary(
        resource=resource,
        change_type="created",
        observations=(observation,),
        findings=(finding,),
    )

    summary = InfrastructureChangeSummary(
        title="Infrastructure Change Summary",
        resource_summaries=(resource_summary,),
    )

    output = service.generate_infrastructure_change_summary_report(summary)

    assert output == (
        "Infrastructure Change Summary\n"
        "=============================\n"
        "\n"
        "Resources:\n"
        "\n"
        "Resource: resource-001\n"
        "Change type: created\n"
        "\n"
        "Observations:\n"
        "- Resource created: resource-001\n"
        "\n"
        "Findings:\n"
        "- New infrastructure introduced: resource-001"
    )


def test_reporting_service_generates_infrastructure_change_summary_report_without_resource_changes():
    service = ReportingService(FakeReporter())

    summary = InfrastructureChangeSummary(
        title="Infrastructure Change Summary",
    )

    output = service.generate_infrastructure_change_summary_report(summary)

    assert output == "No observations."


def test_reporting_service_generates_resource_evolution_report():
    service = ReportingService(FakeReporter())

    observation = Observation(
        subject="resource-001",
        type="resource_created",
        message="Resource created: resource-001",
        timestamp=datetime.now(UTC),
    )

    finding = Finding(
        subject="resource-001",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced: resource-001",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
    )

    result = AnalysisResult(
        diff=diff_result(),
        observations=(observation,),
        findings=(finding,),
    )

    change_history = ResourceChangeHistory(
        resource_external_id="resource-001",
        first_recorded_change=1,
        most_recent_recorded_change=1,
        recorded_change_count=1,
        recorded_change_span="Comparison 1 -> Comparison 1",
        comparison_indices=(1,),
    )

    output = service.generate_resource_evolution_report(
        "resource-001",
        (result,),
        change_history,
    )

    assert output == (
        "Resource Evolution: resource-001\n"
        "================================\n"
        "\n"
        "Resource Change History: resource-001\n"
        "=====================================\n"
        "\n"
        "Summary:\n"
        "- First recorded change: Comparison 1\n"
        "- Most recent recorded change: Comparison 1\n"
        "- Recorded change count: 1\n"
        "- Recorded change span: Comparison 1 -> Comparison 1\n"
        "\n"
        "Comparisons containing recorded changes:\n"
        "- Comparison 1\n"
        "\n"
        "Change 1:\n"
        "\n"
        "Observations:\n"
        "- Resource created: resource-001\n"
        "\n"
        "Findings:\n"
        "- New infrastructure introduced: resource-001"
    )


def test_reporting_service_generates_resource_evolution_report_with_no_recorded_changes():
    service = ReportingService(FakeReporter())

    result = AnalysisResult(diff=diff_result())

    change_history = ResourceChangeHistory(
        resource_external_id="resource-001",
        first_recorded_change=None,
        most_recent_recorded_change=None,
        recorded_change_count=0,
        recorded_change_span=None,
        comparison_indices=(),
    )

    output = service.generate_resource_evolution_report(
        "resource-001",
        (result,),
        change_history,
    )

    assert output == (
        "Resource Evolution: resource-001\n"
        "================================\n"
        "\n"
        "No recorded change history found for resource: resource-001\n"
        "\n"
        "Change 1:\n"
        "\n"
        "No observations.\n"
        "\n"
        "No findings."
    )


def test_reporting_service_generates_empty_resource_evolution_report():
    service = ReportingService(FakeReporter())

    output = service.generate_resource_evolution_report(
        "resource-001",
        (),
    )

    assert output == "No history found for resource: resource-001"


def test_reporting_service_generates_environment_evolution_report():
    service = ReportingService(FakeReporter())

    created = Resource(
        id=Identifier.new(),
        external_id="resource-created",
    )

    modified = Resource(
        id=Identifier.new(),
        external_id="resource-modified",
    )

    deleted = Resource(
        id=Identifier.new(),
        external_id="resource-deleted",
    )

    observation = Observation(
        subject="resource-created",
        type="resource_created",
        message="Resource created: resource-created",
        timestamp=datetime.now(UTC),
    )

    finding = Finding(
        subject="resource-created",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced: resource-created",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
    )

    history = (
        AnalysisResult(
            diff=diff_result(
                created=(created, modified),
            ),
            observations=(observation,),
            findings=(finding,),
        ),
        AnalysisResult(
            diff=diff_result(
                modified=(modified,),
                deleted=(deleted,),
            ),
        ),
    )

    output = service.generate_environment_evolution_report(history)

    assert output == (
        "Environment Evolution\n"
        "=====================\n"
        "\n"
        "Summary:\n"
        "- Comparisons analyzed: 2\n"
        "- Resources introduced: 2\n"
        "- Resources modified: 1\n"
        "- Resources removed: 1\n"
        "- Observations: 1\n"
        "- Findings: 1\n"
        "\n"
        "Most frequently changing resources:\n"
        "- resource-modified: 2 change(s)\n"
        "- resource-created: 1 change(s)\n"
        "- resource-deleted: 1 change(s)\n"
        "\n"
        "Operational activity concentration:\n"
        "- resource-modified: 50.0% (2 of 4 changes)\n"
        "- resource-created: 25.0% (1 of 4 changes)\n"
        "- resource-deleted: 25.0% (1 of 4 changes)\n"
        "\n"
        "Infrastructure activity breakdown:\n"
        "- Created: 50.0% (2 of 4 changes)\n"
        "- Modified: 25.0% (1 of 4 changes)\n"
        "- Deleted: 25.0% (1 of 4 changes)\n"
        "\n"
        "Recent infrastructure activity:\n"
        "- Comparison 1: 2 change(s)\n"
        "- Comparison 2: 2 change(s)\n"
        "\n"
        "Operational Review Queue:\n"
        "1. resource-modified\n"
        "   Appeared in 2 comparisons\n"
        "\n"
        "2. resource-created\n"
        "   Appeared in 1 comparisons\n"
        "\n"
        "3. resource-deleted\n"
        "   Appeared in 1 comparisons\n"
        "\n"
        "Introduced:\n"
        "- resource-created\n"
        "- resource-modified\n"
        "\n"
        "Modified:\n"
        "- resource-modified\n"
        "\n"
        "Removed:\n"
        "- resource-deleted"
    )


def test_reporting_service_generates_environment_evolution_report_with_empty_groups():
    service = ReportingService(FakeReporter())

    observation = Observation(
        subject="resource-001",
        type="resource_modified",
        message="Resource modified: resource-001",
        timestamp=datetime.now(UTC),
    )

    history = (
        AnalysisResult(
            diff=diff_result(),
            observations=(observation,),
        ),
    )

    output = service.generate_environment_evolution_report(history)

    assert output == (
        "Environment Evolution\n"
        "=====================\n"
        "\n"
        "Summary:\n"
        "- Comparisons analyzed: 1\n"
        "- Resources introduced: 0\n"
        "- Resources modified: 0\n"
        "- Resources removed: 0\n"
        "- Observations: 1\n"
        "- Findings: 0\n"
        "\n"
        "Most frequently changing resources:\n"
        "- None\n"
        "\n"
        "Operational activity concentration:\n"
        "- None\n"
        "\n"
        "Infrastructure activity breakdown:\n"
        "- None\n"
        "\n"
        "Recent infrastructure activity:\n"
        "- Comparison 1: 0 change(s)\n"
        "\n"
        "Operational Review Queue:\n"
        "- None\n"
        "\n"
        "Introduced:\n"
        "- None\n"
        "\n"
        "Modified:\n"
        "- None\n"
        "\n"
        "Removed:\n"
        "- None"
    )


def test_reporting_service_generates_empty_environment_evolution_report():
    service = ReportingService(FakeReporter())

    output = service.generate_environment_evolution_report(())

    assert output == "No environment history."


def test_reporting_service_renders_resource_change_history_report():
    service = ReportingService(FakeReporter())

    change_history = ResourceChangeHistory(
        resource_external_id="resource-001",
        first_recorded_change=1,
        most_recent_recorded_change=4,
        recorded_change_count=3,
        recorded_change_span="Comparison 1 -> Comparison 4",
        comparison_indices=(1, 2, 4),
    )

    output = service.generate_resource_change_history_report(change_history)

    assert output == (
        "Resource Change History: resource-001\n"
        "=====================================\n"
        "\n"
        "Summary:\n"
        "- First recorded change: Comparison 1\n"
        "- Most recent recorded change: Comparison 4\n"
        "- Recorded change count: 3\n"
        "- Recorded change span: Comparison 1 -> Comparison 4\n"
        "\n"
        "Comparisons containing recorded changes:\n"
        "- Comparison 1\n"
        "- Comparison 2\n"
        "- Comparison 4"
    )

    # Verify no prohibited words are present in the output
    prohibited_words = [
        "observed",
        "lifetime",
        "age",
        "stable",
        "unstable",
        "present",
        "absent",
        "critical",
        "important",
        "should investigate",
    ]
    for word in prohibited_words:
        assert word not in output.lower()


def test_reporting_service_renders_empty_resource_change_history_report():
    service = ReportingService(FakeReporter())

    change_history = ResourceChangeHistory(
        resource_external_id="resource-001",
        first_recorded_change=None,
        most_recent_recorded_change=None,
        recorded_change_count=0,
        recorded_change_span=None,
        comparison_indices=(),
    )

    output = service.generate_resource_change_history_report(change_history)

    assert output == "No recorded change history found for resource: resource-001"


def test_reporting_service_renders_latest_environment_change_index():
    service = ReportingService(FakeReporter())

    history = (
        AnalysisResult(
            diff=diff_result(),
        ),
    )

    # With changes present (latest_change_index = 1)
    output_with_changes = service.generate_environment_evolution_report(
        history,
        latest_change_index=1,
    )
    assert (
        "Latest comparison containing recorded changes: Comparison 1"
        in output_with_changes
    )

    # With no changes present (latest_change_index = None)
    output_no_changes = service.generate_environment_evolution_report(
        history,
        latest_change_index=None,
    )
    assert "No recorded infrastructure changes found." in output_no_changes


def test_reporting_service_renders_empty_instability_concentration_report():
    service = ReportingService(FakeReporter())

    output = service.generate_instability_concentration_report(
        EnvironmentInstabilitySummary()
    )

    assert output == (
        "Operational Instability Concentration\n"
        "\n"
        "No recorded infrastructure activity found."
    )


def test_reporting_service_renders_single_instability_concentration_resource():
    service = ReportingService(FakeReporter())
    summary = EnvironmentInstabilitySummary(
        resource_summaries=(
            ResourceInstabilitySummary(
                resource_external_id="resource-001",
                comparison_count=2,
                change_count=3,
                observation_count=4,
                finding_count=5,
                first_observed_comparison=1,
                most_recent_observed_comparison=3,
                recorded_activity_count=12,
            ),
        )
    )

    output = service.generate_instability_concentration_report(summary)

    assert output == (
        "Operational Instability Concentration\n"
        "=====================================\n"
        "\n"
        "Resource: resource-001\n"
        "Recorded activity: 12\n"
        "Comparisons involved: 2\n"
        "Changes: 3\n"
        "Observations: 4\n"
        "Findings: 5\n"
        "First observed comparison: 1\n"
        "Most recent observed comparison: 3"
    )


def test_reporting_service_preserves_instability_concentration_input_order():
    service = ReportingService(FakeReporter())
    summary = EnvironmentInstabilitySummary(
        resource_summaries=(
            _instability_summary("resource-b", recorded_activity_count=1),
            _instability_summary("resource-a", recorded_activity_count=10),
        )
    )

    output = service.generate_instability_concentration_report(summary)

    assert output.index("Resource: resource-b") < output.index("Resource: resource-a")


def test_reporting_service_instability_concentration_uses_factual_language():
    service = ReportingService(FakeReporter())
    summary = EnvironmentInstabilitySummary(
        resource_summaries=(
            _instability_summary("resource-001", recorded_activity_count=1),
        )
    )

    output = service.generate_instability_concentration_report(summary)

    assert "Recorded activity" in output
    assert "Comparisons involved" in output
    assert "Changes" in output
    assert "Observations" in output
    assert "Findings" in output


def test_reporting_service_instability_concentration_avoids_judgment_language():
    service = ReportingService(FakeReporter())
    summary = EnvironmentInstabilitySummary(
        resource_summaries=(
            _instability_summary("resource-001", recorded_activity_count=1),
        )
    )

    output = service.generate_instability_concentration_report(summary)

    forbidden_words = (
        "risk",
        "priority",
        "unstable",
        "unhealthy",
        "root cause",
        "recommendation",
        "should",
    )
    for word in forbidden_words:
        assert word not in output.lower()


def test_reporting_service_renders_insufficient_environment_stability_trend_report():
    service = ReportingService(FakeReporter())

    output = service.generate_environment_stability_trend_report(
        EnvironmentStabilityTrend()
    )

    assert output == (
        "Environment Stability Trend\n"
        "\n"
        "Insufficient history to determine activity direction."
    )


def test_reporting_service_renders_decreasing_environment_stability_trend_report():
    service = ReportingService(FakeReporter())
    trend = _stability_trend(
        trend_direction="decreasing",
        first_activity_count=6,
        most_recent_activity_count=2,
        activity_delta=-4,
    )

    output = service.generate_environment_stability_trend_report(trend)

    assert output == (
        "Environment Stability Trend\n"
        "===========================\n"
        "\n"
        "Trend direction: decreasing\n"
        "First recorded activity: 6\n"
        "Most recent recorded activity: 2\n"
        "Activity delta: -4\n"
        "\n"
        "Comparison Activity:\n"
        "- Comparison 1: recorded activity=6, changes=3, observations=2, findings=1\n"
        "- Comparison 2: recorded activity=2, changes=1, observations=1, findings=0"
    )


def test_reporting_service_renders_increasing_environment_stability_trend_report():
    service = ReportingService(FakeReporter())
    trend = _stability_trend(
        trend_direction="increasing",
        first_activity_count=2,
        most_recent_activity_count=6,
        activity_delta=4,
    )

    output = service.generate_environment_stability_trend_report(trend)

    assert "Trend direction: increasing" in output
    assert "First recorded activity: 2" in output
    assert "Most recent recorded activity: 6" in output
    assert "Activity delta: 4" in output


def test_reporting_service_renders_unchanged_environment_stability_trend_report():
    service = ReportingService(FakeReporter())
    trend = _stability_trend(
        trend_direction="unchanged",
        first_activity_count=2,
        most_recent_activity_count=2,
        activity_delta=0,
    )

    output = service.generate_environment_stability_trend_report(trend)

    assert "Trend direction: unchanged" in output
    assert "Activity delta: 0" in output


def test_reporting_service_renders_environment_stability_comparison_activity_details():
    service = ReportingService(FakeReporter())
    trend = EnvironmentStabilityTrend(
        comparison_activity=(
            ComparisonActivity(
                comparison_index=7,
                change_count=3,
                observation_count=2,
                finding_count=1,
                recorded_activity_count=6,
            ),
        ),
        first_activity_count=6,
        most_recent_activity_count=6,
        activity_delta=0,
        trend_direction="unchanged",
    )

    output = service.generate_environment_stability_trend_report(trend)

    assert (
        "- Comparison 7: recorded activity=6, changes=3, observations=2, findings=1"
        in output
    )


def test_reporting_service_preserves_environment_stability_comparison_activity_order():
    service = ReportingService(FakeReporter())
    trend = EnvironmentStabilityTrend(
        comparison_activity=(
            ComparisonActivity(
                comparison_index=3,
                change_count=1,
                observation_count=0,
                finding_count=0,
                recorded_activity_count=1,
            ),
            ComparisonActivity(
                comparison_index=1,
                change_count=2,
                observation_count=0,
                finding_count=0,
                recorded_activity_count=2,
            ),
        ),
        first_activity_count=1,
        most_recent_activity_count=2,
        activity_delta=1,
        trend_direction="increasing",
    )

    output = service.generate_environment_stability_trend_report(trend)

    assert output.index("Comparison 3") < output.index("Comparison 1")


def test_reporting_service_environment_stability_trend_avoids_judgment_language():
    service = ReportingService(FakeReporter())
    trend = _stability_trend(
        trend_direction="decreasing",
        first_activity_count=6,
        most_recent_activity_count=2,
        activity_delta=-4,
    )

    output = service.generate_environment_stability_trend_report(trend)

    forbidden_words = (
        "healthy",
        "unhealthy",
        "safe",
        "unsafe",
        "risk",
        "priority",
        "recommendation",
        "should",
        "good",
        "bad",
        "improved",
        "worsened",
    )
    body = output.replace("Environment Stability Trend", "")
    for word in forbidden_words:
        assert word not in body.lower()


def test_reporting_service_renders_empty_operational_activity_dominance_report():
    service = ReportingService(FakeReporter())

    output = service.generate_operational_activity_dominance_report(
        EnvironmentActivityDominanceSummary()
    )

    assert output == (
        "Operational Activity Dominance\n\nNo recorded operational activity found."
    )


def test_reporting_service_renders_single_operational_activity_dominance_report():
    service = ReportingService(FakeReporter())
    summary = EnvironmentActivityDominanceSummary(
        activity_summaries=(
            OperationalActivitySummary(
                activity_layer="change",
                activity_type="created",
                activity_count=3,
                comparison_count=2,
            ),
        )
    )

    output = service.generate_operational_activity_dominance_report(summary)

    assert output == (
        "Operational Activity Dominance\n"
        "==============================\n"
        "\n"
        "Activity Summary:\n"
        "- Layer: change, Type: created, Count: 3, Comparisons: 2"
    )


def test_reporting_service_preserves_operational_activity_dominance_input_order():
    service = ReportingService(FakeReporter())
    summary = EnvironmentActivityDominanceSummary(
        activity_summaries=(
            _activity_summary("observation", "resource_created", 4, 3),
            _activity_summary("change", "created", 5, 2),
            _activity_summary("finding", "new_infrastructure_introduced", 2, 1),
        )
    )

    output = service.generate_operational_activity_dominance_report(summary)

    assert output.index("Layer: observation") < output.index("Layer: change")
    assert output.index("Layer: change") < output.index("Layer: finding")


def test_reporting_service_renders_operational_activity_dominance_fields():
    service = ReportingService(FakeReporter())
    summary = EnvironmentActivityDominanceSummary(
        activity_summaries=(
            _activity_summary("finding", "new_infrastructure_introduced", 7, 4),
        )
    )

    output = service.generate_operational_activity_dominance_report(summary)

    assert (
        "- Layer: finding, Type: new_infrastructure_introduced, "
        "Count: 7, Comparisons: 4"
    ) in output


def test_reporting_service_operational_activity_dominance_avoids_judgment_language():
    service = ReportingService(FakeReporter())
    summary = EnvironmentActivityDominanceSummary(
        activity_summaries=(_activity_summary("change", "created", 3, 2),)
    )

    output = service.generate_operational_activity_dominance_report(summary)

    forbidden_words = (
        "recommendation",
        "risk",
        "priority",
        "severity",
        "root cause",
        "good",
        "bad",
        "improved",
        "worsened",
        "healthy",
        "unhealthy",
    )
    for word in forbidden_words:
        assert word not in output.lower()


def test_reporting_service_operational_activity_dominance_does_not_render_percentages():
    service = ReportingService(FakeReporter())
    summary = EnvironmentActivityDominanceSummary(
        activity_summaries=(
            _activity_summary("change", "created", 3, 2),
            _activity_summary("change", "deleted", 1, 1),
        )
    )

    output = service.generate_operational_activity_dominance_report(summary)

    assert "%" not in output


def test_reporting_service_renders_empty_resource_change_frequency_report():
    service = ReportingService(FakeReporter())

    output = service.generate_resource_change_frequency_report(
        EnvironmentChangeFrequencySummary()
    )

    assert output == "Resource Change Frequency\n\nNo observed resources found."


def test_reporting_service_renders_single_resource_change_frequency_report():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChangeFrequencySummary(
        resource_summaries=(
            ResourceChangeFrequencySummary(
                resource_external_id="resource-001",
                observed_snapshot_count=4,
                observed_comparison_count=3,
                recorded_change_count=2,
                first_observed_snapshot_index=1,
                most_recent_observed_snapshot_index=4,
                first_changed_comparison=1,
                most_recent_changed_comparison=3,
            ),
        )
    )

    output = service.generate_resource_change_frequency_report(summary)

    assert output == (
        "Resource Change Frequency\n"
        "=========================\n"
        "\n"
        "Resources:\n"
        "\n"
        "- Resource: resource-001\n"
        "  Observed snapshots: 4\n"
        "  Observed comparisons: 3\n"
        "  Recorded changes: 2\n"
        "  First observed snapshot: 1\n"
        "  Most recent observed snapshot: 4\n"
        "  First changed comparison: 1\n"
        "  Most recent changed comparison: 3"
    )


def test_reporting_service_preserves_resource_change_frequency_input_order():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChangeFrequencySummary(
        resource_summaries=(
            _change_frequency_summary("resource-b", recorded_change_count=0),
            _change_frequency_summary("resource-a", recorded_change_count=3),
        )
    )

    output = service.generate_resource_change_frequency_report(summary)

    assert output.index("Resource: resource-b") < output.index("Resource: resource-a")


def test_reporting_service_renders_resource_change_frequency_fields():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChangeFrequencySummary(
        resource_summaries=(
            ResourceChangeFrequencySummary(
                resource_external_id="resource-001",
                observed_snapshot_count=5,
                observed_comparison_count=4,
                recorded_change_count=0,
                first_observed_snapshot_index=2,
                most_recent_observed_snapshot_index=6,
                first_changed_comparison=None,
                most_recent_changed_comparison=None,
            ),
        )
    )

    output = service.generate_resource_change_frequency_report(summary)

    assert "Resource: resource-001" in output
    assert "Observed snapshots: 5" in output
    assert "Observed comparisons: 4" in output
    assert "Recorded changes: 0" in output
    assert "First observed snapshot: 2" in output
    assert "Most recent observed snapshot: 6" in output
    assert "First changed comparison: None" in output
    assert "Most recent changed comparison: None" in output


def test_reporting_service_resource_change_frequency_avoids_judgment_language():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChangeFrequencySummary(
        resource_summaries=(_change_frequency_summary("resource-001"),)
    )

    output = service.generate_resource_change_frequency_report(summary)

    forbidden_words = (
        "stable",
        "unstable",
        "trusted",
        "safe",
        "risky",
        "healthy",
        "unhealthy",
        "stale",
        "priority",
        "recommendation",
        "should",
    )
    for word in forbidden_words:
        assert word not in output.lower()


def test_reporting_service_resource_change_frequency_does_not_render_percentages():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChangeFrequencySummary(
        resource_summaries=(_change_frequency_summary("resource-001"),)
    )

    output = service.generate_resource_change_frequency_report(summary)

    assert "%" not in output


def test_reporting_service_renders_empty_resource_churn_trend_report():
    service = ReportingService(FakeReporter())

    output = service.generate_resource_churn_trend_report(
        EnvironmentChurnTrendSummary()
    )

    assert output == "Resource Churn Trend\n\nNo recorded resource activity found."


def test_reporting_service_renders_single_resource_churn_trend_report():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend(
                resource_external_id="resource-001",
                trend_direction="increasing",
                first_activity_count=1,
                most_recent_activity_count=3,
                activity_delta=2,
            ),
        )
    )

    output = service.generate_resource_churn_trend_report(summary)

    assert output == (
        "Resource Churn Trend\n"
        "====================\n"
        "\n"
        "Resources:\n"
        "\n"
        "- Resource: resource-001\n"
        "  Trend direction: increasing\n"
        "  First activity count: 1\n"
        "  Most recent activity count: 3\n"
        "  Activity delta: 2\n"
        "\n"
        "  Comparison Activity:\n"
        "\n"
        "    Comparison 1\n"
        "      Recorded activity: 1\n"
        "      Changes: 1\n"
        "      Observations: 0\n"
        "      Findings: 0\n"
        "\n"
        "    Comparison 2\n"
        "      Recorded activity: 3\n"
        "      Changes: 1\n"
        "      Observations: 1\n"
        "      Findings: 1"
    )


def test_reporting_service_renders_resource_churn_increasing_trend():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend(
                resource_external_id="resource-001",
                trend_direction="increasing",
                first_activity_count=1,
                most_recent_activity_count=3,
                activity_delta=2,
            ),
        )
    )

    output = service.generate_resource_churn_trend_report(summary)

    assert "Trend direction: increasing" in output
    assert "Activity delta: 2" in output


def test_reporting_service_renders_resource_churn_decreasing_trend():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend(
                resource_external_id="resource-001",
                trend_direction="decreasing",
                first_activity_count=3,
                most_recent_activity_count=1,
                activity_delta=-2,
            ),
        )
    )

    output = service.generate_resource_churn_trend_report(summary)

    assert "Trend direction: decreasing" in output
    assert "Activity delta: -2" in output


def test_reporting_service_renders_resource_churn_unchanged_trend():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend(
                resource_external_id="resource-001",
                trend_direction="unchanged",
                first_activity_count=2,
                most_recent_activity_count=2,
                activity_delta=0,
            ),
        )
    )

    output = service.generate_resource_churn_trend_report(summary)

    assert "Trend direction: unchanged" in output
    assert "Activity delta: 0" in output


def test_reporting_service_renders_resource_churn_insufficient_history():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend(
                resource_external_id="resource-001",
                trend_direction="insufficient_history",
                first_activity_count=1,
                most_recent_activity_count=1,
                activity_delta=0,
            ),
        )
    )

    output = service.generate_resource_churn_trend_report(summary)

    assert "Trend direction: insufficient_history" in output
    assert "First activity count: 1" in output
    assert "Most recent activity count: 1" in output


def test_reporting_service_renders_resource_churn_comparison_activity():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            ResourceChurnTrend(
                resource_external_id="resource-001",
                comparison_activity=(
                    ResourceComparisonActivity(
                        comparison_index=7,
                        change_count=3,
                        observation_count=2,
                        finding_count=1,
                        recorded_activity_count=6,
                    ),
                ),
                first_activity_count=6,
                most_recent_activity_count=6,
                activity_delta=0,
                trend_direction="unchanged",
            ),
        )
    )

    output = service.generate_resource_churn_trend_report(summary)

    assert "Comparison 7" in output
    assert "Recorded activity: 6" in output
    assert "Changes: 3" in output
    assert "Observations: 2" in output
    assert "Findings: 1" in output


def test_reporting_service_preserves_resource_churn_trend_input_order():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend("resource-b"),
            _churn_trend("resource-a"),
        )
    )

    output = service.generate_resource_churn_trend_report(summary)

    assert output.index("Resource: resource-b") < output.index("Resource: resource-a")


def test_reporting_service_limits_resource_churn_trend_report():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend("resource-001"),
            _churn_trend("resource-002"),
            _churn_trend("resource-003"),
        )
    )

    output = service.generate_resource_churn_trend_report(summary, limit=2)

    assert "Resource: resource-001" in output
    assert "Resource: resource-002" in output
    assert "Resource: resource-003" not in output
    assert (
        "Showing 2 of 3 resource trends. "
        "1 omitted. Use --all to show the complete report."
    ) in output


def test_reporting_service_resource_churn_trend_limit_none_matches_full_report():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend("resource-001"),
            _churn_trend("resource-002"),
        )
    )

    output = service.generate_resource_churn_trend_report(summary)
    explicit_full_output = service.generate_resource_churn_trend_report(
        summary,
        limit=None,
    )

    assert explicit_full_output == output
    assert "Resource: resource-001" in explicit_full_output
    assert "Resource: resource-002" in explicit_full_output
    assert "omitted. Use --all to show the complete report." not in explicit_full_output


def test_reporting_service_resource_churn_trend_does_not_render_omitted_count_at_limit():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(
            _churn_trend("resource-001"),
            _churn_trend("resource-002"),
        )
    )

    output = service.generate_resource_churn_trend_report(summary, limit=2)

    assert "Resource: resource-001" in output
    assert "Resource: resource-002" in output
    assert "omitted. Use --all to show the complete report." not in output


def test_reporting_service_resource_churn_trend_avoids_forbidden_language():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(_churn_trend("resource-001"),)
    )

    output = service.generate_resource_churn_trend_report(summary)

    forbidden_words = (
        "recommendation",
        "priority",
        "severity",
        "risk",
        "root cause",
        "healthy",
        "unhealthy",
        "stable",
        "unstable",
        "safe",
        "unsafe",
        "trusted",
        "stale",
        "should",
        "good",
        "bad",
        "improved",
        "worsened",
    )
    body = output.replace("Resource Churn Trend", "")
    for word in forbidden_words:
        assert word not in body.lower()


def test_reporting_service_resource_churn_trend_does_not_render_percentages():
    service = ReportingService(FakeReporter())
    summary = EnvironmentChurnTrendSummary(
        resource_trends=(_churn_trend("resource-001"),)
    )

    output = service.generate_resource_churn_trend_report(summary)

    assert "%" not in output


def test_reporting_service_renders_empty_resource_metadata_grouping_report():
    service = ReportingService(FakeReporter())

    output = service.generate_resource_metadata_grouping_report(())

    assert output == (
        "Resource Metadata Grouping\n\nNo recorded metadata groups found."
    )


def test_reporting_service_renders_single_resource_metadata_group():
    service = ReportingService(FakeReporter())
    groups = (
        ResourceMetadataGroup(
            metadata_key="tags.Environment",
            metadata_value="prod",
            resource_count=2,
            resource_external_ids=("i-001", "i-002"),
        ),
    )

    output = service.generate_resource_metadata_grouping_report(groups)

    assert output == (
        "Resource Metadata Grouping\n"
        "==========================\n"
        "\n"
        "Metadata: tags.Environment\n"
        "\n"
        "Value: prod\n"
        "Recorded resources: 2\n"
        "Resources:\n"
        "- i-001\n"
        "- i-002"
    )


def test_reporting_service_preserves_resource_metadata_grouping_input_order():
    service = ReportingService(FakeReporter())
    groups = (
        ResourceMetadataGroup(
            metadata_key="tags.Environment",
            metadata_value="prod",
            resource_count=1,
            resource_external_ids=("i-prod",),
        ),
        ResourceMetadataGroup(
            metadata_key="tags.Environment",
            metadata_value="dev",
            resource_count=1,
            resource_external_ids=("i-dev",),
        ),
    )

    output = service.generate_resource_metadata_grouping_report(groups)

    assert output.index("Value: prod") < output.index("Value: dev")


def test_reporting_service_renders_metadata_group_resources_deterministically():
    service = ReportingService(FakeReporter())
    groups = (
        ResourceMetadataGroup(
            metadata_key="tags.Environment",
            metadata_value="prod",
            resource_count=3,
            resource_external_ids=("i-003", "i-001", "i-002"),
        ),
    )

    output = service.generate_resource_metadata_grouping_report(groups)

    assert output.index("- i-001") < output.index("- i-002")
    assert output.index("- i-002") < output.index("- i-003")


def test_reporting_service_resource_metadata_grouping_renders_metadata_key():
    service = ReportingService(FakeReporter())
    groups = (
        ResourceMetadataGroup(
            metadata_key="tags.Owner",
            metadata_value="platform",
            resource_count=1,
            resource_external_ids=("i-001",),
        ),
    )

    output = service.generate_resource_metadata_grouping_report(groups)

    assert "Metadata: tags.Owner" in output


def test_reporting_service_resource_metadata_grouping_avoids_forbidden_language():
    service = ReportingService(FakeReporter())
    groups = (
        ResourceMetadataGroup(
            metadata_key="tags.Environment",
            metadata_value="prod",
            resource_count=1,
            resource_external_ids=("i-001",),
        ),
    )

    output = service.generate_resource_metadata_grouping_report(groups)

    forbidden_words = (
        "owner",
        "service",
        "workload",
        "application",
        "missing",
        "required",
        "compliance",
        "risk",
        "priority",
        "recommendation",
        "should",
    )
    for word in forbidden_words:
        assert word not in output.lower()


def test_reporting_service_renders_empty_resource_observation_history_report():
    service = ReportingService(FakeReporter())

    output = service.generate_resource_observation_history_report(())

    assert output == (
        "Resource Observation History\n\nNo resource observation history found."
    )


def test_reporting_service_renders_single_resource_observation_history():
    service = ReportingService(FakeReporter())
    first_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()
    summaries = (
        ResourceObservationSummary(
            resource_external_id="resource-001",
            first_observed_snapshot_id=first_snapshot_id,
            latest_observed_snapshot_id=latest_snapshot_id,
            observed_snapshot_count=7,
            observation_gap_count=2,
        ),
    )

    output = service.generate_resource_observation_history_report(summaries)

    assert output == (
        "Resource Observation History\n"
        "============================\n"
        "\n"
        "Resource: resource-001\n"
        f"First observed snapshot: {first_snapshot_id}\n"
        f"Latest observed snapshot: {latest_snapshot_id}\n"
        "Observed snapshots: 7\n"
        "Observation gaps: 2"
    )


def test_reporting_service_renders_multiple_resource_observation_histories():
    service = ReportingService(FakeReporter())
    summaries = (
        _observation_summary(
            "resource-001",
            observed_snapshot_count=7,
            observation_gap_count=2,
        ),
        _observation_summary(
            "resource-002",
            observed_snapshot_count=3,
            observation_gap_count=0,
        ),
    )

    output = service.generate_resource_observation_history_report(summaries)

    assert "Resource: resource-001" in output
    assert "Observed snapshots: 7" in output
    assert "Observation gaps: 2" in output
    assert "Resource: resource-002" in output
    assert "Observed snapshots: 3" in output
    assert "Observation gaps: 0" in output


def test_reporting_service_preserves_resource_observation_history_input_order():
    service = ReportingService(FakeReporter())
    summaries = (
        _observation_summary("resource-b"),
        _observation_summary("resource-a"),
    )

    output = service.generate_resource_observation_history_report(summaries)

    assert output.index("Resource: resource-b") < output.index("Resource: resource-a")


def test_reporting_service_renders_resource_observation_history_identifiers():
    service = ReportingService(FakeReporter())
    first_snapshot_id = Identifier.new()
    latest_snapshot_id = Identifier.new()
    summaries = (
        ResourceObservationSummary(
            resource_external_id="resource-001",
            first_observed_snapshot_id=first_snapshot_id,
            latest_observed_snapshot_id=latest_snapshot_id,
            observed_snapshot_count=2,
            observation_gap_count=0,
        ),
    )

    output = service.generate_resource_observation_history_report(summaries)

    assert str(first_snapshot_id) in output
    assert str(latest_snapshot_id) in output


def test_reporting_service_renders_zero_resource_observation_gaps():
    service = ReportingService(FakeReporter())
    summaries = (_observation_summary("resource-001", observation_gap_count=0),)

    output = service.generate_resource_observation_history_report(summaries)

    assert "Observation gaps: 0" in output


def test_reporting_service_resource_observation_history_avoids_forbidden_terminology():
    service = ReportingService(FakeReporter())
    summaries = (_observation_summary("resource-001"),)

    output = service.generate_resource_observation_history_report(summaries)

    forbidden_words = (
        "lifetime",
        "created",
        "deleted",
        "age",
        "creation",
        "deletion",
        "continuously observed",
        "existed",
        "uptime",
    )
    for word in forbidden_words:
        assert word not in output.lower()


def test_reporting_service_renders_empty_historical_inventory_timeline_report():
    service = ReportingService(FakeReporter())

    output = service.generate_historical_inventory_timeline_report(())

    assert output == (
        "Historical Inventory Timeline\n\nNo historical inventory observations found."
    )


def test_reporting_service_renders_single_historical_inventory_observation():
    service = ReportingService(FakeReporter())
    snapshot_id = Identifier.new()
    observations = (
        HistoricalInventoryObservation(
            snapshot_id=snapshot_id,
            recorded_resource_count=3,
        ),
    )

    output = service.generate_historical_inventory_timeline_report(observations)

    assert output == (
        "Historical Inventory Timeline\n"
        "=============================\n"
        "\n"
        f"Snapshot: {snapshot_id}\n"
        "Recorded resources: 3"
    )


def test_reporting_service_preserves_historical_inventory_timeline_input_order():
    service = ReportingService(FakeReporter())
    first_snapshot_id = Identifier.new()
    second_snapshot_id = Identifier.new()
    observations = (
        HistoricalInventoryObservation(
            snapshot_id=first_snapshot_id,
            recorded_resource_count=1,
        ),
        HistoricalInventoryObservation(
            snapshot_id=second_snapshot_id,
            recorded_resource_count=2,
        ),
    )

    output = service.generate_historical_inventory_timeline_report(observations)

    assert output.index(f"Snapshot: {first_snapshot_id}") < output.index(
        f"Snapshot: {second_snapshot_id}"
    )


def test_reporting_service_renders_zero_historical_inventory_resource_count():
    service = ReportingService(FakeReporter())
    observations = (
        HistoricalInventoryObservation(
            snapshot_id=Identifier.new(),
            recorded_resource_count=0,
        ),
    )

    output = service.generate_historical_inventory_timeline_report(observations)

    assert "Recorded resources: 0" in output


def test_reporting_service_historical_inventory_timeline_avoids_forbidden_terminology():
    service = ReportingService(FakeReporter())
    observations = (
        HistoricalInventoryObservation(
            snapshot_id=Identifier.new(),
            recorded_resource_count=1,
        ),
    )

    output = service.generate_historical_inventory_timeline_report(observations)

    forbidden_words = (
        "growth",
        "shrinkage",
        "trend",
        "healthy",
        "expected",
        "anomaly",
        "capacity",
        "recommendation",
        "should",
    )
    for word in forbidden_words:
        assert word not in output.lower()


def _instability_summary(
    resource_external_id: str,
    recorded_activity_count: int,
) -> ResourceInstabilitySummary:
    return ResourceInstabilitySummary(
        resource_external_id=resource_external_id,
        comparison_count=1,
        change_count=recorded_activity_count,
        observation_count=0,
        finding_count=0,
        first_observed_comparison=1,
        most_recent_observed_comparison=1,
        recorded_activity_count=recorded_activity_count,
    )


def _stability_trend(
    trend_direction: str,
    first_activity_count: int,
    most_recent_activity_count: int,
    activity_delta: int,
) -> EnvironmentStabilityTrend:
    return EnvironmentStabilityTrend(
        comparison_activity=(
            ComparisonActivity(
                comparison_index=1,
                change_count=3,
                observation_count=2,
                finding_count=1,
                recorded_activity_count=6,
            ),
            ComparisonActivity(
                comparison_index=2,
                change_count=1,
                observation_count=1,
                finding_count=0,
                recorded_activity_count=2,
            ),
        ),
        first_activity_count=first_activity_count,
        most_recent_activity_count=most_recent_activity_count,
        activity_delta=activity_delta,
        trend_direction=trend_direction,
    )


def _activity_summary(
    activity_layer: str,
    activity_type: str,
    activity_count: int,
    comparison_count: int,
) -> OperationalActivitySummary:
    return OperationalActivitySummary(
        activity_layer=activity_layer,
        activity_type=activity_type,
        activity_count=activity_count,
        comparison_count=comparison_count,
    )


def _change_frequency_summary(
    resource_external_id: str,
    recorded_change_count: int = 1,
) -> ResourceChangeFrequencySummary:
    return ResourceChangeFrequencySummary(
        resource_external_id=resource_external_id,
        observed_snapshot_count=3,
        observed_comparison_count=2,
        recorded_change_count=recorded_change_count,
        first_observed_snapshot_index=1,
        most_recent_observed_snapshot_index=3,
        first_changed_comparison=1,
        most_recent_changed_comparison=2,
    )


def _churn_trend(
    resource_external_id: str,
    trend_direction: str = "increasing",
    first_activity_count: int = 1,
    most_recent_activity_count: int = 3,
    activity_delta: int = 2,
) -> ResourceChurnTrend:
    return ResourceChurnTrend(
        resource_external_id=resource_external_id,
        comparison_activity=(
            ResourceComparisonActivity(
                comparison_index=1,
                change_count=1,
                observation_count=0,
                finding_count=0,
                recorded_activity_count=first_activity_count,
            ),
            ResourceComparisonActivity(
                comparison_index=2,
                change_count=1,
                observation_count=1,
                finding_count=1,
                recorded_activity_count=most_recent_activity_count,
            ),
        ),
        first_activity_count=first_activity_count,
        most_recent_activity_count=most_recent_activity_count,
        activity_delta=activity_delta,
        trend_direction=trend_direction,
    )


def _observation_summary(
    resource_external_id: str,
    observed_snapshot_count: int = 1,
    observation_gap_count: int = 0,
) -> ResourceObservationSummary:
    return ResourceObservationSummary(
        resource_external_id=resource_external_id,
        first_observed_snapshot_id=Identifier.new(),
        latest_observed_snapshot_id=Identifier.new(),
        observed_snapshot_count=observed_snapshot_count,
        observation_gap_count=observation_gap_count,
    )

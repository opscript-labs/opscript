from datetime import UTC, datetime

from platformiq.core import Identifier
from platformiq.model import AnalysisResult, DiffResult, Finding, Observation, Resource

from opscript.application import InfrastructureChangeSummaryService


def resource(external_id: str) -> Resource:
    return Resource(
        id=Identifier.new(),
        external_id=external_id,
    )


def diff_result(**kwargs) -> DiffResult:
    return DiffResult(
        previous_snapshot_id=Identifier.new(),
        current_snapshot_id=Identifier.new(),
        **kwargs,
    )


def observation(subject: str, message: str) -> Observation:
    return Observation(
        subject=subject,
        type="resource_changed",
        message=message,
        timestamp=datetime.now(UTC),
    )


def finding(subject: str, message: str) -> Finding:
    return Finding(
        subject=subject,
        type="resource_review_required",
        message=message,
        timestamp=datetime.now(UTC),
        source_observation_type="resource_changed",
    )


def test_infrastructure_change_summary_service_summarizes_analysis_result_by_resource():
    changed_resource = resource("resource-001")

    resource_observation = observation(
        "resource-001",
        "Resource created: resource-001",
    )

    resource_finding = Finding(
        subject="resource-001",
        type="new_infrastructure_introduced",
        message="New infrastructure introduced: resource-001",
        timestamp=datetime.now(UTC),
        source_observation_type="resource_created",
    )

    analysis_result = AnalysisResult(
        diff=diff_result(
            created=(changed_resource,),
        ),
        observations=(resource_observation,),
        findings=(resource_finding,),
    )

    service = InfrastructureChangeSummaryService()

    summary = service.summarize(analysis_result)

    assert summary.title == "Infrastructure Change Summary"
    assert len(summary.resource_summaries) == 1

    resource_summary = summary.resource_summaries[0]

    assert resource_summary.resource == changed_resource
    assert resource_summary.change_type == "created"
    assert resource_summary.observations == (resource_observation,)
    assert resource_summary.findings == (resource_finding,)


def test_infrastructure_change_summary_service_handles_empty_analysis_result():
    analysis_result = AnalysisResult(
        diff=diff_result(),
    )

    service = InfrastructureChangeSummaryService()

    summary = service.summarize(analysis_result)

    assert summary.title == "Infrastructure Change Summary"
    assert summary.resource_summaries == ()


def test_infrastructure_change_summary_service_orders_resource_summaries_for_investigation():
    created_b = resource("resource-b")
    created_a = resource("resource-a")
    modified_b = resource("resource-d")
    modified_a = resource("resource-c")
    deleted_b = resource("resource-f")
    deleted_a = resource("resource-e")

    analysis_result = AnalysisResult(
        diff=diff_result(
            created=(created_b, created_a),
            modified=(modified_b, modified_a),
            deleted=(deleted_b, deleted_a),
        ),
    )

    service = InfrastructureChangeSummaryService()

    summary = service.summarize(analysis_result)

    ordered = tuple(
        (resource_summary.change_type, resource_summary.resource.external_id)
        for resource_summary in summary.resource_summaries
    )

    assert ordered == (
        ("created", "resource-a"),
        ("created", "resource-b"),
        ("modified", "resource-c"),
        ("modified", "resource-d"),
        ("deleted", "resource-e"),
        ("deleted", "resource-f"),
    )


def test_infrastructure_change_summary_service_indexes_interleaved_knowledge_by_subject():
    resource_a = resource("resource-a")
    resource_b = resource("resource-b")
    unrelated_observation = observation("resource-c", "Unrelated observation")
    unrelated_finding = finding("resource-c", "Unrelated finding")
    observation_a = observation("resource-a", "Observation A")
    observation_b = observation("resource-b", "Observation B")
    finding_a = finding("resource-a", "Finding A")
    finding_b = finding("resource-b", "Finding B")

    analysis_result = AnalysisResult(
        diff=diff_result(
            created=(resource_b, resource_a),
        ),
        observations=(unrelated_observation, observation_b, observation_a),
        findings=(finding_b, unrelated_finding, finding_a),
    )

    service = InfrastructureChangeSummaryService()

    summary = service.summarize(analysis_result)

    resource_a_summary, resource_b_summary = summary.resource_summaries

    assert resource_a_summary.resource == resource_a
    assert resource_a_summary.observations == (observation_a,)
    assert resource_a_summary.findings == (finding_a,)

    assert resource_b_summary.resource == resource_b
    assert resource_b_summary.observations == (observation_b,)
    assert resource_b_summary.findings == (finding_b,)


def test_infrastructure_change_summary_service_preserves_knowledge_order_per_subject():
    changed_resource = resource("resource-001")
    first_observation = observation("resource-001", "First observation")
    second_observation = observation("resource-001", "Second observation")
    first_finding = finding("resource-001", "First finding")
    second_finding = finding("resource-001", "Second finding")

    analysis_result = AnalysisResult(
        diff=diff_result(
            created=(changed_resource,),
        ),
        observations=(first_observation, second_observation),
        findings=(first_finding, second_finding),
    )

    service = InfrastructureChangeSummaryService()

    summary = service.summarize(analysis_result)

    resource_summary = summary.resource_summaries[0]

    assert resource_summary.observations == (first_observation, second_observation)
    assert resource_summary.findings == (first_finding, second_finding)


def test_infrastructure_change_summary_service_ignores_knowledge_for_unchanged_resources():
    changed_resource = resource("resource-001")
    unrelated_observation = observation("resource-002", "Unrelated observation")
    unrelated_finding = finding("resource-002", "Unrelated finding")

    analysis_result = AnalysisResult(
        diff=diff_result(
            created=(changed_resource,),
        ),
        observations=(unrelated_observation,),
        findings=(unrelated_finding,),
    )

    service = InfrastructureChangeSummaryService()

    summary = service.summarize(analysis_result)

    resource_summary = summary.resource_summaries[0]

    assert resource_summary.observations == ()
    assert resource_summary.findings == ()


def test_infrastructure_change_summary_service_keeps_empty_knowledge_tuples():
    changed_resource = resource("resource-001")

    analysis_result = AnalysisResult(
        diff=diff_result(
            created=(changed_resource,),
        ),
    )

    service = InfrastructureChangeSummaryService()

    summary = service.summarize(analysis_result)

    resource_summary = summary.resource_summaries[0]

    assert resource_summary.observations == ()
    assert resource_summary.findings == ()

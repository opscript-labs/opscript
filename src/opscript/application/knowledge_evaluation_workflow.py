from opscript.application.frequent_infrastructure_modification_rule import (
    FrequentInfrastructureModificationRule,
)
from opscript.application.recognized_finding_projection import (
    recognized_finding_from_recognition,
)
from opscript.application.recurring_infrastructure_removal_activity_rule import (
    RecurringInfrastructureRemovalActivityRule,
)
from opscript.application.recurring_infrastructure_introduction_activity_rule import (
    RecurringInfrastructureIntroductionActivityRule,
)
from opscript.application.qualified_historical_evidence_service import (
    scope_level_qualified_historical_evidence,
)
from opscript.models import QualifiedHistoricalEvidence, RecognizedFinding


def evaluate_engineering_knowledge(
    qualified_historical_evidence: QualifiedHistoricalEvidence,
) -> tuple[RecognizedFinding, ...]:
    recognition_results = []
    scope_level_evidence = scope_level_qualified_historical_evidence(
        qualified_historical_evidence
    )

    if qualified_historical_evidence.canonical_subject is not None:
        recognition_results.append(
            FrequentInfrastructureModificationRule().evaluate(
                qualified_historical_evidence
            )
        )

    recognition_results.append(
        RecurringInfrastructureRemovalActivityRule().evaluate(scope_level_evidence)
    )
    recognition_results.append(
        RecurringInfrastructureIntroductionActivityRule().evaluate(scope_level_evidence)
    )

    return tuple(
        recognized_finding_from_recognition(recognition_result)
        for recognition_result in recognition_results
        if recognition_result.supported
    )

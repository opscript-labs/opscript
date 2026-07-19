from opscript.models import QualifiedHistoricalEvidence, RecognitionResult


class FrequentInfrastructureModificationRule:
    """
    Evaluates frequent modification across qualified comparison intervals.
    """

    engineering_condition = RecognitionResult.engineering_condition
    recognition_threshold = RecognitionResult.recognition_threshold
    minimum_completed_interval_count = (
        RecognitionResult.minimum_completed_interval_count
    )
    qualifying_observation_type = "resource_modified"

    def evaluate(
        self,
        qualified_historical_evidence: QualifiedHistoricalEvidence,
    ) -> RecognitionResult:
        canonical_subject = qualified_historical_evidence.canonical_subject
        if canonical_subject is None:
            raise ValueError("Frequent modification recognition requires a subject.")

        if (
            len(qualified_historical_evidence.completed_intervals)
            < self.minimum_completed_interval_count
        ):
            raise ValueError(
                "Frequent modification recognition requires at least four "
                "completed intervals."
            )

        qualifying_interval_count = sum(
            1
            for interval in qualified_historical_evidence.completed_intervals
            if any(
                observation.type == self.qualifying_observation_type
                and observation.subject == canonical_subject
                for observation in interval.observations
            )
        )

        outcome = (
            "supported"
            if qualifying_interval_count >= self.recognition_threshold
            else "not_supported"
        )

        return RecognitionResult(
            outcome=outcome,
            qualified_historical_evidence=qualified_historical_evidence,
        )

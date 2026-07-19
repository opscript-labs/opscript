from opscript.models import QualifiedHistoricalEvidence, RecognitionResult


class RecurringInfrastructureRemovalActivityRule:
    """
    Evaluates recurring removals across qualified comparison intervals.
    """

    engineering_condition = (
        RecognitionResult.recurring_infrastructure_removal_activity_condition
    )
    recognition_threshold = RecognitionResult.recognition_threshold
    minimum_completed_interval_count = (
        RecognitionResult.minimum_completed_interval_count
    )
    qualifying_observation_type = "resource_removed"

    def evaluate(
        self,
        qualified_historical_evidence: QualifiedHistoricalEvidence,
    ) -> RecognitionResult:
        if (
            len(qualified_historical_evidence.completed_intervals)
            < self.minimum_completed_interval_count
        ):
            raise ValueError(
                "Recurring removal recognition requires at least four "
                "completed intervals."
            )

        qualifying_interval_count = sum(
            1
            for interval in qualified_historical_evidence.completed_intervals
            if any(
                observation.type == self.qualifying_observation_type
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
            engineering_condition=self.engineering_condition,
        )

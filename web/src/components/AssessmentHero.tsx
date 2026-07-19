import { BadgeCheck, Clock3, FileCheck2 } from "lucide-react";

import type {
  DailyBriefingAssessmentViewModel,
  DailyBriefingEvidenceCoverageViewModel,
} from "../presentation/dailyBriefing/dailyBriefingViewModel";
import { AssessmentMetric } from "./AssessmentMetric";
import { AssessmentStatus } from "./AssessmentStatus";

type AssessmentHeroProps = {
  assessment: DailyBriefingAssessmentViewModel;
  evidenceCoverage: DailyBriefingEvidenceCoverageViewModel;
};

export function AssessmentHero({
  assessment,
  evidenceCoverage,
}: AssessmentHeroProps) {
  const evidenceCount =
    evidenceCoverage.status === "available"
      ? `${evidenceCoverage.completed} of ${evidenceCoverage.expected}`
      : null;

  return (
    <section className="assessment-hero" aria-labelledby="assessment-hero-title">
      <div className="assessment-hero__meta">
        <p className="assessment-hero__label">{assessment.label}</p>
        {assessment.status === "available" ? (
          <p className="assessment-hero__updated">
            <Clock3 size={15} aria-hidden="true" />
            {assessment.updatedAt}
          </p>
        ) : null}
      </div>

      {assessment.status === "available" ? (
        <AssessmentStatus assessment={assessment} />
      ) : (
        <h2 id="assessment-hero-title">{assessment.message}</h2>
      )}

      {assessment.status === "available" ? (
        <p className="assessment-hero__explanation">{assessment.explanation}</p>
      ) : null}

      <div className="assessment-hero__lower">
        <AssessmentMetric label="Evidence coverage">
          {evidenceCoverage.status === "available" ? (
            <>
              <div className="assessment-hero__evidence-values">
                <span className="assessment-hero__evidence-count">
                  {evidenceCount}
                </span>
                <span className="assessment-hero__evidence-percent">
                  {evidenceCoverage.percentage}%
                </span>
              </div>
              <progress
                className="assessment-hero__progress"
                aria-label="Evidence coverage"
                value={evidenceCoverage.percentage}
                max="100"
              />
            </>
          ) : (
            <p>{evidenceCoverage.message}</p>
          )}
        </AssessmentMetric>

        {assessment.status === "available" ? (
          <AssessmentMetric
            label="Confidence"
            icon={<BadgeCheck size={18} aria-hidden="true" />}
          >
            <p className="assessment-hero__confidence">{assessment.confidence}</p>
          </AssessmentMetric>
        ) : null}

        {assessment.status === "available" ? (
          <div className="assessment-hero__supporting-note">
            <FileCheck2 size={17} aria-hidden="true" />
            <p>{assessment.supportingNote}</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}

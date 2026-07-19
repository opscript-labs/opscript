import { TriangleAlert } from "lucide-react";

import type { DailyBriefingAssessmentViewModel } from "../presentation/dailyBriefing/dailyBriefingViewModel";

type AssessmentStatusProps = {
  assessment: Extract<DailyBriefingAssessmentViewModel, { status: "available" }>;
};

const statusLabels: Record<
  Extract<DailyBriefingAssessmentViewModel, { status: "available" }>["statusCategory"],
  string
> = {
  attention: "Attention required",
  critical: "Critical",
  healthy: "Healthy",
  unknown: "Unknown",
};

export function AssessmentStatus({ assessment }: AssessmentStatusProps) {
  return (
    <div className="assessment-status">
      <span
        className="assessment-status__icon"
        data-category={assessment.statusCategory}
        aria-hidden="true"
      >
        <TriangleAlert size={24} strokeWidth={2.2} />
      </span>
      <div className="assessment-status__content">
        <h2 id="assessment-hero-title">{assessment.assessmentStatus}</h2>
        <span
          className="assessment-status__pill"
          data-category={assessment.statusCategory}
        >
          {statusLabels[assessment.statusCategory]}
        </span>
      </div>
    </div>
  );
}

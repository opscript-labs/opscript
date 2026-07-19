import { buildDailyBriefingViewModel } from "../presentation/dailyBriefing/buildDailyBriefingViewModel";
import type { DailyBriefingPresentationSource } from "../presentation/dailyBriefing/dailyBriefingPresentationSource";
import { fixtureDailyBriefingPresentationSource } from "../presentation/dailyBriefing/fixtureDailyBriefingPresentationSource";
import { AssessmentHero } from "./AssessmentHero";
import { BriefingMetrics } from "./BriefingMetrics";
import { EngineeringBrief } from "./EngineeringBrief";
import { EvidenceSummary } from "./EvidenceSummary";
import { ReviewContext } from "./ReviewContext";
import { ReviewFocus } from "./ReviewFocus";

export function DailyBriefingRuntime() {
  return (
    <DailyBriefingSuccess presentation={fixtureDailyBriefingPresentationSource} />
  );
}

function DailyBriefingSuccess({
  presentation,
}: {
  readonly presentation: DailyBriefingPresentationSource;
}) {
  const briefing = buildDailyBriefingViewModel(presentation);

  return (
    <div className="daily-briefing-layout">
      <div className="daily-briefing-layout__primary">
        <AssessmentHero
          assessment={briefing.assessment}
          evidenceCoverage={briefing.evidenceCoverage}
        />
        <BriefingMetrics metrics={briefing.metrics} />
        <ReviewFocus focus={briefing.reviewFocus} />
        <EvidenceSummary summary={briefing.evidenceSummary} />
        <EngineeringBrief brief={briefing.engineeringBrief} />
      </div>
      <aside
        className="daily-briefing-layout__rail"
        aria-label="Daily Briefing context"
      >
        <ReviewContext context={briefing.reviewContext} />
      </aside>
    </div>
  );
}

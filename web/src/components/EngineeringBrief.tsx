import { FileText } from "lucide-react";

import type { DailyBriefingEngineeringBriefViewModel } from "../presentation/dailyBriefing/dailyBriefingViewModel";

type EngineeringBriefProps = {
  brief: DailyBriefingEngineeringBriefViewModel;
};

export function EngineeringBrief({ brief }: EngineeringBriefProps) {
  const label = brief.status === "available" ? brief.value.label : brief.label;
  const title = brief.status === "available" ? brief.value.title : brief.title;

  return (
    <section className="engineering-brief" aria-labelledby="engineering-brief-title">
      <p className="engineering-brief__label">{label}</p>
      <div className="engineering-brief__card">
        <h2 id="engineering-brief-title">{title}</h2>
        {brief.status === "available" ? (
          <>
            <p className="engineering-brief__summary">{brief.value.summary}</p>
            <div className="engineering-brief__note">
              <FileText size={17} aria-hidden="true" />
              <p>{brief.value.supportingNote}</p>
            </div>
          </>
        ) : (
          <p className="engineering-brief__summary">{brief.message}</p>
        )}
      </div>
    </section>
  );
}

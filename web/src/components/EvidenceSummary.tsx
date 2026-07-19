import { FileCheck2 } from "lucide-react";

import type { DailyBriefingEvidenceSummary } from "../data/dailyBriefing";
import { EvidenceSummaryItem } from "./EvidenceSummaryItem";

type EvidenceSummaryProps = {
  summary: DailyBriefingEvidenceSummary;
};

export function EvidenceSummary({ summary }: EvidenceSummaryProps) {
  return (
    <section className="evidence-summary" aria-labelledby="evidence-summary-title">
      <p className="evidence-summary__label">{summary.label}</p>
      <div className="evidence-summary__card">
        <h2 id="evidence-summary-title">{summary.title}</h2>
        <ul className="evidence-summary__list">
          {summary.items.map((item) => (
            <EvidenceSummaryItem key={item.id} item={item} />
          ))}
        </ul>
        <div className="evidence-summary__note">
          <FileCheck2 size={17} aria-hidden="true" />
          <p>{summary.supportingNote}</p>
        </div>
      </div>
    </section>
  );
}

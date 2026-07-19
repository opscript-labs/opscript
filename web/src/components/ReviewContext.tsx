import { ClipboardCheck } from "lucide-react";

import type { DailyBriefingReviewContext } from "../data/dailyBriefing";
import { ReviewContextEntry } from "./ReviewContextEntry";

type ReviewContextProps = {
  context: DailyBriefingReviewContext;
};

export function ReviewContext({ context }: ReviewContextProps) {
  return (
    <section className="review-context" aria-labelledby="review-context-title">
      <p className="review-context__label">{context.label}</p>
      <div className="review-context__card">
        <div className="review-context__heading">
          <span className="review-context__icon" aria-hidden="true">
            <ClipboardCheck size={18} strokeWidth={2} />
          </span>
          <h2 id="review-context-title">{context.title}</h2>
        </div>

        <dl className="review-context__entries">
          {context.entries.map((entry) => (
            <ReviewContextEntry key={entry.label} entry={entry} />
          ))}
        </dl>

        <div className="review-context__note">
          <p>{context.supportingNote}</p>
        </div>
      </div>
    </section>
  );
}

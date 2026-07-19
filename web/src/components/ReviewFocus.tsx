import { FileCheck2, Repeat2, SearchCheck } from "lucide-react";

import type { DailyBriefingReviewFocusViewModel } from "../presentation/dailyBriefing/dailyBriefingViewModel";
import { ReviewFocusDetail } from "./ReviewFocusDetail";

type ReviewFocusProps = {
  focus: DailyBriefingReviewFocusViewModel;
};

export function ReviewFocus({ focus }: ReviewFocusProps) {
  if (focus.status === "unavailable") {
    return null;
  }

  const value = focus.value;

  return (
    <section className="review-focus" aria-labelledby="review-focus-heading">
      <div className="review-focus__label">
        <SearchCheck size={17} aria-hidden="true" />
        <span id="review-focus-heading">{value.label}</span>
      </div>

      <article className="review-focus__item" aria-labelledby="review-focus-title">
        <div className="review-focus__main">
          <div className="review-focus__header">
            <span className="review-focus__icon" aria-hidden="true">
              <Repeat2 size={22} strokeWidth={2.1} />
            </span>
            <div className="review-focus__title-group">
              <h2 id="review-focus-title">{value.title}</h2>
              <span
                className="review-focus__status"
                data-category={value.statusCategory}
              >
                {value.status}
              </span>
            </div>
          </div>

          <div className="review-focus__text-group">
            <p className="review-focus__eyebrow">Observed</p>
            <p className="review-focus__copy review-focus__copy--primary">
              {value.observation}
            </p>
          </div>

          <div className="review-focus__text-group">
            <p className="review-focus__eyebrow">Why this needs review</p>
            <p className="review-focus__copy">{value.interpretation}</p>
          </div>
        </div>

        <aside className="review-focus__context" aria-label="Review context">
          <dl className="review-focus__details">
            <ReviewFocusDetail
              label="Evidence context"
              value={value.evidenceContext}
            />
            <ReviewFocusDetail
              label="Review context"
              value={value.reviewContext}
            />
          </dl>
          <div className="review-focus__note">
            <FileCheck2 size={17} aria-hidden="true" />
            <p>{value.supportingNote}</p>
          </div>
        </aside>
      </article>
    </section>
  );
}

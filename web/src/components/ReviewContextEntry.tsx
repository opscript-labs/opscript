import type { ReviewContextEntry as ReviewContextEntryData } from "../data/dailyBriefing";

type ReviewContextEntryProps = {
  entry: ReviewContextEntryData;
};

export function ReviewContextEntry({ entry }: ReviewContextEntryProps) {
  return (
    <div className="review-context-entry">
      <dt>{entry.label}</dt>
      <dd>{entry.value}</dd>
    </div>
  );
}

import type { DailyBriefingSummaryMetric } from "../data/dailyBriefing";
import { BriefingMetric } from "./BriefingMetric";

type BriefingMetricsProps = {
  metrics: DailyBriefingSummaryMetric[];
};

export function BriefingMetrics({ metrics }: BriefingMetricsProps) {
  return (
    <section className="briefing-metrics" aria-label="Latest review summary">
      <ul className="briefing-metrics__list">
        {metrics.map((metric) => (
          <BriefingMetric key={metric.id} metric={metric} />
        ))}
      </ul>
    </section>
  );
}

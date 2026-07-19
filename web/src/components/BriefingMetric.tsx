import {
  BookCheck,
  ClipboardList,
  GitCompareArrows,
  SearchCheck,
} from "lucide-react";

import type { DailyBriefingSummaryMetric } from "../data/dailyBriefing";

type BriefingMetricProps = {
  metric: DailyBriefingSummaryMetric;
};

const metricIcons = {
  bookCheck: BookCheck,
  clipboardList: ClipboardList,
  gitCompare: GitCompareArrows,
  searchCheck: SearchCheck,
} satisfies Record<DailyBriefingSummaryMetric["icon"], typeof BookCheck>;

export function BriefingMetric({ metric }: BriefingMetricProps) {
  const Icon = metricIcons[metric.icon];

  return (
    <li className="briefing-metric" data-category={metric.category}>
      <span className="briefing-metric__icon" aria-hidden="true">
        <Icon size={20} strokeWidth={2} />
      </span>
      <p className="briefing-metric__label">{metric.label}</p>
      <p className="briefing-metric__value">{metric.value}</p>
      <p className="briefing-metric__supporting">{metric.supportingText}</p>
    </li>
  );
}

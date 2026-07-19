import { GitCompareArrows, History, LibraryBig } from "lucide-react";

import type { EvidenceSummaryItem as EvidenceSummaryItemData } from "../data/dailyBriefing";

type EvidenceSummaryItemProps = {
  item: EvidenceSummaryItemData;
};

const evidenceIcons = {
  history: History,
  knowledge: LibraryBig,
  snapshot: GitCompareArrows,
} satisfies Record<EvidenceSummaryItemData["icon"], typeof History>;

export function EvidenceSummaryItem({ item }: EvidenceSummaryItemProps) {
  const Icon = evidenceIcons[item.icon];

  return (
    <li className="evidence-summary-item">
      <span className="evidence-summary-item__icon" aria-hidden="true">
        <Icon size={19} strokeWidth={2} />
      </span>
      <div className="evidence-summary-item__content">
        <h3 className="evidence-summary-item__title">{item.title}</h3>
        <p className="evidence-summary-item__copy">{item.supportingText}</p>
      </div>
    </li>
  );
}

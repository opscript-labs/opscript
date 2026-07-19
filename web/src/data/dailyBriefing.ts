export type AssessmentStatusCategory =
  | "healthy"
  | "attention"
  | "critical"
  | "unknown";

export type DailyBriefingAssessment = {
  label: string;
  status: string;
  statusCategory: AssessmentStatusCategory;
  explanation: string;
  evidenceCompleted: number;
  evidenceExpected: number;
  evidencePercentage: number;
  confidence: string;
  updatedAt: string;
  supportingNote: string;
};

export type BriefingMetricCategory = "neutral" | "accent" | "attention";

export type BriefingMetricIcon =
  | "gitCompare"
  | "searchCheck"
  | "bookCheck"
  | "clipboardList";

export type DailyBriefingSummaryMetric = {
  id: string;
  label: string;
  value: string;
  supportingText: string;
  category: BriefingMetricCategory;
  icon: BriefingMetricIcon;
};

export type DailyBriefingReviewFocus = {
  label: string;
  title: string;
  status: string;
  statusCategory: AssessmentStatusCategory;
  observation: string;
  interpretation: string;
  evidenceContext: string;
  reviewContext: string;
  supportingNote: string;
};

export type EvidenceSummaryIcon = "snapshot" | "history" | "knowledge";

export type EvidenceSummaryItem = {
  id: string;
  title: string;
  supportingText: string;
  icon: EvidenceSummaryIcon;
};

export type DailyBriefingEvidenceSummary = {
  label: string;
  title: string;
  items: EvidenceSummaryItem[];
  supportingNote: string;
};

export type DailyBriefingEngineeringBrief = {
  label: string;
  title: string;
  summary: string;
  supportingNote: string;
};

export type ReviewContextEntry = {
  label: string;
  value: string;
};

export type DailyBriefingReviewContext = {
  label: string;
  title: string;
  entries: ReviewContextEntry[];
  supportingNote: string;
};

export const dailyBriefingAssessment: DailyBriefingAssessment = {
  label: "Engineering assessment",
  status: "Stable with attention required",
  statusCategory: "attention",
  explanation:
    "Production remains operationally stable, but one recurring change pattern requires review before it becomes established engineering behavior.",
  evidenceCompleted: 18,
  evidenceExpected: 20,
  evidencePercentage: 90,
  confidence: "High confidence",
  updatedAt: "Updated 09:18 AM",
  supportingNote: "Based on the latest completed Production review.",
};

export const dailyBriefingSummaryMetrics: DailyBriefingSummaryMetric[] = [
  {
    id: "changes-observed",
    label: "Changes observed",
    value: "12",
    supportingText: "Across the latest review interval",
    category: "neutral",
    icon: "gitCompare",
  },
  {
    id: "findings-requiring-review",
    label: "Findings requiring review",
    value: "1",
    supportingText: "Engineering attention remains open",
    category: "attention",
    icon: "searchCheck",
  },
  {
    id: "knowledge-reviews-completed",
    label: "Knowledge reviews completed",
    value: "4",
    supportingText: "Derived from completed evidence",
    category: "accent",
    icon: "bookCheck",
  },
  {
    id: "operational-decisions-recorded",
    label: "Operational decisions recorded",
    value: "2",
    supportingText: "Preserved with review context",
    category: "neutral",
    icon: "clipboardList",
  },
];

export const dailyBriefingReviewFocus: DailyBriefingReviewFocus = {
  label: "Review focus",
  title: "Recurring change pattern",
  status: "Review required",
  statusCategory: "attention",
  observation:
    "The same class of configuration change appeared across three completed review intervals.",
  interpretation:
    "Repeated changes can become normalized before their operational intent is documented.",
  evidenceContext: "Observed in 3 completed review intervals",
  reviewContext: "Latest Production review",
  supportingNote: "This item remains open for engineering review.",
};

export const dailyBriefingEvidenceSummary: DailyBriefingEvidenceSummary = {
  label: "Evidence summary",
  title: "Latest completed review",
  items: [
    {
      id: "snapshot-comparison",
      title: "Snapshot comparison",
      supportingText:
        "Compared the two most recent completed infrastructure snapshots.",
      icon: "snapshot",
    },
    {
      id: "historical-review",
      title: "Historical review",
      supportingText:
        "Evaluated completed review intervals for recurring engineering patterns.",
      icon: "history",
    },
    {
      id: "knowledge-review",
      title: "Knowledge review",
      supportingText:
        "Generated engineering knowledge from validated review evidence.",
      icon: "knowledge",
    },
  ],
  supportingNote:
    "This summary reflects the evidence considered during the latest completed Production review.",
};

export const dailyBriefingEngineeringBrief: DailyBriefingEngineeringBrief = {
  label: "Engineering brief",
  title: "Current review summary",
  summary:
    "Recent infrastructure evolution remains consistent with previous completed reviews. Most observed changes align with expected operational activity, while one recurring configuration pattern continues to warrant engineering attention. No evidence currently suggests widespread operational instability, but documenting the intent behind repeated changes will improve future engineering understanding.",
  supportingNote: "This briefing summarizes the latest completed Production review.",
};

export const dailyBriefingReviewContext: DailyBriefingReviewContext = {
  label: "Review context",
  title: "Current review",
  entries: [
    {
      label: "Environment",
      value: "Production",
    },
    {
      label: "Review scope",
      value: "Completed infrastructure review",
    },
    {
      label: "Comparison basis",
      value: "Latest completed snapshot pair",
    },
    {
      label: "Generated",
      value: "Latest completed review",
    },
  ],
  supportingNote:
    "Context shown here describes the review currently presented on this page.",
};


import type {
  DailyBriefingAssessment,
  DailyBriefingEngineeringBrief,
  DailyBriefingEvidenceSummary,
  DailyBriefingReviewContext,
  DailyBriefingReviewFocus,
  DailyBriefingSummaryMetric,
} from "../../data/dailyBriefing";

export type DailyBriefingAvailableEvidenceCoveragePresentation = {
  readonly status: "available";
  readonly completed: number;
  readonly expected: number;
  readonly percentage: number;
};

export type DailyBriefingUnavailableEvidenceCoveragePresentation = {
  readonly status: "unavailable";
};

export type DailyBriefingEvidenceCoveragePresentation =
  | DailyBriefingAvailableEvidenceCoveragePresentation
  | DailyBriefingUnavailableEvidenceCoveragePresentation;

export type DailyBriefingAvailableAssessmentPresentation = {
  readonly status: "available";
  readonly value: Omit<
    DailyBriefingAssessment,
    "evidenceCompleted" | "evidenceExpected" | "evidencePercentage"
  >;
};

export type DailyBriefingUnavailableAssessmentPresentation = {
  readonly status: "unavailable";
};

export type DailyBriefingAssessmentPresentation =
  | DailyBriefingAvailableAssessmentPresentation
  | DailyBriefingUnavailableAssessmentPresentation;

export type DailyBriefingAvailableReviewFocusPresentation = {
  readonly status: "available";
  readonly value: DailyBriefingReviewFocus;
};

export type DailyBriefingUnavailableReviewFocusPresentation = {
  readonly status: "unavailable";
};

export type DailyBriefingReviewFocusPresentation =
  | DailyBriefingAvailableReviewFocusPresentation
  | DailyBriefingUnavailableReviewFocusPresentation;

export type DailyBriefingAvailableEngineeringBriefPresentation = {
  readonly status: "available";
  readonly value: DailyBriefingEngineeringBrief;
};

export type DailyBriefingUnavailableEngineeringBriefPresentation = {
  readonly status: "unavailable";
};

export type DailyBriefingEngineeringBriefPresentation =
  | DailyBriefingAvailableEngineeringBriefPresentation
  | DailyBriefingUnavailableEngineeringBriefPresentation;

export type DailyBriefingPresentationSource = {
  assessment: DailyBriefingAssessmentPresentation;
  evidenceCoverage: DailyBriefingEvidenceCoveragePresentation;
  metrics: DailyBriefingSummaryMetric[];
  reviewFocus: DailyBriefingReviewFocusPresentation;
  evidenceSummary: DailyBriefingEvidenceSummary;
  engineeringBrief: DailyBriefingEngineeringBriefPresentation;
  reviewContext: DailyBriefingReviewContext;
};

export type DailyBriefingAvailablePresentationSource =
  DailyBriefingPresentationSource & {
    readonly assessment: DailyBriefingAvailableAssessmentPresentation;
    readonly reviewFocus: DailyBriefingAvailableReviewFocusPresentation;
    readonly engineeringBrief: DailyBriefingAvailableEngineeringBriefPresentation;
  };

export type DailyBriefingFixturePresentationSource =
  DailyBriefingAvailablePresentationSource & {
    readonly evidenceCoverage: DailyBriefingAvailableEvidenceCoveragePresentation;
    readonly assessment: DailyBriefingAvailableAssessmentPresentation & {
      readonly value: DailyBriefingAvailableAssessmentPresentation["value"];
    };
  };

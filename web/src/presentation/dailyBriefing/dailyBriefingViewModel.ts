import type {
  AssessmentStatusCategory,
  DailyBriefingEngineeringBrief,
  DailyBriefingEvidenceSummary,
  DailyBriefingReviewContext,
  DailyBriefingReviewFocus,
  DailyBriefingSummaryMetric,
} from "../../data/dailyBriefing";

export type DailyBriefingAssessmentViewModel =
  | {
      readonly status: "available";
      readonly label: string;
      readonly assessmentStatus: string;
      readonly statusCategory: AssessmentStatusCategory;
      readonly explanation: string;
      readonly confidence: string;
      readonly updatedAt: string;
      readonly supportingNote: string;
    }
  | {
      readonly status: "unavailable";
      readonly label: string;
      readonly message: string;
    };

export type DailyBriefingEvidenceCoverageViewModel =
  | {
      readonly status: "available";
      readonly completed: number;
      readonly expected: number;
      readonly percentage: number;
    }
  | {
      readonly status: "unavailable";
      readonly message: string;
    };

export type DailyBriefingReviewFocusViewModel =
  | {
      readonly status: "available";
      readonly value: DailyBriefingReviewFocus;
    }
  | {
      readonly status: "unavailable";
    };

export type DailyBriefingEngineeringBriefViewModel =
  | {
      readonly status: "available";
      readonly value: DailyBriefingEngineeringBrief;
    }
  | {
      readonly status: "unavailable";
      readonly label: string;
      readonly title: string;
      readonly message: string;
    };

export type DailyBriefingViewModel = {
  assessment: DailyBriefingAssessmentViewModel;
  evidenceCoverage: DailyBriefingEvidenceCoverageViewModel;
  metrics: DailyBriefingSummaryMetric[];
  reviewFocus: DailyBriefingReviewFocusViewModel;
  evidenceSummary: DailyBriefingEvidenceSummary;
  engineeringBrief: DailyBriefingEngineeringBriefViewModel;
  reviewContext: DailyBriefingReviewContext;
};

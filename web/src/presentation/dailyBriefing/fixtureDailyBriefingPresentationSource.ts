import {
  dailyBriefingAssessment,
  dailyBriefingEngineeringBrief,
  dailyBriefingEvidenceSummary,
  dailyBriefingReviewContext,
  dailyBriefingReviewFocus,
  dailyBriefingSummaryMetrics,
} from "../../data/dailyBriefing";
import type { DailyBriefingFixturePresentationSource } from "./dailyBriefingPresentationSource";

export const fixtureDailyBriefingPresentationSource: DailyBriefingFixturePresentationSource =
  {
    assessment: {
      status: "available",
      value: {
        label: dailyBriefingAssessment.label,
        status: dailyBriefingAssessment.status,
        statusCategory: dailyBriefingAssessment.statusCategory,
        explanation: dailyBriefingAssessment.explanation,
        confidence: dailyBriefingAssessment.confidence,
        updatedAt: dailyBriefingAssessment.updatedAt,
        supportingNote: dailyBriefingAssessment.supportingNote,
      },
    },
    evidenceCoverage: {
      status: "available",
      completed: dailyBriefingAssessment.evidenceCompleted,
      expected: dailyBriefingAssessment.evidenceExpected,
      percentage: dailyBriefingAssessment.evidencePercentage,
    },
    metrics: dailyBriefingSummaryMetrics,
    reviewFocus: {
      status: "available",
      value: dailyBriefingReviewFocus,
    },
    evidenceSummary: dailyBriefingEvidenceSummary,
    engineeringBrief: {
      status: "available",
      value: dailyBriefingEngineeringBrief,
    },
    reviewContext: dailyBriefingReviewContext,
  };

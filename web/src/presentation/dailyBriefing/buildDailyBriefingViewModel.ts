import type { DailyBriefingPresentationSource } from "./dailyBriefingPresentationSource";
import type {
  DailyBriefingAssessmentViewModel,
  DailyBriefingEngineeringBriefViewModel,
  DailyBriefingEvidenceCoverageViewModel,
  DailyBriefingReviewFocusViewModel,
  DailyBriefingViewModel,
} from "./dailyBriefingViewModel";

export const ASSESSMENT_UNAVAILABLE_MESSAGE =
  "Assessment is unavailable for this briefing.";
export const EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE =
  "Evidence coverage is unavailable for this briefing.";
export const ENGINEERING_BRIEF_UNAVAILABLE_MESSAGE =
  "Engineering brief is unavailable for this briefing.";

export function buildDailyBriefingViewModel(
  source: DailyBriefingPresentationSource,
): DailyBriefingViewModel {
  return {
    assessment: buildAssessment(source),
    evidenceCoverage: buildEvidenceCoverage(source),
    metrics: source.metrics,
    reviewFocus: buildReviewFocus(source),
    evidenceSummary: source.evidenceSummary,
    engineeringBrief: buildEngineeringBrief(source),
    reviewContext: source.reviewContext,
  };
}

function buildAssessment(
  source: DailyBriefingPresentationSource,
): DailyBriefingAssessmentViewModel {
  if (source.assessment.status === "unavailable") {
    return {
      status: "unavailable",
      label: "Engineering assessment",
      message: ASSESSMENT_UNAVAILABLE_MESSAGE,
    };
  }

  return {
    status: "available",
    label: source.assessment.value.label,
    assessmentStatus: source.assessment.value.status,
    statusCategory: source.assessment.value.statusCategory,
    explanation: source.assessment.value.explanation,
    confidence: source.assessment.value.confidence,
    updatedAt: source.assessment.value.updatedAt,
    supportingNote: source.assessment.value.supportingNote,
  };
}

function buildEvidenceCoverage(
  source: DailyBriefingPresentationSource,
): DailyBriefingEvidenceCoverageViewModel {
  if (source.evidenceCoverage.status === "unavailable") {
    return {
      status: "unavailable",
      message: EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE,
    };
  }

  return {
    status: "available",
    completed: source.evidenceCoverage.completed,
    expected: source.evidenceCoverage.expected,
    percentage: source.evidenceCoverage.percentage,
  };
}

function buildReviewFocus(
  source: DailyBriefingPresentationSource,
): DailyBriefingReviewFocusViewModel {
  if (source.reviewFocus.status === "unavailable") {
    return {
      status: "unavailable",
    };
  }

  return {
    status: "available",
    value: source.reviewFocus.value,
  };
}

function buildEngineeringBrief(
  source: DailyBriefingPresentationSource,
): DailyBriefingEngineeringBriefViewModel {
  if (source.engineeringBrief.status === "unavailable") {
    return {
      status: "unavailable",
      label: "Engineering brief",
      title: "Current review summary",
      message: ENGINEERING_BRIEF_UNAVAILABLE_MESSAGE,
    };
  }

  return {
    status: "available",
    value: source.engineeringBrief.value,
  };
}

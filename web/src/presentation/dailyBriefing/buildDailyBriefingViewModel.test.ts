import { describe, expect, it } from "vitest";

import {
  type DailyBriefingAssessment,
  type DailyBriefingSummaryMetric,
} from "../../data/dailyBriefing";
import {
  ASSESSMENT_UNAVAILABLE_MESSAGE,
  EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE,
  ENGINEERING_BRIEF_UNAVAILABLE_MESSAGE,
  buildDailyBriefingViewModel,
} from "./buildDailyBriefingViewModel";
import { fixtureDailyBriefingPresentationSource } from "./fixtureDailyBriefingPresentationSource";
import type { DailyBriefingPresentationSource } from "./dailyBriefingPresentationSource";

const distinctAssessment: DailyBriefingAssessment = {
  label: "Engineering assessment",
  status: "Distinct source assessment",
  statusCategory: "healthy",
  explanation: "Distinct source explanation.",
  evidenceCompleted: 1,
  evidenceExpected: 1,
  evidencePercentage: 100,
  confidence: "Distinct confidence",
  updatedAt: "Updated 12:00 PM",
  supportingNote: "Distinct supporting note.",
};

const distinctMetric: DailyBriefingSummaryMetric = {
  id: "distinct-metric",
  label: "Distinct metric",
  value: "99",
  supportingText: "Distinct source metric value",
  category: "neutral",
  icon: "clipboardList",
};

describe("buildDailyBriefingViewModel", () => {
  it("exposes all required sections from the fixture presentation source", () => {
    expect(fixtureDailyBriefingPresentationSource.assessment).toBeDefined();
    expect(fixtureDailyBriefingPresentationSource.metrics).toHaveLength(4);
    expect(fixtureDailyBriefingPresentationSource.reviewFocus).toBeDefined();
    expect(
      fixtureDailyBriefingPresentationSource.evidenceSummary,
    ).toBeDefined();
    expect(
      fixtureDailyBriefingPresentationSource.engineeringBrief,
    ).toBeDefined();
    expect(fixtureDailyBriefingPresentationSource.reviewContext).toBeDefined();
  });

  it("returns the complete Daily Briefing view model", () => {
    const viewModel = buildDailyBriefingViewModel(
      fixtureDailyBriefingPresentationSource,
    );

    expect(viewModel.assessment).toBeDefined();
    expect(viewModel.metrics).toHaveLength(4);
    expect(viewModel.reviewFocus).toBeDefined();
    expect(viewModel.evidenceSummary).toBeDefined();
    expect(viewModel.engineeringBrief).toBeDefined();
    expect(viewModel.reviewContext).toBeDefined();
  });

  it("preserves values supplied by the fixture source", () => {
    const viewModel = buildDailyBriefingViewModel(
      fixtureDailyBriefingPresentationSource,
    );

    expect(viewModel.assessment.status).toBe("available");
    if (viewModel.assessment.status !== "available") {
      throw new Error("Expected assessment to be available.");
    }
    expect(viewModel.assessment.assessmentStatus).toBe(
      "Stable with attention required",
    );
    expect(viewModel.evidenceCoverage).toEqual({
      status: "available",
      completed: 18,
      expected: 20,
      percentage: 90,
    });
    expect(viewModel.metrics.map((metric) => metric.label)).toEqual([
      "Changes observed",
      "Findings requiring review",
      "Knowledge reviews completed",
      "Operational decisions recorded",
    ]);
    expect(viewModel.reviewFocus.status).toBe("available");
    if (viewModel.reviewFocus.status !== "available") {
      throw new Error("Expected review focus to be available.");
    }
    expect(viewModel.reviewFocus.value.title).toBe("Recurring change pattern");
    expect(viewModel.evidenceSummary.title).toBe("Latest completed review");
    expect(viewModel.engineeringBrief.status).toBe("available");
    if (viewModel.engineeringBrief.status !== "available") {
      throw new Error("Expected engineering brief to be available.");
    }
    expect(viewModel.engineeringBrief.value.title).toBe(
      "Current review summary",
    );
    expect(viewModel.reviewContext.title).toBe("Current review");
  });

  it("builds the view model from an explicit source", () => {
    const distinctSource: DailyBriefingPresentationSource = {
      ...fixtureDailyBriefingPresentationSource,
      assessment: {
        status: "available",
        value: {
          label: distinctAssessment.label,
          status: distinctAssessment.status,
          statusCategory: distinctAssessment.statusCategory,
          explanation: distinctAssessment.explanation,
          confidence: distinctAssessment.confidence,
          updatedAt: distinctAssessment.updatedAt,
          supportingNote: distinctAssessment.supportingNote,
        },
      },
      evidenceCoverage: {
        status: "available",
        completed: distinctAssessment.evidenceCompleted,
        expected: distinctAssessment.evidenceExpected,
        percentage: distinctAssessment.evidencePercentage,
      },
      metrics: [distinctMetric],
    };

    const viewModel = buildDailyBriefingViewModel({
      ...distinctSource,
    });

    expect(viewModel.assessment.status).toBe("available");
    if (viewModel.assessment.status !== "available") {
      throw new Error("Expected assessment to be available.");
    }
    expect(viewModel.assessment.assessmentStatus).toBe(
      "Distinct source assessment",
    );
    expect(viewModel.assessment.confidence).toBe("Distinct confidence");
    expect(viewModel.evidenceCoverage).toEqual({
      status: "available",
      completed: 1,
      expected: 1,
      percentage: 100,
    });
    expect(viewModel.metrics).toHaveLength(1);
    expect(viewModel.metrics[0].value).toBe("99");
  });

  it("represents unavailable projection-derived sections explicitly", () => {
    const source: DailyBriefingPresentationSource = {
      ...fixtureDailyBriefingPresentationSource,
      assessment: { status: "unavailable" },
      evidenceCoverage: { status: "unavailable" },
      reviewFocus: { status: "unavailable" },
      engineeringBrief: { status: "unavailable" },
    };

    const viewModel = buildDailyBriefingViewModel(source);

    expect(viewModel.assessment).toEqual({
      status: "unavailable",
      label: "Engineering assessment",
      message: ASSESSMENT_UNAVAILABLE_MESSAGE,
    });
    expect(viewModel.evidenceCoverage).toEqual({
      status: "unavailable",
      message: EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE,
    });
    expect(viewModel.reviewFocus).toEqual({ status: "unavailable" });
    expect(viewModel.engineeringBrief).toEqual({
      status: "unavailable",
      label: "Engineering brief",
      title: "Current review summary",
      message: ENGINEERING_BRIEF_UNAVAILABLE_MESSAGE,
    });
  });

  it("does not omit any rendered Daily Briefing section", () => {
    const viewModel = buildDailyBriefingViewModel(
      fixtureDailyBriefingPresentationSource,
    );

    expect(Object.keys(viewModel).sort()).toEqual([
      "assessment",
      "engineeringBrief",
      "evidenceCoverage",
      "evidenceSummary",
      "metrics",
      "reviewContext",
      "reviewFocus",
    ]);
  });
});

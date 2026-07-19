import { describe, expect, it } from "vitest";

import { buildDailyBriefingViewModel } from "./buildDailyBriefingViewModel";
import type {
  DailyBriefingAssessmentPresentation,
  DailyBriefingAvailableAssessmentPresentation,
  DailyBriefingAvailableEngineeringBriefPresentation,
  DailyBriefingAvailableEvidenceCoveragePresentation,
  DailyBriefingAvailableReviewFocusPresentation,
  DailyBriefingEngineeringBriefPresentation,
  DailyBriefingEvidenceCoveragePresentation,
  DailyBriefingPresentationSource,
  DailyBriefingReviewFocusPresentation,
} from "./dailyBriefingPresentationSource";
import { fixtureDailyBriefingPresentationSource } from "./fixtureDailyBriefingPresentationSource";

describe("Daily Briefing presentation source availability", () => {
  it("supports available and unavailable assessment states", () => {
    const available = fixtureDailyBriefingPresentationSource.assessment satisfies DailyBriefingAvailableAssessmentPresentation;
    const unavailable = {
      status: "unavailable",
    } satisfies DailyBriefingAssessmentPresentation;

    expect(available.status).toBe("available");
    expect(available.value.status).toBe("Stable with attention required");
    expect(unavailable).toEqual({ status: "unavailable" });
    expect(unavailable).not.toHaveProperty("value");
    expect(unavailable).not.toHaveProperty("explanation");
    expect(unavailable).not.toHaveProperty("confidence");
  });

  it("supports available and unavailable review focus states", () => {
    const available = fixtureDailyBriefingPresentationSource.reviewFocus satisfies DailyBriefingAvailableReviewFocusPresentation;
    const unavailable = {
      status: "unavailable",
    } satisfies DailyBriefingReviewFocusPresentation;

    expect(available.status).toBe("available");
    expect(available.value.title).toBe("Recurring change pattern");
    expect(unavailable).toEqual({ status: "unavailable" });
    expect(unavailable).not.toHaveProperty("value");
    expect(unavailable).not.toHaveProperty("title");
    expect(unavailable).not.toHaveProperty("interpretation");
  });

  it("supports available and unavailable engineering brief states", () => {
    const available = fixtureDailyBriefingPresentationSource.engineeringBrief satisfies DailyBriefingAvailableEngineeringBriefPresentation;
    const unavailable = {
      status: "unavailable",
    } satisfies DailyBriefingEngineeringBriefPresentation;

    expect(available.status).toBe("available");
    expect(available.value.summary).toContain("Recent infrastructure evolution");
    expect(unavailable).toEqual({ status: "unavailable" });
    expect(unavailable).not.toHaveProperty("value");
    expect(unavailable).not.toHaveProperty("summary");
    expect(unavailable).not.toHaveProperty("supportingNote");
  });

  it("supports available and unavailable evidence coverage states", () => {
    const available = fixtureDailyBriefingPresentationSource.evidenceCoverage satisfies DailyBriefingAvailableEvidenceCoveragePresentation;
    const unavailable = {
      status: "unavailable",
    } satisfies DailyBriefingEvidenceCoveragePresentation;

    expect(available).toEqual({
      status: "available",
      completed: 18,
      expected: 20,
      percentage: 90,
    });
    expect(unavailable).toEqual({ status: "unavailable" });
    expect(unavailable).not.toHaveProperty("completed");
    expect(unavailable).not.toHaveProperty("expected");
    expect(unavailable).not.toHaveProperty("percentage");
  });

  it("allows factual zero only in available evidence coverage", () => {
    const coverage = {
      status: "available",
      completed: 0,
      expected: 0,
      percentage: 0,
    } satisfies DailyBriefingEvidenceCoveragePresentation;

    expect(coverage).toEqual({
      status: "available",
      completed: 0,
      expected: 0,
      percentage: 0,
    });
  });

  it("preserves the fixture authored values", () => {
    const fixture = fixtureDailyBriefingPresentationSource;

    expect(fixture.assessment.status).toBe("available");
    expect(fixture.assessment.value.status).toBe(
      "Stable with attention required",
    );
    expect(fixture.evidenceCoverage.status).toBe("available");
    expect(fixture.evidenceCoverage.completed).toBe(18);
    expect(fixture.evidenceCoverage.expected).toBe(20);
    expect(fixture.evidenceCoverage.percentage).toBe(90);
    expect(fixture.reviewFocus.status).toBe("available");
    expect(fixture.reviewFocus.value.title).toBe("Recurring change pattern");
    expect(fixture.engineeringBrief.status).toBe("available");
    expect(fixture.engineeringBrief.value.title).toBe("Current review summary");
    expect(fixture.metrics.map(({ label }) => label)).toEqual([
      "Changes observed",
      "Findings requiring review",
      "Knowledge reviews completed",
      "Operational decisions recorded",
    ]);
  });

  it("does not nest evidence coverage inside assessment content", () => {
    expect(fixtureDailyBriefingPresentationSource.assessment.value).not.toHaveProperty(
      "evidenceCoverage",
    );
    expect(fixtureDailyBriefingPresentationSource).toHaveProperty(
      "evidenceCoverage",
    );
  });

  it.each([
    ["available assessment and available coverage", "available", "available"],
    ["available assessment and unavailable coverage", "available", "unavailable"],
    ["unavailable assessment and available coverage", "unavailable", "available"],
    ["unavailable assessment and unavailable coverage", "unavailable", "unavailable"],
  ] as const)(
    "supports %s",
    (_name, assessmentStatus, evidenceCoverageStatus) => {
      const source = {
        ...fixtureDailyBriefingPresentationSource,
        assessment:
          assessmentStatus === "available"
            ? fixtureDailyBriefingPresentationSource.assessment
            : {
                status: "unavailable",
              },
        evidenceCoverage:
          evidenceCoverageStatus === "available"
            ? fixtureDailyBriefingPresentationSource.evidenceCoverage
            : {
                status: "unavailable",
              },
      } satisfies DailyBriefingPresentationSource;

      expect(source.assessment.status).toBe(assessmentStatus);
      expect(source.evidenceCoverage.status).toBe(evidenceCoverageStatus);
    },
  );

  it("supports independent availability for assessment and evidence coverage", () => {
    const source = {
      ...fixtureDailyBriefingPresentationSource,
      assessment: {
        status: "available",
        value: {
          ...fixtureDailyBriefingPresentationSource.assessment.value,
        },
      },
      evidenceCoverage: {
        status: "unavailable",
      },
    } satisfies DailyBriefingPresentationSource;

    expect(source.assessment.status).toBe("available");
    expect(source.evidenceCoverage.status).toBe("unavailable");
  });

  it("keeps the existing view-model builder compatible with the fixture", () => {
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
    expect(viewModel.reviewFocus.status).toBe("available");
    if (viewModel.reviewFocus.status !== "available") {
      throw new Error("Expected review focus to be available.");
    }
    expect(viewModel.reviewFocus.value.title).toBe("Recurring change pattern");
    expect(viewModel.engineeringBrief.status).toBe("available");
    if (viewModel.engineeringBrief.status !== "available") {
      throw new Error("Expected engineering brief to be available.");
    }
    expect(viewModel.engineeringBrief.value.title).toBe(
      "Current review summary",
    );
  });
});

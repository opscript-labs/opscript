import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  ASSESSMENT_UNAVAILABLE_MESSAGE,
  EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE,
  ENGINEERING_BRIEF_UNAVAILABLE_MESSAGE,
  buildDailyBriefingViewModel,
} from "../presentation/dailyBriefing/buildDailyBriefingViewModel";
import { fixtureDailyBriefingPresentationSource } from "../presentation/dailyBriefing/fixtureDailyBriefingPresentationSource";
import { AssessmentHero } from "./AssessmentHero";
import { EngineeringBrief } from "./EngineeringBrief";
import { ReviewFocus } from "./ReviewFocus";

const availableBriefing = buildDailyBriefingViewModel(
  fixtureDailyBriefingPresentationSource,
);

describe("Daily Briefing availability presentation", () => {
  it("renders available assessment and evidence coverage", () => {
    render(
      <AssessmentHero
        assessment={availableBriefing.assessment}
        evidenceCoverage={availableBriefing.evidenceCoverage}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Stable with attention required" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Attention required")).toBeInTheDocument();
    expect(screen.getByText("Updated 09:18 AM")).toBeInTheDocument();
    expect(screen.getByText("18 of 20")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByLabelText("Evidence coverage")).toHaveValue(90);
    expect(screen.getByText("High confidence")).toBeInTheDocument();
  });

  it("renders unavailable assessment and unavailable coverage without stale details", () => {
    render(
      <AssessmentHero
        assessment={{
          status: "unavailable",
          label: "Engineering assessment",
          message: ASSESSMENT_UNAVAILABLE_MESSAGE,
        }}
        evidenceCoverage={{
          status: "unavailable",
          message: EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE,
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: ASSESSMENT_UNAVAILABLE_MESSAGE }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE),
    ).toBeInTheDocument();
    expect(screen.queryByText("Attention required")).not.toBeInTheDocument();
    expect(screen.queryByText("Updated 09:18 AM")).not.toBeInTheDocument();
    expect(screen.queryByText("High confidence")).not.toBeInTheDocument();
    expect(screen.queryByText("18 of 20")).not.toBeInTheDocument();
    expect(screen.queryByText("90%")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Evidence coverage")).not.toBeInTheDocument();
  });

  it("keeps assessment and evidence coverage availability independent", () => {
    const { rerender } = render(
      <AssessmentHero
        assessment={availableBriefing.assessment}
        evidenceCoverage={{
          status: "unavailable",
          message: EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE,
        }}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "Stable with attention required" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(EVIDENCE_COVERAGE_UNAVAILABLE_MESSAGE),
    ).toBeInTheDocument();
    expect(screen.queryByLabelText("Evidence coverage")).not.toBeInTheDocument();

    rerender(
      <AssessmentHero
        assessment={{
          status: "unavailable",
          label: "Engineering assessment",
          message: ASSESSMENT_UNAVAILABLE_MESSAGE,
        }}
        evidenceCoverage={availableBriefing.evidenceCoverage}
      />,
    );

    expect(
      screen.getByRole("heading", { name: ASSESSMENT_UNAVAILABLE_MESSAGE }),
    ).toBeInTheDocument();
    expect(screen.getByText("18 of 20")).toBeInTheDocument();
    expect(screen.getByLabelText("Evidence coverage")).toHaveValue(90);
  });

  it("renders review focus only when available", () => {
    const { container, rerender } = render(
      <ReviewFocus focus={availableBriefing.reviewFocus} />,
    );

    expect(
      screen.getByRole("region", { name: "Review focus" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Recurring change pattern" }),
    ).toBeInTheDocument();

    rerender(<ReviewFocus focus={{ status: "unavailable" }} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("renders engineering brief availability states", () => {
    const { rerender } = render(
      <EngineeringBrief brief={availableBriefing.engineeringBrief} />,
    );

    const availableSection = screen.getByRole("region", {
      name: "Current review summary",
    });

    expect(
      within(availableSection).getByText(
        "This briefing summarizes the latest completed Production review.",
      ),
    ).toBeInTheDocument();

    rerender(
      <EngineeringBrief
        brief={{
          status: "unavailable",
          label: "Engineering brief",
          title: "Current review summary",
          message: ENGINEERING_BRIEF_UNAVAILABLE_MESSAGE,
        }}
      />,
    );

    const unavailableSection = screen.getByRole("region", {
      name: "Current review summary",
    });

    expect(
      within(unavailableSection).getByText(
        ENGINEERING_BRIEF_UNAVAILABLE_MESSAGE,
      ),
    ).toBeInTheDocument();
    expect(
      within(unavailableSection).queryByText(
        "This briefing summarizes the latest completed Production review.",
      ),
    ).not.toBeInTheDocument();
  });
});

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DailyBriefingRuntime } from "./DailyBriefingRuntime";

describe("DailyBriefingRuntime", () => {
  it("renders bundled fixture data without environment configuration", () => {
    render(<DailyBriefingRuntime />);

    expect(
      screen.getByRole("heading", { name: "Stable with attention required" }),
    ).toBeInTheDocument();
    expect(screen.getByText("18 of 20")).toBeInTheDocument();
    expect(screen.getByText("Changes observed")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps stable success layout available for fixture composition", () => {
    render(<DailyBriefingRuntime />);

    const rail = screen.getByRole("complementary", {
      name: "Daily Briefing context",
    });

    expect(within(rail).getByText("Current review")).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Latest review summary" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("region", { name: "Review focus" }),
    ).toBeInTheDocument();
  });
});

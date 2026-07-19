import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("Opscript app shell", () => {
  it("renders the Opscript wordmark", () => {
    render(<App />);

    const sidebar = screen.getByRole("complementary", { name: "Opscript" });
    expect(within(sidebar).getByText("Opscript")).toBeInTheDocument();
  });

  it("represents Daily Briefing as the selected navigation item", () => {
    render(<App />);

    const selectedItem = screen.getByRole("button", { name: "Daily Briefing" });
    expect(selectedItem).toHaveAttribute("aria-current", "page");
  });

  it("renders the Changes and Findings badges", () => {
    render(<App />);

    expect(
      screen.getByRole("button", { name: "Changes, 3 updates" }),
    ).toHaveTextContent("3");
    expect(
      screen.getByRole("button", { name: "Findings, 1 update" }),
    ).toHaveTextContent("1");
  });

  it("renders the Production environment summary", () => {
    render(<App />);

    const environmentSummary = screen.getByLabelText("Environment summary");
    expect(environmentSummary).toHaveTextContent("Production");
    expect(screen.getByText("Last reviewed 09:18 AM")).toBeInTheDocument();
    expect(screen.getByText("Next review tomorrow")).toBeInTheDocument();
  });

  it("renders neutral top bar workspace identity", () => {
    render(<App />);

    const userMenu = screen.getByRole("button", { name: "User menu" });
    expect(within(userMenu).getByText("Opscript")).toBeInTheDocument();
    expect(within(userMenu).getByText("Workspace")).toBeInTheDocument();
  });

  it("renders the page greeting", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: "Daily Briefing" }),
    ).toBeInTheDocument();
  });

  it("exposes stable page landmarks", () => {
    const { container } = render(<App />);

    expect(container.querySelectorAll("main")).toHaveLength(1);
    expect(
      screen.getByRole("navigation", { name: "Primary navigation" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("complementary", { name: "Daily Briefing context" }),
    ).toBeInTheDocument();
  });

  it("resolves all Daily Briefing aria-labelledby references uniquely", () => {
    const { container } = render(<App />);
    const labelledElements = container.querySelectorAll("[aria-labelledby]");

    expect(labelledElements.length).toBeGreaterThan(0);

    labelledElements.forEach((element) => {
      const ids = element.getAttribute("aria-labelledby")?.split(/\s+/) ?? [];

      ids.forEach((id) => {
        expect(container.querySelectorAll(`#${id}`)).toHaveLength(1);
      });
    });
  });

  it("keeps the rendered Daily Briefing heading hierarchy ordered", () => {
    const { container } = render(<App />);
    const main = container.querySelector("main");
    const headingLevels = Array.from(
      main?.querySelectorAll("h1, h2, h3, h4, h5, h6") ?? [],
    ).map((heading) => Number(heading.tagName.slice(1)));

    expect(headingLevels).toEqual([1, 2, 2, 2, 3, 3, 3, 2, 2]);

    headingLevels.slice(1).forEach((level, index) => {
      expect(level).toBeLessThanOrEqual(headingLevels[index] + 1);
    });
  });

  it("keeps Daily Briefing content noninteractive", () => {
    const { container } = render(<App />);
    const main = container.querySelector("main");

    expect(main).not.toBeNull();
    expect(within(main as HTMLElement).queryByRole("button")).not.toBeInTheDocument();
    expect(within(main as HTMLElement).queryByRole("link")).not.toBeInTheDocument();
  });

  it("gives icon controls accessible names", () => {
    render(<App />);

    expect(
      screen.getByRole("group", { name: "Utility controls" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Appearance settings" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument();
  });

  it("renders all eight primary navigation buttons", () => {
    render(<App />);

    const labels = [
      "Daily Briefing",
      "Changes, 3 updates",
      "Findings, 1 update",
      "Evidence",
      "History",
      "Reports",
      "Environments",
      "Settings",
    ];

    for (const label of labels) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("renders the Daily Briefing assessment hero", () => {
    render(<App />);

    expect(screen.getByText("Engineering assessment")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Stable with attention required" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Attention required")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Production remains operationally stable, but one recurring change pattern requires review before it becomes established engineering behavior.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("18 of 20")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByLabelText("Evidence coverage")).toHaveValue(90);
    expect(screen.getByText("High confidence")).toBeInTheDocument();
    expect(screen.getByText("Updated 09:18 AM")).toBeInTheDocument();
    expect(
      screen.getByText("Based on the latest completed Production review."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        "Daily Briefing content will be implemented in the next slice.",
      ),
    ).not.toBeInTheDocument();
  });

  it("renders the latest review summary metrics in fixture order", () => {
    render(<App />);

    const summary = screen.getByRole("region", {
      name: "Latest review summary",
    });
    const metricItems = within(summary).getAllByRole("listitem");

    expect(metricItems).toHaveLength(4);

    const expectedMetrics = [
      {
        label: "Changes observed",
        value: "12",
        supportingText: "Across the latest review interval",
      },
      {
        label: "Findings requiring review",
        value: "1",
        supportingText: "Engineering attention remains open",
      },
      {
        label: "Knowledge reviews completed",
        value: "4",
        supportingText: "Derived from completed evidence",
      },
      {
        label: "Operational decisions recorded",
        value: "2",
        supportingText: "Preserved with review context",
      },
    ];

    expectedMetrics.forEach((metric, index) => {
      const item = within(metricItems[index]);

      expect(item.getByText(metric.label)).toBeInTheDocument();
      expect(item.getByText(metric.value)).toBeInTheDocument();
      expect(item.getByText(metric.supportingText)).toBeInTheDocument();
    });

    expect(within(summary).queryByRole("link")).not.toBeInTheDocument();
    expect(within(summary).queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders the Daily Briefing review focus section", () => {
    render(<App />);

    const reviewFocus = screen.getByRole("region", { name: "Review focus" });

    expect(
      within(reviewFocus).getByRole("heading", {
        name: "Recurring change pattern",
      }),
    ).toBeInTheDocument();
    expect(within(reviewFocus).getByText("Review required")).toBeInTheDocument();
    expect(
      within(reviewFocus).getByText(
        "The same class of configuration change appeared across three completed review intervals.",
      ),
    ).toBeInTheDocument();
    expect(
      within(reviewFocus).getByText("Why this needs review"),
    ).toBeInTheDocument();
    expect(
      within(reviewFocus).getByText(
        "Repeated changes can become normalized before their operational intent is documented.",
      ),
    ).toBeInTheDocument();
    expect(
      within(reviewFocus).getByText("Observed in 3 completed review intervals"),
    ).toBeInTheDocument();
    expect(
      within(reviewFocus).getByText("Latest Production review"),
    ).toBeInTheDocument();
    expect(
      within(reviewFocus).getByText(
        "This item remains open for engineering review.",
      ),
    ).toBeInTheDocument();
    expect(within(reviewFocus).queryByRole("button")).not.toBeInTheDocument();
    expect(within(reviewFocus).queryByRole("link")).not.toBeInTheDocument();
    expect(within(reviewFocus).getAllByRole("article")).toHaveLength(1);
  });

  it("renders the Daily Briefing evidence summary", () => {
    render(<App />);

    const evidenceSummary = screen.getByRole("region", {
      name: "Latest completed review",
    });
    const evidenceItems = within(evidenceSummary).getAllByRole("listitem");

    expect(screen.getByText("Evidence summary")).toBeInTheDocument();
    expect(
      within(evidenceSummary).getByRole("heading", {
        name: "Latest completed review",
      }),
    ).toBeInTheDocument();
    expect(evidenceItems).toHaveLength(3);

    const expectedEvidence = [
      {
        title: "Snapshot comparison",
        copy: "Compared the two most recent completed infrastructure snapshots.",
      },
      {
        title: "Historical review",
        copy: "Evaluated completed review intervals for recurring engineering patterns.",
      },
      {
        title: "Knowledge review",
        copy: "Generated engineering knowledge from validated review evidence.",
      },
    ];

    expectedEvidence.forEach((item, index) => {
      const evidenceItem = within(evidenceItems[index]);

      expect(evidenceItem.getByText(item.title)).toBeInTheDocument();
      expect(evidenceItem.getByText(item.copy)).toBeInTheDocument();
    });

    expect(
      within(evidenceSummary).getByText(
        "This summary reflects the evidence considered during the latest completed Production review.",
      ),
    ).toBeInTheDocument();
    expect(within(evidenceSummary).queryByRole("button")).not.toBeInTheDocument();
    expect(within(evidenceSummary).queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders the Daily Briefing engineering brief", () => {
    render(<App />);

    const engineeringBrief = screen.getByRole("region", {
      name: "Current review summary",
    });

    expect(screen.getByText("Engineering brief")).toBeInTheDocument();
    expect(
      within(engineeringBrief).getByRole("heading", {
        name: "Current review summary",
      }),
    ).toBeInTheDocument();
    expect(
      within(engineeringBrief).getByText(
        "Recent infrastructure evolution remains consistent with previous completed reviews. Most observed changes align with expected operational activity, while one recurring configuration pattern continues to warrant engineering attention. No evidence currently suggests widespread operational instability, but documenting the intent behind repeated changes will improve future engineering understanding.",
      ),
    ).toBeInTheDocument();
    expect(
      within(engineeringBrief).getByText(
        "This briefing summarizes the latest completed Production review.",
      ),
    ).toBeInTheDocument();
    expect(within(engineeringBrief).queryByRole("button")).not.toBeInTheDocument();
    expect(within(engineeringBrief).queryByRole("link")).not.toBeInTheDocument();
  });

  it("renders the Daily Briefing review context rail", () => {
    render(<App />);

    const reviewContext = screen.getByRole("region", {
      name: "Current review",
    });

    expect(screen.getAllByText("Review context").length).toBeGreaterThanOrEqual(
      1,
    );
    expect(
      within(reviewContext).getByRole("heading", { name: "Current review" }),
    ).toBeInTheDocument();
    expect(within(reviewContext).getByText("Production")).toBeInTheDocument();
    expect(
      within(reviewContext).getByText("Completed infrastructure review"),
    ).toBeInTheDocument();
    expect(
      within(reviewContext).getByText("Latest completed snapshot pair"),
    ).toBeInTheDocument();
    expect(
      within(reviewContext).getByText("Latest completed review"),
    ).toBeInTheDocument();
    expect(
      within(reviewContext).getByText(
        "Context shown here describes the review currently presented on this page.",
      ),
    ).toBeInTheDocument();
    expect(within(reviewContext).queryByRole("button")).not.toBeInTheDocument();
    expect(within(reviewContext).queryByRole("link")).not.toBeInTheDocument();
  });
});

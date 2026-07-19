import { DailyBriefingRuntime } from "./DailyBriefingRuntime";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell() {
  return (
    <div className="app-shell">
      <Sidebar />
      <TopBar />
      <main className="app-main" aria-labelledby="daily-briefing-title">
        <section className="briefing-placeholder">
          <h1 id="daily-briefing-title">Daily Briefing</h1>
          <p className="briefing-placeholder__subtitle">
            Here is your engineering briefing for{" "}
            <span className="accent-text">Production</span>.
          </p>
          <DailyBriefingRuntime />
        </section>
      </main>
    </div>
  );
}

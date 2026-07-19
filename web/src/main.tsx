import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/app-shell.css";
import "./styles/assessment-hero.css";
import "./styles/briefing-metrics.css";
import "./styles/review-focus.css";
import "./styles/evidence-summary.css";
import "./styles/engineering-brief.css";
import "./styles/review-context.css";
import "./styles/daily-briefing.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

import { Bell, ChevronDown, Moon } from "lucide-react";

export function TopBar() {
  return (
    <header className="topbar">
      <div className="topbar__controls" role="group" aria-label="Utility controls">
        <button type="button" className="icon-button" aria-label="Appearance settings">
          <Moon size={19} aria-hidden="true" />
        </button>
        <button type="button" className="icon-button" aria-label="Notifications">
          <Bell size={19} aria-hidden="true" />
        </button>
        <button type="button" className="topbar__user" aria-label="User menu">
          <span className="topbar__avatar" aria-hidden="true">
            OP
          </span>
          <span className="topbar__identity">
            <span className="topbar__name">Opscript</span>
            <span className="topbar__role">Workspace</span>
          </span>
          <ChevronDown size={18} aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}

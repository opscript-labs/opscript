import { ShieldCheck } from "lucide-react";

import {
  documentationItem,
  primaryNavigation,
} from "../data/navigation";
import { SidebarItem } from "./SidebarItem";

export function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Opscript">
      <div className="sidebar__brand">
        <div className="sidebar__logo" aria-hidden="true">
          <ShieldCheck size={19} strokeWidth={2.2} />
        </div>
        <span className="sidebar__wordmark">Opscript</span>
      </div>

      <nav className="sidebar__nav" aria-label="Primary navigation">
        {primaryNavigation.map((item) => (
          <SidebarItem key={item.id} item={item} />
        ))}
      </nav>

      <div className="sidebar__spacer" />

      <section className="sidebar__environment" aria-label="Environment summary">
        <div className="sidebar__environment-heading">
          <span className="sidebar__status-dot" aria-hidden="true" />
          <span className="sidebar__environment-name">Production</span>
        </div>
        <p>Last reviewed 09:18 AM</p>
        <p>Next review tomorrow</p>
      </section>

      <div className="sidebar__documentation">
        <SidebarItem item={documentationItem} />
      </div>
    </aside>
  );
}

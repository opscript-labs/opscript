import {
  BookOpen,
  CalendarClock,
  FileClock,
  FileText,
  History,
  LucideIcon,
  Settings,
  ShieldAlert,
  Sparkles,
  Workflow,
} from "lucide-react";

export type NavigationItem = {
  id: string;
  label: string;
  icon: LucideIcon;
  badge?: number;
  selected?: boolean;
};

export const primaryNavigation: NavigationItem[] = [
  { id: "daily-briefing", label: "Daily Briefing", icon: Sparkles, selected: true },
  { id: "changes", label: "Changes", icon: FileClock, badge: 3 },
  { id: "findings", label: "Findings", icon: ShieldAlert, badge: 1 },
  { id: "evidence", label: "Evidence", icon: Workflow },
  { id: "history", label: "History", icon: History },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "environments", label: "Environments", icon: CalendarClock },
  { id: "settings", label: "Settings", icon: Settings },
];

export const documentationItem: NavigationItem = {
  id: "documentation",
  label: "Documentation",
  icon: BookOpen,
};

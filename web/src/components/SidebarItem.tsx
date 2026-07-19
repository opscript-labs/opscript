import type { NavigationItem } from "../data/navigation";

type SidebarItemProps = {
  item: NavigationItem;
  collapsedLabel?: string;
};

export function SidebarItem({ item, collapsedLabel }: SidebarItemProps) {
  const Icon = item.icon;
  const label = collapsedLabel ?? item.label;
  const accessibleLabel = item.badge
    ? `${item.label}, ${item.badge} ${item.badge === 1 ? "update" : "updates"}`
    : item.label;

  return (
    <button
      type="button"
      className="sidebar-item"
      aria-current={item.selected ? "page" : undefined}
      aria-label={accessibleLabel}
      title={label}
      data-selected={item.selected ? "true" : "false"}
    >
      <Icon className="sidebar-item__icon" aria-hidden="true" size={20} />
      <span className="sidebar-item__label">{item.label}</span>
      {item.badge ? <span className="sidebar-item__badge">{item.badge}</span> : null}
    </button>
  );
}

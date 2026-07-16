import { BarChart3, Megaphone, MessageCircle, Store } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { RestaurantSwitcher } from "@/components/RestaurantSwitcher";
import { cn } from "@/lib/utils";

type View = "chat" | "campaigns" | "dashboard";

type AppShellProps = {
  chatPanel: ReactNode;
  campaignsPanel: ReactNode;
  dashboardPanel: ReactNode;
};

/** App shell: 224px sidebar + split view per design-guidelines.md §5.
 * Chat and Campaigns render side by side at desktop widths whenever
 * `activeView` is one of them (no router in this stack; they're two panels
 * of one view, not two routes) — the nav items between them exist for the
 * mobile bottom-tab-bar collapse (design-guidelines.md §5's "below ~768px"
 * breakpoint), where only one panel is visible at a time via responsive
 * visibility classes, not conditional rendering, so desktop widths always
 * show both. Dashboard (Phase 7) is different: it's a separate, full-width
 * view, not part of that split (design-guidelines.md §5/§11) — switching to
 * it conditionally renders the dashboard panel *instead of* the split,
 * rather than just toggling visibility within it. */
export function AppShell({
  chatPanel,
  campaignsPanel,
  dashboardPanel,
}: AppShellProps) {
  const [activeView, setActiveView] = useState<View>("chat");

  return (
    <div className="flex h-screen bg-base text-text">
      <aside className="flex w-56 shrink-0 flex-col gap-4 border-r border-border bg-surface p-4">
        <div className="flex items-center gap-2">
          <Store size={20} className="text-brand" />
          <span className="font-display text-[17px] font-semibold">
            Ask Sous
          </span>
        </div>

        <RestaurantSwitcher />

        <nav className="flex flex-col gap-1">
          <NavButton
            icon={<MessageCircle size={16} />}
            label="Chat"
            active={activeView === "chat"}
            onClick={() => setActiveView("chat")}
          />
          <NavButton
            icon={<Megaphone size={16} />}
            label="Campaigns"
            active={activeView === "campaigns"}
            onClick={() => setActiveView("campaigns")}
          />
          <NavButton
            icon={<BarChart3 size={16} />}
            label="Dashboard"
            active={activeView === "dashboard"}
            onClick={() => setActiveView("dashboard")}
          />
        </nav>
      </aside>

      {activeView === "dashboard" ? (
        <main className="flex-1 overflow-y-auto">{dashboardPanel}</main>
      ) : (
        <main className="grid flex-1 grid-cols-1 lg:grid-cols-[1.6fr_1fr]">
          <section
            className={cn(
              "min-h-0 border-border lg:block lg:border-r",
              activeView !== "chat" && "hidden",
            )}
          >
            {chatPanel}
          </section>
          <section
            className={cn(
              "min-h-0 lg:block",
              activeView !== "campaigns" && "hidden",
            )}
          >
            {campaignsPanel}
          </section>
        </main>
      )}
    </div>
  );
}

type NavButtonProps = {
  icon: ReactNode;
  label: string;
  active: boolean;
  disabled?: boolean;
  onClick: () => void;
};

function NavButton({
  icon,
  label,
  active,
  disabled = false,
  onClick,
}: NavButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 rounded-md px-2.5 py-2 text-left text-sm font-medium disabled:cursor-not-allowed disabled:opacity-42",
        active
          ? "bg-brand-wash text-brand-text"
          : "text-text-secondary hover:bg-overlay",
      )}
    >
      {icon}
      {label}
    </button>
  );
}

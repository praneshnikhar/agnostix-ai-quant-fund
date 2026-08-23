"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Bot,
  LayoutDashboard,
  LineChart,
  Newspaper,
  Boxes,
  Wallet,
  Shield,
  GitBranch,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/store/ui-store";

const NAV = [
  { href: "/dashboard", label: "Command Center", icon: LayoutDashboard },
  { href: "/markets", label: "Markets", icon: LineChart },
  { href: "/research", label: "Research", icon: Newspaper },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/models", label: "Models", icon: Boxes },
  { href: "/portfolio", label: "Portfolio", icon: Wallet },
  { href: "/risk", label: "Risk", icon: Shield },
  { href: "/signals", label: "Decisions", icon: GitBranch },
  { href: "/audit", label: "System", icon: Settings },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r border-border bg-surface transition-[width]",
        collapsed ? "w-12" : "w-48"
      )}
    >
      <div className="flex h-11 items-center justify-between border-b border-border px-3">
        {!collapsed && (
          <span className="text-xs font-semibold tracking-[0.2em] text-foreground">
            AGNOSTIX
          </span>
        )}
        <button
          onClick={toggle}
          aria-label="Toggle sidebar"
          className="text-subtle hover:text-foreground"
        >
          <Activity className="h-3.5 w-3.5" />
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 px-3 py-1.5 text-xs",
                active
                  ? "border-l-2 border-accent bg-elevated text-foreground"
                  : "border-l-2 border-transparent text-muted hover:text-foreground"
              )}
            >
              <Icon className="h-3.5 w-3.5 shrink-0" />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

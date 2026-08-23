"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Bot, Boxes, ChevronLeft, ChevronRight, GitBranch, LayoutDashboard, LineChart, Newspaper, Settings, Shield, Wallet, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/store/ui-store";

const PRIMARY_NAV = [
  { href: "/", label: "Command Center", icon: LayoutDashboard },
  { href: "/markets", label: "Markets", icon: LineChart },
  { href: "/research", label: "Research", icon: Newspaper },
  { href: "/agents", label: "AI / Agents", icon: Bot },
  { href: "/models", label: "Models", icon: Boxes },
  { href: "/portfolio", label: "Portfolio", icon: Wallet },
  { href: "/risk", label: "Risk", icon: Shield },
  { href: "/signals", label: "Decisions", icon: GitBranch },
] as const;

const SYSTEM_NAV = [
  { href: "/audit", label: "System", icon: Activity },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);

  const renderNav = (items: readonly { href: string; label: string; icon: LucideIcon }[]) => items.map(({ href, label, icon: Icon }) => {
    const active = href === "/" ? pathname === "/" || pathname === "/dashboard" : pathname.startsWith(href);
    return <Link key={href} href={href} title={collapsed ? label : undefined} aria-current={active ? "page" : undefined} className={cn("group relative flex items-center gap-3 border-l-2 px-3 py-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent", active ? "border-accent bg-accent/10 text-foreground" : "border-transparent text-muted hover:border-border-strong hover:bg-elevated/60 hover:text-foreground")}>{active ? <span className="absolute left-0 top-1/2 h-4 w-px -translate-y-1/2 bg-accent" /> : null}<Icon className={cn("h-4 w-4 shrink-0", active ? "text-accent" : "text-subtle group-hover:text-muted")} />{!collapsed && <span className="hidden md:inline">{label}</span>}</Link>;
  });

  return <aside className={cn("flex h-full shrink-0 flex-col border-r border-border bg-surface transition-[width] duration-200", collapsed ? "w-14" : "w-14 md:w-56")}>
    <div className="flex h-14 items-center justify-between border-b border-border px-3">
      {!collapsed ? <div className="hidden md:block"><div className="text-xs font-semibold tracking-[0.24em] text-foreground">AGNOSTIX</div><div className="mt-0.5 text-[9px] uppercase tracking-[0.18em] text-subtle">AI quant fund</div></div> : null}<span className={cn("mx-auto text-sm font-semibold text-accent", !collapsed && "md:hidden")}>A</span>
      <button onClick={toggle} aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} className="rounded p-1 text-subtle transition-colors hover:bg-elevated hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent">{collapsed ? <ChevronRight className="h-4 w-4" /> : <><ChevronLeft className="hidden h-4 w-4 md:block" /><ChevronRight className="h-4 w-4 md:hidden" /></>}</button>
    </div>
    <nav aria-label="Primary navigation" className="flex-1 overflow-y-auto px-2 py-4"><div className={cn("mb-2 px-2 text-[9px] font-medium uppercase tracking-[0.18em] text-subtle", collapsed && "sr-only")}>Workspace</div>{renderNav(PRIMARY_NAV)}<div className={cn("mb-2 mt-7 px-2 text-[9px] font-medium uppercase tracking-[0.18em] text-subtle", collapsed && "sr-only")}>System</div>{renderNav(SYSTEM_NAV)}</nav>
    {!collapsed ? <div className="hidden border-t border-border px-3 py-3 text-[10px] text-subtle md:block"><span className="font-mono text-accent">M2</span> · research foundation</div> : null}
  </aside>;
}

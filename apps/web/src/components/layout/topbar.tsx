"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bell, Search, UserRound } from "lucide-react";
import { getHealth } from "@/lib/api";
import { getMarkets } from "@/lib/markets-api";
import { StatusDot } from "@/components/ui";

export function Topbar() {
  const [searchOpen, setSearchOpen] = useState(false);
  const { data: health } = useQuery({ queryKey: ["health"], queryFn: getHealth, refetchInterval: 30_000 });
  const { data: markets } = useQuery({ queryKey: ["markets"], queryFn: getMarkets, refetchInterval: 60_000 });
  const systemStatus = health?.status === "healthy" ? "ok" : health?.status === "degraded" ? "warn" : health ? "error" : "idle";

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setSearchOpen(true); } };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return <header className="flex min-h-14 items-center justify-between gap-3 border-b border-border bg-surface/95 px-4 backdrop-blur-sm">
    <div className="flex min-w-0 items-center gap-4"><span className="hidden items-center gap-2 text-2xs uppercase tracking-wider text-muted sm:flex"><StatusDot status={markets ? "ok" : "idle"} /> Market {markets ? "connected" : "awaiting data"}</span><span className="flex items-center gap-2 text-2xs uppercase tracking-wider text-muted"><StatusDot status={systemStatus} /> System {health ? `· ${health.status}` : "· unavailable"}</span></div>
    <div className="flex items-center gap-2"><button type="button" onClick={() => setSearchOpen(true)} aria-label="Open global search" className="flex h-8 min-w-[150px] items-center justify-between gap-3 rounded border border-border bg-elevated/70 px-2.5 text-2xs text-subtle transition-colors hover:border-border-strong hover:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"><span className="flex items-center gap-2"><Search className="h-3.5 w-3.5" />Search workspace</span><kbd className="hidden rounded border border-border px-1 font-mono text-[9px] sm:inline">⌘K</kbd></button><button type="button" aria-label="Notifications (not connected)" className="rounded p-2 text-subtle hover:bg-elevated hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"><Bell className="h-4 w-4" /></button><button type="button" aria-label="Profile (not connected)" className="rounded p-2 text-subtle hover:bg-elevated hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"><UserRound className="h-4 w-4" /></button></div>
    {searchOpen ? <div role="dialog" aria-modal="true" aria-label="Global search" className="fixed inset-x-4 top-20 z-20 mx-auto max-w-xl rounded-md border border-border-strong bg-surface p-3 shadow-2xl shadow-black/40"><div className="flex items-center gap-2 border-b border-border px-2 pb-3"><Search className="h-4 w-4 text-subtle" /><input autoFocus placeholder="Search symbols, research, and system…" className="min-w-0 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-subtle" /><button type="button" onClick={() => setSearchOpen(false)} className="text-2xs text-muted hover:text-foreground">ESC</button></div><p className="px-2 py-5 text-xs text-muted">Search is ready for future workspace indexing. No backend search endpoint is connected.</p></div> : null}
  </header>;
}

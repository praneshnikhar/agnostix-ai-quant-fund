"use client";

import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

/** Application shell: sidebar + topbar + content area. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen min-w-0 overflow-hidden bg-background">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <main className="flex-1 overflow-y-auto px-3 py-4 sm:px-5 lg:px-7">{children}</main>
      </div>
    </div>
  );
}

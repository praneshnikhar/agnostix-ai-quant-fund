"use client";

import { useQuery } from "@tanstack/react-query";
import { getAgentEvents } from "@/lib/api";
import { EmptyState, ErrorState, LoadingState, Panel, PanelHeader, SectionHeader } from "@/components/ui";

export default function AuditPage() {
  const events = useQuery({ queryKey: ["agent-events", 100], queryFn: () => getAgentEvents(100) });
  return <div className="space-y-5"><SectionHeader eyebrow="SYSTEM / AUDIT" title="System activity" description="Append-only agent events returned by the backend. This view does not infer decisions, orders, or execution state." /><Panel><PanelHeader title="Agent event log" />{events.isLoading ? <LoadingState label="Reading audit events…" /> : events.isError ? <ErrorState description="The audit event endpoint is unavailable." /> : events.data?.length ? <div className="overflow-x-auto"><table className="w-full min-w-[640px] text-xs"><thead><tr className="border-b border-border text-left text-2xs uppercase tracking-wider text-muted"><th className="px-3 py-2">Timestamp</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Agent</th><th className="px-3 py-2">Proposal</th></tr></thead><tbody>{events.data.map((event) => <tr key={event.id} className="border-b border-border/50"><td className="px-3 py-2 text-muted">{new Date(event.timestamp).toLocaleString()}</td><td className="px-3 py-2 font-mono text-accent">{event.event_type}</td><td className="px-3 py-2 text-foreground">{event.agent_id}</td><td className="px-3 py-2 font-mono text-muted">{event.proposal_id ?? "—"}</td></tr>)}</tbody></table></div> : <EmptyState title="No audit events" description="The append-only event stream has not returned any records." />}</Panel></div>;
}

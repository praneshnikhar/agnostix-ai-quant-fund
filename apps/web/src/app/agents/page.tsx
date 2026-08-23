import { EmptyState, Panel, PanelHeader, SectionHeader } from "@/components/ui";

export default function AgentsPage() {
  return <div className="space-y-5"><SectionHeader eyebrow="AI / AGENTS" title="Agent registry" description="A foundation for specialized research agents and future Agent Bands. Runtime status is shown only once an agent registry contract exists." /><div className="grid gap-3 md:grid-cols-2"><Panel><PanelHeader title="Registry" /><EmptyState title="Not yet connected" description="Agent identity, capability, model, provider, latency, and success state are awaiting a backend contract." /></Panel><Panel><PanelHeader title="Agent Bands" /><EmptyState title="Coming in strategy layer" description="The future operating model will connect specialized analysts to debate, risk, and execution gates." /></Panel></div></div>;
}

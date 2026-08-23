import Link from 'next/link';
import { Badge, EmptyState, Panel, PanelHeader, SectionHeader } from '@/components/ui';

export const metadata = { title: 'Settings - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return <div className="space-y-5"><SectionHeader eyebrow="SYSTEM / SETTINGS" title="Settings" description="Configure the Agnostix workspace and its future server-side integrations." /><div className="grid gap-3 md:grid-cols-2"><Panel><PanelHeader title="AI providers" actions={<Badge>backend pending</Badge>} /><div className="p-4"><p className="text-sm text-foreground">Provider and model connections</p><p className="mt-1 text-xs leading-relaxed text-muted">Prepare OpenRouter, Ollama, custom, and future provider configurations without exposing credentials to the browser.</p><Link href="/settings/providers" className="mt-4 inline-flex rounded border border-accent/50 bg-accent/10 px-3 py-2 text-xs text-accent hover:bg-accent/20">Manage AI providers</Link></div></Panel><Panel><PanelHeader title="Workspace" /><EmptyState title="Not connected" description="General workspace, users, and organization settings are not exposed by the current backend." /></Panel></div></div>;
}


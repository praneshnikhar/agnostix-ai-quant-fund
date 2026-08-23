import { EmptyState, Panel, PanelHeader, SectionHeader } from '@/components/ui';

export const metadata = { title: 'Portfolio - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return <div className="space-y-5"><SectionHeader eyebrow="PORTFOLIO" title="Portfolio state" description="Read-only architecture for future positions, attribution, and performance." /><Panel><PanelHeader title="Portfolio infrastructure" /><EmptyState title="Portfolio infrastructure not yet connected" description="No positions, trades, NAV, P&L, or performance values are available from the backend." /></Panel></div>;
}


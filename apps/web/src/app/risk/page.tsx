import { EmptyState, Panel, PanelHeader, SectionHeader } from '@/components/ui';

export const metadata = { title: 'Risk - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return <div className="space-y-5"><SectionHeader eyebrow="RISK" title="Risk state" description="Information architecture for exposure, concentration, drawdown, VaR, CVaR, limits, and scenarios." /><Panel><PanelHeader title="Risk engine" /><EmptyState title="Risk infrastructure not yet connected" description="No exposure, limit, VaR, CVaR, or drawdown values are available from the backend." /></Panel></div>;
}


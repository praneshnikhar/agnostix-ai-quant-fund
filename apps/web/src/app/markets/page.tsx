import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Markets - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Markets' />
      <EmptyState
        title='Markets workspace - foundation placeholder'
        description='Planned sections: Market Overview, Watchlists, Security Explorer.'
      />
    </Panel>
  );
}


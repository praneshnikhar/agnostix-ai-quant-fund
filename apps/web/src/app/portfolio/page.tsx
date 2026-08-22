import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Portfolio - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Portfolio' />
      <EmptyState
        title='Portfolio workspace - foundation placeholder'
        description='Planned sections: Portfolio, Positions, Performance, Attribution.'
      />
    </Panel>
  );
}


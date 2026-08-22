import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Signals - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Signals' />
      <EmptyState
        title='Signals workspace - foundation placeholder'
        description='Planned sections: Signal Feed, Signal Detail.'
      />
    </Panel>
  );
}


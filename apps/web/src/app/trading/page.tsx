import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Trading - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Trading' />
      <EmptyState
        title='Trading workspace - foundation placeholder'
        description='Planned sections: Orders, Executions.'
      />
    </Panel>
  );
}


import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Audit - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Audit' />
      <EmptyState
        title='Audit workspace - foundation placeholder'
        description='Planned sections: Event Log, Decision Replay.'
      />
    </Panel>
  );
}


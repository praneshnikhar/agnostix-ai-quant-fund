import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Agents - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Agents' />
      <EmptyState
        title='Agents workspace - foundation placeholder'
        description='Planned sections: Agent Floor, Agent Detail, Agent Performance.'
      />
    </Panel>
  );
}


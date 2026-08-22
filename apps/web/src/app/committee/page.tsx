import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Committee - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Committee' />
      <EmptyState
        title='Committee workspace - foundation placeholder'
        description='Planned sections: Investment Committee, Debate, Decisions.'
      />
    </Panel>
  );
}


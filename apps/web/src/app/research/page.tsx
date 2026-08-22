import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Research - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Research' />
      <EmptyState
        title='Research workspace - foundation placeholder'
        description='Planned sections: Research Feed, Company Research, News Intelligence.'
      />
    </Panel>
  );
}


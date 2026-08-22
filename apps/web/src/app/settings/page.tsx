import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Settings - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Settings' />
      <EmptyState
        title='Settings workspace - foundation placeholder'
        description='Planned sections: General, API Keys (server-side only), Users.'
      />
    </Panel>
  );
}


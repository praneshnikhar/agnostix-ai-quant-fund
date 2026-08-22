import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Risk - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Risk' />
      <EmptyState
        title='Risk workspace - foundation placeholder'
        description='Planned sections: Risk Dashboard, Exposure, Drawdown, Stress Tests.'
      />
    </Panel>
  );
}


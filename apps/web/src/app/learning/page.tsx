import { EmptyState, Panel, PanelHeader } from '@/components/ui';

export const metadata = { title: 'Learning - AI Quant Fund' };

/** Architectural placeholder - populated in a later milestone. */
export default function Page() {
  return (
    <Panel>
      <PanelHeader title='Learning' />
      <EmptyState
        title='Learning workspace - foundation placeholder'
        description='Planned sections: Model Performance, Strategy Performance, Training Runs, Backtests, Model Registry.'
      />
    </Panel>
  );
}


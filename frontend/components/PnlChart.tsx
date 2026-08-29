"use client";

import { LineChart } from "@/components/LineChart";
import { Panel } from "@/components/Panel";
import { fmtMoney } from "@/lib/format";
import { useAppData } from "@/state/AppData";

export function PnlChart() {
  const { snapshots } = useAppData();
  const points = snapshots.map((s) => ({
    x: Date.parse(s.recorded_at),
    y: s.total_value,
  }));

  return (
    <Panel label="Portfolio Value" testId="pnl-chart" className="h-full" bodyClassName="p-1">
      <LineChart
        points={points}
        color="var(--color-accent)"
        gradientId="pnl-chart-fill"
        formatValue={fmtMoney}
        emptyMessage="Recording first snapshots"
      />
    </Panel>
  );
}

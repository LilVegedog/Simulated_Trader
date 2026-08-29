"use client";

import { useEffect, useState } from "react";
import { LineChart } from "@/components/LineChart";
import { Panel } from "@/components/Panel";
import { getPriceHistory } from "@/lib/api";
import { fmtPercent, fmtPrice } from "@/lib/format";
import type { PricePoint } from "@/lib/types";
import { useAppData } from "@/state/AppData";
import { usePriceStream } from "@/state/PriceStream";

export function MainChart() {
  const { selected } = useAppData();
  const { quotes, series } = usePriceStream();
  const [seed, setSeed] = useState<PricePoint[]>([]);

  useEffect(() => {
    if (!selected) return;
    let stale = false;
    getPriceHistory(selected).then((res) => {
      if (!stale) setSeed(res.points);
    });
    return () => {
      stale = true;
    };
  }, [selected]);

  const cutoff = seed.length > 0 ? seed[seed.length - 1].timestamp : "";
  const live = (selected ? (series[selected] ?? []) : []).filter((p) => p.timestamp > cutoff);
  const points = [...seed, ...live].map((p) => ({
    x: Date.parse(p.timestamp),
    y: p.price,
  }));

  const quote = selected ? quotes[selected] : undefined;
  const change = quote?.change_percent ?? 0;

  return (
    <Panel
      label={selected ? `${selected} - Price` : "Price"}
      testId="main-chart"
      className="h-full"
      bodyClassName="p-1"
      right={
        quote && (
          <>
            <span className="num text-[13px]">{fmtPrice(quote.price)}</span>
            <span
              className={`num text-[11px] ${change > 0 ? "text-up" : change < 0 ? "text-down" : "text-ink-dim"}`}
            >
              {fmtPercent(change)}
            </span>
          </>
        )
      }
    >
      <LineChart
        points={points}
        color="var(--color-primary)"
        gradientId="main-chart-fill"
        formatValue={fmtPrice}
        emptyMessage="Waiting for price history"
      />
    </Panel>
  );
}

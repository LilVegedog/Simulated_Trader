"use client";

import { Panel } from "@/components/Panel";
import { fmtMoney, fmtPercent } from "@/lib/format";
import { livePortfolio } from "@/lib/portfolio";
import { squarify } from "@/lib/treemap";
import { useSize } from "@/lib/useSize";
import { useAppData } from "@/state/AppData";
import { usePriceStream } from "@/state/PriceStream";

/** Diverging fill: red through the panel surface to green, saturating at +/-5%. */
function tileColor(percent: number) {
  const t = Math.max(-1, Math.min(1, percent / 5));
  const hue = t >= 0 ? "var(--color-up)" : "var(--color-down)";
  const weight = 12 + Math.abs(t) * 58;
  return `color-mix(in oklab, ${hue} ${weight.toFixed(0)}%, var(--color-raised))`;
}

function Legend() {
  return (
    <div className="hidden items-center gap-1.5 xl:flex">
      <span className="eyebrow">-5%</span>
      <span
        className="h-2 w-16"
        style={{
          background: `linear-gradient(to right, ${tileColor(-5)}, ${tileColor(0)}, ${tileColor(5)})`,
        }}
      />
      <span className="eyebrow">+5%</span>
    </div>
  );
}

export function Heatmap() {
  const { portfolio } = useAppData();
  const { quotes } = usePriceStream();
  const { ref, width, height } = useSize<HTMLDivElement>();

  const live = portfolio ? livePortfolio(portfolio, quotes) : null;
  const positions = live?.positions ?? [];
  const tiles = squarify(
    positions.map((p) => ({ key: p.ticker, value: p.market_value })),
    width,
    height,
  );
  const byTicker = new Map(positions.map((p) => [p.ticker, p]));

  return (
    <Panel
      label="Position Heatmap"
      testId="portfolio-heatmap"
      className="h-full"
      right={positions.length > 0 ? <Legend /> : undefined}
    >
      <div ref={ref} className="relative h-full w-full overflow-hidden">
        {positions.length === 0 && (
          <p className="eyebrow absolute inset-0 flex items-center justify-center">
            No open positions
          </p>
        )}
        {tiles.map((tile) => {
          const position = byTicker.get(tile.key)!;
          const showValue = tile.width > 64 && tile.height > 38;
          return (
            <div
              key={tile.key}
              title={`${tile.key} ${fmtMoney(position.market_value)} ${fmtPercent(position.unrealized_pnl_percent)}`}
              className="absolute overflow-hidden px-1.5 py-1"
              style={{
                left: tile.x + 1,
                top: tile.y + 1,
                width: Math.max(tile.width - 2, 0),
                height: Math.max(tile.height - 2, 0),
                background: tileColor(position.unrealized_pnl_percent),
              }}
            >
              <div className="num text-[11px] font-medium leading-tight">{tile.key}</div>
              {showValue && (
                <div className="num text-[10px] leading-tight text-ink-dim">
                  {fmtPercent(position.unrealized_pnl_percent)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

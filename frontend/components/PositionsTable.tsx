"use client";

import { Panel } from "@/components/Panel";
import { fmtMoney, fmtPercent, fmtPrice, fmtQty, fmtSignedMoney, pnlColor } from "@/lib/format";
import { livePortfolio } from "@/lib/portfolio";
import { useAppData } from "@/state/AppData";
import { usePriceStream } from "@/state/PriceStream";

const HEADS = ["Ticker", "Qty", "Avg Cost", "Last", "Market Value", "P&L", "%"];

export function PositionsTable() {
  const { portfolio, select } = useAppData();
  const { quotes } = usePriceStream();
  const positions = portfolio ? livePortfolio(portfolio, quotes).positions : [];

  return (
    <Panel label="Positions" className="h-full" bodyClassName="overflow-auto">
      <table data-testid="positions-table" className="w-full border-collapse text-[12px]">
        <thead className="sticky top-0 bg-panel">
          <tr>
            {HEADS.map((head, i) => (
              <th
                key={head}
                className={`eyebrow border-b border-line px-3 py-2 ${i === 0 ? "text-left" : "text-right"}`}
              >
                {head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.length === 0 && (
            <tr>
              <td colSpan={HEADS.length} className="eyebrow px-3 py-6 text-center">
                No open positions
              </td>
            </tr>
          )}
          {positions.map((p) => (
            <tr
              key={p.ticker}
              data-testid={`position-row-${p.ticker}`}
              onClick={() => select(p.ticker)}
              className="num cursor-pointer border-b border-line-soft hover:bg-raised"
            >
              <td className="px-3 py-1.5 font-medium">{p.ticker}</td>
              <td className="px-3 py-1.5 text-right text-ink-dim">{fmtQty(p.quantity)}</td>
              <td className="px-3 py-1.5 text-right text-ink-dim">{fmtPrice(p.avg_cost)}</td>
              <td className="px-3 py-1.5 text-right">{fmtPrice(p.current_price)}</td>
              <td className="px-3 py-1.5 text-right">{fmtMoney(p.market_value)}</td>
              <td className={`px-3 py-1.5 text-right ${pnlColor(p.unrealized_pnl)}`}>
                {fmtSignedMoney(p.unrealized_pnl)}
              </td>
              <td className={`px-3 py-1.5 text-right ${pnlColor(p.unrealized_pnl)}`}>
                {fmtPercent(p.unrealized_pnl_percent)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}

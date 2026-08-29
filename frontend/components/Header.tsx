"use client";

import { fmtMoney, fmtSignedMoney, pnlColor } from "@/lib/format";
import { livePortfolio } from "@/lib/portfolio";
import { useAppData } from "@/state/AppData";
import { usePriceStream } from "@/state/PriceStream";

const STATUS = {
  connected: { color: "bg-up", label: "Live" },
  reconnecting: { color: "bg-accent", label: "Reconnecting" },
  disconnected: { color: "bg-down", label: "Offline" },
} as const;

function Stat({ label, value, className = "", testId }: {
  label: string;
  value: string;
  className?: string;
  testId?: string;
}) {
  return (
    <div className="flex flex-col items-end leading-none">
      <span className="eyebrow">{label}</span>
      <span data-testid={testId} className={`num mt-1.5 text-[15px] ${className}`}>
        {value}
      </span>
    </div>
  );
}

export function Header() {
  const { portfolio } = useAppData();
  const { quotes, status } = usePriceStream();
  const live = portfolio ? livePortfolio(portfolio, quotes) : null;
  const badge = STATUS[status];

  return (
    <header className="flex h-14 shrink-0 items-center gap-6 border-b border-line bg-panel px-4">
      <div className="flex items-baseline gap-2">
        <span className="text-[17px] font-semibold tracking-tight">
          Fin<span className="text-accent">Ally</span>
        </span>
        <span className="eyebrow">Trading Desk</span>
      </div>

      <div
        data-testid="connection-status"
        data-status={status}
        className="flex items-center gap-2 border border-line px-2 py-1"
      >
        <span className={`h-2 w-2 rounded-full ${badge.color}`} />
        <span className="eyebrow">{badge.label}</span>
      </div>

      <div className="ml-auto flex items-center gap-8">
        <Stat
          label="Unrealized P&L"
          testId="unrealized-pnl"
          value={live ? fmtSignedMoney(live.unrealized_pnl) : "--"}
          className={live ? pnlColor(live.unrealized_pnl) : ""}
        />
        <Stat
          label="Cash"
          testId="cash-balance"
          value={live ? fmtMoney(live.cash_balance) : "--"}
          className="text-ink-dim"
        />
        <Stat
          label="Total Value"
          testId="total-value"
          value={live ? fmtMoney(live.total_value) : "--"}
          className="text-accent text-[19px]"
        />
      </div>
    </header>
  );
}

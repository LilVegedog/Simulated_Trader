"use client";

import { useEffect, useRef, useState } from "react";
import { Sparkline } from "@/components/Sparkline";
import { fmtPercent, fmtPrice } from "@/lib/format";
import type { PricePoint, Quote } from "@/lib/types";

interface WatchlistRowProps {
  ticker: string;
  quote?: Quote;
  points: PricePoint[];
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}

export function WatchlistRow({
  ticker,
  quote,
  points,
  selected,
  onSelect,
  onRemove,
}: WatchlistRowProps) {
  const [flash, setFlash] = useState("");
  const previous = useRef<number | undefined>(undefined);

  useEffect(() => {
    const price = quote?.price;
    if (price === undefined) return;
    const last = previous.current;
    previous.current = price;
    if (last === undefined || price === last) return;
    setFlash(price > last ? "flash-up" : "flash-down");
    const timer = setTimeout(() => setFlash(""), 500);
    return () => clearTimeout(timer);
  }, [quote?.price]);

  // Session move: first price seen since page load to the latest tick.
  const opening = points[0]?.price;
  const change =
    opening && quote ? ((quote.price - opening) / opening) * 100 : (quote?.change_percent ?? 0);
  // A ticker added mid-session has no tick yet; show a dash rather than a fake 0.00%.
  const tone = change > 0 ? "text-up" : change < 0 ? "text-down" : "text-ink-dim";
  const rail = change > 0 ? "bg-up" : change < 0 ? "bg-down" : "bg-line";

  return (
    <div
      data-testid={`watchlist-row-${ticker}`}
      data-selected={selected}
      onClick={onSelect}
      className={`group relative grid cursor-pointer grid-cols-[1fr_auto_auto] items-center gap-3 border-b border-line-soft py-1.5 pl-4 pr-2 hover:bg-raised ${
        selected ? "bg-raised" : ""
      }`}
    >
      <span className={`absolute left-0 top-0 h-full w-[2px] ${rail}`} />
      <div className="flex flex-col gap-1">
        <span className="num text-[13px] font-medium">{ticker}</span>
        <span className={`num text-[11px] ${tone}`}>{quote ? fmtPercent(change) : "--"}</span>
      </div>

      <Sparkline values={points.map((p) => p.price)} />

      <div className="flex w-[86px] items-center justify-end gap-1">
        <span
          data-testid={`watchlist-price-${ticker}`}
          className={`num rounded-sm px-1 text-[13px] ${flash}`}
        >
          {quote ? fmtPrice(quote.price) : "--"}
        </span>
        <button
          data-testid={`watchlist-remove-${ticker}`}
          aria-label={`Remove ${ticker}`}
          onClick={(event) => {
            event.stopPropagation();
            onRemove();
          }}
          className="w-4 text-ink-faint opacity-0 transition hover:text-down focus-visible:opacity-100 group-hover:opacity-100"
        >
          x
        </button>
      </div>
    </div>
  );
}

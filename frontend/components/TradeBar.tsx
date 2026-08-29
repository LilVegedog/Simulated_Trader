"use client";

import { useState } from "react";
import { ApiError, executeTrade } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { useAppData } from "@/state/AppData";
import { usePriceStream } from "@/state/PriceStream";

const FIELD =
  "num border border-line bg-void px-2 py-1.5 text-[13px] uppercase placeholder:normal-case placeholder:text-ink-faint";

export function TradeBar() {
  const { selected, applyPortfolio } = useAppData();
  const { quotes } = usePriceStream();
  const [ticker, setTicker] = useState("");
  const [quantity, setQuantity] = useState("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const symbol = (ticker || selected || "").toUpperCase();
  const quote = quotes[symbol];
  const qty = Number(quantity);
  const estimate = quote && qty > 0 ? quote.price * qty : null;

  const submit = async (side: "buy" | "sell") => {
    setError("");
    setNote("");
    try {
      const result = await executeTrade(symbol, qty, side);
      applyPortfolio(result.portfolio);
      setNote(`${side === "buy" ? "Bought" : "Sold"} ${quantity} ${symbol}`);
      setQuantity("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Trade failed.");
    }
  };

  return (
    <div className="flex h-14 shrink-0 items-center gap-3 border-t border-line bg-panel px-4">
      <span className="eyebrow">Market Order</span>
      <input
        data-testid="trade-ticker"
        aria-label="Trade ticker"
        value={ticker}
        onChange={(event) => setTicker(event.target.value)}
        placeholder={selected ?? "Ticker"}
        className={`${FIELD} w-24`}
      />
      <input
        data-testid="trade-quantity"
        aria-label="Trade quantity"
        value={quantity}
        onChange={(event) => setQuantity(event.target.value)}
        inputMode="decimal"
        placeholder="Qty"
        className={`${FIELD} w-24`}
      />
      <button
        data-testid="trade-buy"
        onClick={() => submit("buy")}
        className="border border-up px-5 py-1.5 text-[12px] font-semibold text-up hover:bg-up hover:text-void"
      >
        Buy
      </button>
      <button
        data-testid="trade-sell"
        onClick={() => submit("sell")}
        className="border border-down px-5 py-1.5 text-[12px] font-semibold text-down hover:bg-down hover:text-void"
      >
        Sell
      </button>

      {estimate !== null && (
        <span className="num text-[12px] text-ink-faint">est. {fmtMoney(estimate)}</span>
      )}
      {note && <span className="num text-[12px] text-ink-dim">{note}</span>}
      <span data-testid="trade-error" className="num text-[12px] text-down">
        {error}
      </span>
    </div>
  );
}

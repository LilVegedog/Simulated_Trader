import { describe, expect, it } from "vitest";
import { livePortfolio } from "@/lib/portfolio";
import type { Portfolio, Quote } from "@/lib/types";

const quote = (ticker: string, price: number): Quote => ({
  ticker,
  price,
  previous_price: price,
  change: 0,
  change_percent: 0,
  direction: "flat",
  timestamp: "2026-08-28T12:00:00Z",
});

const portfolio: Portfolio = {
  cash_balance: 1000,
  total_value: 0,
  unrealized_pnl: 0,
  positions: [
    {
      ticker: "AAPL",
      quantity: 10,
      avg_cost: 190,
      current_price: 190,
      market_value: 1900,
      unrealized_pnl: 0,
      unrealized_pnl_percent: 0,
    },
  ],
};

describe("livePortfolio", () => {
  it("re-prices positions from the stream", () => {
    const live = livePortfolio(portfolio, { AAPL: quote("AAPL", 200) });
    expect(live.positions[0].market_value).toBe(2000);
    expect(live.positions[0].unrealized_pnl).toBe(100);
    expect(live.positions[0].unrealized_pnl_percent).toBeCloseTo(5.263, 3);
    expect(live.total_value).toBe(3000);
    expect(live.unrealized_pnl).toBe(100);
  });

  it("falls back to the server price when the stream has no quote", () => {
    const live = livePortfolio(portfolio, {});
    expect(live.total_value).toBe(2900);
    expect(live.unrealized_pnl).toBe(0);
  });
});

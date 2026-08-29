import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PositionsTable } from "@/components/PositionsTable";
import type { Quote } from "@/lib/types";

const quote: Quote = {
  ticker: "AAPL",
  price: 200,
  previous_price: 199,
  change: 1,
  change_percent: 0.5,
  direction: "up",
  timestamp: "2026-08-28T12:00:00Z",
};

vi.mock("@/state/AppData", () => ({
  useAppData: () => ({
    select: vi.fn(),
    portfolio: {
      cash_balance: 1000,
      total_value: 3000,
      unrealized_pnl: 100,
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
    },
  }),
}));
vi.mock("@/state/PriceStream", () => ({
  usePriceStream: () => ({ quotes: { AAPL: quote }, series: {}, status: "connected" }),
}));

describe("PositionsTable", () => {
  it("shows live-priced market value and P&L", () => {
    render(<PositionsTable />);
    const row = within(screen.getByTestId("position-row-AAPL"));
    expect(row.getByText("10")).toBeInTheDocument();
    expect(row.getByText("190.00")).toBeInTheDocument();
    expect(row.getByText("200.00")).toBeInTheDocument();
    expect(row.getByText("$2,000.00")).toBeInTheDocument();
    expect(row.getByText("+$100.00")).toBeInTheDocument();
    expect(row.getByText("+5.26%")).toBeInTheDocument();
    expect(screen.getByTestId("positions-table")).toBeInTheDocument();
  });
});

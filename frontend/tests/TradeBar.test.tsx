import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TradeBar } from "@/components/TradeBar";
import { ApiError } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, executeTrade: vi.fn() };
});

const applyPortfolio = vi.fn();
vi.mock("@/state/AppData", () => ({
  useAppData: () => ({ selected: "AAPL", applyPortfolio }),
}));
vi.mock("@/state/PriceStream", () => ({
  usePriceStream: () => ({
    quotes: {
      AAPL: {
        ticker: "AAPL",
        price: 190,
        previous_price: 189,
        change: 1,
        change_percent: 0.53,
        direction: "up",
        timestamp: "2026-08-28T12:00:00Z",
      },
    },
    series: {},
    status: "connected",
  }),
}));

const api = await import("@/lib/api");

const portfolio = {
  cash_balance: 9620,
  total_value: 10000,
  unrealized_pnl: 0,
  positions: [],
};

describe("TradeBar", () => {
  beforeEach(() => vi.clearAllMocks());

  it("applies the portfolio embedded in the trade response", async () => {
    vi.mocked(api.executeTrade).mockResolvedValueOnce({
      trade: {
        ticker: "AAPL",
        side: "buy",
        quantity: 2,
        price: 190,
        executed_at: "2026-08-28T12:00:00Z",
      },
      portfolio,
    });
    render(<TradeBar />);
    await userEvent.type(screen.getByTestId("trade-quantity"), "2");
    await userEvent.click(screen.getByTestId("trade-buy"));
    expect(api.executeTrade).toHaveBeenCalledWith("AAPL", 2, "buy");
    await waitFor(() => expect(applyPortfolio).toHaveBeenCalledWith(portfolio));
  });

  it("shows the backend message verbatim when a trade is rejected", async () => {
    vi.mocked(api.executeTrade).mockRejectedValueOnce(
      new ApiError("unknown_ticker", "No price is available for AAPL right now."),
    );
    render(<TradeBar />);
    await userEvent.type(screen.getByTestId("trade-quantity"), "2");
    await userEvent.click(screen.getByTestId("trade-sell"));
    expect(await screen.findByTestId("trade-error")).toHaveTextContent(
      "No price is available for AAPL right now.",
    );
  });
});

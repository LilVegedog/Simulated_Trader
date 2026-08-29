import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WatchlistRow } from "@/components/WatchlistRow";
import type { Quote } from "@/lib/types";

const quote = (price: number): Quote => ({
  ticker: "AAPL",
  price,
  previous_price: price,
  change: 0,
  change_percent: 0,
  direction: "flat",
  timestamp: "2026-08-28T12:00:00Z",
});

const row = (price: number) => (
  <WatchlistRow
    ticker="AAPL"
    quote={quote(price)}
    points={[
      { price: 190, timestamp: "a" },
      { price, timestamp: "b" },
    ]}
    selected={false}
    onSelect={() => {}}
    onRemove={() => {}}
  />
);

describe("WatchlistRow", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("renders the ticker, price and session change", () => {
    render(row(190));
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("190.00");
    expect(screen.getByText("+0.00%")).toBeInTheDocument();
  });

  it("flashes green on an uptick and clears after 500ms", () => {
    const { rerender } = render(row(190));
    const price = screen.getByTestId("watchlist-price-AAPL");
    expect(price.className).not.toContain("flash");

    rerender(row(191.5));
    expect(price.className).toContain("flash-up");

    act(() => void vi.advanceTimersByTime(500));
    expect(price.className).not.toContain("flash");
  });

  it("flashes red on a downtick", () => {
    const { rerender } = render(row(190));
    rerender(row(188));
    expect(screen.getByTestId("watchlist-price-AAPL").className).toContain("flash-down");
  });
});

import { expect, type Page } from "@playwright/test";

export const DEFAULT_TICKERS = [
  "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
];

/** Parse a rendered "$1,234.56" / "1,234.56" cell into a number. */
export const money = (text: string | null) => Number((text ?? "").replace(/[^0-9.-]/g, ""));

/** Load the app and wait until the stream is live and portfolio data has arrived. */
export async function openApp(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("connection-status")).toHaveAttribute("data-status", "connected");
  await expect(page.getByTestId("cash-balance")).not.toHaveText("--");
  await expect(page.getByTestId("watchlist-price-AAPL")).not.toHaveText("--");
}

/** Submit a market order through the trade bar. */
export async function trade(page: Page, ticker: string, quantity: string, side: "buy" | "sell") {
  await page.getByTestId("trade-ticker").fill(ticker);
  await page.getByTestId("trade-quantity").fill(quantity);
  await page.getByTestId(`trade-${side}`).click();
}

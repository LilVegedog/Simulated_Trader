import { expect, test } from "@playwright/test";
import { DEFAULT_TICKERS, openApp } from "./helpers";

test.describe("fresh start", () => {
  test("shows the default watchlist, the seeded cash balance, and streaming prices", async ({ page }) => {
    await openApp(page);

    for (const ticker of DEFAULT_TICKERS) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
    }
    await expect(page.getByTestId("watchlist").locator('[data-testid^="watchlist-row-"]')).toHaveCount(
      DEFAULT_TICKERS.length,
    );

    await expect(page.getByTestId("cash-balance")).toHaveText("$10,000.00");
    await expect(page.getByTestId("total-value")).toHaveText("$10,000.00");

    // Prices are streaming: the value moves on its own, no reload involved.
    const price = page.getByTestId("watchlist-price-AAPL");
    const first = await price.textContent();
    await expect(price).not.toHaveText(first!, { timeout: 30_000 });
  });
});

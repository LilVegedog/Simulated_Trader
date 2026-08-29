import { expect, test } from "@playwright/test";
import { openApp, trade } from "./helpers";

const HELD = ["AAPL", "MSFT"];

test.describe("portfolio visualization", () => {
  test("heatmap tiles the open positions and the charts draw data", async ({ page }) => {
    await openApp(page);
    for (const ticker of HELD) {
      await trade(page, ticker, "3", "buy");
      await expect(page.getByTestId(`position-row-${ticker}`)).toBeVisible();
    }

    // One rectangle per position, sized by weight, labelled with the ticker.
    const tiles = page.getByTestId("portfolio-heatmap").locator("div[title]");
    await expect(tiles).toHaveCount(HELD.length);
    for (const ticker of HELD) {
      const tile = page.getByTestId("portfolio-heatmap").locator(`div[title^="${ticker} "]`);
      await expect(tile).toBeVisible();
      const box = await tile.boundingBox();
      expect(box!.width).toBeGreaterThan(0);
      expect(box!.height).toBeGreaterThan(0);
    }

    // Each trade records a snapshot, so the P&L line has points to draw.
    await expect(page.getByTestId("pnl-chart").locator("svg path[stroke]")).toHaveCount(1);

    // The main chart is seeded from GET /api/prices/history for the selection.
    await page.getByTestId("watchlist-row-AAPL").click();
    await expect(page.getByTestId("main-chart")).toContainText("AAPL - Price");
    await expect(page.getByTestId("main-chart").locator("svg path[stroke]")).toHaveCount(1);
  });
});

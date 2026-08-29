import { expect, test } from "@playwright/test";
import { openApp } from "./helpers";

const STREAM = "**/api/stream/prices";

test.describe("sse resilience", () => {
  test("survives a broken price stream and reconnects on its own", async ({ page }) => {
    await openApp(page);
    const status = page.getByTestId("connection-status");
    const price = page.getByTestId("watchlist-price-AAPL");

    // Break the stream endpoint, then force the client onto a fresh connection.
    await page.route(STREAM, (route) => route.abort());
    await page.reload();
    await expect(status).not.toHaveAttribute("data-status", "connected");
    await expect(price).toHaveText("--");

    // Restore the endpoint; EventSource's built-in retry has to recover unaided.
    await page.unroute(STREAM);
    await expect(status).toHaveAttribute("data-status", "connected", { timeout: 40_000 });

    // Ticks are flowing again.
    await expect(price).not.toHaveText("--");
    const resumed = await price.textContent();
    await expect(price).not.toHaveText(resumed!, { timeout: 30_000 });
  });
});

import { expect, test } from "@playwright/test";
import { openApp } from "./helpers";

const EXTRA = "AMD";
const UNSUPPORTED = "ZZZZ";

test.describe("watchlist", () => {
  test("adds a supported ticker and removes it again", async ({ page }) => {
    await openApp(page);
    await expect(page.getByTestId(`watchlist-row-${EXTRA}`)).toHaveCount(0);

    await page.getByTestId("watchlist-add-input").fill(EXTRA);
    await page.getByTestId("watchlist-add-submit").click();

    await expect(page.getByTestId(`watchlist-row-${EXTRA}`)).toBeVisible();
    await expect(page.getByTestId(`watchlist-price-${EXTRA}`)).not.toHaveText("--");

    await page.getByTestId(`watchlist-remove-${EXTRA}`).click();
    await expect(page.getByTestId(`watchlist-row-${EXTRA}`)).toHaveCount(0);
  });

  test("rejects an unsupported ticker with the backend's message", async ({ page }) => {
    await openApp(page);

    await page.getByTestId("watchlist-add-input").fill(UNSUPPORTED);
    await page.getByTestId("watchlist-add-submit").click();

    await expect(page.getByTestId("watchlist-error")).toHaveText(
      `${UNSUPPORTED} is not a supported ticker.`,
    );
    await expect(page.getByTestId(`watchlist-row-${UNSUPPORTED}`)).toHaveCount(0);
  });
});

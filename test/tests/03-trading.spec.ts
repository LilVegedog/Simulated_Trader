import { expect, test } from "@playwright/test";
import { money, openApp, trade } from "./helpers";

const TICKER = "NVDA";
const UNHELD = "META";

test.describe("trading", () => {
  test("buying reduces cash, opens a position, and lifts the portfolio total", async ({ page }) => {
    await openApp(page);
    const cashBefore = money(await page.getByTestId("cash-balance").textContent());

    await trade(page, TICKER, "2", "buy");

    await expect(page.getByTestId(`position-row-${TICKER}`)).toBeVisible();
    await expect(page.getByTestId("trade-error")).toHaveText("");

    const row = page.getByTestId(`position-row-${TICKER}`).locator("td");
    await expect(row.nth(0)).toHaveText(TICKER);
    await expect(row.nth(1)).toHaveText("2");

    await expect
      .poll(async () => money(await page.getByTestId("cash-balance").textContent()))
      .toBeLessThan(cashBefore);

    // The held position is marked to market, so the total exceeds cash alone.
    await expect
      .poll(async () => {
        const cash = money(await page.getByTestId("cash-balance").textContent());
        const total = money(await page.getByTestId("total-value").textContent());
        return total - cash;
      })
      .toBeGreaterThan(0);
  });

  test("selling returns cash and closes the position when fully sold", async ({ page }) => {
    await openApp(page);
    await expect(page.getByTestId(`position-row-${TICKER}`)).toBeVisible();
    const cashBefore = money(await page.getByTestId("cash-balance").textContent());

    await trade(page, TICKER, "1", "sell");
    await expect(page.getByTestId(`position-row-${TICKER}`).locator("td").nth(1)).toHaveText("1");
    await expect
      .poll(async () => money(await page.getByTestId("cash-balance").textContent()))
      .toBeGreaterThan(cashBefore);

    await trade(page, TICKER, "1", "sell");
    await expect(page.getByTestId(`position-row-${TICKER}`)).toHaveCount(0);
  });

  test("rejects selling more shares than are held", async ({ page }) => {
    await openApp(page);

    await trade(page, UNHELD, "5", "sell");

    await expect(page.getByTestId("trade-error")).toHaveText(
      `Not enough shares to sell 5 ${UNHELD}; you hold 0.`,
    );
    await expect(page.getByTestId(`position-row-${UNHELD}`)).toHaveCount(0);
  });

  test("rejects a buy that exceeds available cash", async ({ page }) => {
    await openApp(page);

    await trade(page, UNHELD, "100000", "buy");

    await expect(page.getByTestId("trade-error")).toHaveText(
      new RegExp(String.raw`^Not enough cash to buy 100000 ${UNHELD} at \$[\d,]+\.\d{2}\.$`),
    );
    await expect(page.getByTestId(`position-row-${UNHELD}`)).toHaveCount(0);
  });
});

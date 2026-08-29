import { expect, test } from "@playwright/test";
import { money, openApp } from "./helpers";

const TICKER = "GOOGL";

async function ask(page: import("@playwright/test").Page, message: string) {
  await page.getByTestId("chat-input").fill(message);
  await page.getByTestId("chat-send").click();
}

test.describe("ai chat (LLM_MOCK)", () => {
  test("answers a question and executes a trade requested in chat", async ({ page }) => {
    await openApp(page);

    await ask(page, "how is my exposure looking right now");
    await expect(page.getByTestId("chat-message-0")).toContainText(
      "how is my exposure looking right now",
    );
    await expect(page.getByTestId("chat-message-1")).toContainText("Mock response to:");

    await ask(page, `please buy 4 ${TICKER} for me`);
    const reply = page.getByTestId("chat-message-3");
    await expect(reply).toContainText(`Mock: executing buy 4.0 ${TICKER}.`);

    // The executed trade is confirmed inline in the chat panel...
    await expect(reply).toContainText("BUY");
    await expect(reply).toContainText(`4 ${TICKER}`);

    // ...and it really moved the portfolio.
    await expect(page.getByTestId(`position-row-${TICKER}`)).toBeVisible();
    await expect(
      page.getByTestId(`position-row-${TICKER}`).locator("td").nth(1),
    ).toHaveText("4");
  });
  test("reports a chat-requested trade that fails validation, and books nothing", async ({ page }) => {
    await openApp(page);
    const cashBefore = money(await page.getByTestId("cash-balance").textContent());

    await ask(page, "buy 5000 TSLA");

    // The mock's second pass returns the backend's error message verbatim.
    await expect(page.getByTestId("chat-message-1")).toContainText(
      "Not enough cash to buy 5000 TSLA",
    );
    await expect(page.getByTestId("position-row-TSLA")).toHaveCount(0);
    expect(money(await page.getByTestId("cash-balance").textContent())).toBe(cashBefore);
  });
});

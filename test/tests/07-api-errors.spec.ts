import { expect, test } from "@playwright/test";

/**
 * The error contract in PLAN.md section 8, asserted at the HTTP layer: the UI
 * only ever surfaces `message`, so the codes need coverage of their own.
 *
 * A rejected side reuses the `invalid_quantity` code rather than inventing a
 * fifth one, so those cases assert the status and the message instead.
 */
const cases = [
  { body: { ticker: "AAPL", quantity: 0, side: "buy" }, code: "invalid_quantity" },
  { body: { ticker: "AAPL", quantity: -1, side: "buy" }, code: "invalid_quantity" },
  { body: { ticker: "ZZZZ", quantity: 1, side: "buy" }, code: "unknown_ticker" },
  { body: { ticker: "AAPL", quantity: 1e6, side: "buy" }, code: "insufficient_cash" },
  { body: { ticker: "JPM", quantity: 1, side: "sell" }, code: "insufficient_shares" },
  { body: { ticker: "AAPL", quantity: 1, side: "hold" }, message: 'Side must be "buy" or "sell".' },
  { body: { ticker: "AAPL", quantity: 1, side: "" }, message: 'Side must be "buy" or "sell".' },
];

test.describe("trade error contract", () => {
  for (const { body, code, message } of cases) {
    test(`${body.side || "(empty side)"} ${body.quantity} ${body.ticker} is rejected`, async ({
      request,
    }) => {
      const before = await (await request.get("/api/portfolio")).json();

      const res = await request.post("/api/portfolio/trade", { data: body });
      expect(res.status()).toBe(400);
      expect(await res.json()).toMatchObject(code ? { error: code } : { message });

      // A rejected order must not move cash or open a position.
      const after = await (await request.get("/api/portfolio")).json();
      expect(after.cash_balance).toBe(before.cash_balance);
      expect(after.positions.map((p: { ticker: string }) => p.ticker)).toEqual(
        before.positions.map((p: { ticker: string }) => p.ticker),
      );
    });
  }

  test("a rejected side leaves no row in the trade log", async ({ request }) => {
    const before = (await (await request.get("/api/portfolio/history")).json()).snapshots.length;
    await request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity: 1, side: "hold" },
    });
    const after = (await (await request.get("/api/portfolio/history")).json()).snapshots.length;
    expect(after).toBe(before);
  });

  test("mixed case and padded sides still fill", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", {
      data: { ticker: "AAPL", quantity: 1, side: "  BuY  " },
    });
    expect(res.status()).toBe(200);
    expect((await res.json()).trade).toMatchObject({ ticker: "AAPL", side: "buy", quantity: 1 });
  });

  test("rejects an unsupported watchlist ticker", async ({ request }) => {
    const res = await request.post("/api/watchlist", { data: { ticker: "ZZZZ" } });
    expect(res.status()).toBe(400);
    expect(await res.json()).toMatchObject({ error: "unknown_ticker" });
  });
});

// Dev-only stand-in for the FastAPI backend. Implements planning/AGENT_TEAM.md section 3
// so the UI can be built and inspected before the real backend lands. Not shipped.
import { createServer } from "node:http";

// Never 8000 - that port belongs to the real backend and the container.
const PORT = Number(process.env.MOCK_PORT ?? 8787);

const SEED = {
  AAPL: 190, GOOGL: 175, MSFT: 420, AMZN: 185, TSLA: 250,
  NVDA: 900, META: 500, JPM: 195, V: 275, NFLX: 610, PYPL: 62, AMD: 160,
};

const state = {
  cash: 8261.5,
  watchlist: ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"],
  positions: [
    { ticker: "AAPL", quantity: 6, avg_cost: 188.4 },
    { ticker: "NVDA", quantity: 0.75, avg_cost: 912.0 },
    { ticker: "MSFT", quantity: 1.5, avg_cost: 431.2 },
  ],
  prices: {},
  previous: {},
  history: {},
  snapshots: [],
};

for (const [ticker, price] of Object.entries(SEED)) {
  state.prices[ticker] = price;
  state.previous[ticker] = price;
  const now = Date.now();
  state.history[ticker] = Array.from({ length: 120 }, (_, i) => ({
    price: Number((price * (1 + Math.sin(i / 9) * 0.006 * ((120 - i) / 120))).toFixed(2)),
    timestamp: new Date(now - (120 - i) * 30000).toISOString(),
  }));
}

const totalValue = () =>
  state.cash + state.positions.reduce((s, p) => s + p.quantity * state.prices[p.ticker], 0);

for (let i = 40; i > 0; i -= 1) {
  state.snapshots.push({
    total_value: Number((10000 * (1 + Math.sin(i / 6) * 0.01 + (40 - i) * 0.0009)).toFixed(2)),
    recorded_at: new Date(Date.now() - i * 30000).toISOString(),
  });
}

const clients = new Set();

setInterval(() => {
  const timestamp = new Date().toISOString();
  for (const ticker of Object.keys(SEED)) {
    const prev = state.prices[ticker];
    const next = Number((prev * (1 + (Math.random() - 0.5) * 0.004)).toFixed(2));
    state.previous[ticker] = prev;
    state.prices[ticker] = next;
    const payload = {
      ticker,
      price: next,
      previous_price: prev,
      change: Number((next - prev).toFixed(2)),
      change_percent: Number((((next - prev) / prev) * 100).toFixed(2)),
      direction: next > prev ? "up" : next < prev ? "down" : "flat",
      timestamp,
    };
    state.history[ticker].push({ price: next, timestamp });
    for (const res of clients) res.write(`data: ${JSON.stringify(payload)}\n\n`);
  }
}, 500);

setInterval(() => {
  state.snapshots.push({ total_value: totalValue(), recorded_at: new Date().toISOString() });
}, 30000);

const quote = (ticker) => ({
  ticker,
  price: state.prices[ticker],
  previous_price: state.previous[ticker],
  change: state.prices[ticker] - state.previous[ticker],
  change_percent: ((state.prices[ticker] - state.previous[ticker]) / state.previous[ticker]) * 100,
  direction: state.prices[ticker] >= state.previous[ticker] ? "up" : "down",
  timestamp: new Date().toISOString(),
});

const portfolio = () => {
  const positions = state.positions.map((p) => {
    const price = state.prices[p.ticker];
    const marketValue = price * p.quantity;
    const cost = p.avg_cost * p.quantity;
    return {
      ...p,
      current_price: price,
      market_value: marketValue,
      unrealized_pnl: marketValue - cost,
      unrealized_pnl_percent: ((marketValue - cost) / cost) * 100,
    };
  });
  return {
    cash_balance: state.cash,
    total_value: totalValue(),
    unrealized_pnl: positions.reduce((s, p) => s + p.unrealized_pnl, 0),
    positions,
  };
};

const send = (res, status, body) => {
  res.writeHead(status, { "Content-Type": "application/json", "Cache-Control": "no-store" });
  res.end(JSON.stringify(body));
};

const readBody = (req) =>
  new Promise((resolve) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => resolve(raw ? JSON.parse(raw) : {}));
  });

createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;

  if (path === "/api/stream/prices") {
    res.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" });
    clients.add(res);
    req.on("close", () => clients.delete(res));
    return;
  }
  if (path === "/api/health") return send(res, 200, { status: "ok" });
  if (path === "/api/portfolio") return send(res, 200, portfolio());
  if (path === "/api/portfolio/history") return send(res, 200, { snapshots: state.snapshots });
  if (path === "/api/watchlist" && req.method === "GET")
    return send(res, 200, { tickers: state.watchlist.map(quote) });
  if (path === "/api/prices/history") {
    const ticker = url.searchParams.get("ticker");
    return send(res, 200, { ticker, points: state.history[ticker] ?? [] });
  }
  if (path === "/api/watchlist" && req.method === "POST") {
    const { ticker } = await readBody(req);
    if (!SEED[ticker])
      return send(res, 400, { error: "unknown_ticker", message: `${ticker} is not a supported ticker.` });
    if (!state.watchlist.includes(ticker)) state.watchlist.push(ticker);
    return send(res, 200, { ok: true });
  }
  if (path.startsWith("/api/watchlist/") && req.method === "DELETE") {
    const ticker = decodeURIComponent(path.split("/").pop());
    state.watchlist = state.watchlist.filter((t) => t !== ticker);
    return send(res, 200, { ok: true });
  }
  if (path === "/api/portfolio/trade") {
    const { ticker, quantity, side } = await readBody(req);
    const price = state.prices[ticker];
    if (!price)
      return send(res, 400, { error: "unknown_ticker", message: `${ticker} is not a supported ticker.` });
    if (!(quantity > 0))
      return send(res, 400, { error: "invalid_quantity", message: "Quantity must be greater than zero." });
    const held = state.positions.find((p) => p.ticker === ticker);
    if (side === "buy") {
      if (price * quantity > state.cash)
        return send(res, 400, {
          error: "insufficient_cash",
          message: `Not enough cash to buy ${quantity} ${ticker} at $${price.toFixed(2)}.`,
        });
      state.cash -= price * quantity;
      if (held) {
        held.avg_cost = (held.avg_cost * held.quantity + price * quantity) / (held.quantity + quantity);
        held.quantity += quantity;
      } else {
        state.positions.push({ ticker, quantity, avg_cost: price });
      }
    } else {
      if (!held || held.quantity < quantity)
        return send(res, 400, {
          error: "insufficient_shares",
          message: `You only hold ${held?.quantity ?? 0} ${ticker}.`,
        });
      state.cash += price * quantity;
      held.quantity -= quantity;
      if (held.quantity === 0) state.positions = state.positions.filter((p) => p !== held);
    }
    state.snapshots.push({ total_value: totalValue(), recorded_at: new Date().toISOString() });
    return send(res, 200, { ok: true });
  }
  if (path === "/api/chat") {
    const { message } = await readBody(req);
    await new Promise((r) => setTimeout(r, 900));
    return send(res, 200, {
      message: `Your book is ${portfolio().unrealized_pnl >= 0 ? "up" : "down"} on the day, concentrated in NVDA. Re: "${message}" - I trimmed nothing and added PYPL to the watchlist so we can size into it.`,
      trades: [],
      watchlist_changes: [{ ticker: "PYPL", action: "add" }],
      errors: [],
    });
  }
  send(res, 404, { error: "not_found", message: "No such endpoint." });
}).listen(PORT, () => console.log(`mock backend on http://localhost:${PORT}`));

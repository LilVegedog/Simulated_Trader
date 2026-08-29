import type { ChatReply, Portfolio, PricePoint, Quote, Snapshot, TradeResult } from "./types";

/** Backend validation failure: HTTP 400 with {error, message}. */
export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    cache: "no-store",
    headers: init?.body ? { "Content-Type": "application/json" } : undefined,
  });
  if (!res.ok) {
    const body = await res.json();
    throw new ApiError(body.error, body.message);
  }
  return res.json();
}

export const getPortfolio = () => request<Portfolio>("/api/portfolio");

export const getPortfolioHistory = () =>
  request<{ snapshots: Snapshot[] }>("/api/portfolio/history");

export const getWatchlist = () => request<{ tickers: Quote[] }>("/api/watchlist");

export const getPriceHistory = (ticker: string) =>
  request<{ ticker: string; points: PricePoint[] }>(
    `/api/prices/history?ticker=${encodeURIComponent(ticker)}`,
  );

export const addWatchlist = (ticker: string) =>
  request<unknown>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });

export const removeWatchlist = (ticker: string) =>
  request<unknown>(`/api/watchlist/${encodeURIComponent(ticker)}`, { method: "DELETE" });

export const executeTrade = (ticker: string, quantity: number, side: "buy" | "sell") =>
  request<TradeResult>("/api/portfolio/trade", {
    method: "POST",
    body: JSON.stringify({ ticker, quantity, side }),
  });

export const sendChat = (message: string) =>
  request<ChatReply>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });

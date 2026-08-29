export type Direction = "up" | "down" | "flat";

export interface Quote {
  ticker: string;
  price: number;
  previous_price: number;
  change: number;
  change_percent: number;
  direction: Direction;
  timestamp: string;
}

export interface PricePoint {
  price: number;
  timestamp: string;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface Portfolio {
  cash_balance: number;
  total_value: number;
  unrealized_pnl: number;
  positions: Position[];
}

export interface Snapshot {
  total_value: number;
  recorded_at: string;
}

export interface Trade {
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
}

export interface TradeResult {
  trade: Trade & { price: number; executed_at: string };
  portfolio: Portfolio;
}

export interface WatchlistChange {
  ticker: string;
  action: "add" | "remove";
}

export interface ChatReply {
  message: string;
  trades: Trade[];
  watchlist_changes: WatchlistChange[];
  errors: { code: string; message: string }[];
}

export interface ChatEntry {
  role: "user" | "assistant";
  content: string;
  trades?: Trade[];
  watchlist_changes?: WatchlistChange[];
  errors?: { code: string; message: string }[];
}

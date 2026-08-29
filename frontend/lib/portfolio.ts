import type { Portfolio, Position, Quote } from "./types";

/** Re-prices a position from the live stream, falling back to the server snapshot. */
export function livePosition(position: Position, quote?: Quote): Position {
  const price = quote?.price ?? position.current_price;
  const marketValue = price * position.quantity;
  const cost = position.avg_cost * position.quantity;
  return {
    ...position,
    current_price: price,
    market_value: marketValue,
    unrealized_pnl: marketValue - cost,
    unrealized_pnl_percent: cost === 0 ? 0 : ((marketValue - cost) / cost) * 100,
  };
}

export function livePortfolio(
  portfolio: Portfolio,
  quotes: Record<string, Quote>,
): Portfolio {
  const positions = portfolio.positions.map((p) => livePosition(p, quotes[p.ticker]));
  const marketValue = positions.reduce((sum, p) => sum + p.market_value, 0);
  return {
    ...portfolio,
    positions,
    total_value: portfolio.cash_balance + marketValue,
    unrealized_pnl: positions.reduce((sum, p) => sum + p.unrealized_pnl, 0),
  };
}

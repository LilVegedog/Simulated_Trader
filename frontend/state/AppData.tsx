"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { getPortfolio, getPortfolioHistory, getWatchlist } from "@/lib/api";
import type { Portfolio, Snapshot } from "@/lib/types";

interface AppDataValue {
  portfolio: Portfolio | null;
  watchlist: string[];
  snapshots: Snapshot[];
  selected: string | null;
  select: (ticker: string) => void;
  applyPortfolio: (next: Portfolio) => void;
  refresh: () => Promise<void>;
}

const AppDataContext = createContext<AppDataValue | null>(null);

export const useAppData = () => useContext(AppDataContext)!;

export function AppDataProvider({ children }: { children: React.ReactNode }) {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [next, list, history] = await Promise.all([
      getPortfolio(),
      getWatchlist(),
      getPortfolioHistory(),
    ]);
    setPortfolio(next);
    setWatchlist(list.tickers.map((t) => t.ticker));
    setSnapshots(history.snapshots);
    setSelected((current) => current ?? list.tickers[0]?.ticker ?? null);
  }, []);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => clearInterval(timer);
  }, [refresh]);

  return (
    <AppDataContext.Provider
      value={{
        portfolio,
        watchlist,
        snapshots,
        selected,
        select: setSelected,
        applyPortfolio: setPortfolio,
        refresh,
      }}
    >
      {children}
    </AppDataContext.Provider>
  );
}

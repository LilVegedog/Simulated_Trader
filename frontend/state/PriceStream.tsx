"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { PricePoint, Quote } from "@/lib/types";

export type ConnectionStatus = "connected" | "reconnecting" | "disconnected";

interface StreamValue {
  quotes: Record<string, Quote>;
  series: Record<string, PricePoint[]>;
  status: ConnectionStatus;
}

const MAX_POINTS = 300;

const StreamContext = createContext<StreamValue>({
  quotes: {},
  series: {},
  status: "reconnecting",
});

export const usePriceStream = () => useContext(StreamContext);

export function PriceStreamProvider({ children }: { children: React.ReactNode }) {
  const [value, setValue] = useState<StreamValue>({
    quotes: {},
    series: {},
    status: "reconnecting",
  });
  const pending = useRef<Quote[]>([]);

  useEffect(() => {
    const source = new EventSource("/api/stream/prices");

    source.onopen = () => setValue((v) => ({ ...v, status: "connected" }));
    source.onmessage = (event) => {
      pending.current.push(JSON.parse(event.data) as Quote);
    };
    source.onerror = () =>
      setValue((v) => ({
        ...v,
        status: source.readyState === EventSource.CLOSED ? "disconnected" : "reconnecting",
      }));

    // Batch a burst of per-ticker events into one render.
    const flush = setInterval(() => {
      const batch = pending.current;
      if (batch.length === 0) return;
      pending.current = [];
      setValue((v) => {
        const quotes = { ...v.quotes };
        const series = { ...v.series };
        for (const q of batch) {
          quotes[q.ticker] = q;
          const next = [...(series[q.ticker] ?? []), { price: q.price, timestamp: q.timestamp }];
          series[q.ticker] = next.length > MAX_POINTS ? next.slice(-MAX_POINTS) : next;
        }
        return { ...v, quotes, series };
      });
    }, 250);

    return () => {
      clearInterval(flush);
      source.close();
    };
  }, []);

  return <StreamContext.Provider value={value}>{children}</StreamContext.Provider>;
}

"use client";

import { useState } from "react";
import { Panel } from "@/components/Panel";
import { WatchlistRow } from "@/components/WatchlistRow";
import { ApiError, addWatchlist, removeWatchlist } from "@/lib/api";
import { useAppData } from "@/state/AppData";
import { usePriceStream } from "@/state/PriceStream";

export function Watchlist() {
  const { watchlist, selected, select, refresh } = useAppData();
  const { quotes, series } = usePriceStream();
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const ticker = draft.trim().toUpperCase();
    if (!ticker) return;
    setError("");
    try {
      await addWatchlist(ticker);
      setDraft("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not add that ticker.");
    }
  };

  const remove = async (ticker: string) => {
    await removeWatchlist(ticker);
    await refresh();
  };

  return (
    <Panel
      label="Watchlist"
      testId="watchlist"
      right={<span className="eyebrow">Session %</span>}
      className="h-full"
      bodyClassName="flex flex-col overflow-hidden"
    >
      <div className="min-h-0 flex-1 overflow-y-auto">
        {watchlist.map((ticker) => (
          <WatchlistRow
            key={ticker}
            ticker={ticker}
            quote={quotes[ticker]}
            points={series[ticker] ?? []}
            selected={ticker === selected}
            onSelect={() => select(ticker)}
            onRemove={() => remove(ticker)}
          />
        ))}
      </div>

      <form onSubmit={submit} className="shrink-0 border-t border-line p-2">
        <div className="flex gap-2">
          <input
            data-testid="watchlist-add-input"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Add ticker"
            aria-label="Add ticker"
            className="num min-w-0 flex-1 border border-line bg-void px-2 py-1.5 text-[12px] uppercase placeholder:normal-case placeholder:text-ink-faint"
          />
          <button
            data-testid="watchlist-add-submit"
            type="submit"
            className="border border-primary px-3 py-1.5 text-[11px] font-medium text-primary hover:bg-primary hover:text-void"
          >
            Add
          </button>
        </div>
        {error && (
          <p data-testid="watchlist-error" className="mt-2 text-[11px] text-down">
            {error}
          </p>
        )}
      </form>
    </Panel>
  );
}

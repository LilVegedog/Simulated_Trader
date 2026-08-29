"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, sendChat } from "@/lib/api";
import { fmtQty } from "@/lib/format";
import type { ChatEntry } from "@/lib/types";
import { useAppData } from "@/state/AppData";

function Actions({ entry }: { entry: ChatEntry }) {
  const trades = entry.trades ?? [];
  const changes = entry.watchlist_changes ?? [];
  const errors = entry.errors ?? [];
  if (trades.length + changes.length + errors.length === 0) return null;

  return (
    <ul className="mt-2 flex flex-col gap-1 border-t border-line-soft pt-2">
      {trades.map((t, i) => (
        <li key={`t${i}`} className="num text-[11px]">
          <span className={t.side === "buy" ? "text-up" : "text-down"}>
            {t.side === "buy" ? "BUY" : "SELL"}
          </span>{" "}
          <span className="text-ink">
            {fmtQty(t.quantity)} {t.ticker}
          </span>
        </li>
      ))}
      {changes.map((c, i) => (
        <li key={`w${i}`} className="num text-[11px] text-primary">
          WATCHLIST {c.action.toUpperCase()} {c.ticker}
        </li>
      ))}
      {errors.map((e, i) => (
        <li key={`e${i}`} className="text-[11px] text-down">
          {e.message}
        </li>
      ))}
    </ul>
  );
}

export function ChatPanel() {
  const { refresh } = useAppData();
  const [entries, setEntries] = useState<ChatEntry[]>([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(true);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [entries, loading]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || loading) return;
    setEntries((list) => [...list, { role: "user", content: message }]);
    setDraft("");
    setLoading(true);
    try {
      const reply = await sendChat(message);
      setEntries((list) => [
        ...list,
        {
          role: "assistant",
          content: reply.message,
          trades: reply.trades,
          watchlist_changes: reply.watchlist_changes,
          errors: reply.errors,
        },
      ]);
      await refresh();
    } catch (err) {
      setEntries((list) => [
        ...list,
        {
          role: "assistant",
          content: err instanceof ApiError ? err.message : "The assistant is unavailable.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="eyebrow flex w-10 shrink-0 items-center justify-center border border-line bg-panel"
        aria-label="Open AI assistant"
      >
        <span className="[writing-mode:vertical-rl]">FinAlly AI</span>
      </button>
    );
  }

  return (
    <section
      data-testid="chat-panel"
      className="flex w-[280px] shrink-0 flex-col border border-line bg-panel xl:w-[340px]"
    >
      <header className="flex h-8 shrink-0 items-center gap-2 border-b border-line-soft px-3">
        <span className="h-2.5 w-[2px] bg-secondary" />
        <h2 className="eyebrow">FinAlly Assistant</h2>
        <button
          onClick={() => setOpen(false)}
          aria-label="Collapse AI assistant"
          className="eyebrow ml-auto hover:text-ink"
        >
          Hide
        </button>
      </header>

      <div ref={scroller} className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
        {entries.length === 0 && (
          <p className="text-[12px] leading-relaxed text-ink-faint">
            Ask about your positions, risk concentration, or tell FinAlly what to trade. It can
            place orders and manage the watchlist for you.
          </p>
        )}
        {entries.map((entry, index) => (
          <div
            key={index}
            data-testid={`chat-message-${index}`}
            className={`border px-3 py-2 text-[12px] leading-relaxed ${
              entry.role === "user"
                ? "border-line bg-raised text-ink-dim"
                : "border-secondary/50 bg-void text-ink"
            }`}
          >
            <span className="eyebrow mb-1.5 block">
              {entry.role === "user" ? "You" : "FinAlly"}
            </span>
            <p className="whitespace-pre-wrap">{entry.content}</p>
            <Actions entry={entry} />
          </div>
        ))}
        {loading && (
          <p data-testid="chat-loading" className="eyebrow px-3 py-2">
            Thinking...
          </p>
        )}
      </div>

      <form onSubmit={submit} className="flex shrink-0 gap-2 border-t border-line p-2">
        <input
          data-testid="chat-input"
          aria-label="Message FinAlly"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask FinAlly"
          className="min-w-0 flex-1 border border-line bg-void px-2 py-1.5 text-[12px] placeholder:text-ink-faint"
        />
        <button
          data-testid="chat-send"
          type="submit"
          className="bg-secondary px-3 py-1.5 text-[11px] font-medium text-ink hover:brightness-125"
        >
          Send
        </button>
      </form>
    </section>
  );
}

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "@/components/ChatPanel";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, sendChat: vi.fn() };
});
vi.mock("@/state/AppData", () => ({ useAppData: () => ({ refresh: vi.fn() }) }));

const api = await import("@/lib/api");

describe("ChatPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows the loading indicator until the reply arrives", async () => {
    let resolve!: (value: Awaited<ReturnType<typeof api.sendChat>>) => void;
    vi.mocked(api.sendChat).mockReturnValueOnce(new Promise((r) => (resolve = r)));

    render(<ChatPanel />);
    await userEvent.type(screen.getByTestId("chat-input"), "how am I doing");
    await userEvent.click(screen.getByTestId("chat-send"));

    expect(screen.getByTestId("chat-message-0")).toHaveTextContent("how am I doing");
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();

    resolve({ message: "Up 2% today.", trades: [], watchlist_changes: [], errors: [] });
    await waitFor(() => expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument());
    expect(screen.getByTestId("chat-message-1")).toHaveTextContent("Up 2% today.");
  });

  it("renders executed trades and watchlist changes inline", async () => {
    vi.mocked(api.sendChat).mockResolvedValueOnce({
      message: "Bought the dip.",
      trades: [{ ticker: "AAPL", side: "buy", quantity: 2.5 }],
      watchlist_changes: [{ ticker: "PYPL", action: "add" }],
      errors: [{ code: "insufficient_cash", message: "Not enough cash." }],
    });

    render(<ChatPanel />);
    await userEvent.type(screen.getByTestId("chat-input"), "buy apple");
    await userEvent.click(screen.getByTestId("chat-send"));

    const reply = await screen.findByTestId("chat-message-1");
    expect(reply).toHaveTextContent("BUY");
    expect(reply).toHaveTextContent("2.5 AAPL");
    expect(reply).toHaveTextContent("WATCHLIST ADD PYPL");
    expect(reply).toHaveTextContent("Not enough cash.");
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Watchlist } from "@/components/Watchlist";
import { ApiError } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, addWatchlist: vi.fn(), removeWatchlist: vi.fn() };
});

const refresh = vi.fn();
vi.mock("@/state/AppData", () => ({
  useAppData: () => ({
    watchlist: ["AAPL", "TSLA"],
    selected: "AAPL",
    select: vi.fn(),
    refresh,
    portfolio: null,
    snapshots: [],
  }),
}));
vi.mock("@/state/PriceStream", () => ({
  usePriceStream: () => ({ quotes: {}, series: {}, status: "connected" }),
}));

const api = await import("@/lib/api");

describe("Watchlist", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists the watched tickers", () => {
    render(<Watchlist />);
    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
    expect(screen.getByTestId("watchlist-row-TSLA")).toBeInTheDocument();
  });

  it("adds a ticker and refreshes", async () => {
    render(<Watchlist />);
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "nvda");
    await userEvent.click(screen.getByTestId("watchlist-add-submit"));
    expect(api.addWatchlist).toHaveBeenCalledWith("NVDA");
    await waitFor(() => expect(refresh).toHaveBeenCalled());
  });

  it("shows the backend message when a ticker is rejected", async () => {
    vi.mocked(api.addWatchlist).mockRejectedValueOnce(
      new ApiError("unknown_ticker", "ZZZZ is not a supported ticker."),
    );
    render(<Watchlist />);
    await userEvent.type(screen.getByTestId("watchlist-add-input"), "ZZZZ");
    await userEvent.click(screen.getByTestId("watchlist-add-submit"));
    expect(await screen.findByTestId("watchlist-error")).toHaveTextContent(
      "ZZZZ is not a supported ticker.",
    );
  });

  it("removes a ticker", async () => {
    render(<Watchlist />);
    await userEvent.click(screen.getByTestId("watchlist-remove-TSLA"));
    expect(api.removeWatchlist).toHaveBeenCalledWith("TSLA");
  });
});

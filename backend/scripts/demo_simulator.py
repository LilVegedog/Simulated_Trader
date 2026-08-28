#!/usr/bin/env python3
"""Live terminal demo of the FinAlly market data simulator.

Renders a continuously updating table of simulated stock prices using the
`rich` library, driven by the exact same `SimulatorProvider.stream()` /
`PriceCache` code path the FastAPI app will eventually use (see
planning/MARKET_DATA.md) -- this is a viewer onto the real simulator, not a
separate mock.

Usage (run from `backend/`; requires the "demo" dependency group):

    uv run --group demo python scripts/demo_simulator.py
    uv run --group demo python scripts/demo_simulator.py --tickers AAPL,TSLA,NVDA
    uv run --group demo python scripts/demo_simulator.py --seed 42 --duration 30
    uv run --group demo python scripts/demo_simulator.py --event-probability 0.05

Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import asyncio
import time

from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.market_data.base import PriceCache
from app.market_data.simulator import SimulatorConfig, SimulatorProvider
from app.market_data.symbols import DEFAULT_WATCHLIST, SECTOR_TICKERS

TICKER_SECTOR = {
    ticker: sector for sector, tickers in SECTOR_TICKERS.items() for ticker in tickers
}

SPARK_CHARS = "▁▂▃▄▅▆▇█"
# A per-tick move at or above this is flagged as a simulated "event" (the
# normal GBM step is tuned for ~0.1-0.3%; see MARKET_DATA.md section 5.1).
EVENT_THRESHOLD_PCT = 1.5
EVENT_FLAG_TICKS = 3  # how many ticks the "recent event" flag stays visible


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Live terminal demo of the FinAlly market data simulator.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tickers",
        default=",".join(DEFAULT_WATCHLIST),
        help="Comma-separated tickers to watch.",
    )
    parser.add_argument("--interval", type=float, default=0.5, help="Seconds between ticks.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output.")
    parser.add_argument(
        "--duration", type=float, default=None,
        help="Stop after this many seconds (default: run until Ctrl+C).",
    )
    parser.add_argument(
        "--history", type=int, default=20,
        help="Number of recent ticks shown in each ticker's sparkline.",
    )
    parser.add_argument(
        "--event-probability", type=float, default=None,
        help="Override the per-tick, per-ticker chance of a sudden 2-5%% move "
        "(default: the simulator's own default, 0.0005 -- crank this up to see events more often).",
    )
    return parser.parse_args()


def sparkline(values: list[float]) -> str:
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    if hi == lo:
        return SPARK_CHARS[0] * len(values)
    scale = len(SPARK_CHARS) - 1
    return "".join(SPARK_CHARS[round((v - lo) / (hi - lo) * scale)] for v in values)


def direction_style(direction: str) -> str:
    return {"up": "bold green", "down": "bold red"}.get(direction, "grey62")


def direction_arrow(direction: str) -> str:
    return {"up": "▲", "down": "▼"}.get(direction, "▬")


def build_display(
    cache: PriceCache,
    tickers: list[str],
    history_len: int,
    tick_count: int,
    started_at: float,
    recent_events: dict[str, int],
) -> Group:
    elapsed = time.monotonic() - started_at
    header = Panel(
        Align.center(
            Text.assemble(
                ("FinAlly ", "bold #ecad0a"),
                ("Market Data Simulator", "bold #209dd7"),
                (
                    f"   tick {tick_count}   {elapsed:6.1f}s elapsed   {len(tickers)} tickers",
                    "grey70",
                ),
            )
        ),
        border_style="#753991",
    )

    table = Table(expand=True, border_style="grey42")
    table.add_column("Ticker", style="bold")
    table.add_column("Sector")
    table.add_column("Price", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Change %", justify="right")
    table.add_column("Trend", justify="center")
    table.add_column(f"Last {history_len} ticks")

    for ticker in tickers:
        point = cache.get(ticker)
        if point is None:
            table.add_row(ticker, TICKER_SECTOR.get(ticker, "-"), "waiting...")
            continue

        style = direction_style(point.direction)
        history_prices = [p.price for p in cache.history(ticker)[-history_len:]]
        ticker_label = Text(ticker)
        if recent_events.get(ticker):
            ticker_label.append(" ⚡", style="bold yellow")  # lightning bolt

        table.add_row(
            ticker_label,
            TICKER_SECTOR.get(ticker, "-"),
            f"${point.price:,.2f}",
            Text(f"{point.change:+.2f}", style=style),
            Text(f"{point.change_percent:+.2f}%", style=style),
            Text(direction_arrow(point.direction), style=style),
            Text(sparkline(history_prices), style="#209dd7"),
        )

    footer = Text(
        "Press Ctrl+C to exit   ⚡ = simulated event (a sudden 2-5% move)",
        style="italic grey50",
    )
    return Group(header, table, Align.center(footer))


async def run(args: argparse.Namespace) -> None:
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        raise SystemExit("No tickers given.")

    config_kwargs: dict[str, object] = {"update_interval": args.interval, "seed": args.seed}
    if args.event_probability is not None:
        config_kwargs["event_probability"] = args.event_probability
    sim = SimulatorProvider(config=SimulatorConfig(**config_kwargs))

    unknown = sorted(t for t in tickers if not sim.is_supported(t))
    if unknown:
        raise SystemExit(
            f"Unknown ticker(s): {', '.join(unknown)}. "
            "See app.market_data.symbols.SUPPORTED_TICKERS for the full list."
        )

    cache = PriceCache(history_maxlen=max(args.history, 1))
    console = Console()
    tick_count = 0
    recent_events: dict[str, int] = {}
    started_at = time.monotonic()

    with Live(console=console, refresh_per_second=max(1, round(1 / args.interval))) as live:
        async for batch in sim.stream(lambda: tickers):
            tick_count += 1
            cache.update_many(batch)

            for point in batch:
                if abs(point.change_percent) >= EVENT_THRESHOLD_PCT:
                    recent_events[point.ticker] = EVENT_FLAG_TICKS
            for ticker in list(recent_events):
                recent_events[ticker] -= 1
                if recent_events[ticker] <= 0:
                    del recent_events[ticker]

            live.update(build_display(cache, tickers, args.history, tick_count, started_at, recent_events))

            if args.duration is not None and time.monotonic() - started_at >= args.duration:
                break


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

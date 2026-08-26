# FinAlly

An AI-powered trading workstation for simulated stock trading. Streams live (simulated) market data, lets you trade a virtual $10,000 portfolio, and includes an AI chat assistant that can analyze your positions and execute trades on your behalf.

Built as the capstone project for an agentic AI coding course — implemented entirely by orchestrated Claude Code agents.

## Features

- Live-updating watchlist with sparkline mini-charts
- Buy/sell simulated shares (market orders, fractional shares)
- Portfolio heatmap and P&L chart
- AI chat assistant that can analyze your portfolio and place trades via natural language

## Stack

- **Frontend**: Next.js (TypeScript), static export
- **Backend**: FastAPI (Python, managed with `uv`)
- **Database**: SQLite (volume-mounted)
- **Real-time data**: Server-Sent Events
- **AI**: LiteLLM → OpenRouter (Cerebras inference)
- Single Docker container, single port (`8000`)

## Getting Started

```bash
cp .env.example .env   # add your OPENROUTER_API_KEY
./scripts/start_mac.sh # or scripts/start_windows.ps1
```

Then open `http://localhost:8000`.

## Documentation

Full project specification: [`planning/PLAN.md`](planning/PLAN.md)

## License

See [LICENSE](LICENSE).

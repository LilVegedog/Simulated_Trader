# FinAlly frontend

Next.js + TypeScript single-page trading workstation. Built as a static export
(`output: 'export'`) to `frontend/out/`, which the FastAPI backend serves.

## Commands

```bash
npm run dev     # dev server on :3000, proxies /api to http://localhost:8000
npm run mock    # dev-only stand-in backend on :8787 (simulated prices, SSE, trades)
npm test        # Vitest + React Testing Library
npm run build   # static export to out/
```

The dev proxy target is `API_PROXY_TARGET`, defaulting to the real backend at
`http://localhost:8000` (run it with `uv run uvicorn app.main:app --port 8000`
from `backend/`). To work against the mock instead, run `npm run mock` in one
terminal and start the dev server with `API_PROXY_TARGET=http://localhost:8787`.
The mock's own port is `MOCK_PORT`. It never binds 8000, which belongs to the
real backend and the container.

## Layout

- `app/` — root layout, page shell, Tailwind theme tokens
- `components/` — panels, charts (hand-rolled SVG), trade bar, chat panel
- `state/` — `PriceStream` (single `EventSource`) and `AppData` (REST polling)
- `lib/` — API client, formatting, portfolio math, treemap layout
- `tests/` — unit tests
- `mock/` — dev-only backend stand-in, not part of the build

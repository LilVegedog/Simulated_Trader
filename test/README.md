# FinAlly E2E tests

Playwright suite covering the PLAN.md section 12 scenarios against the real app:
fresh start, watchlist add/remove/reject, buy, sell, trade validation errors,
portfolio visualisation, mocked AI chat, and SSE reconnection.

Assertions are structural. The simulator's prices are GBM-random, so tests check
that a price moved, that a position appeared, that cash fell -- never a value.

## Run locally

Needs the frontend export at `frontend/out/` (`npm run build` in `frontend/`).
Playwright starts the backend itself on port 8000 with `LLM_MOCK=true`,
`MASSIVE_API_KEY` unset, and a throwaway database at `test/.tmp/e2e.db`.

```
cd test
npm install
npx playwright install chromium
npx playwright test
```

Set `E2E_PORT` to use a different port. Set `BASE_URL` to skip the built-in
server and run against an app that is already up.

Note: on Windows, a `&` in the repository path breaks the npm `.cmd` shims, so
`npx playwright` fails. Use `node node_modules/@playwright/test/cli.js test`.

## Run in Docker

```
docker compose -f test/docker-compose.test.yml run --rm playwright
```

`docker-compose.test.yml` is owned by the DevOps Engineer. It sets `BASE_URL`,
so the suite runs against the app container and starts no server of its own.

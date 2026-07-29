# Final whole-branch fix report

## Status

Complete. All Critical and Important final-review findings were addressed in one coherent TDD wave without live AKShare access.

## Production fixes

- Added a bounded, cached local Shanghai/Shenzhen exchange calendar as the default application calendar. Market status works in the module-level app, and manual scans persist the exchange `marketDate` without falling back to the wall-clock date.
- Canonicalized indicator serialization to stable public keys: `rsi`, `atr`, and `bollMiddle`. Added a documented frontend contract whose labels remain configuration-aware (`RSI21`, `ATR7`, and so on).
- Wired every indicator `enabled` flag into chart presentation. MA/BOLL overlays, MACD/RSI/KDJ/ATR oscillators, and the 20-day volume average are omitted when their families are disabled; initial chart choices derive from configuration rather than hardcoded `ma20`/`rsi14`.
- Required `isTradingDay` for automatic after-16:00 scans.
- Removed the scanner retry loop so the AKShare gateway is the sole retry owner. A failed scan symbol now makes three total data attempts through the real scan/service/gateway layers.
- Made real AKShare access fail closed unless `A_SHARE_ALLOW_AKSHARE_NETWORK=1` is explicit. CI, unit tests, process tests, and Playwright run with `0`; injected fake gateways remain usable offline.
- Enabled SQLite `PRAGMA foreign_keys=ON` on every SQLite connection and flushed scan parents before child rows.
- Bounded `scan_daily_candles` globally to the 100 most recently refreshed symbols, evicting complete old-symbol partitions.
- Corrected frontend rounded score percentages so they total exactly 100%.
- Reworked `start.ps1` so readiness polling and service exit status are observed by the foreground process; failed readiness returns a failing exit and terminates the child service.
- Replaced stale README wording with the shipped feature set, network policy, calendar behavior, and verification commands.

## Acceptance additions

- Playwright now starts a real FastAPI process backed by an in-memory SQLite database and deterministic fake market gateway. The non-intercepted browser path performs stock search, real analysis serialization/rendering, watchlist persistence, and a real batch scan.
- A subprocess acceptance test starts Uvicorn with a file-backed SQLite database, creates a deliberately incomplete scan, terminates the backend process, restarts it against the same database, and verifies startup recovery marks the persisted scan failed.

## TDD evidence

The RED runs reproduced:

- unavailable default calendar;
- `bollMid` versus `bollMiddle` and `rsi14`/`atr14` frontend misses;
- disabled indicator families still rendering;
- non-trading-day auto-scan eligibility;
- nine multiplicative data attempts;
- real AKShare calls proceeding under the disabled flag;
- SQLite foreign keys disabled;
- unbounded global scan-cache symbols;
- 100.01% rounded weights;
- readiness errors not reaching the foreground launcher;
- browser acceptance depending only on intercepted API responses.

Focused GREEN runs then passed at each boundary before full validation.

## Final validation

```text
backend:
python -m ruff format --check .
23 files already formatted

python -m ruff check .
All checks passed

python -m mypy
Success: no issues found in 23 source files

python -m pytest
117 passed in 7.89s

frontend:
npm run format:check
All matched files use Prettier code style

npm run typecheck
exit 0

npm test
5 test files passed
28 tests passed

npm run build
production build completed

npm run test:e2e
3 passed

git diff --check
exit 0
```

The Vite build retains the existing non-failing advisory for the ECharts bundle size. No test or acceptance command contacted live AKShare.

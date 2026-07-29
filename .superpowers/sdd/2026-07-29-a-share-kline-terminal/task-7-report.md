# Task 7 Report — 测试与验收

## Status

Completed on branch `codex/a-share-kline-terminal`.

## Acceptance traceability

### Backend indicators and scoring

- `backend/tests/test_indicators.py` checks MA, MACD, RSI, KDJ, BOLL, ATR,
  and 20-day average volume against independently hand-checked values with
  `pytest.approx(..., abs=1e-6)`, including Wilder initialization/smoothing,
  flat ranges, zero losses, and insufficient-history nulls.
- `backend/tests/test_scoring.py` covers all five component rules, exact RSI,
  volume, risk, and grade boundaries, clipping, total-score rounding,
  finite/non-negative weight validation, normalization to exactly 100%,
  insufficient history, and structured visible evidence without advice or
  predictions.

### Mock AKShare, persistence, and failure handling

- `backend/tests/test_gateway.py`, `test_market_services.py`,
  `test_persistence.py`, and `test_api.py` use fake upstream sources only.
- Coverage includes code/name search, same-day catalog and candle cache hits,
  daily qfq requests, bounded date forwarding, full-symbol qfq replacement,
  transient retry and repeated timeout, stale catalog/candle fallback,
  malformed refresh preservation, force refresh, and retryable no-cache
  `DATA_UNAVAILABLE`.

### Batch scanning

- `backend/tests/test_api.py` enforces the 20-symbol maximum and unique
  symbols.
- `backend/tests/test_scan_service.py` proves a peak of three workers, two
  retries after the initial attempt, partial-failure isolation and reporting,
  forced single-row retry semantics, same-market-date de-duplication,
  restart recovery, and retention of exactly the latest 30 batches.

### Frontend unit coverage

- Existing Vitest/Testing Library suites cover ECharts OHLC mapping and
  controls, all indicator colors and series, configuration validation and
  persistence, score/evidence rendering, loading and actionable error states,
  watchlist limits, scan progress, row retry, and state sorting.
- Added an explicit cache-provenance assertion.
- Added a regression test for an empty candle response. The RED run showed
  that ECharts was mounted with no candles; the GREEN implementation now
  renders `暂无可用 K 线数据` and does not mount a misleading empty chart.

### Offline Playwright acceptance

`frontend/e2e/app.spec.ts` now contains a complete deterministic user journey.
Every browser request matching `/api/v1/*` is intercepted with local mock data,
so the test cannot contact AKShare. It verifies:

1. search for `000001` and open 平安银行;
2. visible forward-adjusted daily K-line, score, cache provenance, and
   backend evidence;
3. change MA periods to `5, 20, 60` and raw score weights to `50/20`;
4. return to detail and confirm MA controls plus evidence reflect the saved
   request configuration;
5. add the symbol to the watchlist and complete a batch scan;
6. reload the application and confirm watchlist, scan result, MA periods, and
   weights are restored.

The existing production-server Playwright test continues to verify the health
endpoint, terminal shell, and required disclosures.

## Windows clean-install and startup acceptance

The existing `.venv`, `frontend/node_modules`, and `frontend/dist` directories
were moved out of the worktree before setup. From that clean state:

```text
scripts/setup.ps1
Creating the Python virtual environment...
Installing locked backend dependencies...
Installing locked frontend dependencies...
Building the frontend...
Setup complete. Run scripts\start.ps1 to start the application.
exit 0
```

`scripts/start.ps1 -NoBrowser` was then launched from the repository root:

```text
listener: 127.0.0.1:8000
GET /api/v1/health -> {"status":"ok"}
GET / -> HTTP 200
port released after verification
```

## Final verification

```text
backend:
python -m ruff format --check .
17 files already formatted

python -m ruff check .
All checks passed!

python -m mypy
Success: no issues found in 17 source files

python -m pytest
109 passed in 2.83s

frontend:
npm run format:check
All matched files use Prettier code style!

npm run typecheck
exit 0

npm test
5 test files passed
25 tests passed

npm run build
production build completed

npm run test:e2e
2 passed
```

The production build retains the existing non-failing advisory that the
ECharts bundle is larger than 500 kB.

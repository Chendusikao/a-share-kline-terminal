# Task 6 Report — 批量扫描

## Status

Completed on branch `codex/a-share-kline-terminal`.

## Delivered

- Added `POST /api/v1/scans` (`202`), `GET /api/v1/scans/latest`, and
  `GET /api/v1/scans/{scan_id}` with the existing camelCase scan contracts and
  uniform `SCAN_NOT_FOUND` errors.
- Added a persisted in-process scan runner:
  - one coordinator with at most three concurrent symbol workers;
  - two retries after the first failed attempt;
  - per-symbol isolation and persisted partial failures;
  - same-market-date/config/symbol de-duplication, with explicit forced
    single-row retries;
  - startup recovery from `pending`/`running` to `failed`;
  - retention of the latest 30 batches;
  - comparison against the previous completed batch.
- Reused the analysis request's `IndicatorConfig` and `ScoreWeights`, the
  shared scoring `MINIMUM_HISTORY`, and the existing indicator/scoring
  functions. Scan calculation is limited to the latest required 80 bars.
- Replaced the Task 6 frontend boundary with:
  - manual watchlist refresh;
  - one-second polling while pending/running;
  - completed/total progress;
  - score-sorted rows, grades, deltas, key insights, market date, and cache
    provenance;
  - persisted error reasons and per-row retry actions;
  - first-open automatic scanning after 16:00 Asia/Shanghai only when the
    latest market date is newer than the latest completed scan.

## TDD evidence

1. Backend RED:
   - scan service/repository imports failed;
   - scan POST returned `405`;
   - unknown scan responses lacked the API error envelope.
2. Backend GREEN:
   - focused tests passed for max-three concurrency, three total attempts,
     partial failure continuation, original failure reasons, de-duplication,
     forced retry, startup recovery, 30-run retention, score deltas, and all
     three routes.
3. Frontend RED:
   - automatic eligibility helper did not exist;
   - the scan button remained disabled and no scan result/progress/retry UI
     appeared.
4. Frontend GREEN:
   - focused scan/App tests passed for after-16 eligibility, same-day/active
     suppression, manual execution, progress, sorted results, errors, and
     single-row retry payloads.

## Final verification

```text
backend:
ruff check app tests
All checks passed

mypy app tests
Success: no issues found in 17 source files

pytest
106 passed

frontend:
prettier --check .
All matched files use Prettier code style

tsc -b --pretty false
exit 0

vitest run
5 test files passed
24 tests passed

vite build
production build completed

playwright test
1 passed

git diff --check
exit 0
```

The production build retains the existing advisory that the ECharts bundle is
larger than 500 kB; it does not fail the build.

---

## Review Fix Round 1

### Findings resolved

1. Scan acquisition is now bounded at the gateway and persistence boundaries.
   `required_scan_history` derives the score window from the 80-day scoring
   floor, MACD slow/signal warm-up including the prior histogram, RSI warm-up,
   and ATR warm-up plus the 60 historical risk-percentile observations.
   `CandleService` converts that row requirement to a bounded date request and
   trims the response before replacing the symbol cache.
2. Same-day scan de-duplication now treats symbols as a set. Symbols are sorted
   before the request is encoded as canonical, key-sorted JSON, so equivalent
   requests with different input ordering produce the same hash.

### Root cause and TDD evidence

- Bounded history:
  - Root cause: the gateway exposed no start/end dates, inheriting AKShare's
    1970–2050 defaults, while `CandleService` persisted the full response
    before the scanner sliced it.
  - RED: the real `ScanService` → `CandleService` test could not import a
    derived history function; the gateway accepted no date bounds.
  - GREEN: a configuration requiring 170 bars sends non-null start/end dates,
    completes a real score, and persists exactly 170 rows even when the fake
    upstream returns 600. A gateway boundary test confirms dates are forwarded
    as AKShare `YYYYMMDD` parameters.
- Canonical symbol set:
  - Root cause: `json.dumps(sort_keys=True)` sorted object keys but preserved
    list ordering.
  - RED: `["000001", "600000"]` and its permutation created different scan
    IDs on the same market date.
  - GREEN: the permutation returns the original scan ID; forced refresh still
    creates a new batch.

### Review-fix verification

Run from `backend/`:

```text
ruff check app tests
All checks passed

mypy app tests
Success: no issues found in 17 source files

pytest
108 passed
```

---

## Review Fix Round 2

### Finding resolved

The scanner and detail page now use separate candle persistence:

- `daily_candles` remains the full-history detail cache;
- `scan_daily_candles` stores only the currently derived scanner window.

`CandleService.get_for_scan` prefers a fresh full detail cache without making a
network request, copies only the required tail into the bounded scan cache, and
leaves the detail cache unchanged. A bounded network response is likewise
written only to the scan cache, so a later detail request can still acquire and
retain complete history. Fresh scan-cache reuse also shrinks an oversized
window and refetches when the cached window is too short for a larger config.

### Root cause and TDD evidence

- Root cause: round 1 put bounded scanner data into the detail cache. On a
  cache miss that truncated later detail history; on a fresh-cache hit it
  sliced only the returned object and left full history as scanner
  persistence. One table could not preserve both contracts.
- RED: the new real-service tests failed because no separate
  `ScanCandleRepository` existed.
- GREEN:
  - cache miss: a 170-bar configuration leaves `daily_candles` empty and
    persists exactly 170 rows in `scan_daily_candles`;
  - fresh cache: a prepopulated 600-row detail cache remains at 600 rows, the
    scan cache contains exactly the required 80, the detail service still
    returns all 600, and the gateway is called only for the original detail
    load.

### Review-fix verification

Run from `backend/`:

```text
ruff check app tests
All checks passed

mypy app tests
Success: no issues found in 17 source files

pytest
109 passed
```

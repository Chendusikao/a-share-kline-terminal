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

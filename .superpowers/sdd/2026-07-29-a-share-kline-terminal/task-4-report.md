# Task 4 Report — 公共接口与数据模型

## Status

Completed on branch `codex/a-share-kline-terminal`.

The implementation and this report are committed together in the Task 4
feature commit.

## Changes

- Preserved `GET /api/v1/health` and added the executable Task 4 routes:
  - `GET /api/v1/market/status`
  - `GET /api/v1/stocks/search?q={query}&limit={1..20}`
  - `POST /api/v1/analysis`
- Extended the app factory with injected `Database`, market gateway, and clock
  dependencies. Tests use an in-memory SQLite database and a complete fake
  gateway; no test performs a live AKShare/network request.
- Wired the Task 2 catalog, candle cache, range slicing, indicator calculation,
  and stale-cache behavior to the Task 3 scoring and insight service.
- Added strict camelCase public Pydantic contracts for:
  - market status, stock search, analysis request/response, candles, indicator
    series, scores, breakdowns, effective weights, evidence, insights, cache
    state, warnings, validation details, and error envelopes;
  - scan request, accepted response, per-symbol result/error, and status
    response types compatible with the existing scan persistence schema.
- Added nested camelCase aliases for indicator configuration and score weights
  while preserving existing snake_case domain inputs.
- Added the uniform error envelope
  `{"error":{"code","message","retryable","details"}}`:
  - malformed symbol/range/indicator/weight/query/limit:
    HTTP `422` + `INVALID_CONFIG`;
  - a valid but unknown stock code:
    HTTP `404` + `SYMBOL_NOT_FOUND`;
  - upstream failure without usable cache:
    HTTP `503` + retryable `DATA_UNAVAILABLE`.
- Kept insufficient history as a successful partial analysis: candles,
  available indicators, reasons, and five insights are returned with null
  scores plus an `INSUFFICIENT_HISTORY` warning.
- Exposed cache provenance as `network`, `cache`, or `stale`, with the cached
  update date and visible stale-data warnings.
- Applied `YYYY-MM-DD` date contracts throughout the API and normalized cache
  calendar dates to Asia/Shanghai, including UTC-day boundaries.
- Added a numeric serialization boundary:
  - optional non-finite candle, indicator, and evidence values become `null`;
  - required non-finite analysis values fail as `DATA_UNAVAILABLE`;
  - every public Pydantic model forbids NaN/Infinity.
- Added a persistent default local SQLite file path configurable through
  `A_SHARE_DATABASE_PATH`; local `*.sqlite3` files are ignored by Git.

## Deliberate scan boundary

Task 4 owns the scan Pydantic contracts and the already-present
`scan_runs`/`scan_results` persistence-compatible shapes. Task 6 owns the
executable asynchronous scan endpoints, HTTP `202` scheduling, polling,
concurrency, retry, recovery, deduplication, and retention behavior.

No scan routes or deceptive `501` placeholders were registered in Task 4.

## TDD red/green evidence

1. Initial public API and contract suite:
   - RED: `python -m pytest tests\test_api.py -q`
   - Result: `20 failed`; the app factory did not accept injected dependencies,
     live routes were absent, and `app.api_models` did not exist.
   - GREEN after the minimal route/model implementation: `20 passed`.
2. Public nested camelCase configuration:
   - RED: nested `difColor`, `kSmoothing`, `standardDeviations`,
     `volumeMa20`, and `volumePrice` returned HTTP `422`.
   - GREEN after public aliases: focused test passed; the existing indicator
     and scoring suites also remained green.
3. Stale candle presentation:
   - RED: stale fallback was exposed as ordinary `cache` and omitted its
     warning.
   - GREEN: response now reports `stale`, preserves the original update date,
     and includes a structured `DATA_UNAVAILABLE` warning.
4. Shanghai UTC-day boundary:
   - RED: a refresh at `2026-07-30T16:30:00Z` serialized update date
     `2026-07-30`.
   - GREEN: search and analysis serialize `2026-07-31`.
5. Weekend market date:
   - RED: Saturday status returned Saturday as `marketDate`.
   - GREEN: it returns the latest weekday with `closed` /
     `isTradingDay=false`.

The suite also directly covers cache reuse and force refresh, unknown symbols,
data unavailability, invalid ranges/configurations/weights, non-finite request
weights, null-safe short history, 20-symbol scan limits/uniqueness, all five
score/insight categories, and complete finite JSON traversal.

## Final verification

Run from `backend/` with the repository virtual environment:

```text
python -m ruff format --check app tests
15 files already formatted

python -m ruff check app tests
All checks passed!

python -m mypy
Success: no issues found in 15 source files

python -m pytest
97 passed in 2.06s

git diff --check
exit 0
```

## Self-review

- Confirmed health and static frontend mounting remain registered.
- Confirmed analysis performs no API-layer signal or score inference; it only
  serializes Task 2/3 outputs.
- Confirmed exact-symbol lookup cannot accidentally analyze a partial search
  match.
- Confirmed request validation details never echo a NaN/Infinity input.
- Confirmed every response date is a Pydantic `date`, not a locale-dependent
  string or datetime.
- Confirmed response model validation plus explicit finite/null conversion
  prevents JSON NaN/Infinity.
- Confirmed no Task 5 frontend or Task 6 execution behavior was added.

## Concerns / follow-ups

- Market session status knows Shanghai weekday and exchange session hours but
  does not yet have an exchange holiday calendar. Task 6 should use the latest
  available candle/market date when deciding whether an automatic scan is due,
  rather than relying only on weekday status.
- The default database path is local to `backend/`. Packaging or a future
  installer may prefer an OS user-data directory; `A_SHARE_DATABASE_PATH`
  already provides an override without changing the API.

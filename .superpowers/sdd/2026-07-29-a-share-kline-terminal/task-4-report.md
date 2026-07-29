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

---

## Review Fix Round 1

Follow-up commit: included with this report update.

### Findings resolved

1. Public response mapping keys are now explicitly translated at the domain/API
   boundary. Pydantic field aliases do not transform arbitrary dictionary keys,
   so indicator series now emit `ma20`, `macdDif`, `volumeMa20`, etc., while
   score breakdown and effective-weight maps emit `volumePrice`. The public
   response models also use camelCase component-key literals.
2. Market status no longer treats every weekday as an exchange trading day.
   `create_app` accepts an injected offline `ExchangeCalendar` contract with
   authoritative `is_trading_day` and `latest_trading_day` behavior. A weekday
   holiday is closed and reports the previous market date; when no authoritative
   calendar is available, the route returns `status=unavailable`,
   `marketDate=null`, and never claims the market is open.
3. A non-finite or otherwise invalid total score is validated before Pydantic
   response construction. It now raises the domain `DataUnavailableError` and
   returns the standard HTTP `503` / retryable `DATA_UNAVAILABLE` envelope
   instead of escaping as an unhandled response-validation HTTP `500`.

No scan execution route or Task 6 scheduling behavior was added.

### Root-cause and TDD evidence

- Mapping keys:
  - Reproduction showed `model_dump(by_alias=True)` retained
    `volume_price`; aliases affected model fields only.
  - RED: analysis tests expected `ma20`/`macdDif`/`volumeMa20` and
    `volumePrice` but received snake_case keys.
  - GREEN: focused analysis and custom-weight response tests passed, including
    recursive verification that public JSON mapping keys contain no underscore.
- Exchange holidays:
  - Reproduction at `2026-10-01 10:00 Asia/Shanghai` returned
    `status=open`, because the implementation only checked `weekday()`.
  - RED: injected-calendar calls were unsupported, the National Day holiday
    was reported open, and the no-calendar path also reported open.
  - GREEN: open-day, weekend, weekday-holiday, and unavailable-calendar tests
    all passed using an offline fake calendar.
- Non-finite total score:
  - Reproduction showed Pydantic's `finite_number` validation error occurred
    before the API error handler could standardize it.
  - RED: an injected scorer result with `total_score=NaN` returned HTTP `500`.
  - GREEN: it returns HTTP `503`, `DATA_UNAVAILABLE`, no NaN, and no Infinity.

### Verification

Run from `backend/`:

```text
python -m ruff format --check app tests
15 files already formatted

python -m ruff check app tests
All checks passed!

python -m mypy
Success: no issues found in 15 source files

python -m pytest
100 passed in 2.07s

git diff --check
exit 0
```

### Review-fix self-check

- The domain indicator/scoring names remain unchanged; translation occurs only
  at the public response boundary.
- Calendar tests contain fixed local dates and never access AKShare or another
  live network service.
- An absent calendar is explicit unavailability, not a guessed weekday status.
- Optional warm-up values remain `null`; a corrupt required total score becomes
  a standardized service error.
- The earlier holiday-calendar concern is superseded by the injected
  authoritative-calendar contract and conservative unavailable fallback.

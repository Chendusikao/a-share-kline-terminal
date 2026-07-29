# Task 3 Report — 规则解读与综合评分

## Status

Completed on branch `codex/a-share-kline-terminal`.

Implementation commit: `f616950` (`feat: add transparent technical scoring`)

## Changes

- Added an internal backend scoring domain in `backend/app/scoring.py`; no HTTP
  routes, frontend behavior, scan execution, or investment/return language was
  added.
- Reused Task 2 `MarketBar` and `IndicatorBundle` domain types.
- Added five deterministic `0–100` components:
  - trend: `50 ± 20 ± 20 ± 10`, clipped to `0–100`;
  - momentum: `50 ± 20 ± 15`, plus the exact RSI `30/45/50/55/70`
    bands, clipped to `0–100`;
  - volume-price: exact `0.7` and `1.5` relative-volume boundaries with
    up/down/flat scores;
  - position: clipped 20-day and 60-day high/low percentiles, averaged;
  - risk quality: `100` less `25` for each of RSI extreme, current ATR/close
    above the previous 60-day 80th percentile, daily move above twice the
    previous ATR, and volume at least three times its 20-day average.
- Added default raw weights `35/25/15/15/10`, strict finite non-negative
  validation, at-least-one-positive validation, and exact normalization to
  `100%`.
- Added weighted total calculation with decimal half-up rounding and fixed
  grades: `0–34` weak, `35–44` relatively weak, `45–55` neutral, `56–65`
  relatively strong, and `66–100` strong (returned in Simplified Chinese).
- Added five structured insights. Each carries category, direction
  (`偏多/偏空/中性/风险`), summary, severity, and structured visible evidence
  with sanitized optional values and references.
- Added the 80-valid-trading-day gate. Below 80 days, total, grade, and every
  component score are `None`, the reason is `insufficient_history:80`, and
  available evidence remains visible.
- All numeric outputs pass through finite/null-safe handling; no NaN or
  Infinity is emitted.

## TDD Red/Green Evidence

1. Initial scoring contract:
   - RED: `python -m pytest tests\test_scoring.py -q`
   - Result: `34 failed`; every failure was the expected missing
     `app.scoring` module.
   - GREEN after the minimal scoring implementation: `34 passed`.
2. Exact normalization:
   - RED: the awkward decimal weight case summed to
     `99.99999999999999`, not exactly `100`.
   - GREEN after assigning the floating remainder to the last positive
     component: focused normalization test passed, with zero-weight
     components remaining zero.
3. Boundary expansion:
   - Added explicit coverage for the safe/trigger equality behavior of RSI,
     ATR percentile, twice-ATR daily movement, and three-times volume, plus
     bearish trend/momentum clipping.
   - Focused scoring suite: `36 passed`.

Tests exercise real scoring objects and hand-derived literal expectations;
they use no mocks or network access.

## Final Verification

Run from `backend/`:

```text
python -m ruff format app\scoring.py tests\test_scoring.py
1 file reformatted, 1 file left unchanged

python -m ruff check app tests
All checks passed!

python -m mypy app tests
Success: no issues found in 13 source files

python -m pytest
68 passed in 1.75s

git diff --check
exit 0
```

## Self-review

- Confirmed all five default weights, component point values, score boundaries,
  grade boundaries, risk comparison operators, and the 80-day threshold have
  direct tests.
- Confirmed custom weights affect the total only after backend normalization,
  and effective weights are returned with the result.
- Confirmed the total uses half-up rounding rather than Python's banker
  rounding.
- Confirmed insufficient history cannot leak a partial score or grade.
- Confirmed evidence contains only finite values or `None`.
- Confirmed summaries and evidence contain no buy/sell recommendation, return
  claim, or prediction.
- Confirmed Task 4 routes, Task 5 UI, and Task 6 scan execution remain untouched.

## Concerns / Follow-ups

- MACD histogram change compares the signed current histogram with the signed
  previous histogram. This treats a rising signed value as improving momentum
  and a falling signed value as weakening momentum, including contraction of a
  negative bar.
- The 20-day and 60-day position windows use the current rolling window,
  consistent with the Task 2 rolling-indicator convention. The current bar is
  excluded only where the plan explicitly says “previous 60 days” for the ATR
  risk percentile.
- Task 4 should serialize these internal dataclasses without re-deriving any
  score, direction, severity, or evidence in the API layer.

---

## Review Fix Round 1

Follow-up commit: `5ebcab4` (`fix: harden scoring validation`)

### Findings resolved

1. Made weight normalization overflow-safe for every accepted finite input.
   Values are first scaled by the largest weight, so a set such as five
   `1e308` weights normalizes to `20%` each instead of overflowing its
   aggregate and collapsing to `0/0/0/0/100`.
2. Changed the 80-valid-trading-day gate to count distinct trading dates.
   Duplicate records no longer make a 79-day history scoreable.
3. Split insight unavailability messaging by cause. A component missing its
   required indicators after 80 valid dates now displays the
   `missing_indicators:<component>` reason instead of claiming the history is
   shorter than 80 days.

### TDD RED/GREEN evidence

- Large finite weights:
  - RED: five `1e308` inputs produced effective weights
    `0/0/0/0/100`.
  - GREEN: the same inputs produce finite effective weights
    `20/20/20/20/20`.
- Duplicate dates:
  - RED: 80 records containing only 79 distinct dates returned
    `available=True`.
  - GREEN: it returns `available=False`, `insufficient_history:80`, and null
    score/grade.
- Missing indicator insight:
  - RED: deleting `macd_dif` after 80 valid dates yielded the summary
    “有效交易日不足 80 日”.
  - GREEN: the momentum insight identifies
    `missing_indicators:momentum` and no longer claims insufficient history.

All three focused regression tests were observed failing for the documented
reason before the production changes, then passed after their individual
root-cause fixes.

### Verification

Run from `backend/`:

```text
python -m pytest tests\test_scoring.py -q
39 passed

python -m pytest
71 passed in 1.62s

python -m ruff format --check app tests
13 files already formatted

python -m ruff check app tests
All checks passed!

python -m mypy app tests
Success: no issues found in 13 source files

git diff --check
exit 0
```

### Review-fix self-check

- Normal weight behavior, exact 100% totals, and zero-weight preservation remain
  covered.
- Duplicate dates affect only eligibility; they cannot inflate the valid-day
  count.
- The historical-insufficiency summary remains unchanged for genuinely short
  histories.
- No Task 4 routes, Task 5 UI, Task 6 scan behavior, investment recommendation,
  or return prediction was added.

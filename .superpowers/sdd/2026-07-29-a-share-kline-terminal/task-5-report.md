# Task 5 Report — 深色终端界面

## Status

Completed on branch `codex/a-share-kline-terminal`.

## Delivered

- Added responsive React Router routes for:
  - `/` — 自选扫描首页；
  - `/stocks/:symbol` — 股票详情；
  - `/settings` — 指标与评分配置。
- Integrated only the executable Task 4 APIs:
  - market status;
  - stock code/name search;
  - single-stock analysis.
- Kept the Task 6 boundary explicit. The scan table and complete required
  columns are present, but its execution button remains disabled with
  “扫描服务将在 Task 6 接入”; no fake scan endpoint or client-side scan executor
  was added.
- Implemented an ECharts K-line workspace with:
  - correct `[open, close, low, high]` candle mapping;
  - linked K-line, volume, and oscillator grids;
  - crosshair, wheel zoom, drag pan, slider zoom;
  - range selection (`3m`, `6m`, `1y`, `3y`, `all`);
  - selectable MA/BOLL overlays and oscillator selection;
  - A-share red-up/green-down colors.
- Added the score and interpretation rail:
  - total score, grade, five breakdown bars;
  - backend-provided structured insights and evidence;
  - key-position evidence;
  - score-unavailable, warning, cache, loading, and error states.
- Added versioned local preferences:
  - watchlist capped at 20 unique symbols;
  - recent history capped at 20 and ordered by latest visit;
  - indicator configuration and raw score weights;
  - safe fallback for corrupt or unsupported stored versions.
- Added a complete settings surface for built-in visibility, periods,
  smoothing, standard deviations, indicator colors, raw weights, live
  normalized percentages, and restore-default behavior.
- Added a single local-only dark terminal theme with responsive behavior:
  below `1024px`, the analysis rail moves below the chart; mobile layouts use
  a bottom navigation and compact chart/settings grids.
- Kept “数据来源：AKShare” and “不构成投资建议” visible on every route.

## TDD evidence

1. Storage, configuration, and chart foundations:
   - RED: focused tests failed because `storage`, `config`, `chart`, and public
     frontend types did not exist; behavior stubs then produced eight direct
     assertion failures.
   - GREEN: 8 focused tests passed for version handling, persistence, 20-item
     bounds, ordering, weight normalization, MA validation, OHLC mapping,
     interactions, overlays, and oscillator mapping.
2. Route behavior:
   - RED: four route tests failed against the Task 1 placeholder because the
     scan, detail, and settings routes did not exist.
   - GREEN: route tests passed after API-backed routing, analysis display,
     range controls, local persistence, and settings save behavior.
3. Full indicator configuration:
   - RED: the settings route lacked visibility toggles, full KDJ/BOLL
     parameters, and editable colors.
   - GREEN: the focused test persists visibility, RSI and MA colors, KDJ
     smoothing, and BOLL standard deviation.
4. Loading/error coverage:
   - Pending analysis is asserted as an explicit loading state.
   - Rejected analysis is asserted as an actionable error state with a route
     back to the scan home.

## Final verification

Run from `frontend/`:

```text
npm run format:check
All matched files use Prettier code style!

npm run typecheck
exit 0

npm test
5 test files passed
17 tests passed

npm run build
vite production build completed

npm run test:e2e
1 passed

git diff --check
exit 0
```

Vite reports the existing advisory that the ECharts application chunk exceeds
500 kB after minification. The build succeeds; route-level lazy loading can be
added later if startup size becomes material for this localhost-only app.

## Self-review

- Confirmed the frontend sends Task 4 camelCase request bodies and renders
  backend-provided scores, insights, evidence, warnings, and cache provenance
  without recreating signal logic.
- Confirmed no Task 6 request, polling, retry, or scheduling behavior was
  introduced.
- Confirmed scan rows have a tested descending-score sorter ready for Task 6.
- Confirmed responsive CSS changes the detail layout at exactly `1024px`.
- Confirmed no network-loaded fonts or external UI assets are required.

---

## Review Fix Round 1

### Findings resolved

1. Version `1` local preferences are now accepted only when the complete nested
   shape is valid. Watchlist/recent lists, every indicator section and color,
   all parameter bounds, MACD ordering, and all five score weights are checked.
   Corrupt, incomplete, non-finite, duplicated, or unsupported stored data
   falls back atomically to complete defaults.
2. The effective persisted `indicatorConfig` now flows through `StockDetail`
   to `KlineChart` and `buildKlineOption`. MA colors are resolved by configured
   period index; RSI, KDJ, BOLL, MACD, ATR, and volume-MA series use their
   respective configured colors.
3. Removed the frontend `metric.includes("20")` search and the synthesized
   “近 20 日区间” label. The key-position panel now renders every backend
   position evidence description plus neutral raw metric, comparison, value,
   and reference fields.

The Task 6 boundary remains unchanged; no scan execution, polling, retry, or
scheduling behavior was added.

### Root cause and TDD evidence

- Nested storage validation:
  - Root cause: `loadPreferences` checked only the version and four top-level
    property presences, then shallowly spread unvalidated nested data.
  - RED: a version `1` object with a string MA period collection, missing
    indicator sections, and a missing risk weight retained its watchlist and
    incomplete payload.
  - GREEN: it returns an empty default watchlist and complete default MA, MACD,
    and score configuration.
- Indicator colors:
  - Root cause: the chart boundary accepted only analysis data and selection;
    persisted indicator configuration never reached option construction.
  - RED: configured colors for six series families all produced `undefined`
    line colors.
  - GREEN: focused option assertions pass for MA20, BOLL upper, RSI, KDJ K,
    MACD DIF, and ATR.
- Position evidence:
  - Root cause: `StockDetail` selected evidence by a frontend substring search
    and `AnalysisRail` hardcoded a 20-day percentile presentation.
  - RED: arbitrary backend evidence still produced a synthesized “近 20 日区间
    82%” label.
  - GREEN: only the backend description and neutral raw evidence fields are
    rendered; the synthesized label is absent.

### Review-fix verification

Run from `frontend/`:

```text
npm run typecheck
exit 0

npm test
5 test files passed
19 tests passed

npm run build
vite production build completed

npm run test:e2e
1 passed
```

---

## Review Fix Round 2

Follow-up commit: included with this report update.

### Findings resolved

1. A stored MA color array must now contain at least one color for every
   configured MA period. An otherwise valid version `1` payload with fewer
   colors than periods is rejected atomically and falls back to complete
   defaults.
2. `macdHistogram` is now rendered as a bar series. Its ECharts item-color
   callback uses the persisted `positiveColor` for values greater than or equal
   to zero and `negativeColor` for values below zero.

The backend-evidence-only key-position presentation from review round 1 remains
unchanged, as does the Task 6 scan boundary.

### Root cause and TDD evidence

- MA color coverage:
  - Root cause: nested validation checked only that the color array contained
    `1–8` valid hex values, without relating its length to the MA periods that
    index into it.
  - RED: a payload with four periods and three colors retained its non-default
    watchlist instead of falling back.
  - GREEN: the payload is rejected; default watchlist, periods, and complete
    colors are restored.
- MACD histogram polarity:
  - Root cause: every oscillator was constructed as a line with one static
    color, and `macdHistogram` was mapped only to `positiveColor`.
  - RED: the histogram series type was `line` and had no item-color callback.
  - GREEN: it is a `bar`; direct option assertions verify positive, zero, and
    negative values return the configured positive, positive, and negative
    colors respectively.

### Review-fix verification

Run from `frontend/`:

```text
npm run typecheck
exit 0

npm test
5 test files passed
21 tests passed

npm run build
vite production build completed

npm run test:e2e
1 passed
```

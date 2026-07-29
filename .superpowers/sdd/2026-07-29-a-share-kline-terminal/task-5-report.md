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

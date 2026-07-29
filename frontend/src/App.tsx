import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import {
  type ChangeEvent,
  type FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useParams,
} from "react-router-dom";

import {
  getAnalysis,
  getLatestScan,
  getMarketStatus,
  getScan,
  searchStocks,
  startScan,
} from "./api";
import { KlineChart } from "./KlineChart";
import { normalizeWeights, parseMaPeriods } from "./config";
import { shouldAutoStartScan, sortScanRows } from "./scan";
import {
  addRecentSymbol,
  addWatchlistSymbol,
  defaultPreferences,
  loadPreferences,
  removeWatchlistSymbol,
  savePreferences,
  type Preferences,
} from "./storage";
import type {
  AnalysisRange,
  AnalysisResponse,
  ComponentName,
  IndicatorConfig,
  ScoreWeights,
  ScanStatus,
} from "./types";

const RANGE_OPTIONS: Array<{ value: AnalysisRange; label: string }> = [
  { value: "3m", label: "近 3 月" },
  { value: "6m", label: "近 6 月" },
  { value: "1y", label: "近 1 年" },
  { value: "3y", label: "近 3 年" },
  { value: "all", label: "全部" },
];

const COMPONENT_LABELS: Record<ComponentName, string> = {
  trend: "趋势",
  momentum: "动量",
  volumePrice: "量价",
  position: "关键位置",
  risk: "风险质量",
};

export default function App() {
  return (
    <div className="app-shell">
      <Header />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<ScanHome />} />
          <Route path="/stocks/:symbol" element={<StockDetail />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="terminal-footer">
        <span>
          仅支持 A 股前复权日线 · <b>数据来源：AKShare</b>
        </span>
        <span>
          技术分析仅供参考 · <b>不构成投资建议</b>
        </span>
      </footer>
    </div>
  );
}

function Header() {
  return (
    <header className="terminal-header">
      <Link className="brand" to="/">
        <span className="brand-mark">A</span>
        <span>
          <strong>A 股 K 线终端</strong>
          <small>LOCAL MARKET WORKSTATION</small>
        </span>
      </Link>
      <nav aria-label="主导航">
        <NavLink to="/">扫描</NavLink>
        <NavLink to="/settings">设置</NavLink>
      </nav>
      <span className="local-badge">
        <i />
        本机 127.0.0.1
      </span>
    </header>
  );
}

function ScanHome() {
  const [query, setQuery] = useState("");
  const [scanId, setScanId] = useState<string | null>(null);
  const autoAttempted = useRef(false);
  const market = useQuery({
    queryKey: ["market-status"],
    queryFn: getMarketStatus,
  });
  const search = useQuery({
    queryKey: ["stock-search", query],
    queryFn: () => searchStocks(query.trim()),
    enabled: query.trim().length > 0,
  });
  const preferences = loadPreferences();
  const latest = useQuery({
    queryKey: ["scan-latest"],
    queryFn: getLatestScan,
    retry: false,
  });
  const scan = useQuery({
    queryKey: ["scan-status", scanId],
    queryFn: () => getScan(scanId ?? ""),
    enabled: scanId !== null,
    refetchInterval: (query) => {
      const value = query.state.data;
      return value?.status === "pending" || value?.status === "running"
        ? 1000
        : false;
    },
  });
  const starter = useMutation({
    mutationFn: (input: { symbols: string[]; forceRefresh: boolean }) =>
      startScan({
        ...input,
        indicatorConfig: preferences.indicatorConfig,
        scoreWeights: preferences.scoreWeights,
      }),
    onSuccess: ({ scanId: acceptedId }) => setScanId(acceptedId),
  });
  const shownScan = scan.data ?? latest.data;
  const isActive =
    shownScan?.status === "pending" || shownScan?.status === "running";
  const rows = sortScanRows(shownScan?.results ?? []);

  useEffect(() => {
    if (
      autoAttempted.current ||
      market.data === undefined ||
      !latest.isFetched
    ) {
      return;
    }
    if (
      latest.data?.status === "pending" ||
      latest.data?.status === "running"
    ) {
      autoAttempted.current = true;
      setScanId(latest.data.scanId);
      return;
    }
    if (
      preferences.watchlist.length > 0 &&
      shouldAutoStartScan(market.data, latest.data ?? null)
    ) {
      autoAttempted.current = true;
      starter.mutate({
        symbols: preferences.watchlist,
        forceRefresh: false,
      });
    }
  }, [
    latest.data,
    latest.isFetched,
    market.data,
    preferences.watchlist,
    starter,
  ]);

  return (
    <section className="page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">WATCHLIST SCANNER</p>
          <h1>自选扫描</h1>
          <p>集中查看自选股的技术面状态与结构化信号。</p>
        </div>
        <div className="market-state">
          <span className={market.data?.isOpen ? "dot live" : "dot"} />
          <span>
            {market.data?.isOpen ? "交易中" : "已收盘"}
            <small>{market.data?.marketDate ?? "市场日历不可用"}</small>
          </span>
        </div>
      </div>

      <div className="toolbar-panel">
        <div className="search-wrap">
          <label htmlFor="stock-search">代码 / 名称</label>
          <input
            id="stock-search"
            type="search"
            aria-label="搜索股票"
            placeholder="搜索 000001 或 平安银行"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          {query.trim() !== "" && (
            <div className="search-results">
              {search.isLoading && <span>正在搜索…</span>}
              {search.data?.stocks.map((stock) => (
                <Link key={stock.symbol} to={`/stocks/${stock.symbol}`}>
                  <strong>{stock.name}</strong>
                  <span>{stock.symbol}</span>
                  <em>{stock.exchange}</em>
                </Link>
              ))}
              {search.data?.stocks.length === 0 && <span>未找到匹配股票</span>}
            </div>
          )}
        </div>
        <div className="toolbar-actions">
          <span>{preferences.watchlist.length} / 20 只自选</span>
          <button
            className="primary-button"
            disabled={
              preferences.watchlist.length === 0 ||
              starter.isPending ||
              isActive
            }
            type="button"
            onClick={() =>
              starter.mutate({
                symbols: preferences.watchlist,
                forceRefresh: true,
              })
            }
          >
            {starter.isPending ? "正在创建…" : "运行扫描"}
          </button>
        </div>
      </div>

      <section className="data-panel">
        <header className="panel-header">
          <div>
            <h2>批量扫描结果</h2>
            <p>默认按总分由高到低排列</p>
          </div>
          {shownScan ? (
            <span className="boundary-badge" aria-live="polite">
              {`${shownScan.completedCount}/${shownScan.totalCount} ${
                isActive ? "扫描中" : "已完成"
              }`}
            </span>
          ) : (
            <span className="boundary-badge">等待扫描</span>
          )}
        </header>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>股票</th>
                <th>总分</th>
                <th>等级</th>
                <th>较上次</th>
                <th>关键信号</th>
                <th>行情日期</th>
                <th>缓存状态</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.symbol}>
                  <td>
                    <Link to={`/stocks/${row.symbol}`}>{row.symbol}</Link>
                  </td>
                  <td>
                    <strong>{row.score ?? "—"}</strong>
                  </td>
                  <td>{row.grade ?? "—"}</td>
                  <td>{formatScoreChange(row.scoreChange)}</td>
                  <td>{row.insights?.[0]?.summary ?? "暂无关键信号"}</td>
                  <td>{shownScan?.marketDate ?? "—"}</td>
                  <td>{cacheStatusLabel(row.dataStatus)}</td>
                </tr>
              ))}
              {shownScan?.errors.map((error) => (
                <tr className="scan-error-row" key={error.symbol}>
                  <td>{error.symbol}</td>
                  <td>—</td>
                  <td>失败</td>
                  <td>—</td>
                  <td>
                    <span>{error.message}</span>
                    <button
                      className="row-retry"
                      type="button"
                      aria-label={`重试 ${error.symbol}`}
                      disabled={starter.isPending}
                      onClick={() =>
                        starter.mutate({
                          symbols: [error.symbol],
                          forceRefresh: true,
                        })
                      }
                    >
                      重试
                    </button>
                  </td>
                  <td>{shownScan.marketDate ?? "—"}</td>
                  <td>{error.code}</td>
                </tr>
              ))}
              {rows.length === 0 && (shownScan?.errors.length ?? 0) === 0 && (
                <tr className="empty-row">
                  <td colSpan={7}>
                    <span className="empty-glyph">⌁</span>
                    <strong>{isActive ? "扫描进行中" : "暂无扫描结果"}</strong>
                    <small>
                      {preferences.watchlist.length === 0
                        ? "先搜索股票并加入自选"
                        : isActive
                          ? "结果会每秒自动更新"
                          : "点击“运行扫描”刷新自选股"}
                    </small>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {preferences.recent.length > 0 && (
        <section className="recent-strip">
          <span>最近浏览</span>
          {preferences.recent.map((symbol) => (
            <Link key={symbol} to={`/stocks/${symbol}`}>
              {symbol}
            </Link>
          ))}
        </section>
      )}
    </section>
  );
}

function formatScoreChange(value: number | null): string {
  if (value === null) return "—";
  return value > 0 ? `+${value}` : String(value);
}

function cacheStatusLabel(
  status: ScanStatus["results"][number]["dataStatus"],
): string {
  return {
    network: "网络更新",
    cache: "缓存命中",
    stale: "旧缓存",
    error: "失败",
  }[status];
}

function StockDetail() {
  const { symbol = "" } = useParams();
  const [range, setRange] = useState<AnalysisRange>("3y");
  const [overlays, setOverlays] = useState(["ma20"]);
  const [oscillator, setOscillator] = useState("rsi14");
  const [preferences, setPreferences] = useState(loadPreferences);
  const analysis = useQuery({
    queryKey: [
      "analysis",
      symbol,
      range,
      preferences.indicatorConfig,
      preferences.scoreWeights,
    ],
    queryFn: () =>
      getAnalysis({
        symbol,
        range,
        forceRefresh: false,
        indicatorConfig: preferences.indicatorConfig,
        scoreWeights: preferences.scoreWeights,
      }),
    enabled: /^\d{6}$/.test(symbol),
    placeholderData: keepPreviousData,
  });

  useEffect(() => {
    if (analysis.data === undefined) return;
    const next = addRecentSymbol(preferences, analysis.data.stock.symbol);
    savePreferences(next);
    setPreferences(next);
    // The successful symbol is the only dependency that should record a visit.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysis.data?.stock.symbol]);

  if (!/^\d{6}$/.test(symbol)) {
    return <ErrorState message="股票代码格式无效" />;
  }
  if (analysis.isLoading) {
    return <LoadingState label="正在加载前复权日线与技术分析…" />;
  }
  if (analysis.isError || analysis.data === undefined) {
    return <ErrorState message="行情暂时不可用，请稍后重试" />;
  }

  const data = analysis.data;
  const inWatchlist = preferences.watchlist.includes(data.stock.symbol);
  const availableOverlays = Object.keys(data.indicators.series).filter((key) =>
    /^(ma\d+|boll)/.test(key),
  );
  const toggleWatchlist = () => {
    const next = inWatchlist
      ? removeWatchlistSymbol(preferences, data.stock.symbol)
      : addWatchlistSymbol(preferences, data.stock.symbol);
    savePreferences(next);
    setPreferences(next);
  };

  return (
    <section className="detail-page">
      <div className="stock-heading">
        <div>
          <Link to="/" className="back-link">
            ← 返回扫描
          </Link>
          <div className="stock-title">
            <h1>{data.stock.name}</h1>
            <span>{data.stock.symbol}</span>
            <em>{data.stock.exchange}</em>
          </div>
          <p>
            前复权日线 · 行情日期 {data.marketDate} ·{" "}
            <CacheLabel
              status={data.cache.status}
              updatedAt={data.cache.updatedAt}
            />
          </p>
        </div>
        <button
          className="watch-button"
          type="button"
          onClick={toggleWatchlist}
        >
          {inWatchlist ? "移出自选" : "加入自选"}
        </button>
      </div>

      <div className="range-toolbar" aria-label="图表控制">
        <div className="segmented">
          {RANGE_OPTIONS.map((option) => (
            <button
              className={range === option.value ? "active" : ""}
              key={option.value}
              type="button"
              onClick={() => setRange(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="indicator-switches">
          {availableOverlays.map((key) => (
            <label key={key}>
              <input
                type="checkbox"
                aria-label={indicatorLabel(key)}
                checked={overlays.includes(key)}
                onChange={() =>
                  setOverlays((current) =>
                    current.includes(key)
                      ? current.filter((item) => item !== key)
                      : [...current, key],
                  )
                }
              />
              {indicatorLabel(key)}
            </label>
          ))}
          <label>
            副图
            <select
              aria-label="副图指标"
              value={oscillator}
              onChange={(event) => setOscillator(event.target.value)}
            >
              {Object.keys(data.indicators.series)
                .filter((key) => !/^(ma\d+|boll)/.test(key))
                .map((key) => (
                  <option key={key} value={key}>
                    {indicatorLabel(key)}
                  </option>
                ))}
            </select>
          </label>
        </div>
      </div>

      <div className="analysis-layout">
        <section className="chart-panel">
          {data.candles.length === 0 ? (
            <div className="state-panel">
              <strong>暂无可用 K 线数据</strong>
            </div>
          ) : (
            <>
              <KlineChart
                analysis={data}
                selection={{ overlays, oscillator }}
                indicatorConfig={preferences.indicatorConfig}
              />
              <p className="chart-hint">
                滚轮缩放 · 拖动平移 · 悬停查看十字光标
              </p>
            </>
          )}
        </section>
        <AnalysisRail data={data} />
      </div>
    </section>
  );
}

function AnalysisRail({ data }: { data: AnalysisResponse }) {
  const positionEvidence = data.score.breakdown.position?.evidence ?? [];
  return (
    <aside className="analysis-rail" aria-label="技术面解读">
      <section className="score-card">
        <p>技术面总分</p>
        {data.score.available ? (
          <div className="score-lockup">
            <strong>{data.score.totalScore}</strong>
            <span>/ 100</span>
            <em>{data.score.grade}</em>
          </div>
        ) : (
          <div className="score-unavailable">
            <strong>评分不可用</strong>
            <span>{data.score.reason}</span>
          </div>
        )}
        <div className="score-bars">
          {(
            Object.entries(COMPONENT_LABELS) as Array<[ComponentName, string]>
          ).map(([key, label]) => {
            const component = data.score.breakdown[key];
            return (
              <div key={key}>
                <span>{label}</span>
                <i>
                  <b style={{ width: `${component?.score ?? 0}%` }} />
                </i>
                <strong>{component?.score ?? "—"}</strong>
              </div>
            );
          })}
        </div>
      </section>

      {positionEvidence.length > 0 && (
        <section className="position-card">
          <span>关键位置证据</span>
          {positionEvidence.map((evidence) => (
            <div key={`${evidence.metric}-${evidence.description}`}>
              <strong>{evidence.description}</strong>
              <small>
                {evidence.metric} · {evidence.comparison}
                {evidence.value === null ? "" : ` · 数值 ${evidence.value}`}
                {evidence.reference === null
                  ? ""
                  : ` · 参考 ${evidence.reference}`}
              </small>
            </div>
          ))}
        </section>
      )}

      <section className="insight-list">
        <header>
          <h2>结构化解读</h2>
          <span>后端规则</span>
        </header>
        {data.insights.map((insight, index) => (
          <article
            key={`${insight.category}-${index}`}
            className={`insight ${directionClass(insight.direction)}`}
          >
            <div>
              <span>
                {COMPONENT_LABELS[toPublicComponent(insight.category)]}
              </span>
              <em>{insight.direction}</em>
            </div>
            <p>{insight.summary}</p>
            {insight.evidence.map((evidence) => (
              <small key={`${evidence.metric}-${evidence.description}`}>
                {evidence.description}
              </small>
            ))}
          </article>
        ))}
      </section>

      {data.warnings.map((warning) => (
        <p className="warning" key={`${warning.code}-${warning.message}`}>
          {warning.message}
        </p>
      ))}
    </aside>
  );
}

function Settings() {
  const [preferences, setPreferences] = useState(loadPreferences);
  const [maPeriods, setMaPeriods] = useState(
    preferences.indicatorConfig.ma.periods.join(", "),
  );
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const percentages = useMemo(() => {
    try {
      return normalizeWeights(preferences.scoreWeights);
    } catch {
      return null;
    }
  }, [preferences.scoreWeights]);

  const updateWeight =
    (key: keyof ScoreWeights) => (event: ChangeEvent<HTMLInputElement>) => {
      setPreferences((current) => ({
        ...current,
        scoreWeights: {
          ...current.scoreWeights,
          [key]: Number(event.target.value),
        },
      }));
      setMessage("");
    };

  const updateIndicatorNumber =
    <
      Section extends "macd" | "rsi" | "kdj" | "boll" | "atr",
      Key extends keyof Preferences["indicatorConfig"][Section],
    >(
      section: Section,
      key: Key,
    ) =>
    (event: ChangeEvent<HTMLInputElement>) => {
      setPreferences((current) => ({
        ...current,
        indicatorConfig: {
          ...current.indicatorConfig,
          [section]: {
            ...current.indicatorConfig[section],
            [key]: Number(event.target.value),
          },
        },
      }));
    };

  const patchIndicator = (
    section: keyof IndicatorConfig,
    patch: Record<string, unknown>,
  ) => {
    setPreferences((current) => {
      const indicatorConfig = structuredClone(current.indicatorConfig);
      Object.assign(indicatorConfig[section], patch);
      return { ...current, indicatorConfig };
    });
  };

  const save = (event: FormEvent) => {
    event.preventDefault();
    try {
      const periods = parseMaPeriods(maPeriods);
      normalizeWeights(preferences.scoreWeights);
      const next = {
        ...preferences,
        indicatorConfig: {
          ...preferences.indicatorConfig,
          ma: { ...preferences.indicatorConfig.ma, periods },
        },
      };
      savePreferences(next);
      setPreferences(next);
      setError("");
      setMessage("设置已保存");
    } catch (caught) {
      setMessage("");
      setError(caught instanceof Error ? caught.message : "设置无效");
    }
  };

  const reset = () => {
    const next = defaultPreferences();
    savePreferences(next);
    setPreferences(next);
    setMaPeriods(next.indicatorConfig.ma.periods.join(", "));
    setMessage("已恢复默认设置");
    setError("");
  };

  return (
    <section className="settings-page page-stack">
      <div className="page-heading">
        <div>
          <p className="eyebrow">ANALYSIS CONFIGURATION</p>
          <h1>分析参数</h1>
          <p>参数由后端统一校验，并用于详情分析与后续批量扫描。</p>
        </div>
        <button className="ghost-button" type="button" onClick={reset}>
          恢复默认
        </button>
      </div>

      <form onSubmit={save}>
        <section className="settings-card">
          <header>
            <div>
              <span>01</span>
              <h2>指标参数</h2>
            </div>
            <small>INDICATORS</small>
          </header>
          <div className="indicator-toggles">
            {(
              [
                ["ma", "MA"],
                ["macd", "MACD"],
                ["rsi", "RSI"],
                ["kdj", "KDJ"],
                ["boll", "BOLL"],
                ["atr", "ATR"],
                ["volumeMa20", "20 日均量"],
              ] as const
            ).map(([section, label]) => (
              <label key={section}>
                <input
                  type="checkbox"
                  aria-label={`显示 ${label}`}
                  checked={preferences.indicatorConfig[section].enabled}
                  onChange={(event) =>
                    patchIndicator(section, { enabled: event.target.checked })
                  }
                />
                <span>{label}</span>
              </label>
            ))}
          </div>
          <div className="settings-grid">
            <label className="wide-field">
              <span>MA 周期</span>
              <input
                aria-label="MA 周期"
                value={maPeriods}
                onChange={(event) => setMaPeriods(event.target.value)}
              />
              <small>2–250，逗号分隔，最多 8 条且不重复</small>
            </label>
            <NumberField
              label="MACD 快线"
              value={preferences.indicatorConfig.macd.fast}
              onChange={updateIndicatorNumber("macd", "fast")}
            />
            <NumberField
              label="MACD 慢线"
              value={preferences.indicatorConfig.macd.slow}
              onChange={updateIndicatorNumber("macd", "slow")}
            />
            <NumberField
              label="MACD 信号"
              value={preferences.indicatorConfig.macd.signal}
              onChange={updateIndicatorNumber("macd", "signal")}
            />
            <NumberField
              label="RSI 周期"
              value={preferences.indicatorConfig.rsi.period}
              onChange={updateIndicatorNumber("rsi", "period")}
            />
            <NumberField
              label="KDJ 周期"
              value={preferences.indicatorConfig.kdj.period}
              onChange={updateIndicatorNumber("kdj", "period")}
            />
            <NumberField
              label="KDJ K 平滑"
              value={preferences.indicatorConfig.kdj.kSmoothing}
              onChange={updateIndicatorNumber("kdj", "kSmoothing")}
            />
            <NumberField
              label="KDJ D 平滑"
              value={preferences.indicatorConfig.kdj.dSmoothing}
              onChange={updateIndicatorNumber("kdj", "dSmoothing")}
            />
            <NumberField
              label="BOLL 周期"
              value={preferences.indicatorConfig.boll.period}
              onChange={updateIndicatorNumber("boll", "period")}
            />
            <NumberField
              label="BOLL 标准差"
              value={preferences.indicatorConfig.boll.standardDeviations}
              step="0.1"
              onChange={updateIndicatorNumber("boll", "standardDeviations")}
            />
            <NumberField
              label="ATR 周期"
              value={preferences.indicatorConfig.atr.period}
              onChange={updateIndicatorNumber("atr", "period")}
            />
          </div>
          <div className="color-grid">
            {preferences.indicatorConfig.ma.periods.map((period, index) => (
              <ColorField
                key={`ma-color-${period}`}
                label={`MA ${period} 颜色`}
                value={
                  preferences.indicatorConfig.ma.colors[index] ??
                  preferences.indicatorConfig.ma.colors[0]
                }
                onChange={(value) => {
                  const colors = [...preferences.indicatorConfig.ma.colors];
                  colors[index] = value;
                  patchIndicator("ma", { colors });
                }}
              />
            ))}
            <ColorField
              label="MACD DIF 颜色"
              value={preferences.indicatorConfig.macd.difColor}
              onChange={(value) => patchIndicator("macd", { difColor: value })}
            />
            <ColorField
              label="MACD DEA 颜色"
              value={preferences.indicatorConfig.macd.deaColor}
              onChange={(value) => patchIndicator("macd", { deaColor: value })}
            />
            <ColorField
              label="RSI 颜色"
              value={preferences.indicatorConfig.rsi.color}
              onChange={(value) => patchIndicator("rsi", { color: value })}
            />
            <ColorField
              label="KDJ K 颜色"
              value={preferences.indicatorConfig.kdj.kColor}
              onChange={(value) => patchIndicator("kdj", { kColor: value })}
            />
            <ColorField
              label="KDJ D 颜色"
              value={preferences.indicatorConfig.kdj.dColor}
              onChange={(value) => patchIndicator("kdj", { dColor: value })}
            />
            <ColorField
              label="KDJ J 颜色"
              value={preferences.indicatorConfig.kdj.jColor}
              onChange={(value) => patchIndicator("kdj", { jColor: value })}
            />
            <ColorField
              label="BOLL 中轨颜色"
              value={preferences.indicatorConfig.boll.middleColor}
              onChange={(value) =>
                patchIndicator("boll", { middleColor: value })
              }
            />
            <ColorField
              label="BOLL 上轨颜色"
              value={preferences.indicatorConfig.boll.upperColor}
              onChange={(value) =>
                patchIndicator("boll", { upperColor: value })
              }
            />
            <ColorField
              label="BOLL 下轨颜色"
              value={preferences.indicatorConfig.boll.lowerColor}
              onChange={(value) =>
                patchIndicator("boll", { lowerColor: value })
              }
            />
            <ColorField
              label="ATR 颜色"
              value={preferences.indicatorConfig.atr.color}
              onChange={(value) => patchIndicator("atr", { color: value })}
            />
            <ColorField
              label="均量颜色"
              value={preferences.indicatorConfig.volumeMa20.color}
              onChange={(value) =>
                patchIndicator("volumeMa20", { color: value })
              }
            />
          </div>
        </section>

        <section className="settings-card">
          <header>
            <div>
              <span>02</span>
              <h2>评分权重</h2>
            </div>
            <small>SCORE WEIGHTS</small>
          </header>
          <div className="weight-head">
            <span>分项</span>
            <span>原始值</span>
            <span>实际占比</span>
          </div>
          {(
            Object.entries(COMPONENT_LABELS) as Array<
              [keyof ScoreWeights, string]
            >
          ).map(([key, label]) => (
            <label className="weight-row" key={key}>
              <span>{label}</span>
              <input
                aria-label={`${label}原始权重`}
                min="0"
                step="1"
                type="number"
                value={preferences.scoreWeights[key]}
                onChange={updateWeight(key)}
              />
              <strong>{percentages?.[key]?.toFixed(2) ?? "—"}%</strong>
            </label>
          ))}
          <p className="normalization-note">
            <span>实际占比</span>
            原始权重会自动归一化为 100%，至少一项须大于 0。
          </p>
        </section>

        <div className="settings-actions">
          <span className={error ? "form-error" : "form-success"}>
            {error || message}
          </span>
          <button className="primary-button" type="submit">
            保存设置
          </button>
        </div>
      </form>
    </section>
  );
}

function NumberField({
  label,
  value,
  step,
  onChange,
}: {
  label: string;
  value: number;
  step?: string;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input type="number" step={step} value={value} onChange={onChange} />
    </label>
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input
        type="color"
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <code>{value}</code>
    </label>
  );
}

function LoadingState({ label }: { label: string }) {
  return (
    <section className="state-panel" aria-live="polite">
      <i className="loader" />
      <strong>{label}</strong>
    </section>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <section className="state-panel error-state" role="alert">
      <strong>{message}</strong>
      <Link to="/">返回扫描首页</Link>
    </section>
  );
}

function CacheLabel({
  status,
  updatedAt,
}: {
  status: "network" | "cache" | "stale";
  updatedAt: string;
}) {
  const labels = { network: "网络更新", cache: "缓存命中", stale: "旧缓存" };
  return (
    <span className={`cache-label ${status}`}>
      {labels[status]} {updatedAt}
    </span>
  );
}

function indicatorLabel(key: string): string {
  if (/^ma\d+$/.test(key)) return key.toUpperCase();
  const labels: Record<string, string> = {
    rsi14: "RSI14",
    macdDif: "MACD DIF",
    macdDea: "MACD DEA",
    macdHistogram: "MACD 柱",
    kdjK: "KDJ K",
    kdjD: "KDJ D",
    kdjJ: "KDJ J",
    bollMiddle: "BOLL 中轨",
    bollUpper: "BOLL 上轨",
    bollLower: "BOLL 下轨",
    atr14: "ATR14",
  };
  return labels[key] ?? key;
}

function toPublicComponent(category: string): ComponentName {
  return category === "volume_price"
    ? "volumePrice"
    : (category as ComponentName);
}

function directionClass(direction: string): string {
  if (direction === "偏多") return "bullish";
  if (direction === "偏空" || direction === "风险") return "bearish";
  return "neutral";
}

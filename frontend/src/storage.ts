import type { IndicatorConfig, ScoreWeights } from "./types";

export const STORAGE_KEY = "a-share-terminal:preferences";

export interface Preferences {
  version: 1;
  watchlist: string[];
  recent: string[];
  indicatorConfig: IndicatorConfig;
  scoreWeights: ScoreWeights;
}

export const DEFAULT_INDICATOR_CONFIG: IndicatorConfig = {
  ma: {
    enabled: true,
    periods: [5, 10, 20, 60],
    colors: [
      "#f6c85f",
      "#6f4eed",
      "#42c2ff",
      "#ef6f6c",
      "#8bd17c",
      "#b6992d",
      "#5f6b6d",
      "#d45087",
    ],
  },
  macd: {
    enabled: true,
    fast: 12,
    slow: 26,
    signal: 9,
    difColor: "#f6c85f",
    deaColor: "#42c2ff",
    positiveColor: "#ef5350",
    negativeColor: "#26a69a",
  },
  rsi: { enabled: true, period: 14, color: "#ab47bc" },
  kdj: {
    enabled: true,
    period: 9,
    kSmoothing: 3,
    dSmoothing: 3,
    kColor: "#f6c85f",
    dColor: "#42c2ff",
    jColor: "#ab47bc",
  },
  boll: {
    enabled: true,
    period: 20,
    standardDeviations: 2,
    middleColor: "#f6c85f",
    upperColor: "#ef5350",
    lowerColor: "#26a69a",
  },
  atr: { enabled: true, period: 14, color: "#ff9800" },
  volumeMa20: { enabled: true, color: "#42c2ff" },
};

export const DEFAULT_SCORE_WEIGHTS: ScoreWeights = {
  trend: 35,
  momentum: 25,
  volumePrice: 15,
  position: 15,
  risk: 10,
};

export function defaultPreferences(): Preferences {
  return {
    version: 1,
    watchlist: [],
    recent: [],
    indicatorConfig: structuredClone(DEFAULT_INDICATOR_CONFIG),
    scoreWeights: { ...DEFAULT_SCORE_WEIGHTS },
  };
}

export function loadPreferences(): Preferences {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw === null) {
    return defaultPreferences();
  }
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!isPreferences(parsed)) {
      return defaultPreferences();
    }
    return structuredClone(parsed);
  } catch {
    return defaultPreferences();
  }
}

export function savePreferences(preferences: Preferences): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
}

export function addWatchlistSymbol(
  preferences: Preferences,
  symbol: string,
): Preferences {
  if (!isSymbol(symbol) || preferences.watchlist.includes(symbol)) {
    return preferences;
  }
  return {
    ...preferences,
    watchlist: [...preferences.watchlist, symbol].slice(0, 20),
  };
}

export function addRecentSymbol(
  preferences: Preferences,
  symbol: string,
): Preferences {
  if (!isSymbol(symbol)) {
    return preferences;
  }
  return {
    ...preferences,
    recent: [
      symbol,
      ...preferences.recent.filter((candidate) => candidate !== symbol),
    ].slice(0, 20),
  };
}

export function removeWatchlistSymbol(
  preferences: Preferences,
  symbol: string,
): Preferences {
  return {
    ...preferences,
    watchlist: preferences.watchlist.filter(
      (candidate) => candidate !== symbol,
    ),
  };
}

function isSymbol(value: unknown): value is string {
  return typeof value === "string" && /^\d{6}$/.test(value);
}

function isPreferences(value: unknown): value is Preferences {
  if (!isRecord(value)) return false;
  return (
    value.version === 1 &&
    isSymbolList(value.watchlist) &&
    isSymbolList(value.recent) &&
    isIndicatorConfig(value.indicatorConfig) &&
    isScoreWeights(value.scoreWeights)
  );
}

function isIndicatorConfig(value: unknown): value is IndicatorConfig {
  if (!isRecord(value)) return false;
  const { ma, macd, rsi, kdj, boll, atr, volumeMa20 } = value;
  return (
    isRecord(ma) &&
    typeof ma.enabled === "boolean" &&
    isIntegerList(ma.periods, 1, 8, 2, 250) &&
    new Set(ma.periods).size === ma.periods.length &&
    isColorList(ma.colors, 1, 8) &&
    isRecord(macd) &&
    typeof macd.enabled === "boolean" &&
    isInteger(macd.fast, 2, 250) &&
    isInteger(macd.slow, 2, 250) &&
    macd.fast < macd.slow &&
    isInteger(macd.signal, 1, 250) &&
    isHexColor(macd.difColor) &&
    isHexColor(macd.deaColor) &&
    isHexColor(macd.positiveColor) &&
    isHexColor(macd.negativeColor) &&
    isRecord(rsi) &&
    typeof rsi.enabled === "boolean" &&
    isInteger(rsi.period, 2, 100) &&
    isHexColor(rsi.color) &&
    isRecord(kdj) &&
    typeof kdj.enabled === "boolean" &&
    isInteger(kdj.period, 2, 100) &&
    isInteger(kdj.kSmoothing, 1, 20) &&
    isInteger(kdj.dSmoothing, 1, 20) &&
    isHexColor(kdj.kColor) &&
    isHexColor(kdj.dColor) &&
    isHexColor(kdj.jColor) &&
    isRecord(boll) &&
    typeof boll.enabled === "boolean" &&
    isInteger(boll.period, 2, 250) &&
    isFiniteInRange(boll.standardDeviations, 0.5, 5) &&
    isHexColor(boll.middleColor) &&
    isHexColor(boll.upperColor) &&
    isHexColor(boll.lowerColor) &&
    isRecord(atr) &&
    typeof atr.enabled === "boolean" &&
    isInteger(atr.period, 2, 100) &&
    isHexColor(atr.color) &&
    isRecord(volumeMa20) &&
    typeof volumeMa20.enabled === "boolean" &&
    isHexColor(volumeMa20.color)
  );
}

function isScoreWeights(value: unknown): value is ScoreWeights {
  if (!isRecord(value)) return false;
  const weights = [
    value.trend,
    value.momentum,
    value.volumePrice,
    value.position,
    value.risk,
  ];
  return (
    weights.every(
      (weight) =>
        typeof weight === "number" && Number.isFinite(weight) && weight >= 0,
    ) && weights.some((weight) => Number(weight) > 0)
  );
}

function isSymbolList(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length <= 20 &&
    value.every(isSymbol) &&
    new Set(value).size === value.length
  );
}

function isColorList(
  value: unknown,
  minimum: number,
  maximum: number,
): value is string[] {
  return (
    Array.isArray(value) &&
    value.length >= minimum &&
    value.length <= maximum &&
    value.every(isHexColor)
  );
}

function isIntegerList(
  value: unknown,
  minimumLength: number,
  maximumLength: number,
  minimumValue: number,
  maximumValue: number,
): value is number[] {
  return (
    Array.isArray(value) &&
    value.length >= minimumLength &&
    value.length <= maximumLength &&
    value.every((item) => isInteger(item, minimumValue, maximumValue))
  );
}

function isInteger(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  return (
    typeof value === "number" &&
    Number.isInteger(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function isFiniteInRange(
  value: unknown,
  minimum: number,
  maximum: number,
): value is number {
  return (
    typeof value === "number" &&
    Number.isFinite(value) &&
    value >= minimum &&
    value <= maximum
  );
}

function isHexColor(value: unknown): value is string {
  return typeof value === "string" && /^#[0-9a-f]{6}$/i.test(value);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

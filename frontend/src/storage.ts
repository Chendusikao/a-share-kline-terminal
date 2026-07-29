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
    const parsed = JSON.parse(raw) as Partial<Preferences>;
    if (
      parsed.version !== 1 ||
      !Array.isArray(parsed.watchlist) ||
      !Array.isArray(parsed.recent) ||
      parsed.indicatorConfig === undefined ||
      parsed.scoreWeights === undefined
    ) {
      return defaultPreferences();
    }
    return {
      ...defaultPreferences(),
      ...parsed,
      version: 1,
      watchlist: parsed.watchlist.filter(isSymbol).filter(unique).slice(0, 20),
      recent: parsed.recent.filter(isSymbol).filter(unique).slice(0, 20),
    };
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

function unique(value: string, index: number, values: string[]): boolean {
  return values.indexOf(value) === index;
}

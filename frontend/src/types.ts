export type AnalysisRange = "3m" | "6m" | "1y" | "3y" | "all";
export type ComponentName =
  "trend" | "momentum" | "volumePrice" | "position" | "risk";
export type CacheStatus = "network" | "cache" | "stale";

export interface Stock {
  symbol: string;
  name: string;
  exchange: "SH" | "SZ" | "BJ";
}

export interface Candle {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  amount: number | null;
}

export interface Evidence {
  metric: string;
  value: number | null;
  comparison: string;
  reference: number | null;
  description: string;
}

export interface ComponentScore {
  score: number | null;
  weight: number;
  evidence: Evidence[];
}

export type ComponentMap<T> = Partial<Record<ComponentName, T>>;

export interface Insight {
  category: Exclude<ComponentName, "volumePrice"> | "volume_price";
  direction: "偏多" | "偏空" | "中性" | "风险";
  summary: string;
  severity: "低" | "中" | "高";
  evidence: Evidence[];
}

export interface ScoreWeights {
  trend: number;
  momentum: number;
  volumePrice: number;
  position: number;
  risk: number;
}

export interface IndicatorConfig {
  ma: { enabled: boolean; periods: number[]; colors: string[] };
  macd: {
    enabled: boolean;
    fast: number;
    slow: number;
    signal: number;
    difColor: string;
    deaColor: string;
    positiveColor: string;
    negativeColor: string;
  };
  rsi: { enabled: boolean; period: number; color: string };
  kdj: {
    enabled: boolean;
    period: number;
    kSmoothing: number;
    dSmoothing: number;
    kColor: string;
    dColor: string;
    jColor: string;
  };
  boll: {
    enabled: boolean;
    period: number;
    standardDeviations: number;
    middleColor: string;
    upperColor: string;
    lowerColor: string;
  };
  atr: { enabled: boolean; period: number; color: string };
  volumeMa20: { enabled: boolean; color: string };
}

export interface AnalysisResponse {
  stock: Stock;
  marketDate: string;
  candles: Candle[];
  indicators: {
    dates: string[];
    series: Record<
      string,
      { values: Array<number | null>; reasons: Array<string | null> }
    >;
  };
  score: {
    available: boolean;
    reason: string | null;
    totalScore: number | null;
    grade: "弱" | "偏弱" | "中性" | "偏强" | "强" | null;
    breakdown: ComponentMap<ComponentScore>;
    effectiveWeights: ComponentMap<number>;
  };
  insights: Insight[];
  cache: { status: CacheStatus; updatedAt: string };
  warnings: Array<{ code: string; message: string }>;
}

export interface ScanResult {
  symbol: string;
  score: number | null;
  grade: "弱" | "偏弱" | "中性" | "偏强" | "强" | null;
  breakdown: ComponentMap<ComponentScore> | null;
  insights: Insight[] | null;
  dataStatus: CacheStatus | "error";
  errorCode: string | null;
  scoreChange: number | null;
}

export interface ScanError {
  symbol: string;
  code: string;
  message: string;
}

export interface ScanStatus {
  scanId: string;
  status: "pending" | "running" | "completed" | "failed";
  completedCount: number;
  totalCount: number;
  marketDate: string | null;
  results: ScanResult[];
  errors: ScanError[];
}

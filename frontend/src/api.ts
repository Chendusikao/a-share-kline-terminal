import type {
  AnalysisRange,
  AnalysisResponse,
  IndicatorConfig,
  ScoreWeights,
  ScanStatus,
  Stock,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly retryable: boolean,
  ) {
    super(message);
  }
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const payload = (await response.json()) as {
    error?: { message?: string; code?: string; retryable?: boolean };
  };
  if (!response.ok) {
    throw new ApiError(
      payload.error?.message ?? "服务请求失败",
      payload.error?.code ?? "DATA_UNAVAILABLE",
      payload.error?.retryable ?? false,
    );
  }
  return payload as T;
}

export interface MarketStatus {
  marketDate: string | null;
  status: "preOpen" | "open" | "middayBreak" | "closed" | "unavailable";
  isOpen: boolean;
  isTradingDay: boolean;
}

export function getMarketStatus(): Promise<MarketStatus> {
  return requestJson("/api/v1/market/status");
}

export function searchStocks(query: string): Promise<{
  stocks: Stock[];
  updatedAt: string;
  stale: boolean;
}> {
  return requestJson(
    `/api/v1/stocks/search?q=${encodeURIComponent(query)}&limit=8`,
  );
}

export function getAnalysis(input: {
  symbol: string;
  range: AnalysisRange;
  forceRefresh: boolean;
  indicatorConfig: IndicatorConfig;
  scoreWeights: ScoreWeights;
}): Promise<AnalysisResponse> {
  return requestJson("/api/v1/analysis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function startScan(input: {
  symbols: string[];
  indicatorConfig: IndicatorConfig;
  scoreWeights: ScoreWeights;
  forceRefresh: boolean;
}): Promise<{ scanId: string }> {
  return requestJson("/api/v1/scans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function getScan(scanId: string): Promise<ScanStatus> {
  return requestJson(`/api/v1/scans/${encodeURIComponent(scanId)}`);
}

export function getLatestScan(): Promise<ScanStatus> {
  return requestJson("/api/v1/scans/latest");
}

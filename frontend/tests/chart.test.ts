import { describe, expect, it } from "vitest";

import { buildKlineOption } from "../src/chart";
import type { AnalysisResponse } from "../src/types";

const analysis: AnalysisResponse = {
  stock: { symbol: "000001", name: "平安银行", exchange: "SZ" },
  marketDate: "2026-07-29",
  candles: [
    {
      date: "2026-07-28",
      open: 10,
      close: 11,
      low: 9.5,
      high: 11.5,
      volume: 1000,
      amount: 10000,
    },
    {
      date: "2026-07-29",
      open: 11,
      close: 10.5,
      low: 10,
      high: 11.2,
      volume: 900,
      amount: 9000,
    },
  ],
  indicators: {
    dates: ["2026-07-28", "2026-07-29"],
    series: {
      ma20: { values: [10.2, 10.3], reasons: [null, null] },
      rsi14: { values: [55, 52], reasons: [null, null] },
    },
  },
  score: {
    available: true,
    reason: null,
    totalScore: 68,
    grade: "强",
    breakdown: {},
    effectiveWeights: {},
  },
  insights: [],
  cache: { status: "network", updatedAt: "2026-07-29" },
  warnings: [],
};

describe("K-line option mapping", () => {
  it("maps OHLC in ECharts order and enables terminal interactions", () => {
    const option = buildKlineOption(analysis, {
      overlays: ["ma20"],
      oscillator: "rsi14",
    });

    expect(option.xAxis[0].data).toEqual(["2026-07-28", "2026-07-29"]);
    expect(option.series[0].data).toEqual([
      [10, 11, 9.5, 11.5],
      [11, 10.5, 10, 11.2],
    ]);
    expect(option.axisPointer.link).toEqual([{ xAxisIndex: "all" }]);
    expect(option.dataZoom).toHaveLength(2);
    expect(option.tooltip.trigger).toBe("axis");
  });

  it("adds selected overlays and one oscillator without inventing signals", () => {
    const option = buildKlineOption(analysis, {
      overlays: ["ma20"],
      oscillator: "rsi14",
    });

    expect(option.series.map((series) => series.name)).toEqual([
      "日 K",
      "成交量",
      "MA20",
      "RSI14",
    ]);
    expect(option.series[2].data).toEqual([10.2, 10.3]);
  });
});

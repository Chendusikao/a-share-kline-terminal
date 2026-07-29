import { describe, expect, it } from "vitest";

import { buildKlineOption } from "../src/chart";
import { DEFAULT_INDICATOR_CONFIG } from "../src/storage";
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
    const option = buildKlineOption(
      analysis,
      {
        overlays: ["ma20"],
        oscillator: "rsi14",
      },
      DEFAULT_INDICATOR_CONFIG,
    );

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
    const option = buildKlineOption(
      analysis,
      {
        overlays: ["ma20"],
        oscillator: "rsi14",
      },
      DEFAULT_INDICATOR_CONFIG,
    );

    expect(option.series.map((series) => series.name)).toEqual([
      "日 K",
      "成交量",
      "MA20",
      "RSI14",
    ]);
    expect(option.series[2].data).toEqual([10.2, 10.3]);
  });

  it("maps persisted indicator colors onto every supported series family", () => {
    const configured = structuredClone(DEFAULT_INDICATOR_CONFIG);
    configured.ma.colors[2] = "#112233";
    configured.rsi.color = "#223344";
    configured.kdj.kColor = "#334455";
    configured.boll.upperColor = "#445566";
    configured.macd.difColor = "#556677";
    configured.atr.color = "#667788";
    analysis.indicators.series = {
      ma20: { values: [1, 2], reasons: [null, null] },
      rsi14: { values: [1, 2], reasons: [null, null] },
      kdjK: { values: [1, 2], reasons: [null, null] },
      bollUpper: { values: [1, 2], reasons: [null, null] },
      macdDif: { values: [1, 2], reasons: [null, null] },
      atr14: { values: [1, 2], reasons: [null, null] },
    };

    const option = buildKlineOption(
      analysis,
      {
        overlays: ["ma20", "bollUpper"],
        oscillator: "rsi14",
      },
      configured,
    );
    const colorOf = (name: string) =>
      option.series.find((series) => series.name === name)?.lineStyle?.color;

    expect(colorOf("MA20")).toBe("#112233");
    expect(colorOf("BOLL 上轨")).toBe("#445566");
    expect(colorOf("RSI14")).toBe("#223344");
    expect(
      buildKlineOption(
        analysis,
        { overlays: [], oscillator: "kdjK" },
        configured,
      ).series.find((series) => series.name === "KDJ K")?.lineStyle?.color,
    ).toBe("#334455");
    expect(
      buildKlineOption(
        analysis,
        { overlays: [], oscillator: "macdDif" },
        configured,
      ).series.find((series) => series.name === "MACD DIF")?.lineStyle?.color,
    ).toBe("#556677");
    expect(
      buildKlineOption(
        analysis,
        { overlays: [], oscillator: "atr14" },
        configured,
      ).series.find((series) => series.name === "ATR14")?.lineStyle?.color,
    ).toBe("#667788");
  });

  it("colors MACD histogram bars by their positive or negative sign", () => {
    const configured = structuredClone(DEFAULT_INDICATOR_CONFIG);
    configured.macd.positiveColor = "#aa1122";
    configured.macd.negativeColor = "#11aa88";
    analysis.indicators.series = {
      macdHistogram: { values: [1, -1, 0], reasons: [null, null, null] },
    };

    const option = buildKlineOption(
      analysis,
      { overlays: [], oscillator: "macdHistogram" },
      configured,
    );
    const histogram = option.series.find((series) => series.name === "MACD");
    const color = histogram?.itemStyle?.color;

    expect(histogram?.type).toBe("bar");
    expect(typeof color).toBe("function");
    if (typeof color !== "function") throw new Error("missing color callback");
    expect(color({ value: 1 })).toBe("#aa1122");
    expect(color({ value: 0 })).toBe("#aa1122");
    expect(color({ value: -1 })).toBe("#11aa88");
  });
});

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
      rsi: { values: [55, 52], reasons: [null, null] },
      volumeMa20: { values: [950, 975], reasons: [null, null] },
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
        oscillator: "rsi",
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
        oscillator: "rsi",
      },
      DEFAULT_INDICATOR_CONFIG,
    );

    expect(option.series.map((series) => series.name)).toEqual([
      "日 K",
      "成交量",
      "MA20",
      "20 日均量",
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
      rsi: { values: [1, 2], reasons: [null, null] },
      kdjK: { values: [1, 2], reasons: [null, null] },
      bollUpper: { values: [1, 2], reasons: [null, null] },
      macdDif: { values: [1, 2], reasons: [null, null] },
      atr: { values: [1, 2], reasons: [null, null] },
    };

    const option = buildKlineOption(
      analysis,
      {
        overlays: ["ma20", "bollUpper"],
        oscillator: "rsi",
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
        { overlays: [], oscillator: "atr" },
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

  it("uses the canonical API keys and suppresses every disabled indicator family", () => {
    const configured = structuredClone(DEFAULT_INDICATOR_CONFIG);
    configured.ma.enabled = false;
    configured.macd.enabled = false;
    configured.rsi.enabled = false;
    configured.kdj.enabled = false;
    configured.boll.enabled = false;
    configured.atr.enabled = false;
    configured.volumeMa20.enabled = false;
    analysis.indicators.series = {
      ma20: { values: [1, 2], reasons: [null, null] },
      macdDif: { values: [1, 2], reasons: [null, null] },
      rsi: { values: [50, 51], reasons: [null, null] },
      kdjK: { values: [1, 2], reasons: [null, null] },
      bollMiddle: { values: [1, 2], reasons: [null, null] },
      atr: { values: [1, 2], reasons: [null, null] },
      volumeMa20: { values: [900, 950], reasons: [null, null] },
    };

    for (const oscillator of ["macdDif", "rsi", "kdjK", "atr"]) {
      const option = buildKlineOption(
        analysis,
        { overlays: ["ma20", "bollMiddle"], oscillator },
        configured,
      );
      expect(option.series.map((series) => series.name)).toEqual([
        "日 K",
        "成交量",
      ]);
    }
  });

  it("emphasizes the indicator selected by an evidence locator", () => {
    analysis.indicators.series = {
      ma20: { values: [1, 2], reasons: [null, null] },
    };

    const option = buildKlineOption(
      analysis,
      { overlays: ["ma20"], oscillator: "", focusIndicator: "ma20" },
      DEFAULT_INDICATOR_CONFIG,
    );
    const ma = option.series.find((series) => series.name === "MA20");

    expect(ma?.lineStyle?.width).toBe(2.8);
    expect(ma?.z).toBe(4);
  });

  it("keeps canonical RSI and ATR keys while labels follow configured periods", () => {
    const configured = structuredClone(DEFAULT_INDICATOR_CONFIG);
    configured.rsi.period = 21;
    configured.atr.period = 7;
    analysis.indicators.series = {
      rsi: { values: [50, 51], reasons: [null, null] },
      atr: { values: [1, 2], reasons: [null, null] },
    };

    expect(
      buildKlineOption(
        analysis,
        { overlays: [], oscillator: "rsi" },
        configured,
      ).series.at(-1)?.name,
    ).toBe("RSI21");
    expect(
      buildKlineOption(
        analysis,
        { overlays: [], oscillator: "atr" },
        configured,
      ).series.at(-1)?.name,
    ).toBe("ATR7");
  });
});

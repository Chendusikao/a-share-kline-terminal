import type { AnalysisResponse } from "./types";

export interface ChartSelection {
  overlays: string[];
  oscillator: string;
}

interface TerminalSeries {
  name: string;
  type: string;
  data: unknown[];
  [key: string]: unknown;
}

export interface TerminalChartOption {
  xAxis: Array<{ data: string[]; [key: string]: unknown }>;
  series: TerminalSeries[];
  axisPointer: {
    link: Array<{ xAxisIndex: string }>;
    [key: string]: unknown;
  };
  dataZoom: unknown[];
  tooltip: { trigger: string; [key: string]: unknown };
  [key: string]: unknown;
}

export function buildKlineOption(
  analysis: AnalysisResponse,
  selection: ChartSelection,
): TerminalChartOption {
  const dates = analysis.candles.map((candle) => candle.date);
  const overlaySeries = selection.overlays.flatMap((key) => {
    const indicator = analysis.indicators.series[key];
    return indicator === undefined
      ? []
      : [
          {
            name: displayIndicatorName(key),
            type: "line",
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: indicator.values,
            showSymbol: false,
            connectNulls: false,
            lineStyle: { width: 1.2 },
          },
        ];
  });
  const oscillator = analysis.indicators.series[selection.oscillator];
  const oscillatorSeries =
    oscillator === undefined
      ? []
      : [
          {
            name: displayIndicatorName(selection.oscillator),
            type: "line",
            xAxisIndex: 2,
            yAxisIndex: 2,
            data: oscillator.values,
            showSymbol: false,
            connectNulls: false,
            lineStyle: { width: 1.2 },
          },
        ];

  return {
    animation: false,
    backgroundColor: "transparent",
    legend: {
      top: 0,
      textStyle: { color: "#8996a8", fontFamily: "IBM Plex Mono" },
    },
    axisPointer: {
      link: [{ xAxisIndex: "all" }],
      label: { backgroundColor: "#243146" },
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
      backgroundColor: "rgba(10, 15, 23, .96)",
      borderColor: "#2b3a50",
      textStyle: { color: "#e6edf7" },
    },
    grid: [
      { left: 62, right: 18, top: 42, height: "52%" },
      { left: 62, right: 18, top: "63%", height: "11%" },
      { left: 62, right: 18, top: "78%", height: "14%" },
    ],
    xAxis: [0, 1, 2].map((gridIndex) => ({
      type: "category",
      gridIndex,
      data: dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: "#263246" } },
      axisLabel: {
        color: "#68778d",
        show: gridIndex === 2,
        hideOverlap: true,
      },
      splitLine: { show: false },
    })),
    yAxis: [0, 1, 2].map((gridIndex) => ({
      scale: true,
      gridIndex,
      position: "right",
      axisLabel: { color: "#68778d" },
      splitLine: { lineStyle: { color: "#182230" } },
    })),
    dataZoom: [
      {
        type: "inside",
        xAxisIndex: [0, 1, 2],
        start: Math.max(0, 100 - (120 / Math.max(dates.length, 1)) * 100),
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: "slider",
        xAxisIndex: [0, 1, 2],
        bottom: 4,
        height: 18,
        borderColor: "#263246",
        fillerColor: "rgba(48, 127, 226, .18)",
        backgroundColor: "#101720",
        textStyle: { color: "#68778d" },
      },
    ],
    series: [
      {
        name: "日 K",
        type: "candlestick",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: analysis.candles.map((candle) => [
          candle.open,
          candle.close,
          candle.low,
          candle.high,
        ]),
        itemStyle: {
          color: "#ef5350",
          color0: "#26a69a",
          borderColor: "#ef5350",
          borderColor0: "#26a69a",
        },
      },
      {
        name: "成交量",
        type: "bar",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: analysis.candles.map((candle) => candle.volume),
        itemStyle: { color: "#49617d" },
      },
      ...overlaySeries,
      ...oscillatorSeries,
    ],
  };
}

function displayIndicatorName(key: string): string {
  if (/^ma\d+$/.test(key)) {
    return key.toUpperCase();
  }
  const labels: Record<string, string> = {
    rsi14: "RSI14",
    macdDif: "MACD DIF",
    macdDea: "MACD DEA",
    macdHistogram: "MACD",
    kdjK: "KDJ K",
    kdjD: "KDJ D",
    kdjJ: "KDJ J",
    atr14: "ATR14",
    bollMiddle: "BOLL 中轨",
    bollUpper: "BOLL 上轨",
    bollLower: "BOLL 下轨",
  };
  return labels[key] ?? key;
}

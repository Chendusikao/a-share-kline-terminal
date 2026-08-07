import type { AnalysisResponse, IndicatorConfig } from "./types";
import { indicatorLabel, isIndicatorSeriesEnabled } from "./indicator-contract";

export interface ChartSelection {
  overlays: string[];
  oscillator: string;
  focusIndicator?: string | null;
}

interface TerminalSeries {
  name: string;
  type: string;
  data: unknown[];
  lineStyle?: { color?: string; width?: number };
  itemStyle?: {
    color?: string | ((params: { value: unknown }) => string);
    [key: string]: unknown;
  };
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
  indicatorConfig: IndicatorConfig,
): TerminalChartOption {
  const dates = analysis.candles.map((candle) => candle.date);
  const overlaySeries = selection.overlays.flatMap((key) => {
    const indicator = analysis.indicators.series[key];
    return indicator === undefined ||
      !isIndicatorSeriesEnabled(key, indicatorConfig)
      ? []
      : [
          {
            name: indicatorLabel(key, indicatorConfig),
            type: "line",
            xAxisIndex: 0,
            yAxisIndex: 0,
            data: indicator.values,
            showSymbol: false,
            connectNulls: false,
            lineStyle: {
              color: indicatorColor(key, indicatorConfig),
              width: selection.focusIndicator === key ? 2.8 : 1.2,
            },
            z: selection.focusIndicator === key ? 4 : 2,
          },
        ];
  });
  const oscillator = analysis.indicators.series[selection.oscillator];
  const oscillatorSeries =
    oscillator === undefined ||
    !isIndicatorSeriesEnabled(selection.oscillator, indicatorConfig)
      ? []
      : selection.oscillator === "macdHistogram"
        ? [
            {
              name: indicatorLabel(selection.oscillator, indicatorConfig),
              type: "bar",
              xAxisIndex: 2,
              yAxisIndex: 2,
              data: oscillator.values,
              itemStyle: {
                opacity:
                  selection.focusIndicator === selection.oscillator ? 1 : 0.72,
                color: ({ value }: { value: unknown }) =>
                  typeof value === "number" && value < 0
                    ? indicatorConfig.macd.negativeColor
                    : indicatorConfig.macd.positiveColor,
              },
              z: selection.focusIndicator === selection.oscillator ? 4 : 2,
            },
          ]
        : [
            {
              name: indicatorLabel(selection.oscillator, indicatorConfig),
              type: "line",
              xAxisIndex: 2,
              yAxisIndex: 2,
              data: oscillator.values,
              showSymbol: false,
              connectNulls: false,
              lineStyle: {
                color: indicatorColor(selection.oscillator, indicatorConfig),
                width:
                  selection.focusIndicator === selection.oscillator ? 2.8 : 1.2,
              },
              z: selection.focusIndicator === selection.oscillator ? 4 : 2,
            },
          ];
  const volumeMa = analysis.indicators.series.volumeMa20;
  const volumeMaSeries =
    volumeMa !== undefined && indicatorConfig.volumeMa20.enabled
      ? [
          {
            name: indicatorLabel("volumeMa20", indicatorConfig),
            type: "line",
            xAxisIndex: 1,
            yAxisIndex: 1,
            data: volumeMa.values,
            showSymbol: false,
            connectNulls: false,
            lineStyle: {
              color: indicatorConfig.volumeMa20.color,
              width: selection.focusIndicator === "volumeMa20" ? 2.8 : 1.2,
            },
            z: selection.focusIndicator === "volumeMa20" ? 4 : 2,
          },
        ]
      : [];

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
      ...volumeMaSeries,
      ...oscillatorSeries,
    ],
  };
}

function indicatorColor(
  key: string,
  config: IndicatorConfig,
): string | undefined {
  const maMatch = /^ma(\d+)$/.exec(key);
  if (maMatch !== null) {
    const period = Number(maMatch[1]);
    const index = config.ma.periods.indexOf(period);
    return index >= 0 ? config.ma.colors[index] : undefined;
  }
  const colors: Record<string, string> = {
    macdDif: config.macd.difColor,
    macdDea: config.macd.deaColor,
    macdHistogram: config.macd.positiveColor,
    kdjK: config.kdj.kColor,
    kdjD: config.kdj.dColor,
    kdjJ: config.kdj.jColor,
    bollMiddle: config.boll.middleColor,
    bollUpper: config.boll.upperColor,
    bollLower: config.boll.lowerColor,
    volumeMa20: config.volumeMa20.color,
  };
  if (key === "rsi") return config.rsi.color;
  if (key === "atr") return config.atr.color;
  return colors[key];
}

import type { IndicatorConfig } from "./types";

// Canonical public series keys from POST /api/v1/analysis:
// ma{period}, macdDif/macdDea/macdHistogram, rsi, kdjK/kdjD/kdjJ,
// bollMiddle/bollUpper/bollLower, atr, and volumeMa20.
const MACD_KEYS = ["macdDif", "macdDea", "macdHistogram"] as const;
const KDJ_KEYS = ["kdjK", "kdjD", "kdjJ"] as const;
const BOLL_KEYS = ["bollMiddle", "bollUpper", "bollLower"] as const;

export interface IndicatorPresentation {
  overlays: string[];
  oscillators: string[];
}

/** Map backend evidence names to the closest visible chart series. */
export function metricToIndicatorKey(metric: string): string | null {
  const normalized = metric.toLowerCase();
  const compact = normalized.replace(/[^a-z0-9\u4e00-\u9fff]/g, "");
  const maMatch = /(?:^|[^a-z])ma[_-]?(\d+)/i.exec(metric);
  if (maMatch !== null) return `ma${maMatch[1]}`;
  if (compact.includes("macdhist") || compact.includes("macd柱"))
    return "macdHistogram";
  if (compact.includes("macddif")) return "macdDif";
  if (compact.includes("macddea")) return "macdDea";
  if (compact.includes("macd")) return "macdDif";
  if (compact.includes("rsi")) return "rsi";
  if (compact.includes("kdjk")) return "kdjK";
  if (compact.includes("kdjd")) return "kdjD";
  if (compact.includes("kdjj")) return "kdjJ";
  if (compact.includes("boll") || compact.includes("布林")) return "bollMiddle";
  if (compact.includes("atr")) return "atr";
  if (
    compact.includes("volume") ||
    compact.includes("成交量") ||
    compact.includes("均量")
  )
    return "volumeMa20";
  if (
    compact.includes("position") ||
    compact.includes("price") ||
    compact.includes("support") ||
    compact.includes("resistance")
  )
    return "ma20";
  return null;
}

export function indicatorPresentation(
  config: IndicatorConfig,
): IndicatorPresentation {
  const overlays = [
    ...(config.ma.enabled
      ? config.ma.periods.map((period) => `ma${period}`)
      : []),
    ...(config.boll.enabled ? BOLL_KEYS : []),
  ];
  const oscillators = [
    ...(config.rsi.enabled ? ["rsi"] : []),
    ...(config.macd.enabled ? MACD_KEYS : []),
    ...(config.kdj.enabled ? KDJ_KEYS : []),
    ...(config.atr.enabled ? ["atr"] : []),
  ];
  return { overlays, oscillators };
}

export function isIndicatorSeriesEnabled(
  key: string,
  config: IndicatorConfig,
): boolean {
  if (/^ma\d+$/.test(key)) return config.ma.enabled;
  if ((MACD_KEYS as readonly string[]).includes(key))
    return config.macd.enabled;
  if (key === "rsi") return config.rsi.enabled;
  if ((KDJ_KEYS as readonly string[]).includes(key)) return config.kdj.enabled;
  if ((BOLL_KEYS as readonly string[]).includes(key))
    return config.boll.enabled;
  if (key === "atr") return config.atr.enabled;
  if (key === "volumeMa20") return config.volumeMa20.enabled;
  return false;
}

export function indicatorLabel(key: string, config: IndicatorConfig): string {
  if (/^ma\d+$/.test(key)) return key.toUpperCase();
  const labels: Record<string, string> = {
    rsi: `RSI${config.rsi.period}`,
    macdDif: "MACD DIF",
    macdDea: "MACD DEA",
    macdHistogram: "MACD",
    kdjK: "KDJ K",
    kdjD: "KDJ D",
    kdjJ: "KDJ J",
    atr: `ATR${config.atr.period}`,
    bollMiddle: "BOLL 中轨",
    bollUpper: "BOLL 上轨",
    bollLower: "BOLL 下轨",
    volumeMa20: "20 日均量",
  };
  return labels[key] ?? key;
}

import {
  DEFAULT_INDICATOR_CONFIG,
  DEFAULT_SCORE_WEIGHTS,
  type Preferences,
} from "./storage";
import type { IndicatorConfig, ScoreWeights } from "./types";

export const ONBOARDING_STORAGE_KEY = "a-share-terminal:beginner-guide:v1";

export interface GlossaryEntry {
  key: string;
  title: string;
  summary: string;
  reading: string;
}

export const INDICATOR_GLOSSARY: readonly GlossaryEntry[] = [
  {
    key: "ma",
    title: "MA 均线",
    summary: "把一段时间的收盘价取平均，用来观察趋势方向。",
    reading: "价格在均线上方通常偏强，跌破均线说明趋势可能转弱。",
  },
  {
    key: "macd",
    title: "MACD",
    summary: "比较快慢指数移动平均线，观察趋势动能的变化。",
    reading: "DIF 上穿 DEA 是偏多信号，柱体变短表示动能正在减弱。",
  },
  {
    key: "rsi",
    title: "RSI 相对强弱",
    summary: "用 0–100 的数值衡量近期上涨和下跌的相对力度。",
    reading: "数值高不等于一定会跌，数值低也不等于一定会上涨。",
  },
  {
    key: "kdj",
    title: "KDJ",
    summary: "通过价格在近期高低区间的位置，观察短线节奏。",
    reading: "K、D、J 交叉适合做辅助判断，震荡行情中容易反复。",
  },
  {
    key: "boll",
    title: "BOLL 布林带",
    summary: "用中轨和上下轨描述价格的波动区间。",
    reading: "带宽变窄代表波动收缩，突破轨道后仍要结合成交量确认。",
  },
  {
    key: "atr",
    title: "ATR 波动幅度",
    summary: "衡量价格每天平均波动有多大，不判断涨跌方向。",
    reading: "ATR 越大，价格波动越剧烈，仓位和止损需要更谨慎。",
  },
  {
    key: "volume",
    title: "成交量与均量",
    summary: "成交量表示当天交易活跃度，均量用于做平滑对比。",
    reading: "放量突破比缩量突破更值得关注，但仍不能单独作为买卖依据。",
  },
] as const;

export type PresetId = "default" | "trend" | "swing" | "short";

interface PresetIndicatorFlags {
  ma: boolean;
  macd: boolean;
  rsi: boolean;
  kdj: boolean;
  boll: boolean;
  atr: boolean;
  volumeMa20: boolean;
}

export interface PresetDefinition {
  id: PresetId;
  label: string;
  description: string;
  maPeriods: number[];
  indicatorFlags: PresetIndicatorFlags;
  scoreWeights: ScoreWeights;
}

export const PRESET_DEFINITIONS: readonly PresetDefinition[] = [
  {
    id: "default",
    label: "默认均衡",
    description: "适合第一次打开项目，保留全部常用指标。",
    maPeriods: [...DEFAULT_INDICATOR_CONFIG.ma.periods],
    indicatorFlags: {
      ma: true,
      macd: true,
      rsi: true,
      kdj: true,
      boll: true,
      atr: true,
      volumeMa20: true,
    },
    scoreWeights: { ...DEFAULT_SCORE_WEIGHTS },
  },
  {
    id: "trend",
    label: "趋势观察",
    description: "突出均线、布林带和趋势评分，适合看大方向。",
    maPeriods: [5, 20, 60],
    indicatorFlags: {
      ma: true,
      macd: true,
      rsi: false,
      kdj: false,
      boll: true,
      atr: false,
      volumeMa20: true,
    },
    scoreWeights: {
      trend: 45,
      momentum: 15,
      volumePrice: 20,
      position: 15,
      risk: 5,
    },
  },
  {
    id: "swing",
    label: "波段观察",
    description: "兼顾趋势和动量，适合观察几周到几个月的节奏。",
    maPeriods: [5, 10, 20, 60],
    indicatorFlags: {
      ma: true,
      macd: true,
      rsi: true,
      kdj: false,
      boll: true,
      atr: true,
      volumeMa20: true,
    },
    scoreWeights: {
      trend: 30,
      momentum: 30,
      volumePrice: 20,
      position: 15,
      risk: 5,
    },
  },
  {
    id: "short",
    label: "短线入门",
    description: "减少干扰，聚焦短周期均线、MACD 和成交量。",
    maPeriods: [5, 10, 20],
    indicatorFlags: {
      ma: true,
      macd: true,
      rsi: false,
      kdj: true,
      boll: false,
      atr: true,
      volumeMa20: true,
    },
    scoreWeights: {
      trend: 25,
      momentum: 40,
      volumePrice: 20,
      position: 10,
      risk: 5,
    },
  },
] as const;

export function hasSeenOnboarding(): boolean {
  return localStorage.getItem(ONBOARDING_STORAGE_KEY) === "seen";
}

export function markOnboardingSeen(): void {
  localStorage.setItem(ONBOARDING_STORAGE_KEY, "seen");
}

export function applyPreset(
  preferences: Preferences,
  presetId: PresetId,
): Preferences {
  const preset = PRESET_DEFINITIONS.find(({ id }) => id === presetId);
  if (preset === undefined) return preferences;

  const indicatorConfig = structuredClone(
    preferences.indicatorConfig,
  ) as IndicatorConfig;
  for (const section of Object.keys(preset.indicatorFlags) as Array<
    keyof PresetIndicatorFlags
  >) {
    indicatorConfig[section].enabled = preset.indicatorFlags[section];
  }
  indicatorConfig.ma.periods = [...preset.maPeriods];

  return {
    ...preferences,
    indicatorConfig,
    scoreWeights: { ...preset.scoreWeights },
  };
}

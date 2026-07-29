import type { ScoreWeights } from "./types";

export function normalizeWeights(weights: ScoreWeights): ScoreWeights {
  const values = Object.values(weights);
  if (values.some((value) => !Number.isFinite(value) || value < 0)) {
    throw new Error("评分权重必须是非负数");
  }
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total === 0) {
    throw new Error("至少一项权重必须大于 0");
  }
  const percentage = (value: number) =>
    Number(((value / total) * 100).toFixed(2));
  return {
    trend: percentage(weights.trend),
    momentum: percentage(weights.momentum),
    volumePrice: percentage(weights.volumePrice),
    position: percentage(weights.position),
    risk: percentage(weights.risk),
  };
}

export function parseMaPeriods(value: string): number[] {
  const periods = value
    .split(/[,，\s]+/)
    .filter(Boolean)
    .map(Number);
  if (
    periods.length === 0 ||
    periods.length > 8 ||
    periods.some(
      (period) => !Number.isInteger(period) || period < 2 || period > 250,
    )
  ) {
    throw new Error("MA 周期须在 2–250 之间，最多 8 条");
  }
  if (new Set(periods).size !== periods.length) {
    throw new Error("MA 周期不得重复");
  }
  return periods;
}

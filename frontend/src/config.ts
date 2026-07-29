import type { ScoreWeights } from "./types";

export function normalizeWeights(weights: ScoreWeights): ScoreWeights {
  const keys = [
    "trend",
    "momentum",
    "volumePrice",
    "position",
    "risk",
  ] as const;
  const values = keys.map((key) => weights[key]);
  if (values.some((value) => !Number.isFinite(value) || value < 0)) {
    throw new Error("评分权重必须是非负数");
  }
  const total = values.reduce((sum, value) => sum + value, 0);
  if (total === 0) {
    throw new Error("至少一项权重必须大于 0");
  }
  const normalized = Object.fromEntries(
    keys.map((key) => [key, Number(((weights[key] / total) * 100).toFixed(2))]),
  ) as unknown as ScoreWeights;
  const lastPositive = [...keys].reverse().find((key) => weights[key] > 0);
  if (lastPositive === undefined) {
    throw new Error("至少一项权重必须大于 0");
  }
  normalized[lastPositive] = Number(
    (
      100 -
      keys
        .filter((key) => key !== lastPositive)
        .reduce((sum, key) => sum + normalized[key], 0)
    ).toFixed(2),
  );
  return normalized;
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

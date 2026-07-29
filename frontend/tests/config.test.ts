import { describe, expect, it } from "vitest";

import { normalizeWeights, parseMaPeriods } from "../src/config";

describe("settings helpers", () => {
  it("normalizes non-negative raw weights to percentages", () => {
    expect(
      normalizeWeights({
        trend: 35,
        momentum: 25,
        volumePrice: 15,
        position: 15,
        risk: 10,
      }),
    ).toEqual({
      trend: 35,
      momentum: 25,
      volumePrice: 15,
      position: 15,
      risk: 10,
    });
    expect(
      normalizeWeights({
        trend: 1,
        momentum: 1,
        volumePrice: 1,
        position: 1,
        risk: 1,
      }),
    ).toEqual({
      trend: 20,
      momentum: 20,
      volumePrice: 20,
      position: 20,
      risk: 20,
    });
    const rounded = normalizeWeights({
      trend: 1,
      momentum: 1,
      volumePrice: 1,
      position: 1,
      risk: 2,
    });
    expect(Object.values(rounded).reduce((sum, value) => sum + value, 0)).toBe(
      100,
    );
  });

  it("rejects all-zero weights and invalid MA periods", () => {
    expect(() =>
      normalizeWeights({
        trend: 0,
        momentum: 0,
        volumePrice: 0,
        position: 0,
        risk: 0,
      }),
    ).toThrow("至少一项权重必须大于 0");
    expect(() => parseMaPeriods("5, 20, 20")).toThrow("MA 周期不得重复");
    expect(() => parseMaPeriods("1, 20")).toThrow("MA 周期须在 2–250 之间");
  });
});

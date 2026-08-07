import { beforeEach, describe, expect, it } from "vitest";

import {
  applyPreset,
  hasSeenOnboarding,
  markOnboardingSeen,
  PRESET_DEFINITIONS,
} from "../src/beginner";
import { defaultPreferences } from "../src/storage";
import { metricToIndicatorKey } from "../src/indicator-contract";

describe("beginner mode helpers", () => {
  beforeEach(() => localStorage.clear());

  it("stores the onboarding decision locally", () => {
    expect(hasSeenOnboarding()).toBe(false);
    markOnboardingSeen();
    expect(hasSeenOnboarding()).toBe(true);
  });

  it("offers beginner-friendly presets that only change analysis settings", () => {
    const preferences = defaultPreferences();
    preferences.watchlist = ["000001"];
    preferences.recent = ["600000"];

    const short = applyPreset(preferences, "short");
    expect(short.indicatorConfig.ma.periods).toEqual([5, 10, 20]);
    expect(short.indicatorConfig.rsi.enabled).toBe(false);
    expect(short.indicatorConfig.kdj.enabled).toBe(true);
    expect(short.scoreWeights).toEqual(
      PRESET_DEFINITIONS.find(({ id }) => id === "short")?.scoreWeights,
    );
    expect(short.watchlist).toEqual(["000001"]);
    expect(short.recent).toEqual(["600000"]);
  });

  it("maps common backend evidence names to visible indicator series", () => {
    expect(metricToIndicatorKey("close_vs_ma20")).toBe("ma20");
    expect(metricToIndicatorKey("macd_histogram")).toBe("macdHistogram");
    expect(metricToIndicatorKey("kdj_k")).toBe("kdjK");
    expect(metricToIndicatorKey("backend_position_x")).toBe("ma20");
    expect(metricToIndicatorKey("unrelated_rule")).toBeNull();
  });
});

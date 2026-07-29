import { beforeEach, describe, expect, it } from "vitest";

import {
  STORAGE_KEY,
  addRecentSymbol,
  addWatchlistSymbol,
  loadPreferences,
  savePreferences,
} from "../src/storage";

describe("versioned local preferences", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("discards an unsupported persisted version", () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ version: 0, watchlist: ["000001"] }),
    );

    expect(loadPreferences().watchlist).toEqual([]);
  });

  it("persists configuration and restores it on the next load", () => {
    const preferences = loadPreferences();
    preferences.scoreWeights.trend = 48;
    preferences.indicatorConfig.ma.periods = [5, 20, 60];
    savePreferences(preferences);

    const restored = loadPreferences();
    expect(restored.version).toBe(1);
    expect(restored.scoreWeights.trend).toBe(48);
    expect(restored.indicatorConfig.ma.periods).toEqual([5, 20, 60]);
  });

  it("keeps at most 20 unique watchlist symbols", () => {
    let preferences = loadPreferences();
    for (let index = 0; index < 21; index += 1) {
      preferences = addWatchlistSymbol(
        preferences,
        String(index).padStart(6, "0"),
      );
    }

    expect(preferences.watchlist).toHaveLength(20);
    expect(preferences.watchlist[0]).toBe("000000");
    expect(preferences.watchlist).not.toContain("000020");
    expect(addWatchlistSymbol(preferences, "000001").watchlist).toHaveLength(
      20,
    );
  });

  it("orders recent symbols by latest visit and caps history at 20", () => {
    let preferences = loadPreferences();
    for (let index = 0; index < 21; index += 1) {
      preferences = addRecentSymbol(
        preferences,
        String(index).padStart(6, "0"),
      );
    }
    preferences = addRecentSymbol(preferences, "000010");

    expect(preferences.recent).toHaveLength(20);
    expect(preferences.recent[0]).toBe("000010");
    expect(preferences.recent).not.toContain("000000");
  });
});

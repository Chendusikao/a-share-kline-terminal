import { describe, expect, it } from "vitest";

import { sortScanRows } from "../src/scan";

describe("scan result ordering", () => {
  it("sorts available scores descending and keeps unavailable rows last", () => {
    const rows = sortScanRows([
      { symbol: "000001", score: 55 },
      { symbol: "600000", score: null },
      { symbol: "300750", score: 72 },
    ]);

    expect(rows.map((row) => row.symbol)).toEqual([
      "300750",
      "000001",
      "600000",
    ]);
  });
});

import { describe, expect, it } from "vitest";

import { shouldAutoStartScan, sortScanRows } from "../src/scan";

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

describe("automatic scan eligibility", () => {
  it("starts only after 16:00 when the market date is newer than the last completed scan", () => {
    const eligible = shouldAutoStartScan(
      {
        marketDate: "2026-07-30",
        status: "closed",
        isOpen: false,
        isTradingDay: true,
      },
      {
        scanId: "scan-old",
        status: "completed",
        completedCount: 1,
        totalCount: 1,
        marketDate: "2026-07-29",
        results: [],
        errors: [],
      },
      new Date("2026-07-30T08:01:00.000Z"),
    );
    const tooEarly = shouldAutoStartScan(
      {
        marketDate: "2026-07-30",
        status: "closed",
        isOpen: false,
        isTradingDay: true,
      },
      null,
      new Date("2026-07-30T07:59:00.000Z"),
    );

    expect(eligible).toBe(true);
    expect(tooEarly).toBe(false);
  });

  it("does not duplicate a completed or active scan for the same market date", () => {
    const market = {
      marketDate: "2026-07-30",
      status: "closed" as const,
      isOpen: false,
      isTradingDay: true,
    };
    const now = new Date("2026-07-30T09:00:00.000Z");

    expect(
      shouldAutoStartScan(
        market,
        {
          scanId: "same-day",
          status: "completed",
          completedCount: 1,
          totalCount: 1,
          marketDate: "2026-07-30",
          results: [],
          errors: [],
        },
        now,
      ),
    ).toBe(false);
    expect(
      shouldAutoStartScan(
        market,
        {
          scanId: "active",
          status: "running",
          completedCount: 0,
          totalCount: 1,
          marketDate: "2026-07-30",
          results: [],
          errors: [],
        },
        now,
      ),
    ).toBe(false);
  });

  it("does not auto scan a non-trading day even when the exchange date is older", () => {
    expect(
      shouldAutoStartScan(
        {
          marketDate: "2026-07-31",
          status: "closed",
          isOpen: false,
          isTradingDay: false,
        },
        null,
        new Date("2026-08-01T09:00:00.000Z"),
      ),
    ).toBe(false);
  });
});

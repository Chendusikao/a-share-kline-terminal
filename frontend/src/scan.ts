export interface SortableScanRow {
  symbol: string;
  score: number | null;
}

import type { MarketStatus } from "./api";
import type { ScanStatus } from "./types";

export function sortScanRows<T extends SortableScanRow>(rows: T[]): T[] {
  return [...rows].sort(
    (left, right) => (right.score ?? -1) - (left.score ?? -1),
  );
}

export function shouldAutoStartScan(
  market: MarketStatus,
  latest: ScanStatus | null,
  now = new Date(),
): boolean {
  if (market.marketDate === null || market.status !== "closed") return false;
  const hour = Number(
    new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      hourCycle: "h23",
      timeZone: "Asia/Shanghai",
    })
      .formatToParts(now)
      .find((part) => part.type === "hour")?.value ?? "-1",
  );
  if (hour < 16) return false;
  if (latest?.status === "pending" || latest?.status === "running")
    return false;
  return !(
    latest?.status === "completed" &&
    latest.marketDate !== null &&
    latest.marketDate >= market.marketDate
  );
}

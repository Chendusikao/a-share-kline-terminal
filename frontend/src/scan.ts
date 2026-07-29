export interface SortableScanRow {
  symbol: string;
  score: number | null;
}

export function sortScanRows<T extends SortableScanRow>(rows: T[]): T[] {
  return [...rows].sort(
    (left, right) => (right.score ?? -1) - (left.score ?? -1),
  );
}

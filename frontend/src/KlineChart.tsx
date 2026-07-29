import * as echarts from "echarts";
import { useEffect, useRef } from "react";

import { buildKlineOption, type ChartSelection } from "./chart";
import type { AnalysisResponse } from "./types";

export function KlineChart({
  analysis,
  selection,
}: {
  analysis: AnalysisResponse;
  selection: ChartSelection;
}) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (host.current === null) return;
    const chart = echarts.init(host.current, undefined, { renderer: "svg" });
    chart.setOption(buildKlineOption(analysis, selection));
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [analysis, selection]);

  return (
    <div
      ref={host}
      className="kline-chart"
      role="img"
      aria-label={`${analysis.stock.name} K 线、成交量与副图`}
    />
  );
}

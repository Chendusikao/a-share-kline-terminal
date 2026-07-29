import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import { STORAGE_KEY } from "../src/storage";
import type { AnalysisResponse } from "../src/types";

const analysis: AnalysisResponse = {
  stock: { symbol: "000001", name: "平安银行", exchange: "SZ" },
  marketDate: "2026-07-29",
  candles: Array.from({ length: 90 }, (_, index) => ({
    date: `2026-07-${String((index % 28) + 1).padStart(2, "0")}`,
    open: 10,
    close: 10.5,
    low: 9.8,
    high: 10.8,
    volume: 1000,
    amount: 10000,
  })),
  indicators: {
    dates: [],
    series: {
      ma20: {
        values: Array.from({ length: 90 }, () => 10.2),
        reasons: Array.from({ length: 90 }, () => null),
      },
      rsi14: {
        values: Array.from({ length: 90 }, () => 58),
        reasons: Array.from({ length: 90 }, () => null),
      },
    },
  },
  score: {
    available: true,
    reason: null,
    totalScore: 68,
    grade: "强",
    breakdown: {
      trend: { score: 80, weight: 35, evidence: [] },
      momentum: { score: 70, weight: 25, evidence: [] },
      volumePrice: { score: 60, weight: 15, evidence: [] },
      position: {
        score: 55,
        weight: 15,
        evidence: [
          {
            metric: "range_20",
            value: 82,
            comparison: "区间百分位",
            reference: 100,
            description: "收盘价位于近 20 日区间 82% 位置",
          },
        ],
      },
      risk: { score: 75, weight: 10, evidence: [] },
    },
    effectiveWeights: {
      trend: 35,
      momentum: 25,
      volumePrice: 15,
      position: 15,
      risk: 10,
    },
  },
  insights: [
    {
      category: "trend",
      direction: "偏多",
      summary: "价格运行在 MA20 上方",
      severity: "中",
      evidence: [],
    },
    {
      category: "momentum",
      direction: "中性",
      summary: "动量处于中性区间",
      severity: "低",
      evidence: [],
    },
  ],
  cache: { status: "cache", updatedAt: "2026-07-29" },
  warnings: [],
};

function renderApp(route = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function response(data: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(data),
  } as unknown as Response;
}

describe("App routes", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/market/status")) {
          return Promise.resolve(
            response({
              marketDate: "2026-07-29",
              status: "closed",
              isOpen: false,
              isTradingDay: true,
            }),
          );
        }
        if (url.includes("/analysis")) {
          return Promise.resolve(response(analysis));
        }
        return Promise.resolve(
          response({
            stocks: [{ symbol: "000001", name: "平安银行", exchange: "SZ" }],
            updatedAt: "2026-07-29",
            stale: false,
          }),
        );
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the scan home with a search, results columns and Task 6 boundary", async () => {
    renderApp();

    expect(
      screen.getByRole("heading", { name: "自选扫描" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("searchbox", { name: "搜索股票" })).toBeVisible();
    expect(screen.getByText("总分")).toBeInTheDocument();
    expect(screen.getByText("较上次")).toBeInTheDocument();
    expect(screen.getByText("关键信号")).toBeInTheDocument();
    expect(screen.getByText("行情日期")).toBeInTheDocument();
    expect(screen.getByText("缓存状态")).toBeInTheDocument();
    expect(screen.getByText("扫描服务将在 Task 6 接入")).toBeInTheDocument();
    expect(await screen.findByText("2026-07-29")).toBeInTheDocument();
  });

  it("loads a stock analysis, shows score evidence, and persists watchlist", async () => {
    renderApp("/stocks/000001");

    expect(
      await screen.findByRole("heading", { name: "平安银行" }),
    ).toBeInTheDocument();
    expect(screen.getByText("68")).toBeInTheDocument();
    expect(screen.getByText("强")).toBeInTheDocument();
    expect(screen.getByText("价格运行在 MA20 上方")).toBeInTheDocument();
    expect(screen.getByText("近 20 日区间 82%")).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "平安银行 K 线、成交量与副图" }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "加入自选" }));
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored.watchlist).toEqual(["000001"]);
    expect(stored.recent).toEqual(["000001"]);

    const analysisCall = vi
      .mocked(fetch)
      .mock.calls.find(([url]) => String(url).endsWith("/api/v1/analysis"));
    expect(JSON.parse(String(analysisCall?.[1]?.body))).toMatchObject({
      symbol: "000001",
      range: "3y",
      forceRefresh: false,
    });
  });

  it("switches analysis range and exposes overlays and oscillator controls", async () => {
    renderApp("/stocks/000001");
    await screen.findByRole("heading", { name: "平安银行" });

    fireEvent.click(screen.getByRole("button", { name: "近 6 月" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "MA20" }));
    fireEvent.change(screen.getByLabelText("副图指标"), {
      target: { value: "rsi14" },
    });

    await waitFor(() => {
      const requestBodies = vi
        .mocked(fetch)
        .mock.calls.filter(([url]) => String(url).endsWith("/api/v1/analysis"))
        .map(([, init]) => JSON.parse(String(init?.body)));
      expect(requestBodies.some((body) => body.range === "6m")).toBe(true);
    });
  });

  it("validates and saves settings with visible effective percentages", () => {
    renderApp("/settings");

    expect(
      screen.getByRole("heading", { name: "分析参数" }),
    ).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("MA 周期"), {
      target: { value: "5, 20, 60" },
    });
    fireEvent.change(screen.getByLabelText("趋势原始权重"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("动量原始权重"), {
      target: { value: "1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存设置" }));

    expect(screen.getByText("设置已保存")).toBeInTheDocument();
    expect(screen.getAllByText("实际占比")).toHaveLength(2);
    expect(localStorage.getItem(STORAGE_KEY)).toContain('"periods":[5,20,60]');
  });

  it("persists indicator visibility, colors, and the full built-in parameters", () => {
    renderApp("/settings");

    fireEvent.click(screen.getByRole("checkbox", { name: "显示 RSI" }));
    fireEvent.change(screen.getByLabelText("RSI 颜色"), {
      target: { value: "#123456" },
    });
    fireEvent.change(screen.getByLabelText("MA 5 颜色"), {
      target: { value: "#654321" },
    });
    fireEvent.change(screen.getByLabelText("KDJ K 平滑"), {
      target: { value: "4" },
    });
    fireEvent.change(screen.getByLabelText("BOLL 标准差"), {
      target: { value: "2.5" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存设置" }));

    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    expect(stored.indicatorConfig.rsi).toMatchObject({
      enabled: false,
      color: "#123456",
    });
    expect(stored.indicatorConfig.ma.colors[0]).toBe("#654321");
    expect(stored.indicatorConfig.kdj.kSmoothing).toBe(4);
    expect(stored.indicatorConfig.boll.standardDeviations).toBe(2.5);
  });

  it("keeps source and investment disclosure visible on every route", () => {
    renderApp("/settings");

    expect(screen.getByText("数据来源：AKShare")).toBeInTheDocument();
    expect(screen.getByText("不构成投资建议")).toBeInTheDocument();
  });

  it("renders an explicit loading state while analysis is pending", () => {
    vi.mocked(fetch).mockImplementation(() => new Promise(() => undefined));

    renderApp("/stocks/000001");

    expect(
      screen.getByText("正在加载前复权日线与技术分析…"),
    ).toBeInTheDocument();
  });

  it("renders an actionable error state when analysis fails", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("offline"));

    renderApp("/stocks/000001");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "行情暂时不可用，请稍后重试",
    );
    expect(screen.getByRole("link", { name: "返回扫描首页" })).toHaveAttribute(
      "href",
      "/",
    );
  });
});

import { expect, test, type Page } from "@playwright/test";

async function installMockApi(page: Page) {
  let scanStarted = false;
  const dates = Array.from({ length: 90 }, (_, index) => {
    const value = new Date(Date.UTC(2026, 4, 1 + index));
    return value.toISOString().slice(0, 10);
  });
  const candles = dates.map((date, index) => ({
    date,
    open: 10 + index * 0.01,
    high: 10.3 + index * 0.01,
    low: 9.8 + index * 0.01,
    close: 10.1 + index * 0.01,
    volume: 1_000 + index,
    amount: 10_000 + index,
  }));
  const component = (score: number, weight: number) => ({
    score,
    weight,
    evidence: [],
  });
  const completedScan = {
    scanId: "mock-scan-1",
    status: "completed",
    completedCount: 1,
    totalCount: 1,
    marketDate: "2026-07-30",
    results: [
      {
        symbol: "000001",
        score: 72,
        grade: "强",
        breakdown: {},
        insights: [
          {
            category: "trend",
            direction: "偏多",
            summary: "均线与评分配置同步",
            severity: "中",
            evidence: [],
          },
        ],
        dataStatus: "cache",
        errorCode: null,
        scoreChange: 4,
      },
    ],
    errors: [],
  };

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const reply = (body: unknown, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(body),
      });

    if (url.pathname === "/api/v1/health") {
      return reply({ status: "ok" });
    }
    if (url.pathname === "/api/v1/market/status") {
      return reply({
        marketDate: "2026-07-30",
        status: "closed",
        isOpen: false,
        isTradingDay: true,
      });
    }
    if (url.pathname === "/api/v1/stocks/search") {
      return reply({
        stocks: [{ symbol: "000001", name: "平安银行", exchange: "SZ" }],
        updatedAt: "2026-07-30",
        stale: false,
      });
    }
    if (url.pathname === "/api/v1/analysis") {
      const body = request.postDataJSON() as {
        indicatorConfig?: { ma?: { periods?: number[] } };
        scoreWeights?: { trend?: number; momentum?: number };
      };
      const periods = body.indicatorConfig?.ma?.periods ?? [5, 10, 20, 60];
      const configured =
        periods.join(",") === "5,20,60" &&
        body.scoreWeights?.trend === 50 &&
        body.scoreWeights?.momentum === 20;
      const series = Object.fromEntries(
        periods.map((period) => [
          `ma${period}`,
          {
            values: dates.map((_, index) =>
              index + 1 < period ? null : 10 + index * 0.01,
            ),
            reasons: dates.map((_, index) =>
              index + 1 < period ? `insufficient_history:${period}` : null,
            ),
          },
        ]),
      );
      series.rsi14 = {
        values: dates.map(() => 58),
        reasons: dates.map(() => null),
      };
      return reply({
        stock: { symbol: "000001", name: "平安银行", exchange: "SZ" },
        marketDate: "2026-07-30",
        candles,
        indicators: { dates, series },
        score: {
          available: true,
          reason: null,
          totalScore: 68,
          grade: "强",
          breakdown: {
            trend: component(80, 35),
            momentum: component(70, 25),
            volumePrice: component(60, 15),
            position: component(55, 15),
            risk: component(75, 10),
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
            summary: configured
              ? "MA5/20/60 与评分权重已同步"
              : "MA20 上方，参数已同步",
            severity: "中",
            evidence: [
              {
                metric: "ma_configuration",
                value: periods.length,
                comparison: "configured",
                reference: configured ? 3 : 4,
                description: configured
                  ? "MA5/20/60 与评分权重已同步"
                  : "MA20 上方，参数已同步",
              },
            ],
          },
        ],
        cache: { status: "cache", updatedAt: "2026-07-30" },
        warnings: [],
      });
    }
    if (url.pathname === "/api/v1/scans/latest") {
      return scanStarted
        ? reply(completedScan)
        : reply(
            {
              error: {
                code: "SCAN_NOT_FOUND",
                message: "未找到扫描任务。",
                retryable: false,
              },
            },
            404,
          );
    }
    if (url.pathname === "/api/v1/scans" && request.method() === "POST") {
      scanStarted = true;
      return reply({ scanId: "mock-scan-1" }, 202);
    }
    if (url.pathname === "/api/v1/scans/mock-scan-1") {
      return reply(completedScan);
    }
    return reply(
      {
        error: {
          code: "DATA_UNAVAILABLE",
          message: `Unhandled mock route: ${url.pathname}`,
          retryable: false,
        },
      },
      500,
    );
  });
}

test("production server exposes health and the terminal shell", async ({
  page,
  request,
}) => {
  const healthResponse = await request.get("/api/v1/health");
  expect(healthResponse.ok()).toBe(true);
  await expect(healthResponse.json()).resolves.toEqual({ status: "ok" });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "自选扫描" })).toBeVisible();
  await expect(page.getByRole("searchbox", { name: "搜索股票" })).toBeVisible();
  await expect(page.getByText("批量扫描结果")).toBeVisible();
  await expect(page.getByText("数据来源：AKShare")).toBeVisible();
  await expect(page.getByText("不构成投资建议")).toBeVisible();
});

test("mocked user journey keeps analysis, settings, watchlist and scan state in sync", async ({
  page,
}) => {
  await installMockApi(page);
  await page.goto("/");

  await page.getByRole("searchbox", { name: "搜索股票" }).fill("000001");
  await page.getByRole("link", { name: /平安银行/ }).click();

  await expect(page.getByRole("heading", { name: "平安银行" })).toBeVisible();
  await expect(
    page.getByRole("img", { name: "平安银行 K 线、成交量与副图" }),
  ).toBeVisible();
  await expect(
    page.getByText("前复权日线 · 行情日期 2026-07-30", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("68", { exact: true })).toBeVisible();
  await expect(
    page.locator(".insight-list p").getByText("MA20 上方，参数已同步"),
  ).toBeVisible();

  await page.getByRole("button", { name: "加入自选" }).click();
  await page.getByRole("link", { name: "设置" }).click();
  await page.getByLabel("MA 周期").fill("5, 20, 60");
  await page.getByLabel("趋势原始权重").fill("50");
  await page.getByLabel("动量原始权重").fill("20");
  await page.getByRole("button", { name: "保存设置" }).click();
  await expect(page.getByText("设置已保存")).toBeVisible();

  await page.getByRole("link", { name: "扫描", exact: true }).click();
  await page.getByRole("link", { name: "000001", exact: true }).click();
  await expect(page.getByRole("checkbox", { name: "MA5" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "MA20" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "MA60" })).toBeVisible();
  await expect(
    page.locator(".insight-list p").getByText("MA5/20/60 与评分权重已同步"),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "移出自选" })).toBeVisible();

  await page.getByRole("link", { name: "返回扫描" }).click();
  await expect(page.getByText("1 / 20 只自选")).toBeVisible();
  await page.getByRole("button", { name: "运行扫描" }).click();
  await expect(page.getByText("1/1 已完成")).toBeVisible();
  await expect(page.getByText("均线与评分配置同步")).toBeVisible();
  await expect(page.getByText("72", { exact: true })).toBeVisible();

  await page.reload();
  await expect(page.getByText("1 / 20 只自选")).toBeVisible();
  await expect(page.getByText("1/1 已完成")).toBeVisible();
  await expect(page.getByText("均线与评分配置同步")).toBeVisible();
  await page.getByRole("link", { name: "设置" }).click();
  await expect(page.getByLabel("MA 周期")).toHaveValue("5, 20, 60");
  await expect(page.getByLabel("趋势原始权重")).toHaveValue("50");
  await expect(page.getByLabel("动量原始权重")).toHaveValue("20");
});

import { expect, test } from "@playwright/test";

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

import { expect, test } from "@playwright/test";

test("production server exposes health and the terminal shell", async ({
  page,
  request,
}) => {
  const healthResponse = await request.get("/api/v1/health");
  expect(healthResponse.ok()).toBe(true);
  await expect(healthResponse.json()).resolves.toEqual({ status: "ok" });

  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: "A 股 K 线终端" }),
  ).toBeVisible();
  await expect(page.getByText("数据来源：AKShare")).toBeVisible();
  await expect(page.getByText("不构成投资建议")).toBeVisible();
});

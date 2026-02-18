// @ts-check
import { test, expect } from "@playwright/test";

const DB_NAME = "interview_db";
const DB_URL = "mysql://root:leacock@localhost:3306/interview_db";
const NL_PROMPT = "list first 10 table names from interview_db";

test("mysql interview_db basic workflow", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "+ ADD DATABASE" }).click();
  await page.getByLabel("Connection Name").fill(DB_NAME);
  await page
    .getByLabel("Database URL (PostgreSQL or MySQL)")
    .fill(DB_URL);
  await page.getByRole("button", { name: "OK" }).click();

  await expect(page.locator(".active-db-name")).toHaveText(DB_NAME.toUpperCase(), {
    timeout: 20000,
  });

  // Execute default SQL in editor (SELECT 1 AS value) against selected interview_db.
  await page.getByRole("button", { name: "EXECUTE" }).click();

  await expect(page.locator(".ant-table")).toBeVisible({ timeout: 20000 });

  await page.getByRole("tab", { name: "NATURAL LANGUAGE" }).click();
  await page
    .getByPlaceholder("Describe the SQL you want to generate (PostgreSQL/MySQL)...")
    .fill(NL_PROMPT);
  await page.getByRole("button", { name: "GENERATE SQL" }).click();
  await page.getByRole("button", { name: "EXECUTE" }).click();

  await expect(page.locator(".ant-table")).toBeVisible({ timeout: 20000 });
});

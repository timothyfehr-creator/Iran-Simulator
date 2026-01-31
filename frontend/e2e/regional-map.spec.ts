import { test, expect } from '@playwright/test';

test.describe('Regional Map Tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('regional map tab loads with province markers', async ({ page }) => {
    // Click on Regional Map tab
    await page.click('button:has-text("Regional Map")');

    // Wait for map content to load
    await page.waitForTimeout(500);

    // Check for view mode buttons (indicates map loaded)
    await expect(page.locator('button:has-text("Protest Activity")')).toBeVisible({ timeout: 5000 });

    // Check for Kurdish Regions summary section (proves data loaded)
    await expect(page.locator('text=Kurdish Regions')).toBeVisible({ timeout: 5000 });

    // Check for map SVG element (has specific viewBox for Iran map)
    await expect(page.locator('svg[viewBox="0 0 100 90"]')).toBeVisible();
  });

  test('can switch between view modes', async ({ page }) => {
    await page.click('button:has-text("Regional Map")');
    await page.waitForTimeout(500);

    // Check default view mode (Protest Activity)
    await expect(page.locator('button:has-text("Protest Activity")')).toBeVisible({ timeout: 5000 });

    // Switch to Ethnicity view
    await page.click('button:has-text("Ethnic Groups")');
    await page.waitForTimeout(300);
    // Legend should show ethnicity colors
    await expect(page.locator('text=Persian').first()).toBeVisible();

    // Switch to Risk view
    await page.click('button:has-text("Risk Assessment")');
    await page.waitForTimeout(300);
    // Legend should show risk levels
    await expect(page.locator('text=/Critical|High|Elevated|Low/').first()).toBeVisible();
  });

  test('can click on province to see details', async ({ page }) => {
    await page.click('button:has-text("Regional Map")');
    await page.waitForTimeout(500);

    // Click on Tehran label or nearby circle (more reliable than clicking small circle)
    // First, let's find a clickable circle by looking for cursor-pointer class
    const tehranCircle = page.locator('svg circle').nth(0);
    await tehranCircle.click({ force: true });

    // Should show province details popup with province name and stats
    await expect(page.locator('text=Population').first()).toBeVisible({ timeout: 3000 });
  });

  test('shows high-risk provinces indicator', async ({ page }) => {
    await page.click('button:has-text("Regional Map")');

    // Should show count of high-risk provinces
    await expect(page.locator('text=/\\d+ high-risk provinces/i')).toBeVisible({ timeout: 5000 });
  });

  test('displays strategic sites summary', async ({ page }) => {
    await page.click('button:has-text("Regional Map")');

    // Check for strategic sites section
    await expect(page.locator('text=Strategic Sites')).toBeVisible();
    await expect(page.locator('text=Bushehr - Nuclear Plant')).toBeVisible();
    await expect(page.locator('text=Khuzestan - Oil Fields')).toBeVisible();
  });
});

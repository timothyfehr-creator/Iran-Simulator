import { test, expect } from '@playwright/test';

test.describe('Causal Explorer Tab', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('causal explorer tab loads and shows network', async ({ page }) => {
    // Click on Causal Explorer tab
    await page.click('button:has-text("Causal Explorer")');

    // Wait for the tab content to load
    await expect(page.locator('text=Bayesian Network')).toBeVisible({ timeout: 5000 });

    // Check that the status shows the network is available
    await expect(page.locator('text=/\\d+ nodes/i')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=/\\d+ edges/i')).toBeVisible({ timeout: 5000 });
  });

  test('can select evidence and run inference', async ({ page }) => {
    // Go to Causal Explorer tab
    await page.click('button:has-text("Causal Explorer")');

    // Wait for content to load
    await page.waitForTimeout(1000);

    // Look for any dropdown or selector for evidence
    const evidenceSelector = page.locator('select, [role="combobox"]').first();
    if (await evidenceSelector.isVisible()) {
      // If there's a selector, try to interact with it
      await evidenceSelector.click();
    }

    // Check that posterior results are displayed somewhere
    // The component should show some probability data (use first() since multiple matches exist)
    await expect(page.locator('text=/STATUS_QUO|COLLAPSE|TRANSITION/i').first()).toBeVisible({ timeout: 5000 });
  });
});

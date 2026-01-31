import { test, expect } from '@playwright/test';

test.describe('War Room Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('displays initial dashboard layout', async ({ page }) => {
    // Header with DefconWidget
    await expect(page.getByTestId('defcon-widget')).toBeVisible();
    await expect(page.getByTestId('defcon-widget')).toContainText('REGIME STABILITY');

    // Sidebar controls (visible on desktop)
    await expect(page.getByRole('button', { name: /run simulation/i })).toBeVisible();
    await expect(page.getByRole('slider').first()).toBeVisible();

    // Tab navigation visible
    await expect(page.locator('button:has-text("Executive Summary")')).toBeVisible();
    await expect(page.locator('button:has-text("Analysis")')).toBeVisible();
    await expect(page.locator('button:has-text("Regional Map")')).toBeVisible();

    // Timeline slider
    await expect(page.getByTestId('timeline-slider')).toBeVisible();
  });

  test('run simulation button shows loading state', async ({ page }) => {
    const runButton = page.getByRole('button', { name: /run simulation/i });
    await expect(runButton).toBeEnabled();

    // Click button to start simulation
    await runButton.click();

    // Should show loading text within the button
    await expect(page.locator('button:has-text("Running...")')).toBeVisible({ timeout: 1000 });

    // Wait for simulation to complete
    await expect(page.locator('button:has-text("Run Simulation")')).toBeVisible({ timeout: 5000 });
  });

  test('confidence slider updates value', async ({ page }) => {
    const slider = page.getByRole('slider', { name: /analyst confidence/i });

    // Change slider value
    await slider.fill('85');

    await expect(page.getByText('85%')).toBeVisible();
  });

  test('timeline slider navigates days', async ({ page }) => {
    const timeline = page.getByTestId('timeline-slider').getByRole('slider');

    await timeline.fill('45');

    await expect(page.getByText('Day 45')).toBeVisible();
  });

  test('defcon widget shows critical status', async ({ page }) => {
    const widget = page.getByTestId('defcon-widget');

    // Mock data has critical status
    await expect(widget).toContainText('CRITICAL');
    await expect(widget).toHaveClass(/status-critical/);
  });

  test('interactive elements are focusable', async ({ page }) => {
    // Verify run simulation button can be focused
    const runButton = page.getByRole('button', { name: /run simulation/i });
    await runButton.focus();
    await expect(runButton).toBeFocused();

    // Verify sliders exist and are interactive
    const sliders = page.getByRole('slider');
    await expect(sliders.first()).toBeVisible();

    // Verify tab navigation buttons are accessible
    const tabButtons = page.locator('button:has-text("Executive Summary")');
    await tabButtons.focus();
    await expect(tabButtons).toBeFocused();
  });

  test('outcome chart is visible on Analysis tab', async ({ page }) => {
    // Click Analysis tab to see chart
    await page.click('button:has-text("Analysis")');
    await page.waitForTimeout(300);

    // Wait for chart to render
    await expect(page.locator('.recharts-responsive-container')).toBeVisible();
  });

  test('page title and header are correct', async ({ page }) => {
    await expect(page.getByText('Iran Simulator')).toBeVisible();
    await expect(page.getByText('War Room Dashboard')).toBeVisible();
  });

  test('simulation runs increment count', async ({ page }) => {
    // Initial session runs should be 0
    const sessionRunsRow = page.locator('div:has(> span:text("Session Runs:"))');
    await expect(sessionRunsRow).toBeVisible();
    await expect(sessionRunsRow).toContainText('0');

    // Run simulation once
    await page.locator('button:has-text("Run Simulation")').click();

    // Wait for session runs to increment (more reliable than checking button text)
    // The simulation takes ~1.5s (mock delay) but give it extra time
    await expect(sessionRunsRow).toContainText('1', { timeout: 10000 });
  });
});

test.describe('War Room Dashboard - Mobile', () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test('responsive layout on mobile', async ({ page }) => {
    await page.goto('/');

    // Menu button should appear on mobile
    await expect(page.getByRole('button', { name: /menu/i })).toBeVisible();

    // Sidebar should be hidden initially
    await expect(page.getByTestId('sidebar')).not.toBeInViewport();
  });

  test('mobile menu opens sidebar', async ({ page }) => {
    await page.goto('/');

    // Click menu button
    await page.getByRole('button', { name: /menu/i }).click();

    // Sidebar should be visible
    await expect(page.getByTestId('sidebar')).toBeInViewport();
  });
});

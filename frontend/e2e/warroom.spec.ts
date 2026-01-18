import { test, expect } from '@playwright/test';

test.describe('War Room Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('displays initial dashboard layout', async ({ page }) => {
    // Header with DefconWidget
    await expect(page.getByTestId('defcon-widget')).toBeVisible();
    await expect(page.getByText('REGIME STABILITY')).toBeVisible();

    // Sidebar controls (visible on desktop)
    await expect(page.getByRole('button', { name: /run simulation/i })).toBeVisible();
    await expect(page.getByRole('slider', { name: /analyst confidence/i })).toBeVisible();

    // Map placeholder
    await expect(page.getByText('Map View')).toBeVisible();

    // Timeline slider
    await expect(page.getByTestId('timeline-slider')).toBeVisible();
  });

  test('run simulation button shows loading state', async ({ page }) => {
    const runButton = page.getByRole('button', { name: /run simulation/i });
    await runButton.click();

    // Should show loading
    await expect(runButton).toBeDisabled();
    await expect(page.getByText(/running/i)).toBeVisible();

    // Should complete (mock delay ~1.5s)
    await expect(runButton).toBeEnabled({ timeout: 3000 });
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

  test('keyboard navigation works', async ({ page }) => {
    // Tab to run simulation button
    await page.keyboard.press('Tab');

    // Continue tabbing through controls
    const runButton = page.getByRole('button', { name: /run simulation/i });
    await runButton.focus();
    await expect(runButton).toBeFocused();

    // Tab to confidence slider
    await page.keyboard.press('Tab');
    const slider = page.getByRole('slider', { name: /analyst confidence/i });
    await expect(slider).toBeFocused();
  });

  test('outcome chart is visible', async ({ page }) => {
    // Wait for chart to render
    await expect(page.locator('.recharts-responsive-container')).toBeVisible();
  });

  test('page title and header are correct', async ({ page }) => {
    await expect(page.getByText('Iran Simulator')).toBeVisible();
    await expect(page.getByText('War Room Dashboard')).toBeVisible();
  });

  test('simulation runs increment count', async ({ page }) => {
    // Run simulation twice
    const runButton = page.getByRole('button', { name: /run simulation/i });

    await runButton.click();
    await expect(runButton).toBeEnabled({ timeout: 3000 });

    await runButton.click();
    await expect(runButton).toBeEnabled({ timeout: 3000 });

    // Session runs should show 2
    await expect(page.getByText('Session Runs:')).toBeVisible();
    await expect(page.getByText('2', { exact: false })).toBeVisible();
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

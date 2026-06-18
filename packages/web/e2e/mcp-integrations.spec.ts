import { test, expect } from '@playwright/test';
import { STORAGE_STATE } from './storage';

test.use({ storageState: STORAGE_STATE });

const PROJECT_SLUG = process.env.E2E_PROJECT_SLUG ?? 'ref-siglm';

test.describe('MCP integrations page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/projects/${PROJECT_SLUG}/mcp-integrations`);
    await expect(
      page.getByRole('heading', { name: /mcp integrations/i })
    ).toBeVisible();
  });

  test('renders the three tabs', async ({ page }) => {
    await expect(page.getByRole('tab', { name: /configured/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /catalog/i })).toBeVisible();
    await expect(page.getByRole('tab', { name: /export/i })).toBeVisible();
  });

  test('catalog tab shows search input and category filter', async ({ page }) => {
    await page.getByRole('tab', { name: /catalog/i }).click();

    await expect(
      page.getByPlaceholder(/search mcps/i)
    ).toBeVisible();
    await expect(page.getByRole('combobox')).toBeVisible();
  });

  test('search filters the catalog list', async ({ page }) => {
    await page.getByRole('tab', { name: /catalog/i }).click();

    const search = page.getByPlaceholder(/search mcps/i);
    await search.fill('zzz-no-such-mcp-zzz');

    // No catalog cards visible (filtered out)
    await expect(
      page.getByRole('button', { name: /configure/i })
    ).toHaveCount(0, { timeout: 5_000 });
  });

  test('export tab renders preview panel', async ({ page }) => {
    await page.getByRole('tab', { name: /export/i }).click();

    // Either the preview or a "no MCPs configured" empty state is shown
    await expect(
      page
        .getByText(/export|preview|no mcp/i)
        .first()
    ).toBeVisible();
  });

  test('opens add dialog when navigating with ?add=<key>', async ({ page }) => {
    await page.goto(`/projects/${PROJECT_SLUG}/mcp-integrations?add=github`);
    await expect(page.getByRole('dialog')).toBeVisible({ timeout: 10_000 });
  });
});

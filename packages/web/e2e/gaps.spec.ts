import { test, expect } from '@playwright/test';
import { STORAGE_STATE } from './storage';

test.use({ storageState: STORAGE_STATE });

const PROJECT_SLUG = process.env.E2E_PROJECT_SLUG ?? 'ref-siglm';

test.describe('Coverage gaps page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`/projects/${PROJECT_SLUG}/gaps`);
    await expect(
      page.getByRole('heading', { name: /coverage gaps/i })
    ).toBeVisible();
  });

  test('renders header, stats strip and filter chips', async ({ page }) => {
    // Five-card stats strip
    for (const label of ['Total', 'Open', 'By skill', 'By MCP', 'Out of scope']) {
      await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
    }

    // Filter chips (label may include a trailing count badge)
    await expect(page.getByRole('button', { name: /^All\b/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /^Open\b/ })).toBeVisible();

    // CTA to add a gap
    await expect(page.getByRole('button', { name: /add gap/i })).toBeVisible();
  });

  test('can open and cancel the Add gap dialog', async ({ page }) => {
    await page.getByRole('button', { name: /add gap/i }).click();

    const dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('heading', { name: /add gap/i })).toBeVisible();
    await expect(dialog.getByLabel('Title')).toBeVisible();

    await dialog.getByRole('button', { name: /cancel/i }).click();
    await expect(dialog).toBeHidden();
  });

  test('creates a new gap end-to-end', async ({ page }) => {
    const uniqueTitle = `E2E gap ${Date.now()}`;

    await page.getByRole('button', { name: /add gap/i }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Title').fill(uniqueTitle);
    await dialog.getByRole('button', { name: /create gap/i }).click();

    // Dialog closes and the new gap appears in the list
    await expect(dialog).toBeHidden();
    await expect(page.getByText(uniqueTitle)).toBeVisible({ timeout: 10_000 });
  });

  test('switches filter to Open and back to All', async ({ page }) => {
    await page.getByRole('button', { name: /^Open\b/ }).click();

    await page.getByRole('button', { name: /^All\b/ }).click();
  });
});

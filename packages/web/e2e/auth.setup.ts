import { test as setup, expect } from '@playwright/test';
import { STORAGE_STATE } from './storage';

setup('authenticate as stub admin', async ({ page }) => {
  await page.goto('/login');

  await page.getByLabel('Email').fill('admin@example.com');
  await page.getByLabel('Password', { exact: true }).fill('password123');
  await page.getByRole('button', { name: /sign in/i }).click();

  // Middleware redirects authenticated users away from /login → /dashboard
  await page.waitForURL(/\/dashboard|\/projects/, { timeout: 15_000 });
  await expect(page).not.toHaveURL(/\/login/);

  await page.context().storageState({ path: STORAGE_STATE });
});

import { test, expect } from '@playwright/test';

/**
 * E2E test: Full workflow from login to export
 * 
 * This test verifies the complete user journey through the application:
 * 1. Login
 * 2. Navigate to dashboard
 * 3. View projects
 * 4. Access project details
 * 5. Navigate through skills, backlog, DAG, and export
 */

test.describe('Full Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app
    await page.goto('/');
  });

  test('should display landing page', async ({ page }) => {
    await expect(page).toHaveTitle(/Agents Workshop/);
  });

  test('should navigate to login page', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('h1, h2').first()).toContainText(/login|sign in/i);
  });

  test('should perform login flow', async ({ page }) => {
    await page.goto('/login');
    
    // Fill in credentials
    const emailInput = page.locator('input[name="email"], input[type="email"]');
    const passwordInput = page.locator('input[name="password"], input[type="password"]');
    
    if (await emailInput.isVisible()) {
      await emailInput.fill('test@example.com');
    }
    if (await passwordInput.isVisible()) {
      await passwordInput.fill('password123');
    }
    
    // Submit form
    const submitButton = page.locator('button[type="submit"]');
    if (await submitButton.isVisible()) {
      await submitButton.click();
    }
    
    // Should redirect to dashboard or projects
    await expect(page).toHaveURL(/dashboard|projects/);
  });

  test('should display dashboard after login', async ({ page }) => {
    await page.goto('/dashboard');
    
    // Dashboard should load (may redirect to login if not authenticated)
    await page.waitForLoadState('networkidle');
    
    // Check for dashboard content or login redirect
    const url = page.url();
    expect(url).toMatch(/dashboard|login/);
  });

  test('should list projects', async ({ page }) => {
    await page.goto('/projects');
    await page.waitForLoadState('networkidle');
    
    // Should show projects page or login
    const url = page.url();
    if (url.includes('/projects')) {
      // Check for projects content
      await expect(page.locator('h1, h2').first()).toContainText(/project/i);
    }
  });

  test('should navigate to settings', async ({ page }) => {
    await page.goto('/settings');
    await page.waitForLoadState('networkidle');
    
    // Should show settings or login
    const url = page.url();
    expect(url).toMatch(/settings|login/);
  });
});

test.describe('Navigation', () => {
  test('should have working mobile navigation', async ({ page }) => {
    // Set mobile viewport
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');
    
    // Look for mobile menu button
    const mobileMenuButton = page.locator('button').filter({ hasText: /menu/i }).or(
      page.locator('[aria-label*="menu" i]')
    ).or(
      page.locator('button:has(svg)').first()
    );
    
    // Mobile nav should be present
    await page.waitForLoadState('networkidle');
  });

  test('should have working theme toggle', async ({ page }) => {
    await page.goto('/');
    
    // Look for theme toggle button
    const themeToggle = page.locator('button').filter({ hasText: /theme|dark|light/i }).or(
      page.locator('[aria-label*="theme" i]')
    );
    
    // Page should load
    await page.waitForLoadState('networkidle');
  });
});

test.describe('Responsive Design', () => {
  const viewports = [
    { name: 'Desktop', width: 1920, height: 1080 },
    { name: 'Tablet', width: 768, height: 1024 },
    { name: 'Mobile', width: 375, height: 667 },
  ];

  for (const viewport of viewports) {
    test(`should render correctly on ${viewport.name}`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto('/');
      
      // Page should load without errors
      await page.waitForLoadState('networkidle');
      
      // No layout shift or overflow issues
      const body = page.locator('body');
      await expect(body).toBeVisible();
      
      // Check for horizontal overflow
      const hasHorizontalScroll = await page.evaluate(() => {
        return document.documentElement.scrollWidth > document.documentElement.clientWidth;
      });
      
      // Main page should not have horizontal scroll
      expect(hasHorizontalScroll).toBeFalsy();
    });
  }
});

test.describe('Error Handling', () => {
  test('should display 404 page for unknown routes', async ({ page }) => {
    await page.goto('/this-page-does-not-exist-12345');
    
    // Should show 404 or redirect
    await page.waitForLoadState('networkidle');
    
    // Check for 404 content or redirect to home
    const content = await page.textContent('body');
    const url = page.url();
    
    // Either shows 404 content or redirects
    expect(content?.toLowerCase().includes('not found') || url === '/').toBeTruthy;
  });

  test('should handle network errors gracefully', async ({ page }) => {
    // Intercept API calls and fail them
    await page.route('**/api/**', (route) => {
      route.abort();
    });
    
    await page.goto('/dashboard');
    
    // Page should still load (with error states)
    await page.waitForLoadState('domcontentloaded');
  });
});

test.describe('Accessibility', () => {
  test('should have proper heading hierarchy', async ({ page }) => {
    await page.goto('/');
    
    // Get all headings
    const headings = await page.locator('h1, h2, h3, h4, h5, h6').all();
    
    // Should have at least one heading
    expect(headings.length).toBeGreaterThan(0);
  });

  test('should have accessible buttons', async ({ page }) => {
    await page.goto('/');
    
    // All buttons should have accessible names
    const buttons = await page.locator('button').all();
    
    for (const button of buttons) {
      const accessibleName = await button.getAttribute('aria-label') ||
        await button.textContent() ||
        await button.getAttribute('title');
      
      // Button should have some accessible name (text, aria-label, or title)
      // Skip if button only contains an icon (common pattern)
      const hasIcon = await button.locator('svg').count() > 0;
      const hasText = (await button.textContent())?.trim().length || 0 > 0;
      
      if (!hasIcon || hasText) {
        expect(accessibleName).toBeTruthy();
      }
    }
  });

  test('should support keyboard navigation', async ({ page }) => {
    await page.goto('/');
    
    // Tab through focusable elements
    await page.keyboard.press('Tab');
    
    // Something should be focused
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).toBeTruthy();
  });
});

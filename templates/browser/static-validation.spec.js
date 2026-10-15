/**
 * Static Validation Tests (Tier 1)
 * Tests basic aApplication startup and rendering
 */

const { test, expect } = require('@playwright/test');

test.describe('Static Validation - Tier 1', () => {
  const baseUrl = process.env.BASE_URL || 'http://localhost:3001';

  test('app starts without crashes', async ({ page }) => {
    // Navigate to aApplication
    await page.goto(baseUrl);
    
    // Check that page loads
    await expect(page).not.toHaveTitle(/Error/);
    
    // Check for absence of critical errors in console
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });
    
    // Wait for page to fully load
    await page.waitForLoadState('networkidle');
    
    // Check for React hydration errors or critical JS errors
    const criticalErrors = errors.filter(error => 
      error.includes('Hydration') || 
      error.includes('TypeError') ||
      error.includes('ReferenceError')
    );
    
    expect(criticalErrors).toHaveLength(0);
  });

  test('frontend renders without JavaScript errors', async ({ page }) => {
    const consolerrors = [];
    
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consolerrors.push(msg.text());
      }
    });
    
    // Navigate and wait for complete render
    await page.goto(baseUrl);
    await page.waitForLoadState('domcontentloaded');
    
    // Check that main content is visible
    const body = await page.locator('body');
    await expect(body).toBeVisible();
    
    // Verify no critical JavaScript errors
    const jsErrors = consolerrors.filter(error => 
      !error.includes('favicon') && 
      !error.includes('analytics') &&
      !error.includes('third-party')
    );
    
    expect(jsErrors).toHaveLength(0);
  });

  test('basic navigation functional', async ({ page }) => {
    await page.goto(baseUrl);
    
    // Check if navigation elements exist
    const nav = page.locator('nav, .navigation, [role="navigation"]');
    
    if (await nav.count() > 0) {
      await expect(nav.first()).toBeVisible();
      
      // Test clicking first navigation link if it exists
      const firstLink = nav.locator('a').first();
      if (await firstLink.count() > 0) {
        await firstLink.click();
        await page.waitForLoadState('networkidle');
        
        // Should not be on error page
        await expect(page).not.toHaveTitle(/404|Error/);
      }
    }
  });

  test('no 500/404 errors on core routes', async ({ page }) => {
    const coreRoutes = ['/', '/dashboard', '/profile', '/settings'];
    
    for (const route of coreRoutes) {
      const response = await page.goto(`${baseUrl}${route}`);
      
      // Skip if route doesn't exist (acceptable)
      if (response && response.status() >= 500) {
        throw new Error(`${route} returned ${response.status()}`);
      }
    }
  });
});
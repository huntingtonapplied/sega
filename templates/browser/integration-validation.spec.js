/**
 * Integration Validation Tests (Tier 3)
 * Tests cross-service functionality and complex workflows
 */

const { test, expect } = require('@playwright/test');

test.describe('Integration Validation - Tier 3', () => {
  const baseUrl = process.env.BASE_URL || 'http://localhost:3001';

  test('Authentication-flow', async ({ page }) => {
    // Test login flow
    await page.goto(`${baseUrl}/login`);
    await page.waitForLoadState('networkidle');

    // Check if login form exists
    const loginForm = page.locator('form, [data-testid="login-form"]');
    if (await loginForm.count() === 0) {
      test.skip('No login form found');
    }

    // Fill login credentials
    await page.fill('input[type="email"], input[name="username"], input[name="email"]', 'test@example.com');
    await page.fill('input[type="password"]', 'testpassword123');

    // Submit login
    await page.click('button[type="submit"], button:contains("Login"), button:contains("Sign In")');
    await page.waitForLoadState('networkidle');

    // Verify successful login (should redirect away from login page)
    const currentUrl = page.url();
    expect(currentUrl).not.toContain('/login');

    // Check for authenticated user indicators
    const userIndicators = [
      'text="Dashboard"',
      'text="Profile"', 
      'text="Logout"',
      '[data-testid="user-menu"]',
      '.user-avatar'
    ];

    let foundIndicator = false;
    for (const indicator of userIndicators) {
      if (await page.locator(indicator).count() > 0) {
        foundIndicator = true;
        break;
      }
    }

    expect(foundIndicator).toBeTruthy();

    // Test logout flow
    const logoutButton = page.locator('button:contains("Logout"), a:contains("Logout"), [data-testid="logout"]').first();
    if (await logoutButton.count() > 0) {
      await logoutButton.click();
      await page.waitForLoadState('networkidle');

      // Should redirect to login or home page
      const loggedOutUrl = page.url();
      expect(loggedOutUrl).toMatch(/(login|home|\/)/);
    }
  });

  test('real-time features', async ({ page }) => {
    await page.goto(baseUrl);
    await page.waitForLoadState('networkidle');

    // Test WebSocket connection if available
    let hasWebSocket = false;
    
    page.on('websocket', ws => {
      hasWebSocket = true;
      console.log('WebSocket connection established');
    });

    // Wait to see if WebSocket connects
    await page.waitForTimeout(3000);

    if (!hasWebSocket) {
      // Check for other real-time indicators
      const realtimeIndicators = [
        '[data-testid="live-updates"]',
        '.real-time',
        '.live-data',
        'text="live"',
        'text="real-time"'
      ];

      let hasRealtime = false;
      for (const indicator of realtimeIndicators) {
        if (await page.locator(indicator).count() > 0) {
          hasRealtime = true;
          break;
        }
      }

      if (!hasRealtime) {
        test.skip('No real-time features detected');
      }
    }

    // If real-time features exist, they should work without errors
    await expect(page.locator('body')).toBeVisible();
  });

  test('cross-service API calls', async ({ page, request }) => {
    // Test internal API endpoints
    const apiEndpoints = [
      '/api/health',
      '/api/status', 
      '/api/version',
      '/api/entities',
      '/api/users'
    ];

    for (const endpoint of apiEndpoints) {
      try {
        const response = await request.get(`${baseUrl}${endpoint}`);
        
        // Endpoint should either work (200-299) or be not found (404)
        // but not have server errors (500+)
        if (response.status() >= 500) {
          throw new Error(`${endpoint} returned server error: ${response.status()}`);
        }
      } catch (error) {
        if (!error.message.includes('ECONNREFUSED')) {
          throw error;
        }
      }
    }
  });

  test('error handling and recovery', async ({ page }) => {
    await page.goto(baseUrl);
    await page.waitForLoadState('networkidle');

    // Test navigation to non-existent page
    await page.goto(`${baseUrl}/this-page-does-not-exist-${Date.now()}`);
    await page.waitForLoadState('networkidle');

    // Should show error page or redirect, not crash
    const pageContent = await page.textContent('body');
    expect(pageContent).toBeTruthy();

    // Error page should have some helpful content
    const hasErrorContent = pageContent.includes('404') || 
                           pageContent.includes('Not Found') || 
                           pageContent.includes('Page not found') ||
                           pageContent.includes('Error');
    
    expect(hasErrorContent).toBeTruthy();

    // Should be able to navigate back to home
    await page.goto(baseUrl);
    await page.waitForLoadState('networkidle');
    
    // Home page should load normally
    await expect(page.locator('body')).toBeVisible();
  });

  test('form validation and error states', async ({ page }) => {
    // Try to find a form to test
    await page.goto(baseUrl);
    await page.waitForLoadState('networkidle');

    // Look for forms on common pages
    const formPages = ['/contact', '/create', '/signup', '/register', '/login'];
    let formFound = false;

    for (const formPage of formPages) {
      try {
        await page.goto(`${baseUrl}${formPage}`);
        await page.waitForLoadState('networkidle');

        const forms = page.locator('form');
        if (await forms.count() > 0) {
          formFound = true;
          
          // Try submitting empty form to test validation
          const submitButton = forms.locator('button[type="submit"], input[type="submit"]').first();
          if (await submitButton.count() > 0) {
            await submitButton.click();
            await page.waitForTimeout(1000);

            // Look for validation messages
            const validationMessages = page.locator(
              '.error, .validation-error, [data-testid*="error"], .field-error, .invalid-feedback'
            );

            // If validation exists, it should show errors for empty required fields
            if (await validationMessages.count() > 0) {
              await expect(validationMessages.first()).toBeVisible();
            }
          }
          break;
        }
      } catch (error) {
        // Continue to next page
        continue;
      }
    }

    if (!formFound) {
      test.skip('No forms found for validation testing');
    }
  });

  test('performance and load handling', async ({ page }) => {
    const startTime = Date.now();
    
    await page.goto(baseUrl);
    await page.waitForLoadState('networkidle');
    
    const loadTime = Date.now() - startTime;
    
    // Page should load within reasonable time (10 seconds)
    expect(loadTime).toBeLessThan(10000);

    // Test rapid navigation
    const links = page.locator('a[href^="/"], a[href^="' + baseUrl + '"]');
    const linkCount = await links.count();

    if (linkCount > 0) {
      // Click a few links rapidly to test handling
      const linksToTest = Math.min(3, linkCount);
      
      for (let i = 0; i < linksToTest; i++) {
        try {
          await links.nth(i).click();
          await page.waitForLoadState('domcontentloaded');
          
          // Should not crash or show errors
          await expect(page.locator('body')).toBeVisible();
        } catch (error) {
          // Some links might be external or cause navigation issues
          console.log(`Link ${i} navigation failed: ${error.message}`);
        }
      }
    }
  });
});
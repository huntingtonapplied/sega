import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: false, // Dynamic tests need to run sequentially for data consistency
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Force single worker for database consistency
  reporter: [
    ['html'],
    ['json', { outputFile: 'test-results/dynamic-validation-results.json' }]
  ],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3001',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    extraHTTPHeaders: {
      'Accept': 'application/json',
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    command: 'make dev-shared',
    url: process.env.BASE_URL || 'http://localhost:3001',
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
  timeout: 60 * 1000, // Longer timeout for API operations
  expect: {
    timeout: 10 * 1000,
  },
});
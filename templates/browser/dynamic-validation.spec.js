/**
 * Dynamic Validation Tests (Tier 2) 
 * Tests API + UI integration with CRUD workflows
 */

const { test, expect } = require('@playwright/test');

test.describe('Dynamic Validation - Tier 2', () => {
  const baseUrl = process.env.BASE_URL || 'http://localhost:3001';
  const apiUrl = `${baseUrl}/api`;

  test('verify-created-entity', async ({ page, request }) => {
    const entityId = process.env.TEST_ENTITY_ID;
    
    if (!entityId) {
      test.skip('No entity ID provided');
    }

    // Navigate to dashboard/list page
    await page.goto(`${baseUrl}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Look for the entity created via API
    const entitySelector = `[data-id="${entityId}"], [data-testid="entity-${entityId}"], :text("Test Entity")`;
    const entity = page.locator(entitySelector).first();
    
    // Wait for entity to appear (give it time to load)
    await expect(entity).toBeVisible({ timeout: 10000 });
  });

  test('create record via UI, verify in database', async ({ page, request }) => {
    // Login first if Authentication is required
    await page.goto(`${baseUrl}/login`);
    
    try {
      await page.fill('input[type="email"], input[name="username"]', 'test@example.com');
      await page.fill('input[type="password"]', 'testpassword123');
      await page.click('button[type="submit"]');
      await page.waitForLoadState('networkidle');
    } catch (error) {
      // Skip if login not available
      console.log('Login not available, proceeding without auth');
    }

    // Navigate to create page
    await page.goto(`${baseUrl}/create`);
    await page.waitForLoadState('networkidle');

    const timestamp = Date.now();
    const testTitle = `UI Test Entity ${timestamp}`;

    // Fill out creation form
    await page.fill('input[placeholder*="title"], input[name="title"]', testTitle);
    await page.fill('textarea[placeholder*="description"], textarea[name="description"]', 'Created via UI test');

    // Submit form
    await page.click('button[type="submit"], button:contains("Save"), button:contains("Create")');
    
    // Wait for creation to complete
    await page.waitForLoadState('networkidle');

    // Verify via API that entity was created
    const entitiesResponse = await request.get(`${apiUrl}/entities`);
    expect(entitiesResponse.ok()).toBeTruthy();

    const entities = await entitiesResponse.json();
    const createdEntity = entities.find(e => e.name?.includes(testTitle) || e.title?.includes(testTitle));
    
    expect(createdEntity).toBeTruthy();
  });

  test('update record via UI', async ({ page, request }) => {
    // First create an entity via API
    const testEntity = {
      name: `Update Test ${Date.now()}`,
      description: 'Will be updated'
    };

    const createResponse = await request.post(`${apiUrl}/entities`, {
      data: testEntity
    });
    
    if (!createResponse.ok()) {
      test.skip('Could not create test entity via API');
    }

    const entity = await createResponse.json();
    const entityId = entity.id;

    // Navigate to edit page
    await page.goto(`${baseUrl}/edit/${entityId}`);
    await page.waitForLoadState('networkidle');

    // Update the entity
    const updatedName = `Updated ${Date.now()}`;
    await page.fill('input[name="name"], input[name="title"]', updatedName);
    await page.click('button[type="submit"], button:contains("Save"), button:contains("Update")');
    
    await page.waitForLoadState('networkidle');

    // Verify update via API
    const updatedResponse = await request.get(`${apiUrl}/entities/${entityId}`);
    if (updatedResponse.ok()) {
      const updatedEntity = await updatedResponse.json();
      expect(updatedEntity.name || updatedEntity.title).toContain('Updated');
    }
  });

  test('delete record and confirm removal', async ({ page, request }) => {
    // Create entity via API
    const testEntity = {
      name: `Delete Test ${Date.now()}`,
      description: 'Will be deleted'
    };

    const createResponse = await request.post(`${apiUrl}/entities`, {
      data: testEntity
    });
    
    if (!createResponse.ok()) {
      test.skip('Could not create test entity via API');
    }

    const entity = await createResponse.json();
    const entityId = entity.id;

    // Navigate to list/dashboard page
    await page.goto(`${baseUrl}/dashboard`);
    await page.waitForLoadState('networkidle');

    // Find and delete the entity
    const deleteButton = page.locator(`[data-id="${entityId}"] button:contains("Delete"), [data-testid="delete-${entityId}"]`).first();
    
    if (await deleteButton.count() > 0) {
      await deleteButton.click();
      
      // Confirm deletion if modal appears
      const confirmButton = page.locator('button:contains("Confirm"), button:contains("Yes"), button:contains("Delete")');
      if (await confirmButton.count() > 0) {
        await confirmButton.click();
      }
      
      await page.waitForLoadState('networkidle');

      // Verify entity is gone from UI
      const deletedEntity = page.locator(`[data-id="${entityId}"]`);
      await expect(deletedEntity).not.toBeVisible();
    }

    // Verify deletion via API
    const checkResponse = await request.get(`${apiUrl}/entities/${entityId}`);
    expect(checkResponse.status()).toBe(404);
  });
});
import { Page, expect } from '@playwright/test';

/**
 * Mock Firebase Authentication for E2E tests.
 * This intercepts Firebase Auth calls and injects a mock user state.
 */
export async function setupMockAuth(page: Page, user = {
  uid: 'test-user-123',
  email: 'greg@ggernetzke.com',
  displayName: 'Greg G',
  emailVerified: true,
}) {
  // Use a simple mechanism to tell the app to use a mock user.
  // We'll inject this before the app loads.
  await page.addInitScript((mockUser) => {
    (window as any).__E2E_MOCK_USER__ = mockUser;
  }, user);

  // We need to intercept the common Firebase Auth API calls that the SDK makes
  // to prevent it from failing or showing the login screen.
  
  // 1. Intercept account lookup (common in onAuthStateChanged)
  await page.route('**/identitytoolkit.googleapis.com/v1/accounts:lookup*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        users: [{
          localId: user.uid,
          email: user.email,
          displayName: user.displayName,
          emailVerified: user.emailVerified,
        }]
      })
    });
  });

  // 2. Intercept securetoken (refreshing tokens)
  await page.route('**/securetoken.googleapis.com/v1/token*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        expires_in: '3600',
        token_type: 'Bearer',
        refresh_token: 'mock-refresh-token',
        id_token: 'mock-id-token',
        user_id: user.uid,
        project_id: 'tron-cloud',
      })
    });
  });
}

/**
 * Perform a login bypass and navigate to the dashboard.
 */
export async function bypassLogin(page: Page) {
  await setupMockAuth(page);
  await page.goto('/');
  
  // Wait for the app to transition from loading/login to dashboard content
  // We'll check for the "Portfolio" tab which is the default
  await expect(page.getByText('Portfolio overview')).toBeVisible({ timeout: 10000 });
}

import { test, expect } from '@playwright/test'
import { setupMockAuth } from './auth_utils'

test.describe('API Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockAuth(page)
    await page.goto('/')
    
    // Navigate to Approvals tab
    await page.getByRole('button', { name: 'Approvals' }).click()
  })

  test('Approvals tab shows an error state when API fails', async ({ page }) => {
    // We can simulate an API failure with Playwright's route mocking
    await page.route('**/mercury/pending-payments', (route) => {
      route.abort('failed')
    })
    
    // Check if the error message is displayed
    await expect(page.getByText('Connection error')).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
  })

  test('Retrying after a failed API call works', async ({ page }) => {
    // Intercept the initial call from page load to fail
    await page.route('**/mercury/pending-payments', async (route) => {
      await route.abort('failed')
    }, { times: 1 })

    // Wait for the error message
    await expect(page.getByText('Connection error')).toBeVisible({ timeout: 10000 })
    
    // Now setup the route for the retry to succeed
    await page.route('**/mercury/pending-payments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, count: 0, payments: [] }),
      })
    })

    // Click Retry
    await page.getByRole('button', { name: 'Retry' }).click()

    // Error should be gone, and "All clear" might be shown (empty state)
    await expect(page.getByText('Connection error')).not.toBeVisible({ timeout: 10000 })
    await expect(page.getByText('All clear')).toBeVisible({ timeout: 10000 })
  })
})

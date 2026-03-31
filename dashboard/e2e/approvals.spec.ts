import { test, expect } from '@playwright/test'
import { setupMockAuth } from './auth_utils'

test.describe('Payment Approvals Tab (HITL Flow)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockAuth(page)
    await page.goto('/')
    
    // Ensure navigation to Approvals tab
    await page.getByRole('button', { name: 'Approvals' }).click()
  })

  test('Approvals tab renders header and stat cards', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Payment approvals' })).toBeVisible()
    await expect(page.getByText('Mercury Bank · HITL Gateway')).toBeVisible()
    // Use nth(0) or more specific selector for StatCards
    await expect(page.getByText('Platform', { exact: true })).toBeVisible()
    await expect(page.getByText('Mercury Bank', { exact: true })).toBeVisible()
  })

  test('Pending approvals table renders with correct columns', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Pending approvals' })).toBeVisible()
    
    // Check table headers - wait for the table to be visible after possible demo data loading
    // Since demo data might not have table by default, let's refresh with mocked data
    await page.route('**/mercury/pending-payments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          count: 1,
          payments: [{
            id: 'test-payment-id',
            recipient_id: 'test-recipient',
            amount: 100,
            payment_method: 'ACH',
            idempotency_key: 'key',
            note: 'note',
            status: 'pending',
            created_at: new Date().toISOString()
          }]
        })
      })
    })
    await page.getByRole('button', { name: 'Refresh' }).click()

    const table = page.locator('table.gaa-table');
    await expect(table).toBeVisible();
    await expect(table.getByRole('columnheader', { name: 'Recipient' })).toBeVisible()
    await expect(table.getByRole('columnheader', { name: 'Amount' })).toBeVisible()
    await expect(table.getByRole('columnheader', { name: 'Actions' })).toBeVisible()
  })

  test('Approving a payment shows a success toast', async ({ page }) => {
    // Intercept the API call to approve the payment
    await page.route('**/mercury/pending-payments/*/review', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, payment_id: 'test-id', status: 'approved' })
      })
    })

    // Mock initial payments to ensure at least one is visible
    await page.route('**/mercury/pending-payments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          count: 1,
          payments: [{
            id: 'test-payment-id-long-string',
            recipient_id: 'test-recipient',
            amount: 1500.50,
            payment_method: 'ACH',
            idempotency_key: 'id-key',
            note: 'Test Payment',
            status: 'pending',
            created_at: new Date().toISOString()
          }]
        })
      })
    })

    // Re-load the page or refresh the table
    await page.getByRole('button', { name: 'Refresh' }).click()
    
    // Check table headers - wait for the table to be visible after possible demo data loading
    const table = page.locator('table.gaa-table');
    await expect(table).toBeVisible();

    const approveBtn = page.getByRole('button', { name: 'Approve' }).first()
    await approveBtn.click()
    
    // Check for success toast
    await expect(page.locator('.gaa-toast-success')).toBeVisible({ timeout: 10000 })
    await expect(page.locator('.gaa-toast-success')).toContainText('approved')
  })

  test('Empty state is displayed when no payments are pending', async ({ page }) => {
    // Intercept API with empty payments
    await page.route('**/mercury/pending-payments', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, count: 0, payments: [] })
      })
    })

    await page.getByRole('button', { name: 'Refresh' }).click()

    await expect(page.getByText('All clear')).toBeVisible()
    await expect(page.getByText('No pending payments require approval.')).toBeVisible()
  })
})

import { test, expect } from '@playwright/test'
import { setupMockAuth } from './auth_utils'

test.describe('Client Portfolio Tab', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockAuth(page)
    await page.goto('/')
  })

  test('Portfolio summary KPIs are visible', async ({ page }) => {
    await expect(page.getByText('Managed Balance*')).toBeVisible()
    await expect(page.getByText('Total AR*')).toBeVisible()
    await expect(page.getByText('Total AP*')).toBeVisible()
    await expect(page.getByText('YTD Revenue*')).toBeVisible()
    await expect(page.getByText('Avg Health*')).toBeVisible()
  })

  test('Client health cards are rendered', async ({ page }) => {
    // Demo clients - use heading role or filter to avoid strict mode violation
    await expect(page.getByRole('paragraph').filter({ hasText: 'Hugga' })).toBeVisible()
    await expect(page.getByRole('paragraph').filter({ hasText: 'Cacoon' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Gernetzke & Associates' })).toBeVisible()
    await expect(page.getByRole('paragraph').filter({ hasText: 'Ghost Protocol LLC' })).toBeVisible()
  })

  test('Sorting client cards works', async ({ page }) => {
    // Sort by name
    await page.getByRole('button', { name: 'Name' }).click()
    
    // Use a more specific selector for the client name in the card
    const firstClientName = await page.locator('.gaa-card p.text-sm.font-bold').first().innerText()
    
    // Cacoon should come before Hugga when sorted by name
    expect(firstClientName).toBe('Cacoon')
  })

  test('Expanding a client card shows detailed metrics', async ({ page }) => {
    // Click on Hugga card
    const huggaCard = page.getByText('Hugga', { exact: true })
    await huggaCard.click()
    
    // Check if the detail panel with AR Aging breakdown appears
    await expect(page.getByText('AR aging breakdown', { exact: true })).toBeVisible()
    await expect(page.getByText('12-week revenue vs expense trend', { exact: true })).toBeVisible()
    await expect(page.getByText('Recommended agent actions', { exact: true })).toBeVisible()
  })

  test('Agent action queue is visible', async ({ page }) => {
    await expect(page.getByText('Agent action queue')).toBeVisible()
    await expect(page.getByText('Critical AR aging: 90+ days')).toBeVisible()
  })

  test('Run Agent button opens simulation modal', async ({ page }) => {
    // There are multiple "Run Agent" buttons. Let's pick one in the queue.
    const queueAction = page.locator('.gaa-card').filter({ hasText: 'Agent action queue' });
    const runAgentBtn = queueAction.getByRole('button', { name: 'Run Agent' }).first();
    
    await expect(runAgentBtn).toBeVisible();
    await runAgentBtn.click();
    
    // The modal might take a moment to animate in
    await expect(page.getByText('Agent execution summary')).toBeVisible({ timeout: 10000 })
    await expect(page.getByRole('button', { name: 'Approve & Send' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Dismiss' })).toBeVisible()
  })
})

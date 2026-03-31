import { test, expect } from '@playwright/test'
import { setupMockAuth } from './auth_utils'

// ── Mock analytics API responses so tests don't need a live backend ──────
async function mockAnalyticsAPIs(page: any) {
  // Dashboard summary
  await page.route('**/api/integrations/analytics/summary*', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total_balance: 1250000,
        total_inflow_30d: 425000,
        total_outflow_30d: 310000,
        reconciliation_rate: 94,
        ar_outstanding: 185000,
        ap_outstanding: 72000,
        pending_payments: 7,
        connectors: [{ platform: 'mercury', connected: true }],
      }),
    })
  })

  // Cash flow
  await page.route('**/api/integrations/analytics/cashflow*', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        cashflow: [
          { date: '2024-03-01', inflow: 40000, outflow: 30000, net: 10000 },
          { date: '2024-03-15', inflow: 55000, outflow: 28000, net: 27000 },
        ],
      }),
    })
  })

  // Category breakdown
  await page.route('**/api/integrations/analytics/categories*', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        categories: [
          { category: 'Payroll', amount: 120000, count: 4, color: '#6366f1' },
          { category: 'Software', amount: 18000, count: 12, color: '#8b5cf6' },
        ],
      }),
    })
  })

  // Recent transactions
  await page.route('**/api/integrations/analytics/transactions*', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        transactions: [
          { id: 't1', date: '2024-03-20', counterparty: 'Acme Corp', category: 'Revenue', platform: 'mercury', type: 'inflow', amount: 45000 },
          { id: 't2', date: '2024-03-18', counterparty: 'AWS', category: 'Software', platform: 'mercury', type: 'outflow', amount: 3200 },
        ],
      }),
    })
  })

  // AI insights
  await page.route('**/api/integrations/analytics/insights*', async (route: any) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        insights: [
          { id: 'i1', title: 'Unusual outflow spike detected', description: 'Outflow 28% above 30d average.', severity: 'warning', type: 'anomaly' },
          { id: 'i2', title: 'Cash flow projection: positive through April', description: 'Net positive trend continues.', severity: 'info', type: 'forecast' },
        ],
      }),
    })
  })
}

test.describe('Dashboard Analytics Tab', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockAuth(page)
    await mockAnalyticsAPIs(page)
    await page.goto('/')

    // Navigate to Analytics tab
    await page.getByRole('button', { name: 'Analytics' }).click()
  })

  test('Analytics tab renders header and KPI cards', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Dashboard analytics' })).toBeVisible()
    await expect(page.getByText('Total balance')).toBeVisible()
    await expect(page.getByText('30d inflow')).toBeVisible()
    await expect(page.getByText('30d outflow')).toBeVisible()
  })

  test('Charts are rendered on the analytics page', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Cash flow' })).toBeVisible()
    const count = await page.locator('.recharts-responsive-container').count()
    expect(count).toBeGreaterThanOrEqual(2)
    await expect(page.getByRole('heading', { name: 'Spending by category' })).toBeVisible()
  })

  test('Toggling date range updates charts', async ({ page }) => {
    let dateRangeRequested = ''
    await page.route('**/analytics/cashflow*', async (route: any) => {
      const url = new URL(route.request().url())
      dateRangeRequested = url.searchParams.get('days') || ''
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ cashflow: [] }),
      })
    })

    await page.getByRole('button', { name: '90d' }).click()
    expect(dateRangeRequested).toBe('90')
  })

  test('Recent transactions table is visible', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Recent transactions' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Counterparty' })).toBeVisible()
    await expect(page.getByRole('columnheader', { name: 'Amount' })).toBeVisible()
  })

  test('AI insights are displayed', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'AI insights' })).toBeVisible()
    await expect(page.getByText('Unusual outflow spike detected')).toBeVisible()
    await expect(page.getByText('Cash flow projection: positive through April')).toBeVisible()
  })
})

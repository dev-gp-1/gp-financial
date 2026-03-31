import { test, expect } from '@playwright/test'
import { setupMockAuth } from './auth_utils'

test.describe('Dashboard Layout & Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockAuth(page)
    await page.goto('/')
  })

  test('Main dashboard renders with header and footer', async ({ page }) => {
    await expect(page.locator('header.gaa-header')).toBeVisible()
    await expect(page.locator('footer.gaa-footer')).toBeVisible()
    // Use getByRole for the heading to avoid strict mode violation with the footer text
    await expect(page.getByRole('heading', { name: 'Gernetzke & Associates' })).toBeVisible()
    await expect(page.getByText('Financial Intelligence Platform', { exact: true })).toBeVisible()
  })

  test('Navigation between tabs works', async ({ page }) => {
    // Portfolio tab is default
    await expect(page.getByRole('heading', { name: 'Portfolio overview' })).toBeVisible()

    // Switch to Analytics
    await page.getByRole('button', { name: 'Analytics' }).click()
    await expect(page.getByRole('heading', { name: 'Dashboard analytics' })).toBeVisible()

    // Switch to Approvals
    await page.getByRole('button', { name: 'Approvals' }).click()
    await expect(page.getByRole('heading', { name: 'Payment approvals' })).toBeVisible()

    // Switch back to Portfolio
    await page.getByRole('button', { name: 'Portfolio' }).click()
    await expect(page.getByRole('heading', { name: 'Portfolio overview' })).toBeVisible()
  })

  test('Theme toggle works', async ({ page }) => {
    const html = page.locator('html')
    
    // Check initial state
    const initialTheme = await html.getAttribute('class')
    const themeToggle = page.getByLabel('Toggle theme')
    await themeToggle.click()
    
    // Check if the class changed
    const newTheme = await html.getAttribute('class')
    expect(newTheme).not.toEqual(initialTheme)
  })

  test('User menu displays initials and email', async ({ page }) => {
    // initials for 'Greg G'
    await expect(page.getByText('G', { exact: true }).nth(1)).toBeVisible()
    await expect(page.getByText('greg@ggernetzke.com')).toBeVisible()
    
    const signOutBtn = page.getByRole('button', { name: 'Sign out' })
    await expect(signOutBtn).toBeVisible()
  })
})

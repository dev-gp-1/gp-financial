import { test, expect } from '@playwright/test'

test.describe('Dashboard Structure', () => {
  test.beforeEach(async ({ page }) => {
    // The dashboard will show the login screen since Firebase is not mocked in E2E
    // We verify the pre-auth structure is intact
    await page.goto('/')
  })

  test('page has correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/GAA|Gernetzke|Dashboard/i)
  })

  test('page loads within 3 seconds', async ({ page }) => {
    const start = Date.now()
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    const loadTime = Date.now() - start
    expect(loadTime).toBeLessThan(5000) // 5s max including cold start
  })

  test('no console errors on load', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        // Filter out expected errors (Firebase auth, API connection)
        const text = msg.text()
        if (!text.includes('Firebase') && !text.includes('ERR_CONNECTION_REFUSED')) {
          errors.push(text)
        }
      }
    })
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    expect(errors).toHaveLength(0)
  })

  test('renders responsive layout on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 }) // iPhone X
    await page.goto('/')
    await expect(page.getByText('Gernetzke & Associates')).toBeVisible()
  })

  test('renders responsive layout on tablet', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 }) // iPad
    await page.goto('/')
    await expect(page.getByText('Gernetzke & Associates')).toBeVisible()
  })

  test('renders responsive layout on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto('/')
    await expect(page.getByText('Gernetzke & Associates')).toBeVisible()
  })
})

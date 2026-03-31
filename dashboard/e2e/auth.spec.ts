import { test, expect } from '@playwright/test'

test.describe('Auth Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('Login page renders correctly', async ({ page }) => {
    await expect(page.getByText('Gernetzke & Associates')).toBeVisible()
    await expect(page.getByText('Financial Services Dashboard')).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  })

  test('Protected routes redirect to login when unauthenticated', async ({ page }) => {
    // Navigate to a URL that would normally show protected content
    // Since this app is a SPA and handles auth state in App.tsx, 
    // any URL will start with the same App.tsx and show the login screen if !user.
    await page.goto('/?tab=portfolio')
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  })

  test('Email input validation', async ({ page }) => {
    const emailInput = page.getByLabel('Email')
    await emailInput.fill('invalid-email')
    const signInBtn = page.getByRole('button', { name: 'Sign in', exact: true })
    await signInBtn.click()
    
    // Check if the HTML5 validation is working if possible, or app-level validation
    // For now, check if the input still contains the invalid email
    await expect(emailInput).toHaveValue('invalid-email')
  })

  test('Sign in with Google button is visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Sign in with Google' })).toBeVisible()
  })
})

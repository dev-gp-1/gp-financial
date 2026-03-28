import { test, expect } from '@playwright/test'

test.describe('Login Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('renders company branding', async ({ page }) => {
    await expect(page.getByText('Gernetzke & Associates')).toBeVisible()
    await expect(page.getByText('Financial Services Dashboard')).toBeVisible()
  })

  test('renders G logo', async ({ page }) => {
    await expect(page.locator('text=G').first()).toBeVisible()
  })

  test('renders sign-in form', async ({ page }) => {
    await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
    await expect(page.getByText('Authorized personnel only.')).toBeVisible()
  })

  test('has email and password inputs', async ({ page }) => {
    await expect(page.getByLabel('Email')).toBeVisible()
    await expect(page.getByLabel('Password')).toBeVisible()
  })

  test('has Google sign-in button', async ({ page }) => {
    await expect(page.getByText('Sign in with Google')).toBeVisible()
  })

  test('has Firebase security footer', async ({ page }) => {
    await expect(page.getByText('Secured by Firebase Authentication')).toBeVisible()
  })

  test('email input accepts text', async ({ page }) => {
    const emailInput = page.getByLabel('Email')
    await emailInput.fill('test@example.com')
    await expect(emailInput).toHaveValue('test@example.com')
  })

  test('password input is masked', async ({ page }) => {
    const passwordInput = page.getByLabel('Password')
    await expect(passwordInput).toHaveAttribute('type', 'password')
  })

  test('sign-in button is present and enabled', async ({ page }) => {
    const signInBtn = page.getByRole('button', { name: 'Sign in', exact: true })
    await expect(signInBtn).toBeVisible()
    await expect(signInBtn).toBeEnabled()
  })
})

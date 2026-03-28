import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Auto-cleanup after each test
afterEach(() => {
  cleanup()
})

// Mock Firebase for all tests
vi.mock('../firebase', () => ({
  auth: {},
  isEmailAllowed: (email: string | null) => {
    if (!email) return false
    const allowed = [
      'greg@ggernetzke.com',
      'dean.barrett.86@gmail.com',
      'd.barrett@ghostprotocol.us',
    ]
    return allowed.includes(email.toLowerCase())
  },
  loginWithEmail: vi.fn(),
  loginWithGoogle: vi.fn(),
  logout: vi.fn(),
  onAuthChange: vi.fn(),
}))

// Mock import.meta.env
vi.stubGlobal('import', {
  meta: {
    env: {
      VITE_API_BASE: 'http://localhost:8000/api/integrations',
    },
  },
})

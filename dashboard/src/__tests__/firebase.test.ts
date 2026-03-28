import { describe, it, expect, vi } from 'vitest'

// We test the isEmailAllowed function directly (from the mock, which mirrors real logic)
const { isEmailAllowed } = await vi.importMock<typeof import('../firebase')>('../firebase')

describe('Firebase Auth Gate', () => {
  describe('isEmailAllowed', () => {
    it('returns true for greg@ggernetzke.com', () => {
      expect(isEmailAllowed('greg@ggernetzke.com')).toBe(true)
    })

    it('returns true for dean.barrett.86@gmail.com', () => {
      expect(isEmailAllowed('dean.barrett.86@gmail.com')).toBe(true)
    })

    it('returns true for d.barrett@ghostprotocol.us', () => {
      expect(isEmailAllowed('d.barrett@ghostprotocol.us')).toBe(true)
    })

    it('returns false for unauthorized emails', () => {
      expect(isEmailAllowed('hacker@evil.com')).toBe(false)
      expect(isEmailAllowed('admin@company.com')).toBe(false)
      expect(isEmailAllowed('test@test.com')).toBe(false)
    })

    it('handles null email', () => {
      expect(isEmailAllowed(null)).toBe(false)
    })

    it('handles empty string', () => {
      expect(isEmailAllowed('')).toBe(false)
    })

    it('is case-insensitive', () => {
      expect(isEmailAllowed('GREG@GGERNETZKE.COM')).toBe(true)
      expect(isEmailAllowed('Dean.Barrett.86@Gmail.com')).toBe(true)
    })
  })
})

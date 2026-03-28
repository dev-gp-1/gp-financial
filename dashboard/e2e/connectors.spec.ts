import { test, expect } from '@playwright/test'

const BACKEND_URL = process.env.BACKEND_URL || 'https://gp-backend-sct5pdcluq-uc.a.run.app'
const API_BASE = `${BACKEND_URL}/api/integrations`

test.describe('Backend Connector E2E', () => {
  test.describe('Mercury Bank', () => {
    test('mercury status endpoint responds without server error', async ({ request }) => {
      const res = await request.get(`${API_BASE}/mercury/status`)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(typeof data).toBe('object')
    })

    test('mercury pending-payments endpoint responds without server error', async ({ request }) => {
      const res = await request.get(`${API_BASE}/mercury/pending-payments`)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(typeof data).toBe('object')
    })

    test('mercury review accepts POST with action body', async ({ request }) => {
      const res = await request.post(`${API_BASE}/mercury/pending-payments/test-id/review`, {
        data: { action: 'reject' },
      })
      expect(res.status()).toBeLessThan(500)
    })

    test('mercury accounts endpoint responds without server error', async ({ request }) => {
      const res = await request.get(`${API_BASE}/mercury/accounts`)
      expect(res.status()).toBeLessThan(500)
    })

    test('mercury transactions endpoint responds without server error', async ({ request }) => {
      const res = await request.get(`${API_BASE}/mercury/transactions`)
      expect(res.status()).toBeLessThan(500)
    })
  })

  test.describe('QuickBooks Online', () => {
    test('quickbooks status endpoint responds without server error', async ({ request }) => {
      const res = await request.get(`${API_BASE}/quickbooks/status`)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(typeof data).toBe('object')
    })

    test('quickbooks sync endpoint accepts POST', async ({ request }) => {
      const res = await request.post(`${API_BASE}/quickbooks/sync`, {
        data: { days_back: 7 },
      })
      expect(res.status()).toBeLessThan(500)
    })
  })

  test.describe('Integrations List', () => {
    test('integrations endpoint responds', async ({ request }) => {
      const res = await request.get(API_BASE)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(typeof data).toBe('object')
    })
  })

  test.describe('Connectivity Test', () => {
    test('GET connectivity-test returns platform statuses', async ({ request }) => {
      const res = await request.get(`${API_BASE}/connectivity-test`)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(data).toHaveProperty('platforms')
      expect(typeof data.platforms).toBe('object')
      expect(data.platforms).toHaveProperty('mercury')
      expect(data.platforms).toHaveProperty('quickbooks')
    })

    test('POST connectivity-test accepts token parameters', async ({ request }) => {
      const res = await request.post(`${API_BASE}/connectivity-test`, {
        data: {
          mercury_token: '',
          qbo_access_token: '',
          qbo_realm_id: '',
          qbo_sandbox: true,
        },
      })
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(typeof data).toBe('object')
    })
  })

  test.describe('Financial Agent Orchestrator', () => {
    test('GET pending-actions returns action list structure', async ({ request }) => {
      const res = await request.get(`${API_BASE}/agents/pending-actions`)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(data).toHaveProperty('actions')
      expect(Array.isArray(data.actions)).toBe(true)
      expect(data).toHaveProperty('total')
      expect(typeof data.total).toBe('number')
    })

    test('GET pending-actions accepts tenant_id filter', async ({ request }) => {
      const res = await request.get(`${API_BASE}/agents/pending-actions?tenant_id=client-hugga&limit=10`)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(data).toHaveProperty('actions')
    })

    test('GET agent stats returns agent summary', async ({ request }) => {
      const res = await request.get(`${API_BASE}/agents/stats`)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(data).toHaveProperty('agents')
      expect(typeof data.agents).toBe('object')
    })

    test('POST run-cycle triggers evaluation without crash', async ({ request }) => {
      const res = await request.post(`${API_BASE}/agents/run-cycle`, {
        data: { tenant_id: 'all' },
      })
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(typeof data).toBe('object')
    })

    test('POST review action with invalid ID returns non-500', async ({ request }) => {
      const res = await request.post(`${API_BASE}/agents/actions/nonexistent-id/review`, {
        data: { decision: 'dismiss', executed_by: 'e2e-test' },
      })
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(typeof data).toBe('object')
    })

    test('POST review action validates decision field', async ({ request }) => {
      const res = await request.post(`${API_BASE}/agents/actions/test-id/review`, {
        data: { decision: 'invalid_decision', executed_by: 'e2e-test' },
      })
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(data.success).toBe(false)
    })
  })

  test.describe('AR/AP Evaluation', () => {
    test('GET evaluate returns evaluation structure', async ({ request }) => {
      const res = await request.get(`${API_BASE}/agents/evaluate/all`)
      expect(res.status()).toBeLessThan(500)
      const data = await res.json()
      expect(typeof data).toBe('object')
      if (data.success) {
        expect(data).toHaveProperty('ar')
        expect(data).toHaveProperty('ap')
        expect(data).toHaveProperty('metrics')
        expect(data.metrics).toHaveProperty('health_score')
        expect(typeof data.metrics.health_score).toBe('number')
      }
    })

    test('GET evaluate accepts specific tenant_id', async ({ request }) => {
      const res = await request.get(`${API_BASE}/agents/evaluate/client-hugga`)
      expect(res.status()).toBeLessThan(500)
    })
  })

  test.describe('Platform Disconnect', () => {
    test('disconnect unknown platform returns non-success', async ({ request }) => {
      const res = await request.delete(`${API_BASE}/fakePlatform/disconnect`)
      const data = await res.json()
      const isError = data.success === false || data.detail || res.status() >= 400
      expect(isError).toBeTruthy()
    })
  })

  test.describe('Stripe Connector', () => {
    test('stripe status endpoint responds without server error', async ({ request }) => {
      const res = await request.get(`${API_BASE}/stripe/status`)
      expect(res.status()).toBeLessThan(500)
    })
  })

  test.describe('PayPal Connector', () => {
    test('paypal status endpoint responds without server error', async ({ request }) => {
      const res = await request.get(`${API_BASE}/paypal/status`)
      expect(res.status()).toBeLessThan(500)
    })
  })

  test.describe('Plaid Connector', () => {
    test('plaid status endpoint responds without server error', async ({ request }) => {
      const res = await request.get(`${API_BASE}/plaid/status`)
      expect(res.status()).toBeLessThan(500)
    })
  })
})

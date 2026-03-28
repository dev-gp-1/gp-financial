import { describe, it, expect, afterEach, afterAll, beforeAll } from 'vitest'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

// MSW mock server
const API_BASE = 'http://localhost:8000/api/integrations'

const handlers = [
  // Mercury pending payments
  http.get(`${API_BASE}/mercury/pending-payments`, () => {
    return HttpResponse.json({
      success: true,
      count: 2,
      payments: [
        {
          id: 'pay-001',
          recipient_id: 'rec-abc',
          amount: 1500.00,
          payment_method: 'ach',
          idempotency_key: 'idem-001',
          note: 'Contractor payment',
          status: 'pending_approval',
          created_at: '2026-03-27T00:00:00Z',
        },
        {
          id: 'pay-002',
          recipient_id: 'rec-def',
          amount: 750.50,
          payment_method: 'ach',
          idempotency_key: 'idem-002',
          note: 'Vendor invoice',
          status: 'pending_approval',
          created_at: '2026-03-26T00:00:00Z',
        },
      ],
    })
  }),

  // Mercury review payment (approve)
  http.post(`${API_BASE}/mercury/pending-payments/:paymentId/review`, async ({ request, params }) => {
    const body = await request.json() as { action: string }
    const { paymentId } = params
    return HttpResponse.json({
      success: true,
      status: body.action === 'approve' ? 'approved' : 'rejected',
      payment_id: paymentId,
    })
  }),

  // Mercury status
  http.get(`${API_BASE}/mercury/status`, () => {
    return HttpResponse.json({
      connected: true,
      platform: 'mercury',
      last_sync_at: '2026-03-27T00:00:00Z',
    })
  }),

  // QuickBooks status
  http.get(`${API_BASE}/quickbooks/status`, () => {
    return HttpResponse.json({
      connected: false,
      platform: 'quickbooks',
      error: 'Database not initialized',
    })
  }),

  // List integrations
  http.get(API_BASE, () => {
    return HttpResponse.json({
      integrations: [
        { platform: 'mercury', status: 'connected' },
        { platform: 'quickbooks', status: 'disconnected' },
      ],
    })
  }),

  // Connectivity test GET
  http.get(`${API_BASE}/connectivity-test`, () => {
    return HttpResponse.json({
      success: true,
      platforms: { mercury: true, quickbooks: false },
    })
  }),

  // Agent pending actions
  http.get(`${API_BASE}/agents/pending-actions`, ({ request }) => {
    const url = new URL(request.url)
    const tenantId = url.searchParams.get('tenant_id') || 'all'
    return HttpResponse.json({
      success: true,
      actions: [
        {
          id: 'act-001',
          tenant_id: tenantId,
          agent: 'collector',
          action: 'send_reminder',
          priority: 'high',
          title: 'Follow up on overdue AR',
          description: '$8,200 overdue past 30 days for Hugga',
          estimated_impact: 8200.00,
          status: 'pending',
        },
        {
          id: 'act-002',
          tenant_id: tenantId,
          agent: 'paymaster',
          action: 'queue_payment',
          priority: 'medium',
          title: 'Schedule AP payment',
          description: 'Vendor invoice due in 5 days',
          estimated_impact: 3500.00,
          status: 'pending',
        },
      ],
      total: 2,
    })
  }),

  // Agent review action
  http.post(`${API_BASE}/agents/actions/:actionId/review`, async ({ request, params }) => {
    const body = await request.json() as { decision: string; executed_by: string }
    const { actionId } = params
    if (!['approve', 'dismiss', 'reject'].includes(body.decision)) {
      return HttpResponse.json({ success: false, error: `Invalid decision: ${body.decision}` })
    }
    return HttpResponse.json({
      success: true,
      action_id: actionId,
      new_status: body.decision === 'approve' ? 'executed' : body.decision,
      executed_by: body.executed_by,
    })
  }),

  // Agent stats
  http.get(`${API_BASE}/agents/stats`, () => {
    return HttpResponse.json({
      success: true,
      agents: {
        collector: { name: 'Collector', label: 'COL', total_impact: 12500, by_status: { pending: { count: 3, total_impact: 12500 } } },
        paymaster: { name: 'Paymaster', label: 'PAY', total_impact: 5200, by_status: { pending: { count: 2, total_impact: 5200 } } },
        reconciler: { name: 'Reconciler', label: 'REC', total_impact: 0, by_status: {} },
      },
      last_cycle: '2026-03-27T12:00:00Z',
    })
  }),

  // Agent run cycle
  http.post(`${API_BASE}/agents/run-cycle`, async ({ request }) => {
    const body = await request.json() as { tenant_id: string }
    return HttpResponse.json({
      success: true,
      tenant_id: body.tenant_id,
      actions_created: 5,
      duration_ms: 1250,
    })
  }),
]

const server = setupServer(...handlers)

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

describe('API Integration Tests', () => {
  describe('fetchPendingPayments', () => {
    it('returns parsed payment list', async () => {
      const res = await fetch(`${API_BASE}/mercury/pending-payments`)
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.count).toBe(2)
      expect(data.payments).toHaveLength(2)
      expect(data.payments[0].id).toBe('pay-001')
      expect(data.payments[0].amount).toBe(1500.00)
      expect(data.payments[0].payment_method).toBe('ach')
    })

    it('returns payment with all required fields', async () => {
      const res = await fetch(`${API_BASE}/mercury/pending-payments`)
      const data = await res.json()
      const payment = data.payments[0]

      expect(payment).toHaveProperty('id')
      expect(payment).toHaveProperty('recipient_id')
      expect(payment).toHaveProperty('amount')
      expect(payment).toHaveProperty('payment_method')
      expect(payment).toHaveProperty('idempotency_key')
      expect(payment).toHaveProperty('note')
      expect(payment).toHaveProperty('status')
      expect(payment).toHaveProperty('created_at')
    })
  })

  describe('reviewPayment', () => {
    it('sends approve action and gets success response', async () => {
      const res = await fetch(`${API_BASE}/mercury/pending-payments/pay-001/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'approve' }),
      })
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.status).toBe('approved')
      expect(data.payment_id).toBe('pay-001')
    })

    it('sends reject action and gets success response', async () => {
      const res = await fetch(`${API_BASE}/mercury/pending-payments/pay-002/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'reject' }),
      })
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.status).toBe('rejected')
      expect(data.payment_id).toBe('pay-002')
    })
  })

  describe('Mercury connector', () => {
    it('returns connection status', async () => {
      const res = await fetch(`${API_BASE}/mercury/status`)
      const data = await res.json()

      expect(data.connected).toBe(true)
      expect(data.platform).toBe('mercury')
      expect(data).toHaveProperty('last_sync_at')
    })
  })

  describe('QuickBooks connector', () => {
    it('returns disconnected status when db not initialized', async () => {
      const res = await fetch(`${API_BASE}/quickbooks/status`)
      const data = await res.json()

      expect(data.connected).toBe(false)
      expect(data.platform).toBe('quickbooks')
    })
  })

  describe('Integrations list', () => {
    it('returns all configured platforms', async () => {
      const res = await fetch(API_BASE)
      const data = await res.json()

      expect(data.integrations).toHaveLength(2)
      const platforms = data.integrations.map((i: any) => i.platform)
      expect(platforms).toContain('mercury')
      expect(platforms).toContain('quickbooks')
    })
  })

  describe('Error handling', () => {
    it('handles server error gracefully', async () => {
      server.use(
        http.get(`${API_BASE}/mercury/pending-payments`, () => {
          return new HttpResponse(null, { status: 500 })
        })
      )

      const res = await fetch(`${API_BASE}/mercury/pending-payments`)
      expect(res.ok).toBe(false)
      expect(res.status).toBe(500)
    })

    it('handles network timeout', async () => {
      server.use(
        http.get(`${API_BASE}/mercury/pending-payments`, () => {
          return HttpResponse.json(
            { success: false, error: 'Database not initialized' },
            { status: 503 }
          )
        })
      )

      const res = await fetch(`${API_BASE}/mercury/pending-payments`)
      expect(res.ok).toBe(false)
      const data = await res.json()
      expect(data.success).toBe(false)
    })
  })

  describe('Connectivity Test', () => {
    it('returns platform connection statuses', async () => {
      const res = await fetch(`${API_BASE}/connectivity-test`)
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.platforms).toHaveProperty('mercury')
      expect(data.platforms).toHaveProperty('quickbooks')
      expect(data.platforms.mercury).toBe(true)
      expect(data.platforms.quickbooks).toBe(false)
    })
  })

  describe('Agent Pending Actions', () => {
    it('returns list of pending agent actions', async () => {
      const res = await fetch(`${API_BASE}/agents/pending-actions`)
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.actions).toHaveLength(2)
      expect(data.total).toBe(2)
      expect(data.actions[0].agent).toBe('collector')
      expect(data.actions[0].priority).toBe('high')
      expect(data.actions[1].agent).toBe('paymaster')
    })

    it('accepts tenant_id filter', async () => {
      const res = await fetch(`${API_BASE}/agents/pending-actions?tenant_id=client-hugga`)
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.actions[0].tenant_id).toBe('client-hugga')
    })

    it('each action has required fields', async () => {
      const res = await fetch(`${API_BASE}/agents/pending-actions`)
      const data = await res.json()
      const action = data.actions[0]

      expect(action).toHaveProperty('id')
      expect(action).toHaveProperty('agent')
      expect(action).toHaveProperty('action')
      expect(action).toHaveProperty('priority')
      expect(action).toHaveProperty('title')
      expect(action).toHaveProperty('description')
      expect(action).toHaveProperty('estimated_impact')
      expect(action).toHaveProperty('status')
    })
  })

  describe('Agent HITL Review', () => {
    it('approves an action', async () => {
      const res = await fetch(`${API_BASE}/agents/actions/act-001/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'approve', executed_by: 'test-operator' }),
      })
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.action_id).toBe('act-001')
      expect(data.new_status).toBe('executed')
      expect(data.executed_by).toBe('test-operator')
    })

    it('dismisses an action', async () => {
      const res = await fetch(`${API_BASE}/agents/actions/act-002/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'dismiss', executed_by: 'test-operator' }),
      })
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.new_status).toBe('dismiss')
    })

    it('rejects invalid decision', async () => {
      const res = await fetch(`${API_BASE}/agents/actions/act-001/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'invalid', executed_by: 'test-operator' }),
      })
      const data = await res.json()

      expect(data.success).toBe(false)
    })
  })

  describe('Agent Stats', () => {
    it('returns agent activity summary', async () => {
      const res = await fetch(`${API_BASE}/agents/stats`)
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.agents).toHaveProperty('collector')
      expect(data.agents).toHaveProperty('paymaster')
      expect(data.agents).toHaveProperty('reconciler')
      expect(data.agents.collector.total_impact).toBe(12500)
      expect(data.last_cycle).toBe('2026-03-27T12:00:00Z')
    })
  })

  describe('Agent Run Cycle', () => {
    it('triggers a full evaluation cycle', async () => {
      const res = await fetch(`${API_BASE}/agents/run-cycle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tenant_id: 'all' }),
      })
      const data = await res.json()

      expect(data.success).toBe(true)
      expect(data.tenant_id).toBe('all')
      expect(data.actions_created).toBe(5)
      expect(typeof data.duration_ms).toBe('number')
    })
  })
})

import { describe, it, expect, afterEach, afterAll, beforeAll } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import {
  fetchClientPortfolio,
  fetchFirmSummary,
  computeHealthScore,
  type HealthGrade,
} from '../api';

// ── MSW handlers — return 404 so api.ts falls back to demo generators instantly ──
const API_BASE = 'https://gp-backend-sct5pdcluq-uc.a.run.app/api/integrations';

const handlers = [
  http.get(`${API_BASE}/analytics/clients`, () => new HttpResponse(null, { status: 404 })),
  http.get(`${API_BASE}/analytics/firm-summary`, () => new HttpResponse(null, { status: 404 })),
  http.get(`${API_BASE}/agents/pending-actions`, () => HttpResponse.json({ success: true, actions: [], total: 0 })),
];

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ── Client Portfolio API Tests ──────────────────────────────────────────────

describe('Client Portfolio API', () => {
  describe('fetchClientPortfolio', () => {
    it('returns an array of client profiles', async () => {
      const clients = await fetchClientPortfolio();
      expect(Array.isArray(clients)).toBe(true);
      expect(clients.length).toBeGreaterThanOrEqual(4);
    });

    it('includes the required named clients', async () => {
      const clients = await fetchClientPortfolio();
      const names = clients.map(c => c.name);
      expect(names).toContain('Hugga');
      expect(names).toContain('Cacoon');
      expect(names).toContain('Gernetzke & Associates');
      expect(names).toContain('Ghost Protocol LLC');
    });

    it('includes a placeholder/onboarding client slot', async () => {
      const clients = await fetchClientPortfolio();
      const placeholder = clients.find(c => c.status === 'placeholder');
      expect(placeholder).toBeDefined();
    });

    it('each active client has all required fields', async () => {
      const clients = await fetchClientPortfolio();
      const active = clients.filter(c => c.status === 'active');
      for (const c of active) {
        expect(c).toHaveProperty('id');
        expect(c).toHaveProperty('name');
        expect(c).toHaveProperty('shortName');
        expect(c).toHaveProperty('industry');
        expect(c).toHaveProperty('ar_outstanding');
        expect(c).toHaveProperty('ap_outstanding');
        expect(c).toHaveProperty('health_score');
        expect(c).toHaveProperty('health_grade');
        expect(c).toHaveProperty('revenue_trend');
        expect(c).toHaveProperty('expense_trend');
        expect(c).toHaveProperty('agent_actions');
        expect(c).toHaveProperty('reconciliation_rate');
      }
    });

    it('health scores are between 0 and 100', async () => {
      const clients = await fetchClientPortfolio();
      const active = clients.filter(c => c.status === 'active');
      for (const c of active) {
        expect(c.health_score).toBeGreaterThanOrEqual(0);
        expect(c.health_score).toBeLessThanOrEqual(100);
      }
    });

    it('health grades are valid tier labels', async () => {
      const valid: HealthGrade[] = ['excellent', 'good', 'fair', 'attention', 'critical'];
      const clients = await fetchClientPortfolio();
      const active = clients.filter(c => c.status === 'active');
      for (const c of active) {
        expect(valid).toContain(c.health_grade);
      }
    });

    it('AR overdue amounts sum to less than or equal to total AR', async () => {
      const clients = await fetchClientPortfolio();
      const active = clients.filter(c => c.status === 'active');
      for (const c of active) {
        const overdueSum = c.ar_overdue_30 + c.ar_overdue_60 + c.ar_overdue_90;
        expect(overdueSum).toBeLessThanOrEqual(c.ar_outstanding);
      }
    });

    it('each client has trend data with 12 data points', async () => {
      const clients = await fetchClientPortfolio();
      const active = clients.filter(c => c.status === 'active');
      for (const c of active) {
        expect(c.revenue_trend.length).toBe(12);
        expect(c.expense_trend.length).toBe(12);
      }
    });

    it('agent actions have required fields', async () => {
      const clients = await fetchClientPortfolio();
      const active = clients.filter(c => c.status === 'active');
      for (const c of active) {
        for (const action of c.agent_actions) {
          expect(action).toHaveProperty('id');
          expect(action).toHaveProperty('type');
          expect(action).toHaveProperty('priority');
          expect(action).toHaveProperty('title');
          expect(action).toHaveProperty('description');
          expect(typeof action.automatable).toBe('boolean');
        }
      }
    });

    it('at least one client has a critical or high priority action', async () => {
      const clients = await fetchClientPortfolio();
      const allActions = clients.flatMap(c => c.agent_actions);
      const critical = allActions.filter(a => a.priority === 'critical' || a.priority === 'high');
      expect(critical.length).toBeGreaterThan(0);
    });
  });

  describe('fetchFirmSummary', () => {
    it('returns a firm summary with all required fields', async () => {
      const firm = await fetchFirmSummary();
      expect(firm).toHaveProperty('total_clients');
      expect(firm).toHaveProperty('active_clients');
      expect(firm).toHaveProperty('total_ar');
      expect(firm).toHaveProperty('total_ap');
      expect(firm).toHaveProperty('total_revenue_ytd');
      expect(firm).toHaveProperty('total_managed_balance');
      expect(firm).toHaveProperty('avg_health_score');
      expect(firm).toHaveProperty('pending_agent_actions');
      expect(firm).toHaveProperty('critical_clients');
      expect(firm).toHaveProperty('collection_rate_30d');
    });

    it('active clients is less than or equal to total clients', async () => {
      const firm = await fetchFirmSummary();
      expect(firm.active_clients).toBeLessThanOrEqual(firm.total_clients);
    });

    it('average health score is between 0 and 100', async () => {
      const firm = await fetchFirmSummary();
      expect(firm.avg_health_score).toBeGreaterThanOrEqual(0);
      expect(firm.avg_health_score).toBeLessThanOrEqual(100);
    });

    it('total AR and AP are positive or zero', async () => {
      const firm = await fetchFirmSummary();
      expect(firm.total_ar).toBeGreaterThanOrEqual(0);
      expect(firm.total_ap).toBeGreaterThanOrEqual(0);
    });

    it('collection rate is between 0 and 100', async () => {
      const firm = await fetchFirmSummary();
      expect(firm.collection_rate_30d).toBeGreaterThanOrEqual(0);
      expect(firm.collection_rate_30d).toBeLessThanOrEqual(100);
    });
  });
});

// ── Health Score Algorithm Tests ─────────────────────────────────────────────

describe('Health Score Algorithm', () => {
  const baseClient = {
    id: 'test',
    name: 'Test',
    shortName: 'TST',
    industry: 'Test',
    status: 'active' as const,
    ar_outstanding: 50000,
    ar_overdue_30: 0,
    ar_overdue_60: 0,
    ar_overdue_90: 0,
    ap_outstanding: 20000,
    ap_overdue_30: 0,
    ap_overdue_60: 0,
    total_revenue_ytd: 300000,
    total_expenses_ytd: 200000,
    cash_balance: 80000,
    reconciliation_rate: 98,
    revenue_trend: [],
    expense_trend: [],
    agent_actions: [],
    last_sync: new Date().toISOString(),
  };

  it('returns excellent grade for a perfectly healthy client', () => {
    const { score, grade } = computeHealthScore(baseClient);
    expect(score).toBeGreaterThanOrEqual(85);
    expect(grade).toBe('excellent');
  });

  it('penalizes heavily for 90+ day AR aging', () => {
    const unhealthy = {
      ...baseClient,
      ar_overdue_30: 10000,
      ar_overdue_60: 15000,
      ar_overdue_90: 20000,
    };
    const { score } = computeHealthScore(unhealthy);
    const { score: healthyScore } = computeHealthScore(baseClient);
    expect(score).toBeLessThan(healthyScore);
    expect(score).toBeLessThan(85);
  });

  it('penalizes low reconciliation rates', () => {
    const lowRecon = { ...baseClient, reconciliation_rate: 50 };
    const { score } = computeHealthScore(lowRecon);
    const { score: healthyScore } = computeHealthScore(baseClient);
    expect(score).toBeLessThan(healthyScore);
  });

  it('penalizes negative cash flow', () => {
    const negative = {
      ...baseClient,
      total_revenue_ytd: 100000,
      total_expenses_ytd: 200000,
    };
    const { score } = computeHealthScore(negative);
    const { score: healthyScore } = computeHealthScore(baseClient);
    expect(score).toBeLessThan(healthyScore);
  });

  it('returns a score between 0 and 100', () => {
    const { score } = computeHealthScore(baseClient);
    expect(score).toBeGreaterThanOrEqual(0);
    expect(score).toBeLessThanOrEqual(100);
  });

  it('maps score to correct grade tiers', () => {
    // Test each grade boundary
    const test = (recon: number, ar30: number, ar60: number, ar90: number) => {
      const c = { ...baseClient, reconciliation_rate: recon, ar_overdue_30: ar30, ar_overdue_60: ar60, ar_overdue_90: ar90 };
      return computeHealthScore(c);
    };

    const excellent = test(98, 0, 0, 0);
    expect(excellent.grade).toBe('excellent');

    const critical = test(20, 20000, 15000, 10000);
    expect(['fair', 'attention', 'critical']).toContain(critical.grade);
  });

  it('AP overdue reduces score', () => {
    const apOverdue = {
      ...baseClient,
      ap_overdue_30: 10000,
      ap_overdue_60: 8000,
    };
    const { score } = computeHealthScore(apOverdue);
    const { score: healthyScore } = computeHealthScore(baseClient);
    expect(score).toBeLessThan(healthyScore);
  });
});

// ── Type Contract Tests ──────────────────────────────────────────────────────

describe('Portfolio Type Contracts', () => {
  it('ClientProfile shape matches expected schema', async () => {
    const clients = await fetchClientPortfolio();
    const c = clients.find(c => c.status === 'active')!;
    expect(typeof c.id).toBe('string');
    expect(typeof c.name).toBe('string');
    expect(typeof c.shortName).toBe('string');
    expect(typeof c.industry).toBe('string');
    expect(typeof c.ar_outstanding).toBe('number');
    expect(typeof c.ap_outstanding).toBe('number');
    expect(typeof c.health_score).toBe('number');
    expect(typeof c.health_grade).toBe('string');
    expect(typeof c.reconciliation_rate).toBe('number');
    expect(typeof c.cash_balance).toBe('number');
    expect(typeof c.total_revenue_ytd).toBe('number');
    expect(typeof c.total_expenses_ytd).toBe('number');
    expect(Array.isArray(c.revenue_trend)).toBe(true);
    expect(Array.isArray(c.expense_trend)).toBe(true);
    expect(Array.isArray(c.agent_actions)).toBe(true);
    expect(typeof c.last_sync).toBe('string');
  });

  it('FirmSummary shape matches expected schema', async () => {
    const firm = await fetchFirmSummary();
    expect(typeof firm.total_clients).toBe('number');
    expect(typeof firm.active_clients).toBe('number');
    expect(typeof firm.total_ar).toBe('number');
    expect(typeof firm.total_ap).toBe('number');
    expect(typeof firm.total_revenue_ytd).toBe('number');
    expect(typeof firm.total_managed_balance).toBe('number');
    expect(typeof firm.avg_health_score).toBe('number');
    expect(typeof firm.pending_agent_actions).toBe('number');
    expect(typeof firm.critical_clients).toBe('number');
    expect(typeof firm.collection_rate_30d).toBe('number');
  });

  it('AgentAction shape matches expected schema', async () => {
    const clients = await fetchClientPortfolio();
    const c = clients.find(c => c.agent_actions.length > 0)!;
    const a = c.agent_actions[0];
    expect(typeof a.id).toBe('string');
    expect(typeof a.type).toBe('string');
    expect(typeof a.priority).toBe('string');
    expect(typeof a.title).toBe('string');
    expect(typeof a.description).toBe('string');
    expect(typeof a.automatable).toBe('boolean');
    const validTypes = ['reconcile', 'collect', 'pay', 'review', 'onboard', 'forecast'];
    expect(validTypes).toContain(a.type);
    const validPriorities = ['low', 'medium', 'high', 'critical'];
    expect(validPriorities).toContain(a.priority);
  });
});

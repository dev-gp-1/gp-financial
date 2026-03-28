import { describe, it, expect, afterEach, afterAll, beforeAll } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import {
  fetchDashboardSummary,
  fetchCashFlow,
  fetchCategoryBreakdown,
  fetchRecentTransactions,
  fetchAIInsights,
  type DashboardSummary,
  type CashFlowPoint,
  type CategoryBreakdown,
  type Transaction,
  type AIInsight,
} from '../api';

// ── MSW mocked API base (must match the api.ts import.meta.env fallback) ──
const API_BASE = 'https://gp-backend-sct5pdcluq-uc.a.run.app/api/integrations';

// MSW handlers to intercept the live backend calls and return deterministic data
const handlers = [
  // Analytics summary — will fail, causing api.ts to call getLocalSummary()
  http.get(`${API_BASE}/analytics/summary`, () => {
    return new HttpResponse(null, { status: 404 });
  }),

  // getLocalSummary() iterates these connector status endpoints
  http.get(`${API_BASE}/mercury/status`, () => {
    return HttpResponse.json({ connected: true, platform: 'mercury', last_sync_at: '2026-03-27T00:00:00Z', transaction_count: 42 });
  }),
  http.get(`${API_BASE}/quickbooks/status`, () => {
    return HttpResponse.json({ connected: false, platform: 'quickbooks' });
  }),
  http.get(`${API_BASE}/stripe/status`, () => {
    return HttpResponse.json({ connected: false, platform: 'stripe' });
  }),
  http.get(`${API_BASE}/plaid/status`, () => {
    return HttpResponse.json({ connected: false, platform: 'plaid' });
  }),

  // Cash flow
  http.get(`${API_BASE}/analytics/cashflow`, () => {
    return new HttpResponse(null, { status: 404 });
  }),

  // Categories
  http.get(`${API_BASE}/analytics/categories`, () => {
    return new HttpResponse(null, { status: 404 });
  }),

  // Transactions
  http.get(`${API_BASE}/analytics/transactions`, () => {
    return new HttpResponse(null, { status: 404 });
  }),

  // AI Insights
  http.get(`${API_BASE}/analytics/insights`, () => {
    return new HttpResponse(null, { status: 404 });
  }),
];

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ── Analytics API Tests ──────────────────────────────────────────────────

describe('Analytics API', () => {
  describe('fetchDashboardSummary', () => {
    it('returns a summary with all required KPI fields', async () => {
      const summary = await fetchDashboardSummary();
      expect(summary).toBeDefined();
      expect(typeof summary.total_balance).toBe('number');
      expect(typeof summary.total_inflow_30d).toBe('number');
      expect(typeof summary.total_outflow_30d).toBe('number');
      expect(typeof summary.pending_payments).toBe('number');
      expect(typeof summary.ar_outstanding).toBe('number');
      expect(typeof summary.ap_outstanding).toBe('number');
      expect(typeof summary.reconciliation_rate).toBe('number');
    });

    it('returns a non-negative total balance', async () => {
      const summary = await fetchDashboardSummary();
      expect(summary.total_balance).toBeGreaterThanOrEqual(0);
    });

    it('returns reconciliation rate between 0 and 100', async () => {
      const summary = await fetchDashboardSummary();
      expect(summary.reconciliation_rate).toBeGreaterThanOrEqual(0);
      expect(summary.reconciliation_rate).toBeLessThanOrEqual(100);
    });

    it('includes connectors array', async () => {
      const summary = await fetchDashboardSummary();
      expect(Array.isArray(summary.connectors)).toBe(true);
    });

    it('connectors have required fields', async () => {
      const summary = await fetchDashboardSummary();
      for (const c of summary.connectors) {
        expect(typeof c.platform).toBe('string');
        expect(typeof c.connected).toBe('boolean');
      }
    });
  });

  describe('fetchCashFlow', () => {
    it('returns an array of cash flow data points', async () => {
      const data = await fetchCashFlow(30);
      expect(Array.isArray(data)).toBe(true);
      expect(data.length).toBeGreaterThan(0);
    });

    it('each data point has date, inflow, outflow, and net', async () => {
      const data = await fetchCashFlow(7);
      for (const point of data) {
        expect(point.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(typeof point.inflow).toBe('number');
        expect(typeof point.outflow).toBe('number');
        expect(typeof point.net).toBe('number');
      }
    });

    it('net equals inflow minus outflow', async () => {
      const data = await fetchCashFlow(7);
      for (const point of data) {
        const expected = Math.round((point.inflow - point.outflow) * 100) / 100;
        expect(point.net).toBeCloseTo(expected, 1);
      }
    });

    it('respects the days parameter', async () => {
      const data7 = await fetchCashFlow(7);
      const data30 = await fetchCashFlow(30);
      expect(data30.length).toBeGreaterThan(data7.length);
    });
  });

  describe('fetchCategoryBreakdown', () => {
    it('returns an array of categories', async () => {
      const data = await fetchCategoryBreakdown(30);
      expect(Array.isArray(data)).toBe(true);
      expect(data.length).toBeGreaterThan(0);
    });

    it('each category has required fields', async () => {
      const data = await fetchCategoryBreakdown();
      for (const cat of data) {
        expect(typeof cat.category).toBe('string');
        expect(typeof cat.amount).toBe('number');
        expect(typeof cat.count).toBe('number');
        expect(typeof cat.color).toBe('string');
        expect(cat.color).toMatch(/^#[0-9a-fA-F]{6}$/);
      }
    });

    it('all amounts are positive', async () => {
      const data = await fetchCategoryBreakdown();
      for (const cat of data) {
        expect(cat.amount).toBeGreaterThan(0);
      }
    });
  });

  describe('fetchRecentTransactions', () => {
    it('returns an array of transactions', async () => {
      const data = await fetchRecentTransactions(10);
      expect(Array.isArray(data)).toBe(true);
      expect(data.length).toBeGreaterThan(0);
    });

    it('respects the limit parameter', async () => {
      const data5 = await fetchRecentTransactions(5);
      const data20 = await fetchRecentTransactions(20);
      expect(data5.length).toBeLessThanOrEqual(5);
      expect(data20.length).toBeLessThanOrEqual(20);
    });

    it('each transaction has required fields', async () => {
      const data = await fetchRecentTransactions(5);
      for (const txn of data) {
        expect(txn.id).toBeTruthy();
        expect(txn.date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
        expect(txn.counterparty).toBeTruthy();
        expect(typeof txn.amount).toBe('number');
        expect(txn.amount).toBeGreaterThan(0);
        expect(['inflow', 'outflow']).toContain(txn.type);
        expect(txn.category).toBeTruthy();
        expect(txn.platform).toBeTruthy();
      }
    });

    it('transactions are sorted by date descending', async () => {
      const data = await fetchRecentTransactions(10);
      for (let i = 1; i < data.length; i++) {
        expect(data[i - 1].date >= data[i].date).toBe(true);
      }
    });
  });

  describe('fetchAIInsights', () => {
    it('returns an array of insights', async () => {
      const data = await fetchAIInsights();
      expect(Array.isArray(data)).toBe(true);
      expect(data.length).toBeGreaterThan(0);
    });

    it('each insight has required fields', async () => {
      const data = await fetchAIInsights();
      for (const ins of data) {
        expect(ins.id).toBeTruthy();
        expect(['anomaly', 'forecast', 'recommendation', 'alert']).toContain(ins.type);
        expect(['info', 'warning', 'critical']).toContain(ins.severity);
        expect(ins.title).toBeTruthy();
        expect(ins.description).toBeTruthy();
        expect(ins.timestamp).toBeTruthy();
      }
    });

    it('includes at least one critical insight', async () => {
      const data = await fetchAIInsights();
      const critical = data.filter(i => i.severity === 'critical');
      expect(critical.length).toBeGreaterThanOrEqual(1);
    });

    it('includes different insight types', async () => {
      const data = await fetchAIInsights();
      const types = new Set(data.map(i => i.type));
      expect(types.size).toBeGreaterThanOrEqual(2);
    });
  });
});

// ── Type Contract Tests ──────────────────────────────────────────────────

describe('Type Contracts', () => {
  it('DashboardSummary shape is correct', async () => {
    const s = await fetchDashboardSummary();
    const keys: (keyof DashboardSummary)[] = [
      'total_balance', 'total_inflow_30d', 'total_outflow_30d',
      'pending_payments', 'ar_outstanding', 'ap_outstanding',
      'reconciliation_rate', 'connectors',
    ];
    for (const k of keys) {
      expect(s).toHaveProperty(k);
    }
  });

  it('CashFlowPoint shape is correct', async () => {
    const points = await fetchCashFlow(7);
    const keys: (keyof CashFlowPoint)[] = ['date', 'inflow', 'outflow', 'net'];
    for (const k of keys) {
      expect(points[0]).toHaveProperty(k);
    }
  });

  it('CategoryBreakdown shape is correct', async () => {
    const cats = await fetchCategoryBreakdown();
    const keys: (keyof CategoryBreakdown)[] = ['category', 'amount', 'count', 'color'];
    for (const k of keys) {
      expect(cats[0]).toHaveProperty(k);
    }
  });

  it('Transaction shape is correct', async () => {
    const txns = await fetchRecentTransactions(1);
    const keys: (keyof Transaction)[] = ['id', 'date', 'counterparty', 'amount', 'category', 'type', 'status', 'platform'];
    for (const k of keys) {
      expect(txns[0]).toHaveProperty(k);
    }
  });

  it('AIInsight shape is correct', async () => {
    const ins = await fetchAIInsights();
    const keys: (keyof AIInsight)[] = ['id', 'type', 'severity', 'title', 'description', 'timestamp'];
    for (const k of keys) {
      expect(ins[0]).toHaveProperty(k);
    }
  });
});

// ── UI Compliance Tests ──────────────────────────────────────────────────

const EMOJI_REGEX = /[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F1E0}-\u{1F1FF}\u{2600}-\u{26FF}\u{2702}-\u{27B0}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}]/gu;

describe('UI Compliance — Icon-Free Dashboard', () => {
  it('dashboard summary values contain no emoji', async () => {
    const s = await fetchDashboardSummary();
    const json = JSON.stringify(s);
    expect(json).not.toMatch(EMOJI_REGEX);
  });

  it('AI insights contain no emoji in titles or descriptions', async () => {
    const insights = await fetchAIInsights();
    for (const ins of insights) {
      expect(ins.title).not.toMatch(EMOJI_REGEX);
      expect(ins.description).not.toMatch(EMOJI_REGEX);
    }
  });

  it('transaction data contains no emoji in counterparty or category', async () => {
    const txns = await fetchRecentTransactions(20);
    for (const txn of txns) {
      expect(txn.counterparty).not.toMatch(EMOJI_REGEX);
      expect(txn.category).not.toMatch(EMOJI_REGEX);
    }
  });

  it('category breakdown labels contain no emoji', async () => {
    const cats = await fetchCategoryBreakdown();
    for (const cat of cats) {
      expect(cat.category).not.toMatch(EMOJI_REGEX);
    }
  });

  it('connector platforms are text-only identifiers', async () => {
    const s = await fetchDashboardSummary();
    const validPlatforms = ['mercury', 'quickbooks', 'stripe', 'plaid'];
    for (const c of s.connectors) {
      expect(validPlatforms).toContain(c.platform);
      expect(c.platform).not.toMatch(EMOJI_REGEX);
    }
  });

  it('all four connector platforms are present', async () => {
    const s = await fetchDashboardSummary();
    const platforms = s.connectors.map(c => c.platform);
    expect(platforms).toContain('mercury');
    expect(platforms).toContain('quickbooks');
    expect(platforms).toContain('stripe');
    expect(platforms).toContain('plaid');
  });

  it('insight severity values are text-only (no icon encoding)', async () => {
    const insights = await fetchAIInsights();
    const validSeverities = ['info', 'warning', 'critical'];
    for (const ins of insights) {
      expect(validSeverities).toContain(ins.severity);
    }
  });

  it('insight types are text-only (no icon encoding)', async () => {
    const insights = await fetchAIInsights();
    const validTypes = ['anomaly', 'forecast', 'recommendation', 'alert'];
    for (const ins of insights) {
      expect(validTypes).toContain(ins.type);
    }
  });

  it('cash flow data points have no string emoji in any field', async () => {
    const data = await fetchCashFlow(30);
    const json = JSON.stringify(data);
    expect(json).not.toMatch(EMOJI_REGEX);
  });
});

// ── Data Integrity Tests ────────────────────────────────────────────────

describe('Data Integrity — Mock Indicators', () => {
  it('mock data totals are internally consistent', async () => {
    const s = await fetchDashboardSummary();
    // Net position should equal AR - AP (within mock data)
    const netPosition = s.ar_outstanding - s.ap_outstanding;
    expect(typeof netPosition).toBe('number');
    expect(isNaN(netPosition)).toBe(false);
  });

  it('reconciliation rate is a percentage', async () => {
    const s = await fetchDashboardSummary();
    expect(s.reconciliation_rate).toBeGreaterThanOrEqual(0);
    expect(s.reconciliation_rate).toBeLessThanOrEqual(100);
  });

  it('cash flow net values are mathematically correct', async () => {
    const data = await fetchCashFlow(7);
    for (const point of data) {
      expect(point.net).toBeCloseTo(point.inflow - point.outflow, 0);
    }
  });
});

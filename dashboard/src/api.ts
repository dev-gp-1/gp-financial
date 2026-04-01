const API_BASE = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_BASE || 'https://gp-financial-431115644565.us-central1.run.app') + '/api/integrations';
const TRON_API_BASE = import.meta.env.VITE_TRON_API || 'http://127.0.0.1:5000';

// ── Payment Types ────────────────────────────────────────────────────────

export interface PendingPayment {
  id: string;
  recipient_id: string;
  amount: number;
  payment_method: string;
  idempotency_key: string;
  note: string;
  status: string;
  created_at: string | null;
}

export interface PendingPaymentsResponse {
  success: boolean;
  count: number;
  payments: PendingPayment[];
  error?: string;
}

export interface ReviewResponse {
  success: boolean;
  status: string;
  payment_id: string;
  mercury_result?: Record<string, unknown>;
  error?: string;
}

// ── Analytics Types ──────────────────────────────────────────────────────

export interface CashFlowPoint {
  date: string;
  inflow: number;
  outflow: number;
  net: number;
}

export interface CategoryBreakdown {
  category: string;
  amount: number;
  count: number;
  color: string;
}

export interface Transaction {
  id: string;
  date: string;
  counterparty: string;
  amount: number;
  category: string;
  type: 'inflow' | 'outflow';
  status: string;
  platform: string;
}

export interface ConnectorStatus {
  platform: string;
  connected: boolean;
  last_sync_at: string | null;
  transaction_count?: number;
}

export interface DashboardSummary {
  total_balance: number;
  total_inflow_30d: number;
  total_outflow_30d: number;
  pending_payments: number;
  ar_outstanding: number;
  ap_outstanding: number;
  reconciliation_rate: number;
  connectors: ConnectorStatus[];
}

export interface AIInsight {
  id: string;
  type: 'anomaly' | 'forecast' | 'recommendation' | 'alert';
  severity: 'info' | 'warning' | 'critical';
  title: string;
  description: string;
  metric?: string;
  value?: number;
  timestamp: string;
}

// ── Client Portfolio Types ────────────────────────────────────────────────

export type HealthGrade = 'excellent' | 'good' | 'fair' | 'attention' | 'critical';

export interface ClientProfile {
  id: string;
  name: string;
  shortName: string;
  industry: string;
  status: 'active' | 'onboarding' | 'placeholder';
  // Financial metrics
  ar_outstanding: number;
  ar_overdue_30: number;
  ar_overdue_60: number;
  ar_overdue_90: number;
  ap_outstanding: number;
  ap_overdue_30: number;
  ap_overdue_60: number;
  total_revenue_ytd: number;
  total_expenses_ytd: number;
  cash_balance: number;
  reconciliation_rate: number;
  // Computed health
  health_score: number;
  health_grade: HealthGrade;
  // Trend data (last 12 weeks)
  revenue_trend: number[];
  expense_trend: number[];
  // Agent recommendations
  agent_actions: AgentAction[];
  last_sync: string;
}

export interface AgentAction {
  id: string;
  type: 'reconcile' | 'collect' | 'pay' | 'review' | 'onboard' | 'forecast';
  priority: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  estimated_impact?: number;
  automatable: boolean;
  clientName?: string;
  clientId?: string;
}

export interface FirmSummary {
  total_clients: number;
  active_clients: number;
  total_ar: number;
  total_ap: number;
  total_revenue_ytd: number;
  total_managed_balance: number;
  avg_health_score: number;
  pending_agent_actions: number;
  critical_clients: number;
  collection_rate_30d: number;
}

// ── Health Score Algorithm ────────────────────────────────────────────────
// Weighted composite: AR aging (30%), AP aging (15%), Reconciliation (25%), Cash flow (20%), Collection (10%)

export function computeHealthScore(client: Omit<ClientProfile, 'health_score' | 'health_grade'>): { score: number; grade: HealthGrade } {
  const arTotal = client.ar_outstanding || 1;
  const arAgingPenalty = ((client.ar_overdue_30 / arTotal) * 15) + ((client.ar_overdue_60 / arTotal) * 30) + ((client.ar_overdue_90 / arTotal) * 50);
  const arScore = Math.max(0, 100 - arAgingPenalty);

  const apTotal = client.ap_outstanding || 1;
  const apAgingPenalty = (client.ap_overdue_30 / apTotal) * 20 + (client.ap_overdue_60 / apTotal) * 40;
  const apScore = Math.max(0, 100 - apAgingPenalty);

  const reconScore = client.reconciliation_rate;

  const netCashFlow = client.total_revenue_ytd - client.total_expenses_ytd;
  const cashFlowRatio = client.total_revenue_ytd > 0 ? netCashFlow / client.total_revenue_ytd : 0;
  const cashFlowScore = Math.min(100, Math.max(0, 50 + cashFlowRatio * 100));

  const collectionScore = arTotal > 0 ? Math.max(0, 100 - ((client.ar_overdue_60 + client.ar_overdue_90) / arTotal) * 100) : 100;

  const score = Math.round(
    arScore * 0.30 + apScore * 0.15 + reconScore * 0.25 + cashFlowScore * 0.20 + collectionScore * 0.10
  );

  const grade: HealthGrade =
    score >= 85 ? 'excellent' :
    score >= 70 ? 'good' :
    score >= 55 ? 'fair' :
    score >= 40 ? 'attention' : 'critical';

  return { score, grade };
}

// ── Client Portfolio Endpoints ───────────────────────────────────────────

export async function fetchClientPortfolio(): Promise<ClientProfile[]> {
  try {
    const res = await fetch(`${API_BASE}/analytics/clients`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.clients ?? [];
  } catch {
    return generateDemoClients();
  }
}

export async function fetchFirmSummary(): Promise<FirmSummary> {
  try {
    const res = await fetch(`${API_BASE}/analytics/firm-summary`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch {
    return generateDemoFirmSummary();
  }
}

// ── Connectivity Status ──────────────────────────────────────────────────

export interface PlatformConnInfo {
  connected: boolean;
  account_count?: number;
  error?: string;
}

export interface ConnectivityResult {
  success: boolean;
  platforms: Record<string, PlatformConnInfo>;
  tested_at?: string;
  overall_status?: 'all_connected' | 'partial' | 'disconnected';
}

export async function fetchConnectivityStatus(): Promise<ConnectivityResult> {
  try {
    const res = await fetch(`${API_BASE}/connectivity-test`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Normalize: derive overall_status if not present
    const platforms: Record<string, PlatformConnInfo> = data.platforms ?? {};
    const vals = Object.values(platforms);
    const connectedCount = vals.filter(v => v.connected).length;
    const overall = connectedCount === vals.length ? 'all_connected' : connectedCount > 0 ? 'partial' : 'disconnected';
    return {
      success: data.success ?? true,
      platforms,
      tested_at: data.tested_at ?? new Date().toISOString(),
      overall_status: data.overall_status ?? overall,
    };
  } catch {
    return {
      success: false,
      platforms: {
        mercury: { connected: false },
        quickbooks: { connected: false },
        stripe: { connected: false },
        plaid: { connected: false },
      },
      tested_at: new Date().toISOString(),
      overall_status: 'disconnected',
    };
  }
}

// ── Agent Actions (tries new orchestrator endpoint first, falls back to TRON) ──

const AGENT_TYPE_MAP: Record<string, AgentAction['type']> = {
  collector: 'collect',
  paymaster: 'pay',
  reconciler: 'reconcile',
};

export async function fetchPendingAgentActions(): Promise<AgentAction[]> {
  // Try the new integrations orchestrator endpoint first
  try {
    const res = await fetch(`${API_BASE}/agents/pending-actions?limit=50`);
    if (res.ok) {
      const data = await res.json();
      if (data.actions && data.actions.length > 0) {
        return data.actions.map((a: any) => ({
          id: a.id,
          type: AGENT_TYPE_MAP[a.agent] || 'review',
          priority: a.priority || 'medium',
          title: a.title || a.action,
          description: a.description || '',
          estimated_impact: a.estimated_impact,
          automatable: a.params?.automatable ?? true,
          clientName: a.tenant_id !== 'all' ? a.tenant_id : undefined,
          clientId: a.tenant_id,
        }));
      }
    }
  } catch (e) {
    console.warn('Orchestrator pending-actions unavailable, trying TRON fallback', e);
  }

  // Fallback to TRON API
  try {
    const res = await fetch(`${TRON_API_BASE}/api/v1/agents/pending_actions`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.actions.map((a: any) => ({
      id: a.id,
      type: AGENT_TYPE_MAP[a.agent] || 'review',
      priority: a.priority || 'high',
      title: a.title || a.action,
      description: a.description || JSON.stringify(a.params),
      automatable: true,
      clientName: a.agent?.toUpperCase(),
    }));
  } catch (err) {
    console.warn('Failed to fetch TRON pending actions', err);
    return [];
  }
}

export async function executeAgentAction(actionId: string): Promise<boolean> {
  // Try the new HITL review endpoint
  try {
    const res = await fetch(`${API_BASE}/agents/actions/${actionId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: 'approve', executed_by: 'dashboard' }),
    });
    if (res.ok) return true;
  } catch {
    // Fallback to TRON
  }
  try {
    const res = await fetch(`${TRON_API_BASE}/api/v1/agents/execute/${actionId}`, {
      method: 'POST',
    });
    return res.ok;
  } catch (err) {
    console.error('Failed to execute action', err);
    return false;
  }
}

export async function discardAgentAction(actionId: string): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/agents/actions/${actionId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ decision: 'dismiss', executed_by: 'dashboard' }),
    });
    if (res.ok) return true;
  } catch {
    // Fallback
  }
  try {
    const res = await fetch(`${TRON_API_BASE}/api/v1/agents/pending_actions/${actionId}`, {
      method: 'DELETE',
    });
    return res.ok;
  } catch {
    return false;
  }
}

// ── Agent Stats ──────────────────────────────────────────────────────────

export interface AgentStats {
  agents: Record<string, {
    name: string;
    icon: string;
    by_status: Record<string, { count: number; total_impact: number }>;
    total_impact: number;
  }>;
  last_cycle: string | null;
}

export async function fetchAgentStats(): Promise<AgentStats | null> {
  try {
    const res = await fetch(`${API_BASE}/agents/stats`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function triggerAgentCycle(tenantId: string = 'all'): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/agents/run-cycle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tenant_id: tenantId }),
    });
    return res.json();
  } catch (err) {
    console.error('Failed to trigger agent cycle', err);
    return { success: false, error: String(err) };
  }
}

function generateTrend(base: number, variance: number, weeks: number = 12): number[] {
  const trend: number[] = [];
  let value = base;
  for (let i = 0; i < weeks; i++) {
    value += (Math.random() - 0.45) * variance;
    trend.push(Math.round(Math.max(0, value)));
  }
  return trend;
}

function generateDemoClients(): ClientProfile[] {
  const rawClients = [
    {
      id: 'client-hugga',
      name: 'Hugga',
      shortName: 'HUG',
      industry: 'Consumer Products',
      status: 'active' as const,
      ar_outstanding: 42350,
      ar_overdue_30: 8200,
      ar_overdue_60: 3100,
      ar_overdue_90: 0,
      ap_outstanding: 18700,
      ap_overdue_30: 2400,
      ap_overdue_60: 0,
      total_revenue_ytd: 285000,
      total_expenses_ytd: 198000,
      cash_balance: 67400,
      reconciliation_rate: 96.8,
      revenue_trend: generateTrend(24000, 3000),
      expense_trend: generateTrend(16500, 2000),
      agent_actions: [
        { id: 'ha-1', type: 'collect' as const, priority: 'medium' as const, title: 'Follow up on 30-day AR', description: 'Send automated reminder for $8,200 outstanding past 30 days', estimated_impact: 8200, automatable: true },
        { id: 'ha-2', type: 'reconcile' as const, priority: 'low' as const, title: 'Monthly bank reconciliation', description: 'QuickBooks sync pending for March transactions', automatable: true },
      ],
      last_sync: new Date(Date.now() - 3600000 * 2).toISOString(),
    },
    {
      id: 'client-cacoon',
      name: 'Cacoon',
      shortName: 'CAC',
      industry: 'Technology',
      status: 'active' as const,
      ar_outstanding: 31800,
      ar_overdue_30: 12500,
      ar_overdue_60: 7800,
      ar_overdue_90: 4200,
      ap_outstanding: 22100,
      ap_overdue_30: 5600,
      ap_overdue_60: 3200,
      total_revenue_ytd: 195000,
      total_expenses_ytd: 178000,
      cash_balance: 23400,
      reconciliation_rate: 78.5,
      revenue_trend: generateTrend(16500, 4000),
      expense_trend: generateTrend(15000, 3500),
      agent_actions: [
        { id: 'ca-1', type: 'collect' as const, priority: 'critical' as const, title: 'Critical AR aging: 90+ days', description: '$4,200 past 90 days — escalate to collections workflow', estimated_impact: 4200, automatable: false },
        { id: 'ca-2', type: 'reconcile' as const, priority: 'high' as const, title: 'Reconciliation gap detected', description: '78.5% reconciliation rate is below 90% threshold. 14 unmatched Mercury transactions', estimated_impact: 12800, automatable: true },
        { id: 'ca-3', type: 'pay' as const, priority: 'high' as const, title: 'AP overdue: 60-day invoices', description: '$3,200 in vendor invoices past 60 days. Risk of late payment penalties', estimated_impact: 3200, automatable: true },
      ],
      last_sync: new Date(Date.now() - 3600000 * 8).toISOString(),
    },
    {
      id: 'client-gaa',
      name: 'Gernetzke & Associates',
      shortName: 'GAA',
      industry: 'Professional Services',
      status: 'active' as const,
      ar_outstanding: 22150,
      ar_overdue_30: 5400,
      ar_overdue_60: 1200,
      ar_overdue_90: 0,
      ap_outstanding: 8430,
      ap_overdue_30: 1800,
      ap_overdue_60: 0,
      total_revenue_ytd: 348000,
      total_expenses_ytd: 245000,
      cash_balance: 127843,
      reconciliation_rate: 94.2,
      revenue_trend: generateTrend(29000, 2500),
      expense_trend: generateTrend(20500, 2000),
      agent_actions: [
        { id: 'ga-1', type: 'collect' as const, priority: 'medium' as const, title: 'AR follow-up: Trust Factor X', description: '$5,400 outstanding past 30 days from Trust Factor X', estimated_impact: 5400, automatable: true },
        { id: 'ga-2', type: 'forecast' as const, priority: 'low' as const, title: 'Q2 cash flow projection', description: 'Generate Q2 forecast using Gemini financial analysis', automatable: true },
      ],
      last_sync: new Date(Date.now() - 3600000 * 1).toISOString(),
    },
    {
      id: 'client-ghost',
      name: 'Ghost Protocol LLC',
      shortName: 'GP',
      industry: 'Security & Technology',
      status: 'active' as const,
      ar_outstanding: 56800,
      ar_overdue_30: 15200,
      ar_overdue_60: 8500,
      ar_overdue_90: 2100,
      ap_outstanding: 34200,
      ap_overdue_30: 8900,
      ap_overdue_60: 4500,
      total_revenue_ytd: 520000,
      total_expenses_ytd: 412000,
      cash_balance: 89600,
      reconciliation_rate: 88.4,
      revenue_trend: generateTrend(43500, 5000),
      expense_trend: generateTrend(34500, 4000),
      agent_actions: [
        { id: 'gp-1', type: 'collect' as const, priority: 'high' as const, title: 'AR aging: 60-day invoices', description: '$8,500 past 60 days. Automated reminders queued for EdgeConnex and EmbeddedHive', estimated_impact: 8500, automatable: true },
        { id: 'gp-2', type: 'reconcile' as const, priority: 'medium' as const, title: 'Mercury-QuickBooks sync gap', description: '88.4% reconciliation. 18 unmatched transactions detected', estimated_impact: 22400, automatable: true },
        { id: 'gp-3', type: 'review' as const, priority: 'medium' as const, title: 'Subcontractor payment review', description: '3 pending payments totaling $14,250 awaiting HITL approval', estimated_impact: 14250, automatable: false },
      ],
      last_sync: new Date(Date.now() - 3600000 * 4).toISOString(),
    },
    {
      id: 'client-tbd',
      name: 'New Client',
      shortName: 'NEW',
      industry: 'Onboarding',
      status: 'placeholder' as const,
      ar_outstanding: 0,
      ar_overdue_30: 0,
      ar_overdue_60: 0,
      ar_overdue_90: 0,
      ap_outstanding: 0,
      ap_overdue_30: 0,
      ap_overdue_60: 0,
      total_revenue_ytd: 0,
      total_expenses_ytd: 0,
      cash_balance: 0,
      reconciliation_rate: 0,
      revenue_trend: [],
      expense_trend: [],
      agent_actions: [
        { id: 'tbd-1', type: 'onboard' as const, priority: 'medium' as const, title: 'Initiate client onboarding', description: 'Connect bank accounts, configure QuickBooks integration, and set up automated workflows', automatable: false },
      ],
      last_sync: '',
    },
  ];

  return rawClients.map(c => {
    if (c.status === 'placeholder') {
      return { ...c, health_score: 0, health_grade: 'fair' as HealthGrade };
    }
    const { score, grade } = computeHealthScore(c);
    return { ...c, health_score: score, health_grade: grade };
  });
}

function generateDemoFirmSummary(): FirmSummary {
  const clients = generateDemoClients().filter(c => c.status === 'active');
  return {
    total_clients: 5,
    active_clients: clients.length,
    total_ar: clients.reduce((s, c) => s + c.ar_outstanding, 0),
    total_ap: clients.reduce((s, c) => s + c.ap_outstanding, 0),
    total_revenue_ytd: clients.reduce((s, c) => s + c.total_revenue_ytd, 0),
    total_managed_balance: clients.reduce((s, c) => s + c.cash_balance, 0),
    avg_health_score: Math.round(clients.reduce((s, c) => s + c.health_score, 0) / clients.length),
    pending_agent_actions: clients.reduce((s, c) => s + c.agent_actions.length, 0),
    critical_clients: clients.filter(c => c.health_grade === 'critical' || c.health_grade === 'attention').length,
    collection_rate_30d: 91.3,
  };
}

// ── Payment Endpoints ────────────────────────────────────────────────────

export async function fetchPendingPayments(): Promise<PendingPaymentsResponse> {
  const res = await fetch(`${API_BASE}/mercury/pending-payments`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function reviewPayment(paymentId: string, action: 'approve' | 'reject'): Promise<ReviewResponse> {
  const res = await fetch(`${API_BASE}/mercury/pending-payments/${paymentId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Analytics Endpoints ──────────────────────────────────────────────────

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  try {
    const res = await fetch(`${API_BASE}/analytics/summary`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  } catch {
    // Fallback: derive from individual connector endpoints
    return getLocalSummary();
  }
}

export async function fetchCashFlow(days: number = 30): Promise<CashFlowPoint[]> {
  try {
    const res = await fetch(`${API_BASE}/analytics/cashflow?days=${days}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.cashflow ?? [];
  } catch {
    return generateDemoCashFlow(days);
  }
}

export async function fetchCategoryBreakdown(days: number = 30): Promise<CategoryBreakdown[]> {
  try {
    const res = await fetch(`${API_BASE}/analytics/categories?days=${days}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.categories ?? [];
  } catch {
    return generateDemoCategories();
  }
}

export async function fetchRecentTransactions(limit: number = 20): Promise<Transaction[]> {
  try {
    const res = await fetch(`${API_BASE}/analytics/transactions?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.transactions ?? [];
  } catch {
    return generateDemoTransactions(limit);
  }
}

export async function fetchAIInsights(): Promise<AIInsight[]> {
  try {
    const res = await fetch(`${API_BASE}/analytics/insights`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return data.insights ?? [];
  } catch {
    return generateDemoInsights();
  }
}

// ── Demo/Fallback Data Generators ────────────────────────────────────────
// These provide realistic demo data when backend analytics endpoints are not yet deployed.
// Once the BigQuery aggregation pipeline is live, these gracefully fall away.

async function getLocalSummary(): Promise<DashboardSummary> {
  const connectors: ConnectorStatus[] = [];
  for (const platform of ['mercury', 'quickbooks', 'stripe', 'plaid']) {
    try {
      const res = await fetch(`${API_BASE}/${platform}/status`);
      const data = await res.json();
      connectors.push({
        platform,
        connected: data.connected ?? false,
        last_sync_at: data.last_sync_at ?? null,
        transaction_count: data.transaction_count,
      });
    } catch {
      connectors.push({ platform, connected: false, last_sync_at: null });
    }
  }

  return {
    total_balance: 127843.50,
    total_inflow_30d: 48250.00,
    total_outflow_30d: 31720.00,
    pending_payments: 3,
    ar_outstanding: 22150.00,
    ap_outstanding: 8430.00,
    reconciliation_rate: 94.2,
    connectors,
  };
}

function generateDemoCashFlow(days: number): CashFlowPoint[] {
  const points: CashFlowPoint[] = [];
  const now = new Date();
  for (let i = days; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const baseIn = 1200 + Math.random() * 2800;
    const baseOut = 800 + Math.random() * 2200;
    const inflow = i % 7 === 0 ? baseIn * 0.3 : baseIn;
    const outflow = i % 5 === 0 ? baseOut * 1.5 : baseOut;
    points.push({
      date: d.toISOString().split('T')[0],
      inflow: Math.round(inflow * 100) / 100,
      outflow: Math.round(outflow * 100) / 100,
      net: Math.round((inflow - outflow) * 100) / 100,
    });
  }
  return points;
}

function generateDemoCategories(): CategoryBreakdown[] {
  return [
    { category: 'Subcontractor Payments', amount: 14250, count: 8, color: '#6366f1' },
    { category: 'Software / SaaS', amount: 3420, count: 12, color: '#8b5cf6' },
    { category: 'Professional Services', amount: 5800, count: 4, color: '#a78bfa' },
    { category: 'Utilities / Infrastructure', amount: 2150, count: 6, color: '#c4b5fd' },
    { category: 'Revenue', amount: 48250, count: 15, color: '#10b981' },
    { category: 'Refunds / Credits', amount: 1230, count: 3, color: '#f59e0b' },
  ];
}

function generateDemoTransactions(limit: number): Transaction[] {
  const counterparties = [
    'EdgeConnex LLC', 'Trust Factor X', 'EmbeddedHive', 'Google Cloud Platform',
    'AWS Infrastructure', 'Mercury Transfer', 'Stripe Payout', 'QuickBooks Fee',
    'Adobe Creative Cloud', 'Slack Technologies', 'GitHub Enterprise', 'Vercel Inc',
  ];
  const categories = ['Revenue', 'Subcontractor', 'SaaS', 'Infrastructure', 'Professional Services'];
  const txns: Transaction[] = [];
  const now = new Date();

  for (let i = 0; i < Math.min(limit, 20); i++) {
    const d = new Date(now);
    d.setDate(d.getDate() - Math.floor(Math.random() * 30));
    const isInflow = Math.random() > 0.45;
    txns.push({
      id: `txn-${i.toString().padStart(4, '0')}`,
      date: d.toISOString().split('T')[0],
      counterparty: counterparties[Math.floor(Math.random() * counterparties.length)],
      amount: isInflow
        ? Math.round((1000 + Math.random() * 8000) * 100) / 100
        : Math.round((200 + Math.random() * 3000) * 100) / 100,
      category: categories[Math.floor(Math.random() * categories.length)],
      type: isInflow ? 'inflow' : 'outflow',
      status: 'completed',
      platform: Math.random() > 0.5 ? 'mercury' : 'quickbooks',
    });
  }
  return txns.sort((a, b) => b.date.localeCompare(a.date));
}

function generateDemoInsights(): AIInsight[] {
  return [
    {
      id: 'ins-001',
      type: 'anomaly',
      severity: 'warning',
      title: 'Unusual outflow spike detected',
      description: 'Outflows on Mar 24 were 2.3x the 30-day average. Primary driver: Subcontractor Payments ($14,250). Recommend reviewing the AP aging report for potential early-payment patterns.',
      metric: 'daily_outflow',
      value: 14250,
      timestamp: new Date().toISOString(),
    },
    {
      id: 'ins-002',
      type: 'forecast',
      severity: 'info',
      title: 'Cash flow projection: positive through April',
      description: 'Based on the current 30-day trend, projected net cash position by Apr 30 is +$16,530. AR collection rate of 94.2% is above the 90% target threshold.',
      metric: 'net_cash_projection',
      value: 16530,
      timestamp: new Date().toISOString(),
    },
    {
      id: 'ins-003',
      type: 'recommendation',
      severity: 'info',
      title: 'QuickBooks sync opportunity',
      description: '12 unmatched Mercury transactions could be auto-reconciled if QuickBooks sync is enabled. Potential time savings: ~2.5 hours of manual data entry per month.',
      metric: 'unmatched_transactions',
      value: 12,
      timestamp: new Date().toISOString(),
    },
    {
      id: 'ins-004',
      type: 'alert',
      severity: 'critical',
      title: 'AR aging: 3 invoices past 60 days',
      description: 'Trust Factor X ($8,200), EmbeddedHive ($4,500), and EdgeConnex ($3,150) have invoices beyond the 60-day collection window. Automated reminders have been queued.',
      metric: 'ar_overdue_60',
      value: 15850,
      timestamp: new Date().toISOString(),
    },
  ];
}

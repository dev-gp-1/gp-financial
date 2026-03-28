import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  fetchClientPortfolio,
  fetchFirmSummary,
  fetchPendingAgentActions,
  executeAgentAction,
  discardAgentAction,
  fetchConnectivityStatus,
  triggerAgentCycle,
  type ClientProfile,
  type FirmSummary,
  type HealthGrade,
  type AgentAction,
  type ConnectivityResult,
} from './api';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell, AreaChart, Area, Treemap,
} from 'recharts';

// ── Helpers ────────────────────────────────────────────────────────────────

const fmt = (n: number) =>
  n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` :
  n >= 1_000 ? `$${(n / 1_000).toFixed(0)}K` :
  `$${n.toFixed(0)}`;

const fmtFull = (n: number) =>
  `$${n.toLocaleString('en-US', { minimumFractionDigits: 0 })}`;

const HEALTH_COLORS: Record<HealthGrade, string> = {
  excellent: '#10B981',
  good: '#22D3EE',
  fair: '#F59E0B',
  attention: '#F97316',
  critical: '#EF4444',
};

const HEALTH_BG: Record<HealthGrade, string> = {
  excellent: 'rgba(16, 185, 129, 0.12)',
  good: 'rgba(34, 211, 238, 0.12)',
  fair: 'rgba(245, 158, 11, 0.12)',
  attention: 'rgba(249, 115, 22, 0.15)',
  critical: 'rgba(239, 68, 68, 0.15)',
};

const HEALTH_LABEL: Record<HealthGrade, string> = {
  excellent: 'Excellent',
  good: 'Good',
  fair: 'Fair',
  attention: 'Needs Attention',
  critical: 'Critical',
};

const PRIORITY_COLORS = {
  low: '#9CA3AF',
  medium: '#F59E0B',
  high: '#F97316',
  critical: '#EF4444',
};

const ACTION_LABELS: Record<AgentAction['type'], string> = {
  reconcile: 'REC',
  collect: 'COL',
  pay: 'PAY',
  review: 'REV',
  onboard: 'NEW',
  forecast: 'FCS',
};

type ChartType = 'bar' | 'area' | 'treemap';
type SortBy = 'health' | 'ar' | 'revenue' | 'name';

// ── Main Component ─────────────────────────────────────────────────────────

export default function ClientPortfolio() {
  const [clients, setClients] = useState<ClientProfile[]>([]);
  const [firm, setFirm] = useState<FirmSummary | null>(null);
  const [realActions, setRealActions] = useState<AgentAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedClient, setSelectedClient] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<SortBy>('health');
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [showActions, setShowActions] = useState(true);
  const [activeAction, setActiveAction] = useState<AgentAction | null>(null);
  const [agentStatus, setAgentStatus] = useState<'idle' | 'running' | 'done'>('idle');
  const [connectivity, setConnectivity] = useState<ConnectivityResult | null>(null);
  const [connLoading, setConnLoading] = useState(false);
  const [cycleRunning, setCycleRunning] = useState(false);

  useEffect(() => {
    Promise.all([fetchClientPortfolio(), fetchFirmSummary(), fetchPendingAgentActions()])
      .then(([c, f, a]) => {
        setClients(c);
        setFirm(f);
        setRealActions(a);
      })
      .finally(() => setLoading(false));

    // Auto-probe connectivity on mount
    fetchConnectivityStatus().then(setConnectivity).catch(() => {});
  }, []);

  const runConnectivityProbe = useCallback(async () => {
    setConnLoading(true);
    try {
      const result = await fetchConnectivityStatus();
      setConnectivity(result);
    } catch { /* silent */ }
    setConnLoading(false);
  }, []);

  const runAgentCycle = useCallback(async () => {
    setCycleRunning(true);
    try {
      await triggerAgentCycle();
      const refreshed = await fetchPendingAgentActions();
      setRealActions(refreshed);
    } catch { /* silent */ }
    setCycleRunning(false);
  }, []);

  const sortedClients = useMemo(() => {
    const active = clients.filter(c => c.status !== 'placeholder');
    const placeholder = clients.filter(c => c.status === 'placeholder');
    const sorted = [...active].sort((a, b) => {
      switch (sortBy) {
        case 'health': return a.health_score - b.health_score; // worst first (attention priority)
        case 'ar': return b.ar_outstanding - a.ar_outstanding;
        case 'revenue': return b.total_revenue_ytd - a.total_revenue_ytd;
        case 'name': return a.name.localeCompare(b.name);
        default: return 0;
      }
    });
    return [...sorted, ...placeholder];
  }, [clients, sortBy]);

  const activeClients = useMemo(() => clients.filter(c => c.status === 'active'), [clients]);

  const selected = useMemo(
    () => activeClients.find(c => c.id === selectedClient),
    [activeClients, selectedClient],
  );

  const allActions = useMemo(
    () => {
      const mockActions = activeClients.flatMap(c => c.agent_actions.map(a => ({ ...a, clientName: c.name, clientId: c.id })));
      return [...realActions, ...mockActions];
    },
    [activeClients, realActions],
  );

  const criticalActions = useMemo(
    () => allActions.filter(a => a.priority === 'critical' || a.priority === 'high').sort((a, b) => {
      const order = { critical: 0, high: 1, medium: 2, low: 3 };
      return order[a.priority] - order[b.priority];
    }),
    [allActions],
  );

  // ── AR/AP comparison data for chart ──────────────────────────────────
  const comparisonData = useMemo(
    () => activeClients.map(c => ({
      name: c.shortName,
      fullName: c.name,
      ar: c.ar_outstanding,
      ap: c.ap_outstanding,
      ar30: c.ar_overdue_30,
      ar60: c.ar_overdue_60,
      ar90: c.ar_overdue_90,
      health: c.health_score,
    })),
    [activeClients],
  );

  // ── Treemap data ─────────────────────────────────────────────────────
  const treemapData = useMemo(
    () => activeClients.map(c => ({
      name: c.shortName,
      size: c.total_revenue_ytd,
      fill: HEALTH_COLORS[c.health_grade],
    })),
    [activeClients],
  );

  // ── Pie data for firm AR distribution ─────────────────────────────────
  const arDistribution = useMemo(
    () => activeClients.map(c => ({
      name: c.shortName,
      value: c.ar_outstanding,
      color: HEALTH_COLORS[c.health_grade],
    })),
    [activeClients],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="w-10 h-10 rounded-full border-2 border-t-transparent animate-spin mx-auto mb-3"
            style={{ borderColor: 'var(--color-gaa-accent)', borderTopColor: 'transparent' }} />
          <p className="text-sm gaa-text-muted">Loading portfolio intelligence...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Connection Status Bar ────────────────────────────────────── */}
      <div className="gaa-card p-3 sm:p-4" style={{ background: 'var(--color-gaa-surface)' }}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold gaa-text-primary">Connectors</span>
            </div>
            {connectivity ? (
              Object.entries(connectivity.platforms || {}).map(([name, info]) => (
                <div key={name} className="flex items-center gap-1.5 text-xs">
                  <span className={`w-2 h-2 rounded-full inline-block ${(info as any)?.connected ? 'bg-emerald-400' : 'bg-red-400'}`}
                    style={{ boxShadow: (info as any)?.connected ? '0 0 6px #10B981' : '0 0 6px #EF4444' }} />
                  <span className="gaa-text-muted capitalize">{name}</span>
                </div>
              ))
            ) : (
              ['Mercury', 'QuickBooks', 'Stripe', 'Plaid'].map(n => (
                <div key={n} className="flex items-center gap-1.5 text-xs">
                  <span className="w-2 h-2 rounded-full inline-block bg-gray-500" />
                  <span className="gaa-text-muted">{n}</span>
                </div>
              ))
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={runConnectivityProbe} disabled={connLoading}
              className="gaa-btn-ghost text-[11px] px-3 py-1.5 rounded-md font-medium flex items-center gap-1.5 transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
              style={{ border: '1px solid var(--color-gaa-border)' }}>
              {connLoading ? 'Testing...' : 'Test Connections'}
            </button>
            <button onClick={runAgentCycle} disabled={cycleRunning}
              className="text-[11px] px-3 py-1.5 rounded-md font-bold flex items-center gap-1.5 transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
              style={{ background: 'rgba(99, 102, 241, 0.12)', color: '#818CF8', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
              {cycleRunning ? 'Running...' : 'Run Agent Cycle'}
            </button>
          </div>
        </div>
        {connectivity?.tested_at && (
          <div className="text-[10px] gaa-text-muted mt-2 flex items-center gap-2">
            <span>Last tested: {new Date(connectivity.tested_at).toLocaleString()}</span>
            {connectivity.overall_status && (
              <span className={`px-1.5 py-0.5 rounded-full font-bold ${
                connectivity.overall_status === 'all_connected' ? 'text-emerald-400' :
                connectivity.overall_status === 'partial' ? 'text-amber-400' : 'text-red-400'
              }`} style={{ background: connectivity.overall_status === 'all_connected' ? 'rgba(16,185,129,0.12)' :
                connectivity.overall_status === 'partial' ? 'rgba(245,158,11,0.12)' : 'rgba(239,68,68,0.12)' }}>
                {connectivity.overall_status === 'all_connected' ? 'All Connected' :
                 connectivity.overall_status === 'partial' ? 'Partial' : 'Disconnected'}
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── Firm KPI Banner ──────────────────────────────────────────── */}
      {firm && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <FirmKPI label="Managed Balance*" value={fmt(firm.total_managed_balance)} accent />
          <FirmKPI label="Total AR*" value={fmt(firm.total_ar)} />
          <FirmKPI label="Total AP*" value={fmt(firm.total_ap)} />
          <FirmKPI label="YTD Revenue*" value={fmt(firm.total_revenue_ytd)} />
          <FirmKPI label="Avg Health*" value={`${firm.avg_health_score}`} isScore score={firm.avg_health_score} />
          <FirmKPI label="Agent Actions" value={`${firm.pending_agent_actions}`} badge={firm.critical_clients > 0 ? `${firm.critical_clients} critical` : undefined} />
        </div>
      )}

      {/* ── Agent Action Queue (critical/high priority) ──────────────── */}
      {showActions && criticalActions.length > 0 && (
        <div className="gaa-card p-4 sm:p-5" style={{ background: 'var(--color-gaa-surface)' }}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-bold gaa-text-primary">Agent action queue</h3>
              <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#EF4444' }}>
                {criticalActions.length} priority
              </span>
            </div>
            <button onClick={() => setShowActions(false)} className="gaa-btn-ghost text-xs px-2 py-1">
              Collapse
            </button>
          </div>
          <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
            {criticalActions.map(action => (
              <div key={action.id} className="flex items-start gap-3 p-2.5 rounded-lg transition-colors"
                style={{ background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
                <span className="text-[10px] font-bold shrink-0 mt-0.5 w-7 h-7 rounded-md flex items-center justify-center" style={{ background: `${PRIORITY_COLORS[action.priority]}15`, color: PRIORITY_COLORS[action.priority] }}>{ACTION_LABELS[action.type]}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-bold gaa-text-primary truncate">{action.title}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold shrink-0"
                      style={{ background: `${PRIORITY_COLORS[action.priority]}20`, color: PRIORITY_COLORS[action.priority] }}>
                      {action.priority.toUpperCase()}
                    </span>
                  </div>
                  <p className="text-xs gaa-text-muted leading-relaxed">{action.description}</p>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="text-[10px] gaa-text-muted">{action.clientName}</span>
                    {action.estimated_impact && (
                      <span className="text-[10px] font-semibold" style={{ color: '#F59E0B' }}>
                        Impact: {fmtFull(action.estimated_impact)}
                      </span>
                    )}
                    {action.automatable && (
                      <button onClick={() => { setActiveAction(action); setAgentStatus('idle'); }} className="text-[10px] px-2 py-1 rounded-md font-bold transition-all hover:scale-105 active:scale-95"
                        style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10B981', outline: '1px solid #10B981' }}>
                        Run Agent
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {!showActions && criticalActions.length > 0 && (
        <button onClick={() => setShowActions(true)} className="gaa-btn-ghost text-xs w-full py-2">
          Show agent action queue ({criticalActions.length} priority items)
        </button>
      )}

      {/* ── Client Health Heatmap Grid ──────────────────────────────── */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-sm font-bold gaa-text-primary flex items-center gap-2">Client portfolio <span className="text-[10px] font-normal gaa-text-muted">* Mockup Data</span></h3>
            <p className="text-xs gaa-text-muted mt-0.5">Financial health heatmap — click a client for detailed view</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] gaa-text-muted font-medium">SORT:</span>
            {(['health', 'ar', 'revenue', 'name'] as SortBy[]).map(s => (
              <button key={s} onClick={() => setSortBy(s)}
                className={`text-[11px] px-2 py-1 rounded-md font-medium transition-all ${
                  sortBy === s ? 'gaa-text-primary' : 'gaa-text-muted'
                }`}
                style={sortBy === s ? { background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' } : undefined}>
                {s === 'ar' ? 'AR' : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {sortedClients.map((client, idx) => (
            <ClientHealthCard
              key={client.id}
              client={client}
              index={idx}
              isSelected={selectedClient === client.id}
              onClick={() => setSelectedClient(selectedClient === client.id ? null : client.id)}
            />
          ))}
        </div>
      </div>

      {/* ── Selected Client Detail Panel ─────────────────────────────── */}
      {selected && (
        <div className="gaa-card p-5 sm:p-6 fade-up" style={{ borderColor: HEALTH_COLORS[selected.health_grade] }}>
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold"
                style={{ background: HEALTH_BG[selected.health_grade], color: HEALTH_COLORS[selected.health_grade] }}>
                {selected.shortName}
              </div>
              <div>
                <h3 className="text-base font-bold gaa-text-primary">{selected.name}</h3>
                <p className="text-xs gaa-text-muted">{selected.industry} · Last sync {timeAgo(selected.last_sync)}</p>
              </div>
            </div>
            <button onClick={() => setSelectedClient(null)} className="gaa-btn-ghost text-xs px-2 py-1">Close</button>
          </div>

          {/* Detail Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            <DetailMetric label="AR Outstanding" value={fmtFull(selected.ar_outstanding)} color={selected.ar_overdue_60 > 0 ? '#F59E0B' : undefined} />
            <DetailMetric label="AP Outstanding" value={fmtFull(selected.ap_outstanding)} color={selected.ap_overdue_60 > 0 ? '#F97316' : undefined} />
            <DetailMetric label="Cash Balance" value={fmtFull(selected.cash_balance)} />
            <DetailMetric label="Reconciliation" value={`${selected.reconciliation_rate}%`} color={selected.reconciliation_rate < 90 ? '#EF4444' : '#10B981'} />
          </div>

          {/* AR Aging Breakdown */}
          <div className="mb-5">
            <h4 className="text-xs font-bold gaa-text-muted uppercase tracking-wide mb-2">AR aging breakdown</h4>
            <div className="flex items-center gap-1 h-5 rounded-full overflow-hidden" style={{ background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
              {(() => {
                const current = selected.ar_outstanding - selected.ar_overdue_30 - selected.ar_overdue_60 - selected.ar_overdue_90;
                const total = selected.ar_outstanding || 1;
                return (
                  <>
                    <div style={{ width: `${(current / total) * 100}%`, background: '#10B981' }} className="h-full rounded-l-full transition-all" title={`Current: ${fmtFull(current)}`} />
                    <div style={{ width: `${(selected.ar_overdue_30 / total) * 100}%`, background: '#F59E0B' }} className="h-full transition-all" title={`30+ days: ${fmtFull(selected.ar_overdue_30)}`} />
                    <div style={{ width: `${(selected.ar_overdue_60 / total) * 100}%`, background: '#F97316' }} className="h-full transition-all" title={`60+ days: ${fmtFull(selected.ar_overdue_60)}`} />
                    <div style={{ width: `${(selected.ar_overdue_90 / total) * 100}%`, background: '#EF4444' }} className="h-full rounded-r-full transition-all" title={`90+ days: ${fmtFull(selected.ar_overdue_90)}`} />
                  </>
                );
              })()}
            </div>
            <div className="flex items-center gap-4 mt-2">
              <span className="flex items-center gap-1 text-[10px] gaa-text-muted"><span className="w-2 h-2 rounded-full inline-block" style={{ background: '#10B981' }} /> Current</span>
              <span className="flex items-center gap-1 text-[10px] gaa-text-muted"><span className="w-2 h-2 rounded-full inline-block" style={{ background: '#F59E0B' }} /> 30+ days</span>
              <span className="flex items-center gap-1 text-[10px] gaa-text-muted"><span className="w-2 h-2 rounded-full inline-block" style={{ background: '#F97316' }} /> 60+ days</span>
              <span className="flex items-center gap-1 text-[10px] gaa-text-muted"><span className="w-2 h-2 rounded-full inline-block" style={{ background: '#EF4444' }} /> 90+ days</span>
            </div>
          </div>

          {/* Revenue vs Expense Trend */}
          {selected.revenue_trend.length > 0 && (
            <div>
              <h4 className="text-xs font-bold gaa-text-muted uppercase tracking-wide mb-2">12-week revenue vs expense trend</h4>
              <div className="h-[200px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={selected.revenue_trend.map((r, i) => ({
                    week: `W${i + 1}`,
                    revenue: r,
                    expenses: selected.expense_trend[i] || 0,
                    net: r - (selected.expense_trend[i] || 0),
                  }))}>
                    <defs>
                      <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="expGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#EF4444" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="week" tick={{ fontSize: 10 }} stroke="var(--color-gaa-text-muted, #9CA3AF)" />
                    <YAxis tick={{ fontSize: 10 }} stroke="var(--color-gaa-text-muted, #9CA3AF)" tickFormatter={v => fmt(v)} />
                    <Tooltip formatter={(v) => fmtFull(Number(v))} contentStyle={{ background: 'var(--color-gaa-surface, #fff)', border: '1px solid var(--color-gaa-border)', borderRadius: 8, fontSize: 12 }} />
                    <Area type="monotone" dataKey="revenue" stroke="#10B981" strokeWidth={2} fill="url(#revGrad)" name="Revenue" />
                    <Area type="monotone" dataKey="expenses" stroke="#EF4444" strokeWidth={2} fill="url(#expGrad)" name="Expenses" />
                    <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}

          {/* Client Agent Actions */}
          {selected.agent_actions.length > 0 && (
            <div className="mt-5">
              <h4 className="text-xs font-bold gaa-text-muted uppercase tracking-wide mb-2">Recommended agent actions</h4>
              <div className="space-y-2">
                {selected.agent_actions.map(action => (
                  <div key={action.id} className="flex items-start gap-3 p-3 rounded-lg"
                    style={{ background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
                    <span className="text-[10px] font-bold shrink-0 w-7 h-7 rounded-md flex items-center justify-center" style={{ background: `${PRIORITY_COLORS[action.priority]}15`, color: PRIORITY_COLORS[action.priority] }}>{ACTION_LABELS[action.type]}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold gaa-text-primary">{action.title}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold"
                          style={{ background: `${PRIORITY_COLORS[action.priority]}20`, color: PRIORITY_COLORS[action.priority] }}>
                          {action.priority.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-xs gaa-text-muted mt-0.5">{action.description}</p>
                    </div>
                    {action.automatable && (
                      <button onClick={() => { setActiveAction(action); setAgentStatus('idle'); }} className="gaa-btn-primary text-[10px] px-3 py-1.5 shrink-0 uppercase font-bold tracking-wider">Run Agent</button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Comparative Analytics Section ─────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* AR/AP Comparison Chart */}
        <div className="gaa-card p-4 sm:p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-bold gaa-text-primary">AR vs AP comparison*</h3>
              <p className="text-xs gaa-text-muted mt-0.5">Outstanding balances across all clients</p>
            </div>
            <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--color-gaa-border)' }}>
              {(['bar', 'area'] as ChartType[]).map(t => (
                <button key={t} onClick={() => setChartType(t)}
                  className={`text-[11px] px-2.5 py-1 font-medium transition-all ${
                    chartType === t ? 'bg-gaa-text text-white' : 'gaa-text-secondary'
                  }`}>
                  {t === 'bar' ? 'Bar' : 'Area'}
                </button>
              ))}
            </div>
          </div>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              {chartType === 'bar' ? (
                <BarChart data={comparisonData} barGap={6}>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--color-gaa-text-muted, #9CA3AF)" />
                  <YAxis tick={{ fontSize: 10 }} stroke="var(--color-gaa-text-muted, #9CA3AF)" tickFormatter={v => fmt(v)} />
                  <Tooltip formatter={(v) => fmtFull(Number(v))} contentStyle={{ background: 'var(--color-gaa-surface, #fff)', border: '1px solid var(--color-gaa-border)', borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="ar" name="AR Outstanding" fill="#F59E0B" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="ap" name="AP Outstanding" fill="#8B5CF6" radius={[4, 4, 0, 0]} />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                </BarChart>
              ) : (
                <AreaChart data={comparisonData}>
                  <defs>
                    <linearGradient id="arColorGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#F59E0B" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#F59E0B" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="apColorGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8B5CF6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#8B5CF6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--color-gaa-text-muted, #9CA3AF)" />
                  <YAxis tick={{ fontSize: 10 }} stroke="var(--color-gaa-text-muted, #9CA3AF)" tickFormatter={v => fmt(v)} />
                  <Tooltip formatter={(v) => fmtFull(Number(v))} contentStyle={{ background: 'var(--color-gaa-surface, #fff)', border: '1px solid var(--color-gaa-border)', borderRadius: 8, fontSize: 12 }} />
                  <Area type="monotone" dataKey="ar" stroke="#F59E0B" strokeWidth={2} fill="url(#arColorGrad)" name="AR Outstanding" />
                  <Area type="monotone" dataKey="ap" stroke="#8B5CF6" strokeWidth={2} fill="url(#apColorGrad)" name="AP Outstanding" />
                  <Legend iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                </AreaChart>
              )}
            </ResponsiveContainer>
          </div>
        </div>

        {/* AR Distribution Pie */}
        <div className="gaa-card p-4 sm:p-5">
          <div>
            <h3 className="text-sm font-bold gaa-text-primary">AR distribution by client*</h3>
            <p className="text-xs gaa-text-muted mt-0.5">Total receivables allocation</p>
          </div>
          <div className="h-[260px] flex items-center">
            <ResponsiveContainer width="60%" height="100%">
              <PieChart>
                <Pie data={arDistribution} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={90} innerRadius={45}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                  labelLine={false} stroke="var(--color-gaa-surface, #fff)" strokeWidth={2}>
                  {arDistribution.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => fmtFull(Number(v))} contentStyle={{ background: 'var(--color-gaa-surface, #fff)', border: '1px solid var(--color-gaa-border)', borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-2">
              {arDistribution.map(d => (
                <div key={d.name} className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: d.color }} />
                  <span className="text-xs gaa-text-secondary flex-1">{d.name}</span>
                  <span className="text-xs font-semibold gaa-text-primary">{fmt(d.value)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── AR Aging Heatmap Table ──────────────────────────────── */}
      <div className="gaa-card overflow-hidden">
        <div className="p-4 sm:p-5 border-b" style={{ borderColor: 'var(--color-gaa-border)' }}>
          <h3 className="text-sm font-bold gaa-text-primary">AR aging heatmap*</h3>
          <p className="text-xs gaa-text-muted mt-0.5">Visual receivables aging across all clients — warmer colors indicate higher risk</p>
        </div>
        <div className="overflow-x-auto">
          <table className="gaa-table w-full text-left">
            <thead>
              <tr>
                <th className="sticky left-0 z-10" style={{ background: 'var(--color-gaa-bg, #F9FAFB)' }}>Client</th>
                <th>Current</th>
                <th>30+ Days</th>
                <th>60+ Days</th>
                <th>90+ Days</th>
                <th>Total AR</th>
                <th>Health</th>
              </tr>
            </thead>
            <tbody>
              {activeClients.sort((a, b) => a.health_score - b.health_score).map(c => {
                const current = c.ar_outstanding - c.ar_overdue_30 - c.ar_overdue_60 - c.ar_overdue_90;
                const total = c.ar_outstanding || 1;
                return (
                  <tr key={c.id} className="cursor-pointer" onClick={() => setSelectedClient(c.id)}>
                    <td className="sticky left-0 z-10 font-semibold text-sm gaa-text-primary" style={{ background: 'var(--color-gaa-surface, #fff)' }}>
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: HEALTH_COLORS[c.health_grade] }} />
                        {c.shortName}
                      </div>
                    </td>
                    <td>
                      <span className="text-sm font-medium" style={{ color: '#10B981', background: `rgba(16, 185, 129, ${Math.min(0.2, (current / total) * 0.3)})`, padding: '2px 8px', borderRadius: 6 }}>
                        {fmtFull(current)}
                      </span>
                    </td>
                    <td>
                      <span className="text-sm font-medium" style={{ color: c.ar_overdue_30 > 0 ? '#F59E0B' : 'var(--color-gaa-text-muted)', background: c.ar_overdue_30 > 0 ? `rgba(245, 158, 11, ${Math.min(0.3, (c.ar_overdue_30 / total) * 0.6)})` : 'transparent', padding: '2px 8px', borderRadius: 6 }}>
                        {fmtFull(c.ar_overdue_30)}
                      </span>
                    </td>
                    <td>
                      <span className="text-sm font-medium" style={{ color: c.ar_overdue_60 > 0 ? '#F97316' : 'var(--color-gaa-text-muted)', background: c.ar_overdue_60 > 0 ? `rgba(249, 115, 22, ${Math.min(0.35, (c.ar_overdue_60 / total) * 0.7)})` : 'transparent', padding: '2px 8px', borderRadius: 6 }}>
                        {fmtFull(c.ar_overdue_60)}
                      </span>
                    </td>
                    <td>
                      <span className="text-sm font-medium" style={{ color: c.ar_overdue_90 > 0 ? '#EF4444' : 'var(--color-gaa-text-muted)', background: c.ar_overdue_90 > 0 ? `rgba(239, 68, 68, ${Math.min(0.35, (c.ar_overdue_90 / total) * 0.8)})` : 'transparent', padding: '2px 8px', borderRadius: 6 }}>
                        {fmtFull(c.ar_overdue_90)}
                      </span>
                    </td>
                    <td className="text-sm font-bold gaa-text-primary">{fmtFull(c.ar_outstanding)}</td>
                    <td>
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-2 rounded-full overflow-hidden" style={{ background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
                          <div className="h-full rounded-full transition-all" style={{ width: `${c.health_score}%`, background: HEALTH_COLORS[c.health_grade] }} />
                        </div>
                        <span className="text-xs font-bold" style={{ color: HEALTH_COLORS[c.health_grade] }}>{c.health_score}</span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Revenue Treemap ───────────────────────────────────────── */}
      <div className="gaa-card p-4 sm:p-5 relative">
        <div className="mb-4">
          <h3 className="text-sm font-bold gaa-text-primary flex items-center gap-2">YTD revenue — proportional view <span className="text-[10px] font-normal gaa-text-muted">* Mockup Data</span></h3>
          <p className="text-xs gaa-text-muted mt-0.5">Block size = revenue share, color = health score</p>
        </div>
        <div className="h-[200px]">
          <ResponsiveContainer width="100%" height="100%">
            <Treemap data={treemapData} dataKey="size" nameKey="name" stroke="var(--color-gaa-surface, #fff)"
              content={(props: any) => {
                const { x, y, width, height, name, fill } = props;
                if (width < 35 || height < 35) return <g />;
                const client = activeClients.find(c => c.shortName === name);
                const valText = client ? `${fmt(client.total_revenue_ytd)}*` : '';
                return (
                  <g className="cursor-pointer group">
                    <rect x={x} y={y} width={width} height={height} rx={6} fill={fill} opacity={0.85} className="transition-all duration-300 group-hover:opacity-100" />
                    <text x={x + width / 2} y={y + height / 2 - 6} textAnchor="middle" fill="#fff" fontSize={15} fontWeight={800}>{name}</text>
                    <text x={x + width / 2} y={y + height / 2 + 12} textAnchor="middle" fill="rgba(255,255,255,0.9)" fontSize={13} fontWeight={700}>
                      {valText}
                    </text>
                  </g>
                );
              }}
            />
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Health Score Legend ──────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-center gap-4 py-3">
        {(Object.keys(HEALTH_COLORS) as HealthGrade[]).map(grade => (
          <div key={grade} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-sm" style={{ background: HEALTH_COLORS[grade] }} />
            <span className="text-[11px] gaa-text-muted font-medium">{HEALTH_LABEL[grade]}</span>
          </div>
        ))}
      </div>

      {/* ── Agent Execution Modal (HITL) ─────────────────────────── */}
      {activeAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm fade-in">
          <div className="gaa-card w-full max-w-xl p-0 overflow-hidden fade-up shadow-2xl border border-gaa-border">
            {/* Header */}
            <div className="p-4 sm:p-5 border-b" style={{ borderColor: 'var(--color-gaa-border)', background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold gaa-text-primary">Agent execution summary</h2>
                </div>
                <button onClick={() => { setActiveAction(null); setAgentStatus('idle'); }} className="text-xs font-medium gaa-text-muted hover:gaa-text-primary px-2 py-1">Close</button>
              </div>
              <p className="text-sm font-semibold gaa-text-primary">{activeAction.title}</p>
              <p className="text-xs gaa-text-muted mt-1 leading-relaxed">The agent has structured the following workflow based on your target constraints.</p>
            </div>
            
            {/* Reasoning / Payload */}
            <div className="p-4 sm:p-5 space-y-4">
              <div className="rounded-lg p-4 font-mono text-[11px] sm:text-xs text-green-400 overflow-x-auto border border-green-900/30"
                   style={{ background: '#0f172a' }}>
                <p className="text-gray-400 mb-2">// Proposed Agent Intent:</p>
                <div className="whitespace-pre-wrap leading-relaxed">
{`{
  "target": "${activeAction.clientName || 'Internal'}",
  "action_type": "${activeAction.type}",
  "priority_flag": "${activeAction.priority}",
  "parameters": {
    "estimated_recovery": ${activeAction.estimated_impact || 0},
    "trigger_reason": "${activeAction.description.replace(/"/g, '\\"')}"
  },
  "safety_guard": "HITL_REQUIRED"
}`}
                </div>
              </div>

              {/* Status Simulation */}
              {agentStatus === 'running' && (
                <div className="flex items-center gap-3 text-sm font-bold" style={{ color: 'var(--color-gaa-accent)' }}>
                  <div className="w-5 h-5 rounded-full border-2 border-t-transparent animate-spin" style={{ borderColor: 'var(--color-gaa-accent)', borderTopColor: 'transparent' }} />
                  Agent executing action...
                </div>
              )}
              {agentStatus === 'done' && (
                <div className="flex items-center gap-2 p-3 rounded-lg" style={{ background: 'rgba(16, 185, 129, 0.12)', color: '#10B981' }}>
                  <span className="text-xs font-bold uppercase" style={{ color: '#10B981' }}>Done</span>
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wide">Execution Complete</h4>
                    <p className="text-xs mt-0.5">Agent successfully completed the workflow and updated internal logs.</p>
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="p-4 sm:p-5 border-t flex justify-end gap-3" style={{ borderColor: 'var(--color-gaa-border)', background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
              <button 
                onClick={() => { setActiveAction(null); setAgentStatus('idle'); }}
                className="gaa-btn-ghost text-xs px-4 py-2"
                disabled={agentStatus === 'running'}
              >
                {agentStatus === 'done' ? 'Close' : 'Cancel'}
              </button>
              {agentStatus === 'idle' && (
                <>
                  <button 
                    onClick={async () => {
                      if (activeAction && realActions.some(a => a.id === activeAction.id)) {
                        await discardAgentAction(activeAction.id);
                        setRealActions(prev => prev.filter(a => a.id !== activeAction.id));
                      }
                      setActiveAction(null);
                    }}
                    className="text-xs px-4 py-2 rounded-md font-medium transition-all hover:scale-105 active:scale-95"
                    style={{ background: 'rgba(239, 68, 68, 0.10)', color: '#EF4444', border: '1px solid rgba(239, 68, 68, 0.25)' }}
                  >
                    Dismiss
                  </button>
                  <button 
                    onClick={async () => { 
                      setAgentStatus('running'); 
                      if (activeAction && realActions.some(a => a.id === activeAction.id)) {
                        await executeAgentAction(activeAction.id);
                        setRealActions(prev => prev.filter(a => a.id !== activeAction.id));
                      }
                      setTimeout(() => setAgentStatus('done'), 1500); 
                    }}
                    className="gaa-btn-primary text-xs px-5 py-2 flex items-center gap-2 font-bold"
                  >
                    Approve & Send
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-Components ──────────────────────────────────────────────────────────

function FirmKPI({ label, value, accent, isScore, score, badge }: {
  label: string; value: string; accent?: boolean; isScore?: boolean; score?: number; badge?: string;
}) {
  const gradeColor = isScore && score
    ? score >= 85 ? '#10B981' : score >= 70 ? '#22D3EE' : score >= 55 ? '#F59E0B' : '#EF4444'
    : undefined;

  return (
    <div className={`gaa-card p-3 sm:p-4 ${accent ? 'gaa-card-featured' : ''}`}>
      <p className="text-[10px] font-bold uppercase tracking-wider gaa-text-muted mb-1">{label}</p>
      <p className="text-lg sm:text-xl font-bold gaa-text-primary" style={gradeColor ? { color: gradeColor } : undefined}>
        {value}
      </p>
      {badge && (
        <span className="text-[10px] mt-1 inline-block px-2 py-0.5 rounded-full font-bold"
          style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#EF4444' }}>
          {badge}
        </span>
      )}
    </div>
  );
}

function ClientHealthCard({ client, index, isSelected, onClick }: {
  client: ClientProfile; index: number; isSelected: boolean; onClick: () => void;
}) {
  const isPlaceholder = client.status === 'placeholder';
  const color = isPlaceholder ? '#9CA3AF' : HEALTH_COLORS[client.health_grade];
  const bg = isPlaceholder ? 'rgba(156, 163, 175, 0.08)' : HEALTH_BG[client.health_grade];

  return (
    <div
      className={`gaa-card p-4 cursor-pointer transition-all duration-300 fade-up ${isSelected ? 'ring-2' : ''}`}
      style={{
        animationDelay: `${index * 80}ms`,
        borderLeftWidth: 4,
        borderLeftColor: color,
        ...(isSelected ? { ringColor: color, boxShadow: `0 0 0 2px ${color}40` } : {}),
      }}
      onClick={onClick}
    >
      {isPlaceholder ? (
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-3 text-xl"
            style={{ background: bg, color }}>
            +
          </div>
          <p className="text-sm font-semibold gaa-text-primary">Add / onboard client</p>
          <p className="text-xs gaa-text-muted mt-1">Connect bank, QuickBooks, and start workflows</p>
        </div>
      ) : (
        <>
          {/* Header */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold"
                style={{ background: bg, color }}>
                {client.shortName}
              </div>
              <div>
                <p className="text-sm font-bold gaa-text-primary leading-tight">{client.name}</p>
                <p className="text-[10px] gaa-text-muted">{client.industry}</p>
              </div>
            </div>
            {/* Health Score Circle */}
            <div className="relative w-11 h-11">
              <svg className="w-11 h-11 -rotate-90" viewBox="0 0 44 44">
                <circle cx="22" cy="22" r="18" fill="none" stroke="var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))" strokeWidth="3" />
                <circle cx="22" cy="22" r="18" fill="none" stroke={color} strokeWidth="3"
                  strokeDasharray={`${(client.health_score / 100) * 113.1} 113.1`}
                  strokeLinecap="round" className="transition-all duration-700" />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-xs font-bold" style={{ color }}>
                {client.health_score}
              </span>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-3 gap-2 mb-3">
            <div className="rounded-lg p-2 text-center" style={{ background: bg }}>
              <p className="text-[9px] font-bold uppercase tracking-wide gaa-text-muted">AR</p>
              <p className="text-xs font-bold gaa-text-primary">{fmt(client.ar_outstanding)}</p>
            </div>
            <div className="rounded-lg p-2 text-center" style={{ background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
              <p className="text-[9px] font-bold uppercase tracking-wide gaa-text-muted">AP</p>
              <p className="text-xs font-bold gaa-text-primary">{fmt(client.ap_outstanding)}</p>
            </div>
            <div className="rounded-lg p-2 text-center" style={{ background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
              <p className="text-[9px] font-bold uppercase tracking-wide gaa-text-muted">Recon</p>
              <p className="text-xs font-bold" style={{ color: client.reconciliation_rate >= 90 ? '#10B981' : '#F59E0B' }}>
                {client.reconciliation_rate}%
              </p>
            </div>
          </div>

          {/* Health Bar */}
          <div className="flex items-center gap-2 mb-2">
            <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
              <div className="h-full rounded-full transition-all duration-700" style={{ width: `${client.health_score}%`, background: color }} />
            </div>
            <span className="text-[10px] font-bold shrink-0" style={{ color }}>{HEALTH_LABEL[client.health_grade]}</span>
          </div>

          {/* Agent Actions Count */}
          {client.agent_actions.length > 0 && (
            <div className="flex items-center justify-between pt-2 border-t" style={{ borderColor: 'var(--color-gaa-border)' }}>
              <span className="text-[10px] gaa-text-muted">
                {client.agent_actions.length} agent action{client.agent_actions.length !== 1 ? 's' : ''}
              </span>
              {client.agent_actions.some(a => a.priority === 'critical') && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full font-bold" style={{ background: 'rgba(239, 68, 68, 0.12)', color: '#EF4444' }}>
                  Critical
                </span>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function DetailMetric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-lg p-3" style={{ background: 'var(--color-gaa-bg-alt, var(--color-gaa-dark-bg-alt))' }}>
      <p className="text-[10px] font-bold uppercase tracking-wide gaa-text-muted mb-1">{label}</p>
      <p className="text-sm font-bold" style={{ color: color || 'var(--color-gaa-text)' }}>{value}</p>
    </div>
  );
}

function timeAgo(iso: string): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

import { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  fetchDashboardSummary, fetchCashFlow, fetchCategoryBreakdown,
  fetchRecentTransactions, fetchAIInsights,
  type DashboardSummary, type CashFlowPoint, type CategoryBreakdown,
  type Transaction, type AIInsight,
} from './api';

type ChartType = 'area' | 'bar';
type DateRange = 7 | 14 | 30 | 60 | 90;

const CHART_COLORS = {
  inflow: '#10b981',
  outflow: '#ef4444',
  net: '#6366f1',
  accent: '#8b5cf6',
};

// ── Currency Formatter ───────────────────────────────────────────────────
const fmt = (n: number) => new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', minimumFractionDigits: 0, maximumFractionDigits: 0,
}).format(n);

const fmtFull = (n: number) => new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', minimumFractionDigits: 2,
}).format(n);

// ── Custom Tooltip ───────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="gaa-card p-3 shadow-lg border text-xs" style={{ background: 'var(--color-gaa-surface)' }}>
      <p className="font-semibold gaa-text-primary mb-1">{label}</p>
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color }} className="flex justify-between gap-4">
          <span>{p.name}</span>
          <span className="font-mono">{fmtFull(p.value)}</span>
        </p>
      ))}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────
export default function AnalyticsDashboard() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [cashflow, setCashflow] = useState<CashFlowPoint[]>([]);
  const [categories, setCategories] = useState<CategoryBreakdown[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [insights, setInsights] = useState<AIInsight[]>([]);
  const [loading, setLoading] = useState(true);

  // Customization state
  const [dateRange, setDateRange] = useState<DateRange>(30);
  const [chartType, setChartType] = useState<ChartType>('area');
  const [showNet, setShowNet] = useState(true);
  const [txnFilter, setTxnFilter] = useState<'all' | 'inflow' | 'outflow'>('all');

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, cf, cat, txn, ins] = await Promise.all([
        fetchDashboardSummary(),
        fetchCashFlow(dateRange),
        fetchCategoryBreakdown(dateRange),
        fetchRecentTransactions(20),
        fetchAIInsights(),
      ]);
      setSummary(s);
      setCashflow(cf);
      setCategories(cat);
      setTransactions(txn);
      setInsights(ins);
    } catch (err) {
      console.error('Analytics load error:', err);
    } finally {
      setLoading(false);
    }
  }, [dateRange]);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredTxns = transactions.filter(t =>
    txnFilter === 'all' ? true : t.type === txnFilter
  );

  if (loading && !summary) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <div className="w-8 h-8 border-2 border-gaa-border rounded-full animate-spin mb-4"
          style={{ borderTopColor: 'var(--color-gaa-primary)' }} />
        <p className="text-sm gaa-text-muted">Loading analytics</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* ── KPI Summary Cards ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KPICard
          label="Total balance"
          value={fmt(summary?.total_balance ?? 0)}
          trend={summary && summary.total_inflow_30d > summary.total_outflow_30d ? 'up' : 'down'}
        />
        <KPICard
          label="30d inflow"
          value={fmt(summary?.total_inflow_30d ?? 0)}
          color="var(--color-gaa-success, #10b981)"
        />
        <KPICard
          label="30d outflow"
          value={fmt(summary?.total_outflow_30d ?? 0)}
          color="var(--color-gaa-danger, #ef4444)"
        />
        <KPICard
          label="Reconciliation"
          value={`${summary?.reconciliation_rate ?? 0}%`}
          featured
        />
      </div>

      {/* ── AR/AP + Pending Row ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        <div className="gaa-card p-4 sm:p-5">
          <p className="gaa-label text-xs mb-2">Accounts receivable</p>
          <p className="text-lg sm:text-xl font-bold gaa-text-primary" style={{ color: 'var(--color-gaa-success, #10b981)' }}>
            {fmt(summary?.ar_outstanding ?? 0)}
          </p>
          <p className="text-xs gaa-text-muted mt-1">Outstanding invoices</p>
        </div>
        <div className="gaa-card p-4 sm:p-5">
          <p className="gaa-label text-xs mb-2">Accounts payable</p>
          <p className="text-lg sm:text-xl font-bold gaa-text-primary" style={{ color: 'var(--color-gaa-danger, #ef4444)' }}>
            {fmt(summary?.ap_outstanding ?? 0)}
          </p>
          <p className="text-xs gaa-text-muted mt-1">Bills due</p>
        </div>
        <div className="gaa-card p-4 sm:p-5">
          <p className="gaa-label text-xs mb-2">Pending approvals</p>
          <p className="text-lg sm:text-xl font-bold gaa-text-primary" style={{ color: 'var(--color-gaa-warning, #f59e0b)' }}>
            {summary?.pending_payments ?? 0}
          </p>
          <p className="text-xs gaa-text-muted mt-1">Awaiting HITL review</p>
        </div>
      </div>

      {/* ── Cash Flow Chart ────────────────────────────────────────── */}
      <div className="gaa-card p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-6">
          <div>
            <h3 className="gaa-heading text-lg">Cash flow</h3>
            <p className="text-xs gaa-text-muted mt-0.5">Inflows, outflows, and net position over time</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {/* Date Range Selector */}
            <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--color-gaa-border)' }}>
              {([7, 14, 30, 60, 90] as DateRange[]).map(d => (
                <button
                  key={d}
                  onClick={() => setDateRange(d)}
                  className={`px-2.5 py-1.5 text-xs font-medium transition-all duration-200 ${
                    dateRange === d
                      ? 'bg-gaa-text text-white'
                      : 'gaa-text-secondary hover:bg-gaa-bg-alt'
                  }`}
                >
                  {d}d
                </button>
              ))}
            </div>

            {/* Chart Type Toggle */}
            <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--color-gaa-border)' }}>
              <button
                onClick={() => setChartType('area')}
                className={`px-2.5 py-1.5 text-xs font-medium transition-all duration-200 ${
                  chartType === 'area' ? 'bg-gaa-text text-white' : 'gaa-text-secondary hover:bg-gaa-bg-alt'
                }`}
                title="Area chart"
              >
                Area
              </button>
              <button
                onClick={() => setChartType('bar')}
                className={`px-2.5 py-1.5 text-xs font-medium transition-all duration-200 ${
                  chartType === 'bar' ? 'bg-gaa-text text-white' : 'gaa-text-secondary hover:bg-gaa-bg-alt'
                }`}
                title="Bar chart"
              >
                Bar
              </button>
            </div>

            {/* Net Toggle */}
            <button
              onClick={() => setShowNet(!showNet)}
              className={`px-2.5 py-1.5 text-xs font-medium rounded-lg border transition-all duration-200 ${
                showNet ? 'bg-gaa-text text-white' : 'gaa-text-secondary hover:bg-gaa-bg-alt'
              }`}
              style={{ borderColor: showNet ? 'transparent' : 'var(--color-gaa-border)' }}
            >
              Net
            </button>
          </div>
        </div>

        <div className="h-[280px] sm:h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            {chartType === 'area' ? (
              <AreaChart data={cashflow}>
                <defs>
                  <linearGradient id="gradIn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.inflow} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={CHART_COLORS.inflow} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradOut" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.outflow} stopOpacity={0.2} />
                    <stop offset="100%" stopColor={CHART_COLORS.outflow} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradNet" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.net} stopOpacity={0.25} />
                    <stop offset="100%" stopColor={CHART_COLORS.net} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-gaa-border)" opacity={0.5} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--color-gaa-text-muted)' }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--color-gaa-text-muted)' }} tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Area type="monotone" dataKey="inflow" name="Inflow" stroke={CHART_COLORS.inflow} fill="url(#gradIn)" strokeWidth={2} />
                <Area type="monotone" dataKey="outflow" name="Outflow" stroke={CHART_COLORS.outflow} fill="url(#gradOut)" strokeWidth={2} />
                {showNet && <Area type="monotone" dataKey="net" name="Net" stroke={CHART_COLORS.net} fill="url(#gradNet)" strokeWidth={2} strokeDasharray="4 2" />}
              </AreaChart>
            ) : (
              <BarChart data={cashflow}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--color-gaa-border)" opacity={0.5} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--color-gaa-text-muted)' }} tickFormatter={d => d.slice(5)} />
                <YAxis tick={{ fontSize: 10, fill: 'var(--color-gaa-text-muted)' }} tickFormatter={v => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="inflow" name="Inflow" fill={CHART_COLORS.inflow} radius={[3, 3, 0, 0]} opacity={0.85} />
                <Bar dataKey="outflow" name="Outflow" fill={CHART_COLORS.outflow} radius={[3, 3, 0, 0]} opacity={0.85} />
                {showNet && <Bar dataKey="net" name="Net" fill={CHART_COLORS.net} radius={[3, 3, 0, 0]} opacity={0.7} />}
              </BarChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Category Breakdown + AI Insights Row ──────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
        {/* Category Pie */}
        <div className="gaa-card p-4 sm:p-6">
          <h3 className="gaa-heading text-lg mb-1">Spending by category</h3>
          <p className="text-xs gaa-text-muted mb-4">Top expense categories ({dateRange}-day window)</p>
          <div className="flex flex-col sm:flex-row items-center gap-4">
            <div className="w-[180px] h-[180px] sm:w-[200px] sm:h-[200px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categories.filter(c => c.category !== 'Revenue')}
                    cx="50%" cy="50%"
                    innerRadius={50} outerRadius={80}
                    dataKey="amount"
                    nameKey="category"
                    paddingAngle={3}
                    stroke="none"
                  >
                    {categories.filter(c => c.category !== 'Revenue').map((c, i) => (
                      <Cell key={i} fill={c.color} />
                    ))}
                  </Pie>
                  <Tooltip formatter={((v: unknown) => fmtFull(Number(v))) as any} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-2 w-full">
              {categories.filter(c => c.category !== 'Revenue').map((c, i) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: c.color }} />
                    <span className="gaa-text-secondary">{c.category}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="gaa-text-muted">{c.count} txns</span>
                    <span className="font-semibold gaa-text-primary tabular-nums">{fmt(c.amount)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* AI Insights Panel */}
        <div className="gaa-card p-4 sm:p-6">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="gaa-heading text-lg">AI insights</h3>
          </div>
          <p className="text-xs gaa-text-muted mb-4">Powered by Gemini financial analysis</p>
          <div className="space-y-3 max-h-[280px] overflow-y-auto pr-1">
            {insights.map(ins => (
              <InsightCard key={ins.id} insight={ins} />
            ))}
          </div>
        </div>
      </div>

      {/* ── Recent Transactions Table ─────────────────────────────── */}
      <div className="gaa-card overflow-hidden">
        <div className="px-4 sm:px-6 py-4 sm:py-5 border-b flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h3 className="gaa-heading text-lg">Recent transactions</h3>
            <p className="text-xs gaa-text-muted mt-0.5">Across all connected platforms</p>
          </div>
          <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--color-gaa-border)' }}>
            {(['all', 'inflow', 'outflow'] as const).map(f => (
              <button
                key={f}
                onClick={() => setTxnFilter(f)}
                className={`px-3 py-1.5 text-xs font-medium transition-all duration-200 capitalize ${
                  txnFilter === f ? 'bg-gaa-text text-white' : 'gaa-text-secondary hover:bg-gaa-bg-alt'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Desktop Table */}
        <div className="hidden md:block overflow-x-auto">
          <table className="w-full gaa-table">
            <thead>
              <tr>
                <th className="text-left">Date</th>
                <th className="text-left">Counterparty</th>
                <th className="text-left">Category</th>
                <th className="text-left">Platform</th>
                <th className="text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {filteredTxns.map((t, idx) => (
                <tr key={t.id} className="fade-up" style={{ animationDelay: `${idx * 30}ms` }}>
                  <td>
                    <span className="text-xs gaa-text-muted tabular-nums">{t.date}</span>
                  </td>
                  <td>
                    <span className="text-sm font-medium gaa-text-primary">{t.counterparty}</span>
                  </td>
                  <td>
                    <span className="gaa-badge gaa-badge-alt text-xs" style={{ background: 'var(--color-gaa-bg-alt)' }}>
                      {t.category}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs gaa-text-muted capitalize">{t.platform}</span>
                  </td>
                  <td className="text-right">
                    <span className={`font-semibold tabular-nums text-sm ${
                      t.type === 'inflow' ? 'text-emerald-500' : 'text-red-400'
                    }`}>
                      {t.type === 'inflow' ? '+' : '-'}{fmtFull(t.amount)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Mobile Cards */}
        <div className="md:hidden divide-y divide-gaa-border">
          {filteredTxns.slice(0, 10).map((t, idx) => (
            <div key={t.id} className="p-4 fade-up" style={{ animationDelay: `${idx * 40}ms` }}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium gaa-text-primary">{t.counterparty}</span>
                <span className={`font-semibold tabular-nums text-sm ${
                  t.type === 'inflow' ? 'text-emerald-500' : 'text-red-400'
                }`}>
                  {t.type === 'inflow' ? '+' : '-'}{fmtFull(t.amount)}
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs gaa-text-muted">
                <span>{t.date}</span>
                <span>·</span>
                <span className="capitalize">{t.platform}</span>
                <span>·</span>
                <span>{t.category}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Connector Status ──────────────────────────────────────── */}
      {summary?.connectors && summary.connectors.length > 0 && (
        <div className="gaa-card p-4 sm:p-6">
          <h3 className="gaa-heading text-lg mb-4">Connected platforms</h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {summary.connectors.map(c => (
              <div key={c.platform} className="flex items-center gap-3 p-3 rounded-lg" style={{ background: 'var(--color-gaa-bg-alt, #f8f9fa)' }}>
                <div className={`w-2.5 h-2.5 rounded-full shrink-0 ${c.connected ? 'bg-emerald-400' : 'bg-gray-400'}`} />
                <div>
                  <p className="text-xs font-semibold gaa-text-primary capitalize">{c.platform}</p>
                  <p className="text-[10px] gaa-text-muted">
                    {c.connected ? 'Connected' : 'Disconnected'}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Sub-Components ───────────────────────────────────────────────────────

function KPICard({ label, value, trend, color, featured }: {
  label: string; value: string; trend?: 'up' | 'down'; color?: string; featured?: boolean;
}) {
  return (
    <div className={`gaa-card ${featured ? 'gaa-card-featured' : ''} p-4 sm:p-5`}>
      <p className="gaa-label text-xs mb-2">{label}</p>
      <div className="flex items-baseline gap-2">
        <p className="text-lg sm:text-2xl font-bold gaa-text-primary tabular-nums" style={color ? { color } : undefined}>
          {value}
        </p>
        {trend && (
          <span className={`text-xs font-bold ${trend === 'up' ? 'text-emerald-500' : 'text-red-400'}`}>
            {trend === 'up' ? '↑' : '↓'}
          </span>
        )}
      </div>
    </div>
  );
}

function InsightCard({ insight }: { insight: AIInsight }) {
  const severityStyles: Record<string, { bg: string; border: string; icon: string }> = {
    info: { bg: 'rgba(99,102,241,0.08)', border: 'rgba(99,102,241,0.2)', icon: '#6366f1' },
    warning: { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.2)', icon: '#f59e0b' },
    critical: { bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.2)', icon: '#ef4444' },
  };
  const s = severityStyles[insight.severity] || severityStyles.info;

  const typeIcons: Record<string, string> = {
    anomaly: 'Anomaly',
    forecast: 'Forecast',
    recommendation: 'Tip',
    alert: 'Alert',
  };

  return (
    <div className="rounded-lg p-3 transition-all duration-200 hover:translate-x-0.5"
      style={{ background: s.bg, border: `1px solid ${s.border}` }}>
      <div className="flex items-start gap-2.5">
        <div className="shrink-0 mt-0.5">
          <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded"
            style={{ background: s.border, color: s.icon }}>
            {typeIcons[insight.type] || 'Info'}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold gaa-text-primary mb-0.5">{insight.title}</p>
          <p className="text-[11px] gaa-text-secondary leading-relaxed">{insight.description}</p>
          {insight.value !== undefined && (
            <p className="text-xs font-bold mt-1.5 tabular-nums" style={{ color: s.icon }}>
              {fmtFull(insight.value)}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

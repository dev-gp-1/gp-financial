import { useState, useEffect } from 'react';
import { fetchPendingPayments, reviewPayment, type PendingPayment } from './api';

export default function PendingApprovalTable() {
  const [payments, setPayments] = useState<PendingPayment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  async function loadPayments() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchPendingPayments();
      setPayments(data.payments ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch payments');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPayments();
  }, []);

  function showToast(msg: string, type: 'success' | 'error') {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  }

  async function handleAction(id: string, action: 'approve' | 'reject') {
    setActionLoading(id);
    try {
      const res = await reviewPayment(id, action);
      if (res.success) {
        showToast(
          action === 'approve' ? `Payment ${id.slice(0, 8)} approved` : `Payment ${id.slice(0, 8)} rejected`,
          'success'
        );
        await loadPayments();
      } else {
        showToast(res.error ?? 'Action failed', 'error');
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Action failed', 'error');
    } finally {
      setActionLoading(null);
    }
  }

  return (
    <>
      {/* Toast */}
      {toast && (
        <div className={`gaa-toast ${toast.type === 'success' ? 'gaa-toast-success' : 'gaa-toast-error'}`}>
          {toast.msg}
        </div>
      )}

      <div className="gaa-card overflow-hidden">
        {/* Table Header */}
        <div className="px-4 sm:px-6 py-4 sm:py-5 border-b flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div>
            <h3 className="gaa-heading text-lg sm:text-xl">Pending approvals</h3>
            <p className="text-xs sm:text-sm gaa-text-muted mt-0.5">
              {payments.length} payment{payments.length !== 1 ? 's' : ''} awaiting review
            </p>
          </div>
          <button
            onClick={loadPayments}
            disabled={loading}
            className="gaa-btn-primary text-xs sm:text-sm w-full sm:w-auto justify-center"
          >
            Refresh
          </button>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-16 sm:py-20">
            <div className="w-8 h-8 border-2 border-gaa-border rounded-full animate-spin mb-4"
              style={{ borderTopColor: 'var(--color-gaa-primary)' }} />
            <p className="text-sm gaa-text-muted">Loading payments</p>
          </div>
        )}

        {/* Error State */}
        {!loading && error && (
          <div className="flex flex-col items-center justify-center py-16 sm:py-20 px-4">
            <p className="text-sm font-medium gaa-text-primary mb-1">Connection error</p>
            <p className="text-xs gaa-text-muted max-w-sm text-center mb-4">{error}</p>
            <button onClick={loadPayments} className="gaa-btn-primary text-sm">Retry</button>
          </div>
        )}

        {/* Empty State */}
        {!loading && !error && payments.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 sm:py-20">
            <p className="text-sm font-medium gaa-text-primary mb-1">All clear</p>
            <p className="text-xs gaa-text-muted">No pending payments require approval.</p>
          </div>
        )}

        {/* Data */}
        {!loading && !error && payments.length > 0 && (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full gaa-table">
                <thead>
                  <tr>
                    <th className="text-left">Recipient</th>
                    <th className="text-right">Amount</th>
                    <th className="text-left">Method</th>
                    <th className="text-left">Note</th>
                    <th className="text-left">Status</th>
                    <th className="text-left">Created</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {payments.map((p, idx) => (
                    <tr key={p.id} className="fade-up" style={{ animationDelay: `${idx * 50}ms` }}>
                      <td>
                        <span className="font-mono text-xs gaa-text-secondary gaa-code-bg px-2 py-1 rounded"
                          style={{ background: 'var(--color-gaa-bg-alt)' }}>
                          {p.recipient_id.slice(0, 12)}
                        </span>
                      </td>
                      <td className="text-right">
                        <span className="font-semibold gaa-text-primary tabular-nums">
                          ${p.amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                        </span>
                      </td>
                      <td>
                        <span className="gaa-badge gaa-badge-alt" style={{ background: 'var(--color-gaa-bg-alt)' }}>
                          {p.payment_method}
                        </span>
                      </td>
                      <td>
                        <span className="text-sm gaa-text-secondary">{p.note || '—'}</span>
                      </td>
                      <td>
                        <span className="gaa-badge gaa-badge-warning bg-gaa-warning-bg text-yellow-800">
                          {p.status}
                        </span>
                      </td>
                      <td>
                        <span className="text-xs gaa-text-muted tabular-nums">
                          {p.created_at ? new Date(p.created_at).toLocaleDateString('en-US', {
                            month: 'short', day: 'numeric', year: 'numeric'
                          }) : '—'}
                        </span>
                      </td>
                      <td className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleAction(p.id, 'approve')}
                            disabled={actionLoading === p.id}
                            className="gaa-btn-primary text-xs"
                          >
                            Approve
                          </button>
                          <button
                            onClick={() => handleAction(p.id, 'reject')}
                            disabled={actionLoading === p.id}
                            className="gaa-btn-danger text-xs"
                          >
                            Reject
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile card view */}
            <div className="md:hidden divide-y divide-gaa-border">
              {payments.map((p, idx) => (
                <div key={p.id} className="p-4 fade-up" style={{ animationDelay: `${idx * 50}ms` }}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-mono text-xs gaa-text-secondary gaa-code-bg px-2 py-1 rounded"
                      style={{ background: 'var(--color-gaa-bg-alt)' }}>
                      {p.recipient_id.slice(0, 12)}
                    </span>
                    <span className="gaa-badge gaa-badge-warning bg-gaa-warning-bg text-yellow-800 text-xs">
                      {p.status}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between mb-2">
                    <span className="text-xl font-semibold gaa-text-primary tabular-nums">
                      ${p.amount.toLocaleString('en-US', { minimumFractionDigits: 2 })}
                    </span>
                    <span className="gaa-badge gaa-badge-alt text-xs" style={{ background: 'var(--color-gaa-bg-alt)' }}>
                      {p.payment_method}
                    </span>
                  </div>
                  {p.note && <p className="text-sm gaa-text-secondary mb-3">{p.note}</p>}
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => handleAction(p.id, 'approve')}
                      disabled={actionLoading === p.id}
                      className="gaa-btn-primary text-xs flex-1 justify-center"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => handleAction(p.id, 'reject')}
                      disabled={actionLoading === p.id}
                      className="gaa-btn-danger text-xs flex-1 justify-center"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </>
  );
}

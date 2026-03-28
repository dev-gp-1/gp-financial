import { useState, useEffect } from 'react';
import PendingApprovalTable from './PendingApprovalTable';
import AnalyticsDashboard from './AnalyticsDashboard';
import ClientPortfolio from './ClientPortfolio';
import LoginScreen from './LoginScreen';
import { onAuthChange, isEmailAllowed, logout, type User } from './firebase';

type Tab = 'portfolio' | 'analytics' | 'approvals';

function useTheme() {
  const [dark, setDark] = useState(() => {
    if (typeof window === 'undefined') return false;
    const stored = localStorage.getItem('gaa-theme');
    if (stored) return stored === 'dark';
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  });

  useEffect(() => {
    const root = document.documentElement;
    if (dark) {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    localStorage.setItem('gaa-theme', dark ? 'dark' : 'light');
  }, [dark]);

  return [dark, () => setDark((d) => !d)] as const;
}

export default function App() {
  const [dark, toggleTheme] = useTheme();
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('portfolio');

  useEffect(() => {
    const unsub = onAuthChange((u) => {
      if (u && isEmailAllowed(u.email)) {
        setUser(u);
      } else {
        setUser(null);
      }
      setAuthLoading(false);
    });
    return unsub;
  }, []);

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center transition-colors duration-300">
        <div className="text-center">
          <div className="w-12 h-12 rounded-full bg-gaa-text flex items-center justify-center mx-auto mb-4 animate-pulse">
            <span className="text-white font-bold text-xl" style={{ fontFamily: 'var(--font-display)' }}>G</span>
          </div>
          <p className="text-sm gaa-text-muted">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginScreen onLogin={(u) => setUser(u)} />;
  }

  const displayName = user.displayName || user.email?.split('@')[0] || 'User';
  const initials = displayName.charAt(0).toUpperCase();

  const tabs: { id: Tab; label: string }[] = [
    { id: 'portfolio', label: 'Portfolio' },
    { id: 'analytics', label: 'Analytics' },
    { id: 'approvals', label: 'Approvals' },
  ];

  return (
    <div className="min-h-screen transition-colors duration-300">
      {/* Header */}
      <header className="gaa-header border-b bg-gaa-surface sticky top-0 z-40">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-3 sm:py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-gaa-text flex items-center justify-center shrink-0">
              <span className="text-white font-bold text-base sm:text-lg" style={{ fontFamily: 'var(--font-display)' }}>G</span>
            </div>
            <div className="min-w-0">
              <h1 className="text-sm sm:text-base font-bold gaa-text-primary tracking-tight truncate">Gernetzke &amp; Associates</h1>
              <p className="text-xs gaa-text-muted hidden sm:block">Financial Intelligence Platform</p>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* Tab Navigation */}
            <nav className="hidden sm:flex rounded-lg overflow-hidden border" style={{ borderColor: 'var(--color-gaa-border)' }}>
              {tabs.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-all duration-200 ${
                    activeTab === tab.id
                      ? 'bg-gaa-text text-white'
                      : 'gaa-text-secondary hover:bg-gaa-bg-alt'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            <button
              onClick={toggleTheme}
              className="gaa-theme-toggle"
              aria-label="Toggle theme"
              title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {dark ? (
                <span className="text-xs font-semibold" style={{ color: 'var(--color-gaa-text-muted)' }}>Light</span>
              ) : (
                <span className="text-xs font-semibold" style={{ color: 'var(--color-gaa-text-muted)' }}>Dark</span>
              )}
            </button>

            {/* User menu */}
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
                style={{ background: 'var(--color-gaa-accent, #1CCBD6)', color: '#fff' }}>
                {initials}
              </div>
              <span className="hidden sm:inline text-xs gaa-text-secondary truncate max-w-[140px]">{user.email}</span>
              <button onClick={logout} className="gaa-btn-ghost text-xs px-2 py-1" title="Sign out">
                Sign out
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Tab Bar */}
        <div className="sm:hidden border-t flex" style={{ borderColor: 'var(--color-gaa-border)' }}>
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-all duration-200 ${
                activeTab === tab.id
                  ? 'gaa-text-primary border-b-2'
                  : 'gaa-text-muted'
              }`}
              style={activeTab === tab.id ? { borderColor: 'var(--color-gaa-text)' } : undefined}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {activeTab === 'portfolio' && (
          <>
            <div className="mb-6 sm:mb-8">
              <p className="gaa-label mb-1 sm:mb-2">Client Intelligence</p>
              <h2 className="gaa-heading text-2xl sm:text-3xl lg:text-4xl mb-2 sm:mb-3">Portfolio overview</h2>
              <p className="gaa-text-secondary text-sm sm:text-base max-w-2xl">
                Multi-client financial health monitoring with AI-powered agent recommendations. Heatmap scoring reflects AR aging, AP management, reconciliation accuracy, and cash flow strength.
              </p>
            </div>
            <ClientPortfolio />
          </>
        )}

        {activeTab === 'analytics' && (
          <>
            <div className="mb-6 sm:mb-8">
              <p className="gaa-label mb-1 sm:mb-2">Financial Intelligence</p>
              <h2 className="gaa-heading text-2xl sm:text-3xl lg:text-4xl mb-2 sm:mb-3">Dashboard analytics</h2>
              <p className="gaa-text-secondary text-sm sm:text-base max-w-xl">
                Aggregated financial data from Mercury, QuickBooks, and connected platforms. AI-powered insights and customizable analytics.
              </p>
            </div>
            <AnalyticsDashboard />
          </>
        )}

        {activeTab === 'approvals' && (
          <>
            <div className="mb-6 sm:mb-10">
              <p className="gaa-label mb-1 sm:mb-2">Mercury Bank · HITL Gateway</p>
              <h2 className="gaa-heading text-2xl sm:text-3xl lg:text-4xl mb-2 sm:mb-3">Payment approvals</h2>
              <p className="gaa-text-secondary text-sm sm:text-base max-w-xl">
                Review and authorize pending ACH transfers. All payments require human-in-the-loop approval before execution.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-5 mb-6 sm:mb-10">
              <StatCard label="Platform" value="Mercury Bank" />
              <StatCard label="Security" value="HITL Required" featured />
              <StatCard label="Environment" value="Development" />
            </div>

            <PendingApprovalTable />
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="gaa-footer border-t mt-12 sm:mt-16 bg-gaa-surface">
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-4 sm:py-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <p className="text-xs gaa-text-muted">Gernetzke &amp; Associates · Financial Intelligence Platform</p>
          <p className="text-xs gaa-text-muted">Secured by Firebase Authentication</p>
        </div>
      </footer>
    </div>
  );
}

function StatCard({ label, value, featured }: { label: string; value: string; featured?: boolean }) {
  return (
    <div className={`gaa-card ${featured ? 'gaa-card-featured' : ''} p-4 sm:p-5`}>
      <p className="gaa-label text-xs mb-2">{label}</p>
      <p className="text-sm sm:text-base font-semibold gaa-text-primary">{value}</p>
    </div>
  );
}
